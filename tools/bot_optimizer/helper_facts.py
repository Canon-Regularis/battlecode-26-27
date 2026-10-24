"""Share successful immutable guards between compiler-generated helpers.

Contracts are registered by the emitting passes, never inferred from user names
or annotations. Exact builtin container types survive calls; only exact integer
tuples also carry content facts. Mutable contents and fields are rechecked.
"""

import ast
import copy
from dataclasses import dataclass

from .analysis import Bindings
from .model import Change
from .records import used_names


@dataclass(frozen=True)
class IntTuple:
    argument: int
    maximum: int | None


class HelperFacts:
    def __init__(self):
        self.producers = {}
        self.consumers = {}
        self.guard_counts = {}
        self.shapes = {}

    def produces(self, name, *, argument, maximum):
        """A True return certifies this immutable argument's complete shape."""
        self.producers[name] = IntTuple(argument, maximum)

    def consumes(self, function, *, argument, maximum, guards):
        """Mark only the failure predicates justified by the shared contract."""
        self.consumers[function.name] = IntTuple(argument, maximum)
        self.guard_counts[function.name] = len(guards)
        for guard in guards:
            guard._bcopt_immutable_guard = True

    def shape(self, function, *, argument, kinds, guard):
        requirements = self.shapes.setdefault(function.name, [])
        guard._bcopt_shape_guard = len(requirements)
        requirements.append((argument, frozenset(kinds)))


def specialize_helper(original, name, removable):
    """Shared cloning machinery for emitter-registered failure predicates."""
    class RemoveGuards(ast.NodeTransformer):
        def visit(self, node):
            if removable(node):
                return ast.copy_location(ast.Constant(False), node)
            return super().visit(node)

        def visit_BoolOp(self, node):
            node = self.generic_visit(node)
            if isinstance(node.op, ast.Or):
                node.values = [value for value in node.values
                               if not (isinstance(value, ast.Constant) and value.value is False)]
                if not node.values:
                    return ast.Constant(False)
                if len(node.values) == 1:
                    return node.values[0]
            return node

        def visit_If(self, node):
            node = self.generic_visit(node)
            if isinstance(node.test, ast.Constant) and node.test.value is False:
                return node.orelse
            return node

    clone = RemoveGuards().visit(copy.deepcopy(original))
    clone.name = name
    used = {n.id for statement in clone.body for n in ast.walk(statement)
            if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)}
    required = len(clone.args.args) - len(clone.args.defaults)
    optional = [(arg, value) for arg, value in zip(clone.args.args[required:], clone.args.defaults)
                if arg.arg in used]
    clone.args.args = [*clone.args.args[:required], *(arg for arg, _ in optional)]
    clone.args.defaults = [value for _, value in optional]
    return clone


