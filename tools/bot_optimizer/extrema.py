"""Direct min/max loops with iterator fallback and generator-equivalent cleanup."""

import ast
import copy

from .analysis import Bindings, arguments
from .model import Change
from .records import used_names
from .helper_bindings import cache_helper_builtins


class ExtremumLoops:
    def __init__(self, program, module, options):
        self.program, self.module, self.options = program, module, options
        self.names = used_names(program.modules[module].tree)
        self.changes, self.helpers, self.cache = [], [], {}
        self.builtins = {name: self.fresh(name) for name in
                         ('type', 'list', 'tuple', 'object', 'StopIteration', 'RuntimeError', 'BaseException', 'min', 'max')}
        self.sentinel = self.fresh('empty')

    def fresh(self, stem):
        index = 0
        while f'_bcopt_ext_{stem}_{index}' in self.names:
            index += 1
        name = f'_bcopt_ext_{stem}_{index}'
        self.names.add(name)
        return name

    def apply(self, tree):
        if 'extremum-loop' in self.options.disabled or 'builtins' in self.program.modules:
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
                    not isinstance(target, ast.Name) for target in n.targets)) for n in ast.walk(function)):
                continue
            local = set(Bindings(function.body).counts) | {arg.arg for arg in arguments(function)}
            definite = {arg.arg for arg in arguments(function)}
            owner = self

            class Calls(ast.NodeTransformer):
                def visit_GeneratorExp(self, node):
                    return node

                visit_ListComp = visit_GeneratorExp
                visit_SetComp = visit_GeneratorExp
                visit_DictComp = visit_GeneratorExp

                def visit_Call(self, node):
                    node = self.generic_visit(node)
                    return owner.rewrite(node, local, definite)

            visitor = Calls()
            for index, statement in enumerate(function.body):
                function.body[index] = visitor.visit(statement)
                if isinstance(statement, ast.Delete):
                    definite.difference_update(target.id for target in statement.targets)
                elif isinstance(statement, (ast.Assign, ast.AnnAssign)) and statement.value is not None:
                    targets = statement.targets if isinstance(statement, ast.Assign) else [statement.target]
                    for target in targets:
                        definite.update(n.id for n in ast.walk(target)
                                        if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store))
        if self.helpers:
            imports = ast.ImportFrom(module='builtins', names=[ast.alias(name=n, asname=a)
                for n, a in self.builtins.items()], level=0)
            helpers = [imports, *self.helpers]
            if 'helper-loop-shape' in self.options.disabled:
                helpers[1:1] = ast.parse(f'{self.sentinel} = {self.builtins["object"]}()').body
            index = 0
            if tree.body and isinstance(tree.body[0], ast.Expr) and isinstance(tree.body[0].value, ast.Constant) and isinstance(tree.body[0].value.value, str):
                index = 1
            while index < len(tree.body) and isinstance(tree.body[index], ast.ImportFrom) and tree.body[index].module == '__future__':
                index += 1
            tree.body[index:index] = helpers
        return tree

    def rewrite(self, node, local, definite):
        if (not isinstance(node.func, ast.Name) or node.func.id in local or node.keywords
                or len(node.args) != 1 or not isinstance(node.args[0], ast.GeneratorExp)):
            return node
        consumer = self.program.resolve(self.module, node.func)
        if consumer not in {'min', 'max', 'builtins.min', 'builtins.max'}:
            return node
        consumer = consumer.removeprefix('builtins.')
        gen = node.args[0]
        if len(gen.generators) != 1:
            return node
        comp = gen.generators[0]
        if isinstance(gen.elt, ast.Name) and isinstance(comp.target, ast.Name) and gen.elt.id == comp.target.id:
            return node  # The existing identity pass removes this generator entirely.
        if not any(isinstance(n, (ast.Attribute, ast.Subscript)) for n in ast.walk(gen.elt)):
            return node  # Keep arithmetic-only generators with existing integer passes.
        if not (isinstance(comp.target, ast.Name) and isinstance(comp.iter, ast.Name)
                and comp.iter.id in definite and not comp.ifs and not comp.is_async):
            return node
        allowed = (ast.Name, ast.Constant, ast.Attribute, ast.Subscript, ast.Slice,
                   ast.BinOp, ast.UnaryOp, ast.operator, ast.unaryop, ast.Load)
        if any(not isinstance(n, allowed) or isinstance(n, ast.Attribute) and n.attr.startswith('__')
               for n in ast.walk(gen.elt)):
            return node
        captures = sorted({n.id for n in ast.walk(gen.elt) if isinstance(n, ast.Name)} - {comp.target.id})
        if not set(captures) <= definite:
            return node
        # A captured local is read early only when definitely bound. It cannot
        # be rebound by callbacks because escaping mutable cells are excluded.
        substitutions = {name: f'arg{index}' for index, name in enumerate(captures)}
        substitutions[comp.target.id] = 'item'

        class Substitute(ast.NodeTransformer):
            def visit_Name(self, name):
                name.id = substitutions[name.id]
                return name

        expression = Substitute().visit(copy.deepcopy(gen.elt))
        key = consumer, ast.dump(expression), len(captures)
        if key not in self.cache:
            helper = self.fresh(consumer)
            arguments_ = ', '.join(['items', *(f'arg{i}' for i in range(len(captures)))])
            expr, b = ast.unparse(expression), self.builtins
            operation = '<' if consumer == 'min' else '>'
            source = f'''def {helper}({arguments_}):
    if not ({b['type']}(items) is {b['tuple']} or {b['type']}(items) is {b['list']}):
        return {b[consumer]}({expr} for item in items)
    best = None
    have_best = False
    for item in items:
        try:
            try:
                value = {expr}
            except {b['StopIteration']} as error:
                raise {b['RuntimeError']}('generator raised StopIteration') from error
        except {b['BaseException']}:
            del best
            raise
        try:
            if have_best:
                if value {operation} best:
                    best = value
            else:
                best = value
                have_best = True
        except {b['BaseException']}:
            del value, best, item, {arguments_}
            raise
        del value
    if not have_best:
        return {b[consumer]}(())
    return best
'''
            original_loop = source.replace('    best = None\n    have_best = False', f'    best = {self.sentinel}')
            original_loop = original_loop.replace(
                f'            if have_best:\n                if value {operation} best:\n                    best = value\n'
                '            else:\n                best = value\n                have_best = True',
                f'            if best is {self.sentinel} or value {operation} best:\n                best = value')
            original_loop = original_loop.replace('if not have_best:', f'if best is {self.sentinel}:')
            if 'helper-loop-shape' in self.options.disabled:
                source = original_loop
            else:
                self.changes.append(Change('helper-loop-shape', node.lineno, original_loop, source))
            self.helpers.extend(cache_helper_builtins(ast.parse(source).body, self.builtins,
                {'type'}, self.options, self.changes, node.lineno))
            self.cache[key] = helper
        replacement = ast.Call(func=ast.Name(id=self.cache[key], ctx=ast.Load()),
            args=[copy.deepcopy(comp.iter), *(ast.Name(id=name, ctx=ast.Load()) for name in captures)], keywords=[])
        self.changes.append(Change('extremum-loop', node.lineno, ast.unparse(node), ast.unparse(replacement)))
        return ast.copy_location(replacement, node)
