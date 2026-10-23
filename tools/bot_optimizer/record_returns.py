"""Inline cached fresh-record allocation at narrowly proven terminal returns.

The original object and dictionary are still allocated at the original point.
This removes a factory call, not the record or its shared-key side effects.
"""

import ast
import copy

from .analysis import Bindings, arguments
from .model import Change
from .records import used_names


class InlineRecordReturns:
    def __init__(self, program, module, options):
        self.program, self.module, self.options = program, module, options
        self.names = used_names(program.modules[module].tree)
        self.changes = []
        self.object = self.fresh('return_object')
        self.allocator = self.fresh('new')

    def fresh(self, stem):
        index = 0
        while f'_bcopt_{stem}_{index}' in self.names:
            index += 1
        name = f'_bcopt_{stem}_{index}'
        self.names.add(name)
        return name

    def apply(self, tree):
        if ('record-inline-return' in self.options.disabled or 'record-allocator-cache' in self.options.disabled
                or self.program.dynamic_modules or self.program._cyclic_imports()):
            return tree
        functions = [n for n in tree.body if isinstance(n, ast.FunctionDef)]
        functions.extend(method for owner in tree.body if isinstance(owner, ast.ClassDef) and not owner.type_params
                         for method in owner.body if isinstance(method, ast.FunctionDef))
        for function in functions:
            self.transform(function)
        if self.changes:
            helpers = ast.parse(f'from builtins import object as {self.object}\n'
                                f'{self.allocator} = {self.object}.__new__\n').body
            index = 0
            if tree.body and isinstance(tree.body[0], ast.Expr) and isinstance(tree.body[0].value, ast.Constant) and isinstance(tree.body[0].value.value, str):
                index = 1
            while index < len(tree.body) and isinstance(tree.body[index], ast.ImportFrom) and tree.body[index].module == '__future__':
                index += 1
            tree.body[index:index] = helpers
        return tree

    def transform(self, function):
        if (function.type_params or not function.body or not isinstance(function.body[-1], ast.Return)
                or not isinstance(function.body[-1].value, ast.Call)):
            return
        if any(isinstance(n, (ast.Global, ast.Nonlocal, ast.NamedExpr, ast.Delete, ast.Try, ast.TryStar,
                              ast.Lambda, ast.ClassDef, ast.Yield, ast.YieldFrom, ast.Await))
               or isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n is not function
               for n in ast.walk(function)):
            return
        original = function.body[-1]
        call = original.value
        local = set(Bindings(function.body).counts) | {arg.arg for arg in arguments(function)}
        root = call.func
        while isinstance(root, ast.Attribute):
            root = root.value
        if not isinstance(root, ast.Name) or root.id in local:
            return
        record = self.program.records.get(self.program.resolve(self.module, call.func))
        if not (record and record.simple and record.frozen and 2 <= len(record.fields) <= 20
                and self.program.available(self.module, call.func, function.lineno)):
            return
        dependency = 'small-record-call' if len(record.fields) <= 3 else 'record-call'
        if dependency in self.options.disabled:
            return
        bound = record.signature.bind(call)
        if bound is None or set(bound) != set(record.fields):
            return
        definite = {arg.arg for arg in arguments(function)}
        for statement in function.body[:-1]:
            if isinstance(statement, ast.Assign):
                for target in statement.targets:
                    definite.update(n.id for n in ast.walk(target)
                                    if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store))
            elif isinstance(statement, ast.AnnAssign) and statement.value is not None and isinstance(statement.target, ast.Name):
                definite.add(statement.target.id)
        effectful = []
        for value in [*call.args, *(kw.value for kw in call.keywords)]:
            if isinstance(value, ast.Name):
                if value.id not in definite:
                    return
            elif not isinstance(value, ast.Constant):
                effectful.append(value)
        # A second effectful argument could raise after the first produced a
        # finalizable temporary. Do not retain such a temporary in a traceback.
        if len(effectful) > 1:
            return
        values = {field: copy.deepcopy(value) for field, value in bound.items()}
        replacement = []
        if effectful:
            temporary = self.fresh('return_value')
            replacement.append(ast.Assign(targets=[ast.Name(id=temporary, ctx=ast.Store())], value=copy.deepcopy(effectful[0])))
            for field, value in bound.items():
                if value is effectful[0]:
                    values[field] = ast.Name(id=temporary, ctx=ast.Load())
        row, dictionary = self.fresh('return_record'), self.fresh('return_dict')
        replacement.extend(ast.parse(f'{row} = {self.allocator}({ast.unparse(call.func)})\n'
                                     f'{dictionary} = {row}.__dict__\n').body)
        replacement.extend(ast.Assign(targets=[ast.Subscript(value=ast.Name(id=dictionary, ctx=ast.Load()),
            slice=ast.Constant(field), ctx=ast.Store())], value=values[field]) for field in record.fields)
        replacement.extend(ast.parse(f'del {dictionary}\nreturn {row}\n').body)
        replacement = [ast.copy_location(statement, original) for statement in replacement]
        function.body[-1:] = replacement
        self.changes.append(Change('record-inline-return', original.lineno, ast.unparse(original),
                                   '\n'.join(ast.unparse(statement) for statement in replacement)))
