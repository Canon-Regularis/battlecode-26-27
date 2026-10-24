"""Native adjacency for an exact tuple kept alive by an immutable local owner."""

import ast
import copy

from .analysis import Bindings, arguments
from .model import Change
from .records import used_names


class AdjacentPairs:
    def __init__(self, program, module, options):
        self.program, self.module, self.options = program, module, options
        self.names = used_names(program.modules[module].tree)
        self.changes = []
        self.aliases = {n: self.fresh(n) for n in ('pairwise', 'type', 'tuple', 'iter', 'next')}

    def fresh(self, stem):
        index = 0
        while f'_bcopt_adj_{stem}_{index}' in self.names:
            index += 1
        name = f'_bcopt_adj_{stem}_{index}'
        self.names.add(name)
        return name

    def apply(self, tree):
        if 'tuple-adjacent' in self.options.disabled or {'itertools', 'builtins'} & self.program.modules.keys():
            return tree
        functions = [n for n in tree.body if isinstance(n, ast.FunctionDef)]
        functions.extend(method for owner in tree.body if isinstance(owner, ast.ClassDef) and not owner.type_params
                         for method in owner.body if isinstance(method, ast.FunctionDef))
        for function in functions:
            if function.type_params or any(
                isinstance(n, (ast.Global, ast.Nonlocal, ast.NamedExpr, ast.Lambda, ast.ClassDef,
                               ast.Yield, ast.YieldFrom, ast.Await))
                or isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n is not function
                for n in ast.walk(function)):
                continue
            bindings = Bindings(function.body)
            params = {a.arg for a in arguments(function)}
            local = set(bindings.counts) | params
            # Restrict to parameters never rebound/deleted, including handlers.
            owners = params - set(bindings.counts)
            replacements = {}
            for loop in ast.walk(function):
                if not isinstance(loop, ast.For):
                    continue
                call = loop.iter
                if not (isinstance(call, ast.Call) and isinstance(call.func, ast.Name)
                        and call.func.id not in local and self.program.resolve(self.module, call.func) in {'zip', 'builtins.zip'}
                        and len(call.args) == 2 and not call.keywords):
                    continue
                first, second = call.args
                if not (isinstance(first, ast.Name) and first.id in owners and isinstance(second, ast.Subscript)
                        and isinstance(second.value, ast.Name) and second.value.id == first.id
                        and isinstance(second.slice, ast.Slice) and second.slice.upper is second.slice.step is None
                        and isinstance(second.slice.lower, ast.Constant) and type(second.slice.lower.value) is int
                        and second.slice.lower.value == 1):
                    continue
                # An unpacked pair cannot escape as an observably reused tuple.
                if not (isinstance(loop.target, (ast.Tuple, ast.List)) and len(loop.target.elts) == 2
                        and all(isinstance(n, ast.Name) for n in loop.target.elts)):
                    continue
                a = self.aliases
                replacement = ast.parse(f'{a["pairwise"]}({first.id}) if {a["type"]}({first.id}) is {a["tuple"]} else {ast.unparse(call)}', mode='eval').body
                loop.iter = ast.copy_location(replacement, call)
                self.changes.append(Change('tuple-adjacent', call.lineno, ast.unparse(call), ast.unparse(replacement)))
                # Binding the right item first is harmless only when both loop
                # locals are otherwise never assigned. Their previous values
                # are then owned by this same never-rebound tuple parameter.
                targets = [n.id for n in loop.target.elts]
                if ('tuple-adjacent-iterator' not in self.options.disabled
                        and len(set(targets)) == 2 and not set(targets) & params
                        and all(bindings.counts[n] == 1 for n in targets)
                        and not any(isinstance(n, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp))
                                    for n in ast.walk(loop))):
                    replacements[id(loop)] = (first.id, targets)
            owner = self

            class Loops(ast.NodeTransformer):
                def visit_For(self, node):
                    node = self.generic_visit(node)
                    if id(node) not in replacements:
                        return node
                    route, (left, right) = replacements[id(node)]
                    return owner.iterator_loop(node, route, left, right)

            function.body = [Loops().visit(statement) for statement in function.body]
        if self.changes:
            imports = ast.parse(f'from itertools import pairwise as {self.aliases["pairwise"]}\n'
                                'from builtins import ' + ', '.join(f'{n} as {self.aliases[n]}'
                                    for n in ('type', 'tuple', 'iter', 'next')) + '\n').body
            index = 0
            if tree.body and isinstance(tree.body[0], ast.Expr) and isinstance(tree.body[0].value, ast.Constant) and isinstance(tree.body[0].value.value, str):
                index = 1
            while index < len(tree.body) and isinstance(tree.body[index], ast.ImportFrom) and tree.body[index].module == '__future__':
                index += 1
            tree.body[index:index] = imports
        return tree

    def iterator_loop(self, loop, route, left, right):
        iterator, previous = self.fresh('iterator'), self.fresh('previous')
        a = self.aliases
        fast = copy.deepcopy(loop)
        fast.target = ast.Name(id=right, ctx=ast.Store())
        fast.iter = ast.Name(id=iterator, ctx=ast.Load())
        fast.body[:0] = ast.parse(f'{left} = {previous}\n{previous} = {right}').body
        initialize = ast.parse(f'{iterator} = {a["iter"]}({route})\n'
                               f'{previous} = {a["next"]}({iterator}, None)').body
        cleanup = ast.parse(f'del {previous}, {iterator}').body
        original = copy.deepcopy(loop)
        original.iter = original.iter.orelse  # Retain the original zip protocol.
        # CPython clears fast locals in lexical binding order. Reserve the
        # original left/right order without binding either on empty inputs.
        # Otherwise the new right-item loop target swaps payload finalizers.
        reserve = ast.parse(f'if False:\n    {left}, {right} = ()').body
        replacement = ast.If(test=copy.deepcopy(loop.iter.test),
            body=[*reserve, *initialize, ast.Try(body=[fast], handlers=[], orelse=[], finalbody=cleanup)],
            orelse=[original])
        if getattr(loop, '_bcopt_ordered_pair_fold', False):
            replacement._bcopt_ordered_pair_fold = True
            if all(getattr(part, '_bcopt_bound_kind', None) == 'int' for part in loop.target.elts):
                for part in ast.walk(replacement):
                    if isinstance(part, ast.Name) and part.id in {left, right} and isinstance(part.ctx, ast.Store):
                        part._bcopt_bound_kind = 'int'
        self.changes.append(Change('tuple-adjacent-iterator', loop.lineno,
                                   ast.unparse(loop), ast.unparse(replacement)))
        return ast.copy_location(replacement, loop)
