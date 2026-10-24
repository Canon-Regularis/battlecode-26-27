"""Inline certified numeric entries into their closed consumer epoch.

Only emitter-owned contracts authorize this pass. Inputs and surviving numeric
locals contain validated primitives/private containers; result records remain
fresh and their extra return alias is released immediately. Native-index retry,
the original dispatch fallback, and dirty-callback invalidation stay in place.
"""

import ast
from collections import Counter
import copy
from types import SimpleNamespace

from .analysis import Bindings, arguments
from .model import Change
from .numeric_regions import Unsupported, inline_numeric_helpers
from .records import used_names


class InlineNumericEntries:
    def __init__(self, options):
        self.options = options
        self.changes = []
        self.taken = set()
        self.allocated = set()

    def fresh(self, stem):
        index = 0
        while f'_bcopt_entry_{stem}_{index}' in self.taken:
            index += 1
        name = f'_bcopt_entry_{stem}_{index}'
        self.taken.add(name)
        self.allocated.add(name)
        return name

    def apply(self, tree):
        if 'numeric-entry-inline' in self.options.disabled:
            return tree
        self.taken = used_names(tree)
        entries = {node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)
                   and getattr(node, '_bcopt_numeric_clone', False)
                   and getattr(node, '_bcopt_index_retry', None) is not None}
        for consumer in tree.body:
            contract = getattr(consumer, '_bcopt_numeric_consumer', None)
            if not isinstance(consumer, ast.FunctionDef) or contract is None:
                continue
            root, width = contract
            ready = [node for node in consumer.body if getattr(node, '_bcopt_consumer_ready', False)]
            if len(ready) != 1:
                continue
            hoisted = []
            owner = self
            class Inline(ast.NodeTransformer):
                def visit_Assign(self, node):
                    if (not getattr(node, '_bcopt_numeric_assignment', False)
                            or len(node.targets) != 1 or not isinstance(node.targets[0], ast.Name)
                            or not isinstance(node.value, ast.IfExp) or not isinstance(node.value.body, ast.Call)
                            or not isinstance(node.value.body.func, ast.Name)
                            or node.value.body.func.id not in entries):
                        return self.generic_visit(node)
                    result = owner.inline(node, entries[node.value.body.func.id], consumer, root, width)
                    if result is None:
                        return node
                    replacement, loads = result
                    hoisted.extend(loads)
                    owner.changes.append(Change('numeric-entry-inline', node.lineno,
                        ast.unparse(node), ast.unparse(replacement)))
                    if getattr(replacement, '_bcopt_prepared_version', False):
                        owner.changes.append(Change('numeric-prepared-versions', node.lineno,
                            ast.unparse(node), ast.unparse(replacement)))
                    return replacement
            Inline().visit(consumer)
            index = consumer.body.index(ready[0])+1
            consumer.body[index:index] = hoisted
        return ast.fix_missing_locations(tree)

    def inline(self, node, numeric, consumer, root, width):
        if len(numeric.body) != 1 or not isinstance(numeric.body[0], ast.Try):
            return None
        retry = numeric.body[0]
        if (retry.finalbody or retry.orelse or len(retry.handlers) != 1
                or len(retry.handlers[0].body) != 1 or not isinstance(retry.handlers[0].body[0], ast.Return)):
            return None
        call = node.value.body
        if (not call.args or not isinstance(call.args[0], ast.Name) or call.args[0].id != root
                or any(not isinstance(value, (ast.Name, ast.Constant))
                       for value in [*call.args, *(keyword.value for keyword in call.keywords)])):
            return None
        helper = copy.deepcopy(numeric)
        helper.body = helper.body[0].body
        locals_ = set(Bindings(helper.body).counts) | {arg.arg for arg in arguments(helper)}
        loads = {part.id for part in ast.walk(helper) if isinstance(part, ast.Name) and isinstance(part.ctx, ast.Load)}
        caller_locals = set(Bindings(consumer.body).counts) | {arg.arg for arg in arguments(consumer)}
        if (loads-locals_) & caller_locals:
            return None  # Inlining must not capture a previously global name.
        assignment = copy.deepcopy(node)
        assignment.value = copy.deepcopy(call)
        wrapper = ast.parse('def wrapper():\n    pass\n').body[0]
        wrapper.body = [assignment]
        entry = SimpleNamespace(function=wrapper)
        builder = SimpleNamespace(fresh=self.fresh, clones={
            'entry': entry, 'helper': SimpleNamespace(name=helper.name, function=helper)})
        allocated_before = set(self.allocated)
        try:
            changed = inline_numeric_helpers(builder, entry, helper_limit=6000, output_limit=12000)
        except Unsupported:
            return None
        if changed != 1:
            return None
        allocated = self.allocated-allocated_before
        target = node.targets[0].id
        class Release(ast.NodeTransformer):
            def visit_Assign(self, statement):
                if (len(statement.targets) == 1 and isinstance(statement.targets[0], ast.Name)
                        and statement.targets[0].id == target and isinstance(statement.value, ast.Name)
                        and statement.value.id in allocated):
                    return [statement, ast.Delete(targets=[ast.Name(id=statement.value.id, ctx=ast.Del())])]
                return self.generic_visit(statement)
        body = Release().visit(entry.function).body
        writes = Counter(part.id for statement in body for part in ast.walk(statement)
                         if isinstance(part, ast.Name) and isinstance(part.ctx, (ast.Store, ast.Del)))
        def root_read(value):
            if isinstance(value, ast.Tuple):
                return bool(value.elts) and all(root_read(item) for item in value.elts)
            return (isinstance(value, ast.Subscript) and isinstance(value.value, ast.Name)
                    and value.value.id == root and isinstance(value.slice, ast.Constant)
                    and type(value.slice.value) is int and 0 <= value.slice.value < width)
        def target_names(value):
            if isinstance(value, ast.Name):
                return [value.id]
            if isinstance(value, (ast.Tuple, ast.List)):
                parts = [target_names(item) for item in value.elts]
                if all(part is not None for part in parts):
                    return [name for part in parts for name in part]
            return None
        hoisted = []
        class Hoist(ast.NodeTransformer):
            def generic_visit(self, node):
                node = super().generic_visit(node)
                if isinstance(node, (ast.If, ast.For, ast.While, ast.Try, ast.ExceptHandler)) and not node.body:
                    node.body = [ast.copy_location(ast.Pass(), node)]
                return node
            def visit_Assign(self, statement):
                names = [target_names(value) for value in statement.targets]
                if (root_read(statement.value) and all(names)
                        and all(name in allocated and writes[name] == 1 for group in names for name in group)):
                    statement._bcopt_snapshot_hoisted = True
                    hoisted.append(statement)
                    return None
                return self.generic_visit(statement)
        body = Hoist().visit(ast.Module(body=body, type_ignores=[])).body
        handler = copy.deepcopy(retry.handlers[0])
        handler.body = [ast.Assign(targets=copy.deepcopy(node.targets), value=handler.body[0].value)]
        protected = ast.Try(body=body, handlers=[handler], orelse=[], finalbody=[])
        version = self.prepared_version(protected, hoisted)
        if version is not None:
            version._bcopt_private_numeric_locals = tuple(sorted(allocated))
        fallback = copy.deepcopy(node)
        fallback.value = node.value.orelse
        result = ast.If(test=node.value.test, body=[version or protected], orelse=[fallback])
        result._bcopt_inlined_entry = numeric.name
        result._bcopt_prepared_version = version is not None
        if getattr(node, '_bcopt_losing_entry', None):
            result._bcopt_losing_entry = copy.deepcopy(node._bcopt_losing_entry)
        return ast.fix_missing_locations(ast.copy_location(result, node)), hoisted

    def prepared_version(self, protected, hoisted):
        """Unswitch emitter-owned preparation tests for one closed epoch."""
        if 'numeric-prepared-versions' in self.options.disabled:
            return None
        tables = {node.targets[0].id for node in hoisted
                  if getattr(node, '_bcopt_prepared_table', False)
                  and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name)}
        def known_test(node):
            return (getattr(node, '_bcopt_prepared_test', False)
                    and isinstance(node, ast.Compare) and isinstance(node.left, ast.Name)
                    and node.left.id in tables and len(node.ops) == 1 and isinstance(node.ops[0], ast.Is)
                    and len(node.comparators) == 1 and isinstance(node.comparators[0], ast.Constant)
                    and node.comparators[0].value is None)
        needed = sorted({node.test.left.id for node in ast.walk(protected)
                         if isinstance(node, ast.IfExp) and known_test(node.test)})
        if not needed or len(needed) > 16 or sum(1 for _ in ast.walk(protected)) > 8000:
            return None
        class Prepared(ast.NodeTransformer):
            def visit_IfExp(self, node):
                if known_test(node.test):
                    return self.visit(node.orelse)
                return self.generic_visit(node)
        specialized = Prepared().visit(copy.deepcopy(protected))
        ready = self.fresh('prepared_ready')
        hoisted.extend(ast.parse(f'{ready} = '+ ' and '.join(f'{name} is not None' for name in needed)).body)
        result = ast.If(test=ast.Name(id=ready, ctx=ast.Load()), body=[specialized], orelse=[protected])
        result._bcopt_prepared_dispatch = True
        return result
