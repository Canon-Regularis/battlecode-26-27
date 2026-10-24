"""Inline two-argument extrema without extra calls or lingering temporaries."""

import ast
import copy

from .analysis import Bindings, arguments
from .model import Change
from .records import used_names


class ScalarExtrema:
    def __init__(self, program, module, options):
        self.program, self.module, self.options = program, module, options
        self.names = used_names(program.modules[module].tree)
        self.changes = []

    def fresh(self):
        index = 0
        while f'_bcopt_scalar_{index}' in self.names:
            index += 1
        name = f'_bcopt_scalar_{index}'
        self.names.add(name)
        return name

    def apply(self, tree):
        if 'scalar-extremum' in self.options.disabled:
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
            definite = {a.arg for a in arguments(function)}
            local = set(Bindings(function.body).counts) | definite
            body = []
            for statement in function.body:
                value = statement.value if isinstance(statement, (ast.Assign, ast.Return)) else None
                consumer = self.consumer(value, local)
                if consumer and all(self.atom(a, definite) for a in value.args):
                    before = ast.unparse(statement)
                    statement.value = self.expression(consumer, *value.args)
                    self.changes.append(Change('scalar-extremum', statement.lineno, before, ast.unparse(statement)))
                elif consumer and isinstance(statement, ast.Return) and self.chain(value, local, definite):
                    replacement = self.lower(value, local, definite)
                    body.extend(ast.copy_location(n, statement) for n in replacement)
                    self.changes.append(Change('scalar-extremum', statement.lineno, ast.unparse(statement),
                                               '\n'.join(ast.unparse(n) for n in replacement)))
                    continue
                body.append(statement)
                if isinstance(statement, ast.Delete):
                    definite.difference_update(t.id for t in statement.targets)
                elif isinstance(statement, (ast.Assign, ast.AnnAssign)) and statement.value is not None:
                    targets = statement.targets if isinstance(statement, ast.Assign) else [statement.target]
                    definite.update(n.id for t in targets for n in ast.walk(t)
                                    if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store))
            function.body = body
        return tree

    def consumer(self, node, local):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id not in local
                and len(node.args) == 2 and not node.keywords and not any(isinstance(a, ast.Starred) for a in node.args)):
            return None
        name = self.program.resolve(self.module, node.func)
        return name.removeprefix('builtins.') if name in {'min', 'max', 'builtins.min', 'builtins.max'} else None

    @staticmethod
    def atom(node, definite):
        return isinstance(node, ast.Constant) or isinstance(node, ast.Name) and node.id in definite

    def chain(self, node, local, definite):
        # Only the second argument may be effectful. Its original evaluation is
        # retained, and every materialized result is cleared on all exit paths.
        if not self.consumer(node, local) or not self.atom(node.args[0], definite):
            return False
        second = node.args[1]
        if self.consumer(second, local):
            return self.chain(second, local, definite)
        return not any(isinstance(n, (ast.GeneratorExp, ast.ListComp, ast.SetComp, ast.DictComp))
                       for n in ast.walk(second))

    @staticmethod
    def expression(consumer, first, second):
        return ast.IfExp(test=ast.Compare(left=copy.deepcopy(second),
            ops=[ast.Lt() if consumer == 'min' else ast.Gt()], comparators=[copy.deepcopy(first)]),
            body=copy.deepcopy(second), orelse=copy.deepcopy(first))

    def lower(self, root, local, definite):
        statements = []

        def materialize(node):
            consumer = self.consumer(node, local)
            if not consumer:
                name = self.fresh()
                statements.append(ast.Assign(targets=[ast.Name(id=name, ctx=ast.Store())], value=copy.deepcopy(node)))
                return name
            first, second = node.args
            name = materialize(second)
            result = self.fresh()
            value = self.expression(consumer, first, ast.Name(id=name, ctx=ast.Load()))
            statements.append(ast.Try(body=[ast.Assign(targets=[ast.Name(id=result, ctx=ast.Store())], value=value)],
                handlers=[], orelse=[], finalbody=[ast.Delete(targets=[ast.Name(id=name, ctx=ast.Del())])]))
            return result

        first, second = root.args
        name = materialize(second)
        statements.append(ast.Try(body=[ast.Return(value=self.expression(self.consumer(root, local), first,
            ast.Name(id=name, ctx=ast.Load())))], handlers=[], orelse=[],
            finalbody=[ast.Delete(targets=[ast.Name(id=name, ctx=ast.Del())])]))
        return ast.fix_missing_locations(ast.Module(body=statements, type_ignores=[])).body
