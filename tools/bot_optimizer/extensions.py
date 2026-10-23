"""Incremental list extension over guarded adjacent primitive tuple indices."""

import ast
import copy

from .analysis import Bindings, arguments
from .model import Change
from .records import used_names
from .helper_bindings import cache_helper_builtins


class AdjacentExtensions:
    def __init__(self, program, module, options):
        self.program, self.module, self.options = program, module, options
        self.names = used_names(program.modules[module].tree)
        self.changes, self.helpers = [], []
        self.builtins = {n: self.fresh(n) for n in ('type', 'list', 'tuple', 'int', 'len', 'iter', 'next', 'StopIteration', 'RuntimeError')}
        self.pairwise = self.fresh('pairwise')

    def fresh(self, stem):
        index = 0
        while f'_bcopt_extend_{stem}_{index}' in self.names:
            index += 1
        name = f'_bcopt_extend_{stem}_{index}'
        self.names.add(name)
        return name

    def apply(self, tree):
        if 'adjacent-extend' in self.options.disabled or {'itertools', 'builtins'} & self.program.modules.keys():
            return tree
        functions = [n for n in tree.body if isinstance(n, ast.FunctionDef)]
        functions.extend(method for owner in tree.body if isinstance(owner, ast.ClassDef) and not owner.type_params
                         for method in owner.body if isinstance(method, ast.FunctionDef))
        for function in functions:
            if function.type_params or any(
                isinstance(n, (ast.Global, ast.Nonlocal, ast.NamedExpr, ast.Lambda, ast.ClassDef,
                               ast.Try, ast.TryStar, ast.With, ast.AsyncWith, ast.Yield, ast.YieldFrom, ast.Await))
                or isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n is not function
                or isinstance(n, ast.Delete) and (n not in function.body or any(
                    not isinstance(t, ast.Name) for t in n.targets)) for n in ast.walk(function)):
                continue
            definite = {a.arg for a in arguments(function)}
            local = set(Bindings(function.body).counts) | definite
            for index, statement in enumerate(function.body):
                function.body[index] = self.rewrite(statement, local, definite)
                if isinstance(statement, ast.Delete):
                    definite.difference_update(t.id for t in statement.targets)
                elif isinstance(statement, (ast.Assign, ast.AnnAssign)) and statement.value is not None:
                    targets = statement.targets if isinstance(statement, ast.Assign) else [statement.target]
                    definite.update(n.id for t in targets for n in ast.walk(t)
                                    if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store))
        if self.helpers:
            imports = [ast.ImportFrom(module='builtins', names=[ast.alias(name=n, asname=a)
                for n, a in self.builtins.items()], level=0),
                ast.ImportFrom(module='itertools', names=[ast.alias(name='pairwise', asname=self.pairwise)], level=0)]
            index = 0
            if tree.body and isinstance(tree.body[0], ast.Expr) and isinstance(tree.body[0].value, ast.Constant) and isinstance(tree.body[0].value.value, str):
                index = 1
            while index < len(tree.body) and isinstance(tree.body[index], ast.ImportFrom) and tree.body[index].module == '__future__':
                index += 1
            tree.body[index:index] = [*imports, *self.helpers]
        return tree

    def rewrite(self, statement, local, definite):
        if not (isinstance(statement, ast.Expr) and isinstance(statement.value, ast.Call)):
            return statement
        call = statement.value
        if not (isinstance(call.func, ast.Attribute) and call.func.attr == 'extend'
                and isinstance(call.func.value, ast.Name) and call.func.value.id in definite
                and len(call.args) == 1 and not call.keywords and isinstance(call.args[0], ast.GeneratorExp)):
            return statement
        gen = call.args[0]
        if len(gen.generators) != 1:
            return statement
        comp = gen.generators[0]
        if not (not comp.is_async and not comp.ifs and isinstance(comp.target, (ast.Tuple, ast.List))
                and len(comp.target.elts) == 2 and all(isinstance(n, ast.Name) for n in comp.target.elts)):
            return statement
        iterable = comp.iter
        if not (isinstance(iterable, ast.Call) and isinstance(iterable.func, ast.Name)
                and iterable.func.id not in local and self.program.resolve(self.module, iterable.func) in {'zip', 'builtins.zip'}
                and len(iterable.args) == 2 and not iterable.keywords):
            return statement
        first, second = iterable.args
        if not (isinstance(first, ast.Name) and first.id in definite and isinstance(second, ast.Subscript)
                and isinstance(second.value, ast.Name) and second.value.id == first.id
                and isinstance(second.slice, ast.Slice) and second.slice.upper is second.slice.step is None
                and isinstance(second.slice.lower, ast.Constant) and type(second.slice.lower.value) is int
                and second.slice.lower.value == 1):
            return statement
        targets = [n.id for n in comp.target.elts]
        if len(set(targets)) != 2:
            return statement
        allowed = (ast.Name, ast.Constant, ast.Attribute, ast.Subscript, ast.Slice,
                   ast.BinOp, ast.UnaryOp, ast.operator, ast.unaryop, ast.Load)
        if any(not isinstance(n, allowed) or isinstance(n, ast.Attribute) and n.attr.startswith('__')
               for n in ast.walk(gen.elt)):
            return statement
        captures = sorted({n.id for n in ast.walk(gen.elt) if isinstance(n, ast.Name)} - set(targets))
        if not set(captures) <= definite:
            return statement
        names = {name: f'arg{i}' for i, name in enumerate(captures)}
        names.update(zip(targets, ('a', 'b')))

        class Substitute(ast.NodeTransformer):
            def visit_Name(self, node):
                node.id = names[node.id]
                return node

        expression = ast.unparse(Substitute().visit(copy.deepcopy(gen.elt)))
        helper = self.fresh('pairs')
        parameters = ', '.join(['target', 'route', *(f'arg{i}' for i in range(len(captures)))])
        b = self.builtins
        source = f'''def {helper}({parameters}):
    if {b['type']}(target) is not {b['list']} or {b['type']}(route) is not {b['tuple']}:
        return False
    if {b['len']}(route) > 8:
        return False
    for index in route:
        if {b['type']}(index) is not {b['int']}:
            return False
    try:
        for a, b in {self.pairwise}(route):
            try:
                value = {expression}
            except {b['StopIteration']} as error:
                raise {b['RuntimeError']}('generator raised StopIteration') from error
            try:
                target.append(value)
            finally:
                del value
        return True
    finally:
        del target
'''
        if 'tuple-adjacent-iterator' not in self.options.disabled:
            previous = source
            source = source.replace(f'        for a, b in {self.pairwise}(route):',
                f'        iterator = {b["iter"]}(route)\n        a = {b["next"]}(iterator, None)\n        for b in iterator:')
            source = source.replace('                del value\n', '                del value\n            a = b\n')
            self.changes.append(Change('tuple-adjacent-iterator', statement.lineno, previous, source))
        if 'wide-helper-limit' not in self.options.disabled:
            previous = source
            source = source.replace(f"{b['len']}(route) > 8", f"{b['len']}(route) > 16")
            self.changes.append(Change('wide-helper-limit', statement.lineno, previous, source))
        self.helpers.extend(cache_helper_builtins(ast.parse(source).body, self.builtins,
            {'type', 'int', 'list', 'tuple', 'len'}, self.options, self.changes, statement.lineno))
        test = ast.Call(func=ast.Name(id=helper, ctx=ast.Load()),
            args=[copy.deepcopy(call.func.value), copy.deepcopy(first),
                  *(ast.Name(id=n, ctx=ast.Load()) for n in captures)], keywords=[])
        replacement = ast.If(test=ast.UnaryOp(op=ast.Not(), operand=test), body=[copy.deepcopy(statement)], orelse=[])
        self.changes.append(Change('adjacent-extend', statement.lineno, ast.unparse(statement), ast.unparse(replacement)))
        return ast.copy_location(replacement, statement)
