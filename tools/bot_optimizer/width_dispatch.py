"""Select emitter-certified ordered-fold widths once per fused base traversal.

The producer owns an exact integer size and fresh tuple routes of that size.
Specialized copies keep callback/exception/control-flow and allocation points.
Only the proven width chain is simplified; every other expression is retained.
"""

import ast
from collections import Counter
import copy

from .model import Change


class WidthDispatch:
    def __init__(self, options):
        self.options, self.changes = options, []

    def specialize(self, consumer, producer):
        fact = producer._bcopt_fused_insertion
        if set(fact) != {'base', 'item', 'position', 'route', 'size'}:
            return
        dispatches = [node for node in ast.walk(producer) if getattr(node, '_bcopt_ordered_width_dispatch', None)]
        if len(dispatches) != 1:
            return
        dispatch = dispatches[0]
        width, route, maximum = dispatch._bcopt_ordered_width_dispatch
        if route != fact['route'] or type(maximum) is not int or not 2 <= maximum <= 12:
            return
        writes = Counter(node.id for node in ast.walk(consumer) if isinstance(node, ast.Name)
                         and isinstance(node.ctx, (ast.Store, ast.Del)))
        bindings = [node for node in ast.walk(producer) if isinstance(node, ast.Assign)
                    and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name)
                    and node.targets[0].id == width]
        if (writes[width] != 1 or writes[fact['size']] != 1 or len(bindings) != 1
                or not isinstance(bindings[0].value, ast.Name) or bindings[0].value.id != fact['size']
                or any(isinstance(node, ast.Name) and node.id == fact['size']
                       and isinstance(node.ctx, (ast.Store, ast.Del)) for node in ast.walk(producer))):
            return
        # Bound code growth before copying; larger/custom sites retain dispatch.
        if sum(1 for _ in ast.walk(producer))*maximum > 100000:
            return
        chain, current = [], dispatch
        for count in range(2, maximum+1):
            if (not isinstance(current, ast.If) or not isinstance(current.test, ast.Compare)
                    or not isinstance(current.test.left, ast.Name) or current.test.left.id != width
                    or len(current.test.ops) != 1 or not isinstance(current.test.ops[0], ast.Eq)
                    or len(current.test.comparators) != 1 or not isinstance(current.test.comparators[0], ast.Constant)
                    or type(current.test.comparators[0].value) is not int or current.test.comparators[0].value != count
                    or len(current.orelse) != 1):
                return
            chain.append(current)
            current = current.orelse[0]
        expected_loads = {node.test.left for node in chain}
        if any(node not in expected_loads for node in ast.walk(producer)
               if isinstance(node, ast.Name) and node.id == width and isinstance(node.ctx, ast.Load)):
            return
        fallback = [producer]
        for count in reversed(range(2, maximum+1)):
            variant = copy.deepcopy(producer)
            class Fold(ast.NodeTransformer):
                def visit_If(self, node):
                    if getattr(node, '_bcopt_ordered_width_dispatch', None) == (width, route, maximum):
                        selected = node
                        for _ in range(count-2):
                            selected = selected.orelse[0]
                        return selected.body
                    return self.generic_visit(node)
            variant = Fold().visit(variant)
            fallback = [ast.If(test=ast.Compare(left=ast.Name(id=fact['size'], ctx=ast.Load()),
                ops=[ast.Eq()], comparators=[ast.Constant(count)]), body=[variant], orelse=fallback)]
            fallback[0]._bcopt_width_specialization = count
        self.changes.append(Change('insertion-width-dispatch', producer.lineno,
            'per-evaluation ordered-fold width chain', 'bounded width specialization once per fused base route'))
        return fallback

    def apply(self, tree):
        if 'insertion-width-dispatch' in self.options.disabled:
            return tree
        for consumer in tree.body:
            if not getattr(consumer, '_bcopt_fused_consumer', False):
                continue
            producers = [node for node in ast.walk(consumer) if isinstance(node, ast.For)
                         and getattr(node, '_bcopt_fused_insertion', None)]
            # Multiple sites can inflate each other's copies and write counts.
            if len(producers) != 1:
                continue
            producer = producers[0]
            replacement = self.specialize(consumer, producer)
            if replacement:
                class Replace(ast.NodeTransformer):
                    def visit_For(self, node):
                        return replacement if node is producer else self.generic_visit(node)
                Replace().visit(consumer)
        return ast.fix_missing_locations(tree)
