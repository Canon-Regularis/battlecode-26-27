"""Reuse a private buffer when yielding every insertion into an owned tuple.

The tuple owner is a never-rebound parameter, and the inserted value is a bound
local. A finally block drops the buffer before leaving the original scope, so
generator close/throw cannot extend payload lifetimes through a saved traceback.
"""

import ast
import copy

from .analysis import Bindings, arguments
from .model import Change
from .records import used_names


class TupleInsertions:
    def __init__(self, program, module, options):
        self.program, self.module, self.options = program, module, options
        self.names = used_names(program.modules[module].tree)
        self.changes = []
        self.aliases = {name: self.fresh(name) for name in ('type', 'tuple', 'list')}

    def fresh(self, stem):
        index = 0
        while f'_bcopt_insert_{stem}_{index}' in self.names:
            index += 1
        name = f'_bcopt_insert_{stem}_{index}'
        self.names.add(name)
        return name

    def apply(self, tree):
        if 'tuple-insertion-buffer' in self.options.disabled or 'builtins' in self.program.modules:
            return tree
        functions = [n for n in tree.body if isinstance(n, ast.FunctionDef)]
        functions.extend(method for owner in tree.body if isinstance(owner, ast.ClassDef) and not owner.type_params
                         for method in owner.body if isinstance(method, ast.FunctionDef))
        for function in functions:
            before = ast.unparse(function)
            parts = list(ast.walk(function))
            if function.type_params or not any(isinstance(n, ast.Yield) for n in parts) or any(
                isinstance(n, (ast.Global, ast.Nonlocal, ast.NamedExpr, ast.Lambda, ast.ClassDef,
                               ast.Try, ast.TryStar, ast.With, ast.AsyncWith, ast.Await, ast.YieldFrom))
                or isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n is not function for n in parts):
                continue
            bindings = Bindings(function.body)
            parameters = {a.arg for a in arguments(function)}
            self.local = set(bindings.counts) | parameters
            self.owners = parameters - set(bindings.counts)
            self.flags = {}
            self.buffers = {}
            function.body = self.block(function.body, set(parameters))
            if self.flags:
                prefix = [ast.Assign(targets=[ast.Name(id=flag, ctx=ast.Store())], value=ast.Compare(
                    left=ast.Call(func=ast.Name(id=self.aliases['type'], ctx=ast.Load()),
                                  args=[ast.Name(id=owner, ctx=ast.Load())], keywords=[]),
                    ops=[ast.Is()], comparators=[ast.Name(id=self.aliases['tuple'], ctx=ast.Load())]))
                    for owner, flag in self.flags.items()]
                index = int(bool(function.body and isinstance(function.body[0], ast.Expr)
                            and isinstance(function.body[0].value, ast.Constant)
                            and isinstance(function.body[0].value.value, str)))
                if self.buffers:
                    for owner, work in self.buffers.items():
                        prefix.extend(ast.parse(f'{work} = {self.aliases["list"]}({owner}) '
                                                f'if {self.flags[owner]} else None').body)
                    cleanup = ast.parse('del ' + ', '.join(self.buffers.values())).body
                    function.body[index:] = [*prefix, ast.Try(body=function.body[index:],
                        handlers=[], orelse=[], finalbody=cleanup)]
                    self.changes.append(Change('tuple-insertion-hoist', function.lineno,
                                               before, ast.unparse(ast.fix_missing_locations(function))))
                else:
                    function.body[index:index] = prefix
        if self.changes:
            imports = ast.ImportFrom(module='builtins', names=[ast.alias(name=n, asname=a)
                for n, a in self.aliases.items()], level=0)
            index = 0
            if tree.body and isinstance(tree.body[0], ast.Expr) and isinstance(tree.body[0].value, ast.Constant) and isinstance(tree.body[0].value.value, str):
                index = 1
            while index < len(tree.body) and isinstance(tree.body[index], ast.ImportFrom) and tree.body[index].module == '__future__':
                index += 1
            tree.body[index:index] = [imports]
        return tree

    @staticmethod
    def stores(target):
        return {n.id for n in ast.walk(target) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store)}

    def block(self, statements, definite, depth=0):
        result = []
        for statement in statements:
            if isinstance(statement, ast.For):
                statement.body = self.block(statement.body, definite | self.stores(statement.target), depth + 1)
                statement.orelse = self.block(statement.orelse, set(definite), depth)
                result.append(self.rewrite(statement, definite, depth))
            elif isinstance(statement, (ast.If, ast.While)):
                statement.body = self.block(statement.body, set(definite), depth + isinstance(statement, ast.While))
                statement.orelse = self.block(statement.orelse, set(definite), depth)
                result.append(statement)
            else:
                result.append(statement)
            if isinstance(statement, (ast.Assign, ast.AnnAssign)) and statement.value is not None:
                targets = statement.targets if isinstance(statement, ast.Assign) else [statement.target]
                for target in targets:
                    definite.update(self.stores(target))
            elif isinstance(statement, ast.Delete):
                definite.difference_update(n.id for t in statement.targets for n in ast.walk(t) if isinstance(n, ast.Name))
        return result

    def builtin(self, call, name):
        return (isinstance(call, ast.Call) and isinstance(call.func, ast.Name) and call.func.id not in self.local
                and self.program.resolve(self.module, call.func) in {name, f'builtins.{name}'}
                and len(call.args) == 1 and not call.keywords)

    def rewrite(self, loop, definite, depth):
        if not (isinstance(loop.target, ast.Name) and not loop.orelse and len(loop.body) == 1
                and isinstance(loop.body[0], ast.Expr) and isinstance(loop.body[0].value, ast.Yield)
                and self.builtin(loop.iter, 'range')):
            return loop
        bound = loop.iter.args[0]
        if not (isinstance(bound, ast.BinOp) and isinstance(bound.op, ast.Add)
                and isinstance(bound.right, ast.Constant) and type(bound.right.value) is int and bound.right.value == 1
                and self.builtin(bound.left, 'len') and isinstance(bound.left.args[0], ast.Name)
                and bound.left.args[0].id in self.owners):
            return loop
        owner, position = bound.left.args[0].id, loop.target.id
        value = loop.body[0].value.value
        if not (isinstance(value, ast.BinOp) and isinstance(value.op, ast.Add)
                and isinstance(value.left, ast.BinOp) and isinstance(value.left.op, ast.Add)
                and isinstance(value.left.right, ast.Tuple) and len(value.left.right.elts) == 1):
            return loop
        prefix, item, suffix = value.left.left, value.left.right.elts[0], value.right
        if not (isinstance(item, ast.Name) and item.id in definite | {position}):
            return loop
        for expression, before in ((prefix, True), (suffix, False)):
            if not (isinstance(expression, ast.Subscript) and isinstance(expression.value, ast.Name)
                    and expression.value.id == owner and isinstance(expression.slice, ast.Slice)
                    and expression.slice.step is None):
                return loop
            cut = expression.slice.upper if before else expression.slice.lower
            empty = expression.slice.lower if before else expression.slice.upper
            if not (empty is None and isinstance(cut, ast.Name) and cut.id == position):
                return loop
        if owner not in self.flags:
            self.flags[owner] = self.fresh('exact')
        hoist = depth > 0 and 'tuple-insertion-hoist' not in self.options.disabled
        if hoist:
            if owner not in self.buffers:
                self.buffers[owner] = self.fresh('work')
            work = self.buffers[owner]
        else:
            work = self.fresh('work')
        generated = copy.deepcopy(loop)
        generated.body = ast.parse(f'{work}.insert({position}, {item.id})\n'
                                    f'yield {self.aliases["tuple"]}({work})\n'
                                    f'del {work}[{position}]\n').body
        generated._bcopt_tuple_buffer_loop = (self.aliases['tuple'], loop.iter.func.id, bound.left.func.id)
        fast = [*ast.parse(f'{work} = {self.aliases["list"]}({owner})').body,
                ast.Try(body=[generated], handlers=[], orelse=[],
                        finalbody=[ast.Delete(targets=[ast.Name(id=work, ctx=ast.Del())])])]
        if hoist:
            fast = [generated]
        replacement = ast.If(test=ast.Name(id=self.flags[owner], ctx=ast.Load()), body=fast, orelse=[copy.deepcopy(loop)])
        if hasattr(loop, '_bcopt_insertion_key_loop'):
            replacement._bcopt_insertion_key_loop = loop._bcopt_insertion_key_loop
            replacement._bcopt_insertion_exact_branch = True
        self.changes.append(Change('tuple-insertion-buffer', loop.lineno, ast.unparse(loop), ast.unparse(replacement)))
        return ast.copy_location(replacement, loop)
