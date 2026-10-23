"""Guarded fusion of three short indexed integer reductions.

Annotations are not proofs. The helper checks exact containers, indices, records
and values, and drops all speculative references before the original fallback.
"""

import ast
import copy

from .analysis import Bindings, arguments
from .model import Change
from .records import used_names
from .helper_bindings import cache_helper_builtins


class ShortReductions:
    def __init__(self, program, module, options):
        self.program, self.module, self.options = program, module, options
        self.names = used_names(program.modules[module].tree)
        self.changes, self.helpers = [], []
        self.builtins = {name: self.fresh(name) for name in
                         ('type', 'list', 'tuple', 'int', 'len', 'AttributeError', 'IndexError')}

    def fresh(self, stem):
        index = 0
        while f'_bcopt_reduce_{stem}_{index}' in self.names:
            index += 1
        name = f'_bcopt_reduce_{stem}_{index}'
        self.names.add(name)
        return name

    def match(self, node, local):
        if not (isinstance(node, ast.Assign) and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name) and isinstance(node.value, ast.Call)):
            return None
        call = node.value
        if (not isinstance(call.func, ast.Name) or call.func.id in local
                or self.program.resolve(self.module, call.func) not in {'sum', 'builtins.sum'}
                or len(call.args) != 1 or call.keywords or not isinstance(call.args[0], ast.GeneratorExp)):
            return None
        gen = call.args[0]
        if len(gen.generators) != 1:
            return None
        comp, value = gen.generators[0], gen.elt
        if not (isinstance(comp.target, ast.Name) and isinstance(comp.iter, ast.Name)
                and not comp.ifs and not comp.is_async and isinstance(value, ast.Attribute)
                and isinstance(value.value, ast.Subscript) and isinstance(value.value.value, ast.Name)
                and isinstance(value.value.slice, ast.Name) and value.value.slice.id == comp.target.id
                and comp.target.id not in {comp.iter.id, value.value.value.id}):
            return None
        return node.targets[0].id, value.value.value.id, comp.iter.id, value.attr

    def apply(self, tree):
        if ('short-int-reductions' in self.options.disabled or self.program.dynamic_modules
                or self.program._cyclic_imports() or self.program.explicit_attribute_mutation):
            return tree
        functions = [n for n in tree.body if isinstance(n, ast.FunctionDef)]
        functions.extend(method for owner in tree.body if isinstance(owner, ast.ClassDef) and not owner.type_params
                         for method in owner.body if isinstance(method, ast.FunctionDef))
        for function in functions:
            if function.type_params:
                continue
            parts = list(ast.walk(function))
            if any(isinstance(n, (ast.Global, ast.Nonlocal, ast.NamedExpr,
                                  ast.Lambda, ast.Yield, ast.YieldFrom, ast.Await, ast.ClassDef,
                                  ast.Try, ast.TryStar))
                   or isinstance(n, ast.Delete) and (n not in function.body or any(
                       not isinstance(target, ast.Name) for target in n.targets))
                   or isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n is not function for n in parts):
                continue
            bindings = Bindings(function.body)
            params = {arg.arg for arg in arguments(function)}
            local = set(bindings.counts) | params
            definite = set(params)
            index = 0
            while index < len(function.body):
                triple = function.body[index:index + 3]
                matches = [self.match(n, local) for n in triple]
                if len(matches) == 3 and all(matches):
                    targets, rows, routes, fields = zip(*matches)
                    if (len(set(rows)) == len(set(routes)) == 1
                            and rows[0] in definite and routes[0] in definite
                            and len(set(targets)) == 3 and not set(targets) & definite
                            and all(bindings.counts[name] == 1 for name in targets)):
                        record_name = self.record_name(fields, local, function.lineno)
                        if record_name:
                            replacement = self.rewrite(triple, targets, rows[0], routes[0], fields, record_name)
                            function.body[index:index + 3] = replacement
                            definite.update(targets)
                            index += len(replacement)
                            continue
                statement = function.body[index]
                if isinstance(statement, ast.Delete):
                    definite.difference_update(target.id for target in statement.targets)
                if isinstance(statement, (ast.Assign, ast.AnnAssign)) and statement.value is not None:
                    targets_ = statement.targets if isinstance(statement, ast.Assign) else [statement.target]
                    for target in targets_:
                        definite.update(n.id for n in ast.walk(target)
                                        if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store))
                index += 1
        if self.helpers:
            imports = ast.ImportFrom(module='builtins', names=[ast.alias(name=n, asname=a)
                for n, a in self.builtins.items()], level=0)
            index = 0
            if tree.body and isinstance(tree.body[0], ast.Expr) and isinstance(tree.body[0].value, ast.Constant) and isinstance(tree.body[0].value.value, str):
                index = 1
            while index < len(tree.body) and isinstance(tree.body[index], ast.ImportFrom) and tree.body[index].module == '__future__':
                index += 1
            tree.body[index:index] = [imports, *self.helpers]
        return tree

    def record_name(self, fields, local, before):
        for name in self.program.modules[self.module].symbols:
            if name in local:
                continue
            expression = ast.Name(id=name, ctx=ast.Load())
            record = self.program.records.get(self.program.resolve(self.module, expression))
            if (record and record.simple and record.frozen and set(fields) <= set(record.fields)
                    and self.program.available(self.module, expression, before)):
                return name
        return None

    def rewrite(self, triple, targets, rows, route, fields, record):
        helper, packed = self.fresh('three'), self.fresh('totals')
        typ, seq, tup, integer, length, error = (self.builtins[n] for n in
                                               ('type', 'list', 'tuple', 'int', 'len', 'AttributeError'))
        source = f'''def {helper}(rows, route, record):
    if {typ}(route) is not {tup} or {length}(route) > 8 or not ({typ}(rows) is {seq} or {typ}(rows) is {tup}):
        return None
    size = {length}(rows)
    lower = -size
    a = b = c = 0
    for index in route:
        if {typ}(index) is not {integer} or index < lower or index >= size:
            return None
        row = rows[index]
        if {typ}(row) is not record:
            return None
        try:
            x, y, z = row.{fields[0]}, row.{fields[1]}, row.{fields[2]}
        except {error}:
            return None
        if not ({typ}(x) is {typ}(y) is {typ}(z) is {integer}):
            return None
        a += x
        b += y
        c += z
    return a, b, c
'''
        original_loop = source.replace('    lower = -size\n', '').replace(
            'index < lower or index >= size', 'not -size <= index < size')
        if 'helper-loop-shape' in self.options.disabled:
            source = original_loop
        elif 'native-index-guard' in self.options.disabled:
            self.changes.append(Change('helper-loop-shape', triple[0].lineno, original_loop, source))
        if 'native-index-guard' not in self.options.disabled:
            previous = source
            source = source.replace(f'    size = {length}(rows)\n', '').replace('    lower = -size\n', '')
            source = source.replace(' or index < lower or index >= size:', ':')
            source = source.replace(' or not -size <= index < size:', ':')
            source = source.replace('        row = rows[index]\n',
                f'        try:\n            row = rows[index]\n        except {self.builtins["IndexError"]}:\n            return None\n')
            self.changes.append(Change('native-index-guard', triple[0].lineno, previous, source))
        if 'wide-helper-limit' not in self.options.disabled:
            previous = source
            source = source.replace(f'{length}(route) > 8', f'{length}(route) > 16')
            self.changes.append(Change('wide-helper-limit', triple[0].lineno, previous, source))
        self.helpers.extend(cache_helper_builtins(ast.parse(source).body, self.builtins,
            {'type', 'int', 'list', 'tuple', 'len'}, self.options, self.changes, triple[0].lineno))
        replacement = ast.parse(f'''{packed} = {helper}({rows}, {route}, {record})
if {packed} is None:
    pass
else:
    {', '.join(targets)} = {packed}
del {packed}
''').body
        replacement[1].body = copy.deepcopy(triple)
        self.changes.append(Change('short-int-reductions', triple[0].lineno,
            '\n'.join(ast.unparse(n) for n in triple), '\n'.join(ast.unparse(n) for n in replacement)))
        return [ast.copy_location(n, triple[0]) for n in replacement]
