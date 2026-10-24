"""Avoid generator resumptions for guarded any/all element comparisons."""

import ast
import copy

from .analysis import Bindings, arguments
from .model import Change
from .records import used_names
from .helper_bindings import cache_helper_builtins


class ShortCircuit:
    def __init__(self, program, module, options, facts=None):
        self.program, self.module, self.options = program, module, options
        self.names = used_names(program.modules[module].tree)
        self.changes, self.helpers, self.cache = [], [], {}
        self.facts = facts
        self.builtins = {name: self.fresh(name) for name in (
            'type', 'list', 'tuple', 'StopIteration', 'RuntimeError', 'BaseException', 'any', 'all')}

    def fresh(self, stem):
        index = 0
        while f'_bcopt_short_{stem}_{index}' in self.names:
            index += 1
        name = f'_bcopt_short_{stem}_{index}'
        self.names.add(name)
        return name

    def apply(self, tree):
        if 'short-circuit-loop' in self.options.disabled or 'builtins' in self.program.modules:
            return tree
        functions = [n for n in tree.body if isinstance(n, ast.FunctionDef)]
        functions.extend(method for owner in tree.body if isinstance(owner, ast.ClassDef) and not owner.type_params
                         for method in owner.body if isinstance(method, ast.FunctionDef))
        for function in functions:
            if function.type_params or any(isinstance(n, (ast.Global, ast.Nonlocal, ast.NamedExpr, ast.Lambda, ast.ClassDef))
                   or isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n is not function
                   for n in ast.walk(function)):
                continue
            # A local owner keeps the container alive through the call. No
            # escaping cell may rebind it while comparison/bool callbacks run.
            local = set(Bindings(function.body).counts) | {arg.arg for arg in arguments(function)}
            outer = self

            class Calls(ast.NodeTransformer):
                def visit_GeneratorExp(self, node):
                    return node

                visit_ListComp = visit_GeneratorExp
                visit_SetComp = visit_GeneratorExp
                visit_DictComp = visit_GeneratorExp

                def visit_Call(self, node):
                    node = self.generic_visit(node)
                    return outer.rewrite(node, local)

            visitor = Calls()
            function.body = [visitor.visit(statement) for statement in function.body]
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

    def rewrite(self, node, local):
        if (not isinstance(node.func, ast.Name) or node.func.id in local
                or len(node.args) != 1 or node.keywords or not isinstance(node.args[0], ast.GeneratorExp)):
            return node
        consumer = self.program.resolve(self.module, node.func)
        if consumer not in {'any', 'all', 'builtins.any', 'builtins.all'}:
            return node
        consumer = consumer.removeprefix('builtins.')
        gen = node.args[0]
        if len(gen.generators) != 1:
            return node
        comp, predicate = gen.generators[0], gen.elt
        if not (isinstance(comp.target, ast.Name) and isinstance(comp.iter, ast.Name)
                and comp.iter.id in local and not comp.ifs and not comp.is_async
                and isinstance(predicate, ast.Compare) and len(predicate.ops) == 1
                and isinstance(predicate.left, ast.Name) and predicate.left.id == comp.target.id
                and isinstance(predicate.ops[0], (ast.Lt, ast.LtE, ast.Gt, ast.GtE, ast.Eq, ast.NotEq))):
            return node
        constant = predicate.comparators[0]
        if not (isinstance(constant, ast.Constant) or isinstance(constant, ast.UnaryOp)
                and isinstance(constant.op, (ast.UAdd, ast.USub)) and isinstance(constant.operand, ast.Constant)
                and type(constant.operand.value) in {int, float, complex}):
            return node
        predicate = copy.deepcopy(predicate)
        predicate.left.id = 'item'
        key = consumer, ast.dump(predicate)
        if key not in self.cache:
            helper = self.fresh(consumer)
            b = self.builtins
            expression = ast.unparse(predicate)
            source = f'''def {helper}(items):
    if not ({b['type']}(items) is {b['list']} or {b['type']}(items) is {b['tuple']}):
        return {b[consumer]}({expression} for item in items)
    for item in items:
        try:
            value = {expression}
        except {b['StopIteration']} as error:
            raise {b['RuntimeError']}('generator raised StopIteration') from error
        try:
            try:
                if {'not ' if consumer == 'all' else ''}value:
                    return {consumer == 'any'}
            finally:
                del value
        except {b['BaseException']}:
            del item, items
            raise
    return {consumer == 'all'}
'''
            # Predicate exceptions occur inside the original generator; boolean
            # exceptions occur in the consumer. Explicit cleanup preserves that
            # distinction and avoids retaining the item in a bool-error traceback.
            generated = cache_helper_builtins(ast.parse(source).body, self.builtins,
                {'type'}, self.options, self.changes, node.lineno)
            self.helpers.extend(generated)
            if self.facts is not None:
                self.facts.shape(generated[0], argument=0, kinds={'list', 'tuple'}, guard=generated[0].body[0].test)
            self.cache[key] = helper
        replacement = ast.Call(func=ast.Name(id=self.cache[key], ctx=ast.Load()),
                               args=[copy.deepcopy(comp.iter)], keywords=[])
        self.changes.append(Change('short-circuit-loop', node.lineno, ast.unparse(node), ast.unparse(replacement)))
        return ast.copy_location(replacement, node)