class StaticHelperShapes:
    """Exact builtin container types survive mutation; their contents do not."""
    def __init__(self, facts, options):
        self.facts, self.options = facts, options
        self.changes = []

    def apply(self, tree):
        if 'static-helper-shapes' in self.options.disabled:
            return tree
        names = used_names(tree)
        helpers = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)
                   and n.name in self.facts.shapes}
        clones = {}
        owner = self

        class Calls(ast.NodeTransformer):
            def visit_GeneratorExp(self, node):
                return node

            visit_ListComp = visit_SetComp = visit_DictComp = visit_Lambda = visit_GeneratorExp

            def visit_Call(self, node):
                node = self.generic_visit(node)
                if not (isinstance(node.func, ast.Name) and node.func.id in helpers
                        and not node.keywords and all(isinstance(arg, ast.Name) for arg in node.args)):
                    return node
                original_name = node.func.id
                removable = frozenset(i for i, (argument, kinds) in enumerate(owner.facts.shapes[original_name])
                    if argument < len(node.args) and known.get(node.args[argument].id) in kinds)
                if not removable:
                    return node
                key = original_name, removable
                if key not in clones:
                    index = 0
                    while f'_bcopt_shape_trusted_{index}' in names:
                        index += 1
                    name = f'_bcopt_shape_trusted_{index}'
                    names.add(name)
                    clone = specialize_helper(helpers[original_name], name,
                        lambda n: getattr(n, '_bcopt_shape_guard', None) in removable)
                    clones[key] = clone
                    if original_name in owner.facts.producers:
                        owner.facts.producers[name] = owner.facts.producers[original_name]
                    count = sum(bool(getattr(n, '_bcopt_immutable_guard', False)) for n in ast.walk(clone))
                    if original_name in owner.facts.consumers and count:
                        owner.facts.consumers[name] = owner.facts.consumers[original_name]
                        owner.facts.guard_counts[name] = count
                before = ast.unparse(node)
                node.func.id = clones[key].name
                owner.changes.append(Change('static-helper-shapes', node.lineno, before, ast.unparse(node)))
                return node

        functions = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name not in helpers]
        functions.extend(method for n in tree.body if isinstance(n, ast.ClassDef)
                         for method in n.body if isinstance(method, ast.FunctionDef))
        for function in functions:
            if any(isinstance(n, (ast.Global, ast.Nonlocal)) or
                   isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and n is not function
                   for n in ast.walk(function)):
                continue
            known = {}
            for index, statement in enumerate(function.body):
                previous = dict(known)
                for name in Bindings([statement]).counts:
                    known.pop(name, None)
                function.body[index] = Calls().visit(statement)
                if isinstance(statement, (ast.Assign, ast.AnnAssign)):
                    value = statement.value
                    kind = 'list' if isinstance(value, (ast.List, ast.ListComp)) else (
                        'tuple' if isinstance(value, ast.Tuple) else None)
                    if isinstance(value, ast.Name):
                        kind = previous.get(value.id)
                    if kind:
                        targets = statement.targets if isinstance(statement, ast.Assign) else [statement.target]
                        # Destructuring or attribute/subscript stores can invoke
                        # callbacks before a later target; keep only plain locals.
                        if all(isinstance(target, ast.Name) for target in targets):
                            known.update((target.id, kind) for target in targets)
        if clones:
            body = []
            for statement in tree.body:
                body.append(statement)
                if isinstance(statement, ast.FunctionDef):
                    body.extend(clone for (name, _), clone in clones.items() if name == statement.name)
            tree.body = body
        return tree


