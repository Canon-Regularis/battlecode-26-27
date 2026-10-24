"""Remove unused, definitely-bound primitive stores in prepared numeric regions.

Private-local emitter provenance and exact-int store contracts rule out visible
binding/lifetime effects. Every use in every dispatch arm must be locally
definitely bound, so another iteration or fallback cannot observe a removed
assignment. Removed expressions are only existing direct-route scalars/constants.
"""

import ast

from .base_edge_scalars import named, writes
from .model import Change


def definitely_bound(body, name, bound=False):
    """Check this private name without relying on any previous invocation."""
    def expression(node, current):
        return not any(named(n, name) and isinstance(n.ctx, ast.Load) and not current for n in ast.walk(node))
    def targets(node):
        return any(named(n, name) and isinstance(n.ctx, (ast.Store, ast.Del)) for n in ast.walk(node))
    for statement in body:
        if isinstance(statement, ast.Assign):
            if not expression(statement.value, bound):
                return False, bound
            if any(not expression(t, bound) for t in statement.targets):
                return False, bound
            if any(targets(t) for t in statement.targets):
                bound = True
        elif isinstance(statement, ast.If):
            if not expression(statement.test, bound):
                return False, bound
            yes, yb = definitely_bound(statement.body, name, bound)
            no, nb = definitely_bound(statement.orelse, name, bound)
            if not yes or not no:
                return False, bound
            bound = yb and nb
        elif isinstance(statement, (ast.For, ast.While)):
            expr = statement.iter if isinstance(statement, ast.For) else statement.test
            if not expression(expr, bound):
                return False, bound
            inner = bound or isinstance(statement, ast.For) and targets(statement.target)
            if not definitely_bound(statement.body, name, inner)[0] or not definitely_bound(statement.orelse, name, bound)[0]:
                return False, bound
        elif isinstance(statement, ast.Try):
            if not definitely_bound(statement.body, name, bound)[0]:
                return False, bound
            if any(h.type is not None and not expression(h.type, bound) for h in statement.handlers):
                return False, bound
            # Conservative about partially completed bodies and exceptional joins.
            for block in [statement.orelse, statement.finalbody, *(h.body for h in statement.handlers)]:
                if not definitely_bound(block, name, bound)[0]:
                    return False, bound
        elif isinstance(statement, ast.Delete):
            if any(targets(t) for t in statement.targets):
                if not bound:
                    return False, bound
                bound = False
        elif isinstance(statement, ast.AugAssign):
            if targets(statement.target):
                if not bound:
                    return False, bound
            if not expression(statement.value, bound) or not expression(statement.target, bound):
                return False, bound
        else:
            if not expression(statement, bound):
                return False, bound
            if any(named(n, name) and isinstance(n.ctx, (ast.Store, ast.Del)) for n in ast.walk(statement)):
                return False, bound
    return True, bound


class DeadPrimitiveSlots:
    def __init__(self, options):
        self.options, self.changes = options, []

    def apply(self, tree):
        if 'numeric-dead-primitive-slots' in self.options.disabled:
            return tree
        for consumer in tree.body:
            if not getattr(consumer, '_bcopt_fused_consumer', False):
                continue
            versions = [n for n in ast.walk(consumer) if getattr(n, '_bcopt_prepared_dispatch', False)]
            covered = {n for v in versions for block in (v.body, v.orelse) for s in block for n in ast.walk(s)}
            occurrences = {}
            for n in ast.walk(consumer):
                if isinstance(n, ast.Name):
                    occurrences.setdefault(n.id, []).append(n)
            safe = {}
            def local_integer(name):
                if name not in safe:
                    nodes = occurrences[name]
                    safe[name] = (all(n in covered for n in nodes)
                        and all(getattr(n, '_bcopt_bound_kind', None) == 'int' for n in nodes
                                if isinstance(n.ctx, (ast.Store, ast.Del)))
                        and all(definitely_bound(block, name)[0] for v in versions for block in (v.body, v.orelse)))
                return safe[name]
            for wrapper in [n for n in ast.walk(consumer) if getattr(n, '_bcopt_unrolled_position', None)]:
                if not isinstance(wrapper, ast.For) or not wrapper.body:
                    continue
                route = wrapper.body[0]
                contract = getattr(route, '_bcopt_direct_tuple', None)
                if (not contract or not isinstance(route, ast.Assign) or not isinstance(route.value, ast.Tuple)
                        or tuple(getattr(n, 'id', None) for n in route.value.elts) != contract[2]):
                    continue
                scalars = set(contract[2])
                if any(writes(wrapper)[name] for name in scalars):
                    continue
                for version in [n for n in ast.walk(wrapper) if getattr(n, '_bcopt_prepared_dispatch', False)]:
                    region = ast.Module(body=version.body, type_ignores=[])
                    private = set(getattr(version, '_bcopt_private_numeric_locals', ()))
                    private.update(n.targets[0].id for n in ast.walk(region) if isinstance(n, ast.Assign)
                                   and getattr(n, '_bcopt_private_integer_assignment', False)
                                   and len(n.targets) == 1 and isinstance(n.targets[0], ast.Name))
                    loads = {n.id for n in ast.walk(region) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)}
                    def pure(node):
                        return (isinstance(node, ast.Name) and node.id in scalars
                                or isinstance(node, ast.Constant) and type(node.value) is int
                                or isinstance(node, ast.Tuple) and all(pure(n) for n in node.elts))
                    owner = self
                    class Remove(ast.NodeTransformer):
                        def visit_Assign(self, node):
                            if len(node.targets) != 1 or not pure(node.value):
                                return node
                            target = node.targets[0]
                            parts = target.elts if isinstance(target, ast.Tuple) else [target]
                            if isinstance(target, ast.Tuple):
                                if (not isinstance(node.value, ast.Tuple) or len(parts) != len(node.value.elts)
                                        or any(isinstance(n, ast.Tuple) for n in node.value.elts)):
                                    return node
                            elif isinstance(node.value, ast.Tuple):
                                return node
                            if all(isinstance(n, ast.Name) and n.id in private and n.id not in loads
                                   and local_integer(n.id) for n in parts):
                                owner.changes.append(Change('numeric-dead-primitive-slots', node.lineno,
                                    'unused definitely-bound private integer assignment', 'removed redundant primitive store'))
                                return None
                            return node
                    version.body = Remove().visit(region).body
        return ast.fix_missing_locations(tree)