class ReuseHelperFacts:
    def __init__(self, facts, options):
        self.facts, self.options = facts, options
        self.changes = []
        self.clones = {}

    def fresh(self, stem):
        index = 0
        while f'_bcopt_facts_{stem}_{index}' in self.names:
            index += 1
        name = f'_bcopt_facts_{stem}_{index}'
        self.names.add(name)
        return name

    def specialize(self, name):
        if name in self.clones:
            return self.clones[name]
        original = self.helpers[name]
        if sum(bool(getattr(n, '_bcopt_immutable_guard', False)) for n in ast.walk(original)) != self.facts.guard_counts[name]:
            return None

        clone = specialize_helper(original, self.fresh('trusted'),
                                  lambda n: getattr(n, '_bcopt_immutable_guard', False))
        self.clones[name] = clone
        return clone

    def specialize_region(self, function):
        """Version one bounded continuation rather than redispatch each call.

        The copied branches execute the same statements in the same lexical
        scope. Only compiler-created conditional calls using this proof change.
        Keeping one region per function bounds code growth to at most twofold.
        """
        if 'immutable-helper-regions' in self.options.disabled:
            return
        for index, branch in enumerate(function.body):
            if not (isinstance(branch, ast.If) and isinstance(branch.test, ast.UnaryOp)
                    and isinstance(branch.test.op, ast.Not) and isinstance(branch.test.operand, ast.NamedExpr)
                    and getattr(branch, '_bcopt_proof_branch', False)):
                continue
            tail = function.body[index + 1:]
            if sum(1 for statement in tail for _ in ast.walk(statement)) > 2000:
                continue
            before = ast.unparse(function)
            flag = branch.test.operand.target.id

            class ResolveProof(ast.NodeTransformer):
                def __init__(self, truth):
                    self.truth = truth

                def visit_IfExp(self, node):
                    if isinstance(node.test, ast.Name) and node.test.id == flag:
                        return node.body if self.truth else node.orelse
                    return self.generic_visit(node)

            branch.test.operand = branch.test.operand.value
            branch.body.extend(ResolveProof(False).visit(copy.deepcopy(n)) for n in tail)
            branch.orelse = [ResolveProof(True).visit(copy.deepcopy(n)) for n in tail]
            function.body = function.body[:index + 1]
            self.changes.append(Change('immutable-helper-regions', function.lineno, before,
                                       ast.unparse(ast.fix_missing_locations(function))))
            break

    def apply(self, tree):
        if 'immutable-helper-facts' in self.options.disabled:
            return tree
        self.names = used_names(tree)
        self.helpers = {node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)
                        and node.name in self.facts.consumers}
        functions = [node for node in tree.body if isinstance(node, ast.FunctionDef)]
        functions.extend(method for node in tree.body if isinstance(node, ast.ClassDef)
                         for method in node.body if isinstance(method, ast.FunctionDef))
        for function in functions:
            if any(isinstance(n, (ast.Global, ast.Nonlocal)) or
                   isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and n is not function
                   for n in ast.walk(function)):
                continue
            known = {}
            for statement in function.body:
                # Invalidate before inspecting the whole statement: branches,
                # exception targets, deletes and walrus stores all count.
                for name in Bindings([statement]).counts:
                    known.pop(name, None)
                if (isinstance(statement, ast.If) and isinstance(statement.test, ast.UnaryOp)
                        and isinstance(statement.test.op, ast.Not)
                        and isinstance(statement.test.operand, ast.Call)):
                    call = statement.test.operand
                    contract = self.facts.producers.get(call.func.id) if isinstance(call.func, ast.Name) else None
                    if (contract and not call.keywords and len(call.args) > contract.argument
                            and isinstance(call.args[contract.argument], ast.Name)):
                        route = call.args[contract.argument].id
                        if route not in Bindings([statement]).counts:
                            known[route] = [statement, contract, None]
                if not (isinstance(statement, ast.Assign) and isinstance(statement.value, ast.Call)):
                    continue
                call = statement.value
                contract = self.facts.consumers.get(call.func.id) if isinstance(call.func, ast.Name) else None
                if not (contract and call.func.id in self.helpers and not call.keywords
                        and len(call.args) > contract.argument
                        and all(isinstance(arg, ast.Name) for arg in call.args)):
                    continue
                proof = known.get(call.args[contract.argument].id)
                if proof is None or contract.maximum is not None and proof[1].maximum > contract.maximum:
                    continue
                clone = self.specialize(call.func.id)
                if clone is None:
                    continue
                before = ast.unparse(statement)
                if proof[2] is None:
                    proof[2] = self.fresh('valid')
                    test = proof[0].test
                    test.operand = ast.NamedExpr(target=ast.Name(id=proof[2], ctx=ast.Store()), value=test.operand)
                    proof[0]._bcopt_proof_branch = True
                fast = copy.deepcopy(call)
                fast.func.id = clone.name
                statement.value = ast.IfExp(test=ast.Name(id=proof[2], ctx=ast.Load()), body=fast, orelse=call)
                self.changes.append(Change('immutable-helper-facts', statement.lineno, before,
                                           ast.unparse(ast.fix_missing_locations(statement))))
            self.specialize_region(function)
        if self.clones:
            body = []
            for statement in tree.body:
                body.append(statement)
                if isinstance(statement, ast.FunctionDef) and statement.name in self.clones:
                    body.append(self.clones[statement.name])
            tree.body = body
        return tree
