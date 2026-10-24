"""Reuse lazy sequential prefixes whose complete dependencies are base-invariant.

The first prefix runs at its original point with unchanged addition order. A
later insertion can reuse it only in the same base traversal and only when all
table/index dependencies are immutable emitter-proven primitives. End insertions
and inserted-item-dependent initial accumulators do not qualify.
"""

import ast
import copy

from .base_edge_scalars import named, writes
from .model import Change
from .records import used_names


class BasePrefixScalars:
    def __init__(self, options):
        self.options, self.changes = options, []
        self.taken = set()

    def fresh(self):
        name = '_bcopt_base_prefix'
        while name in self.taken:
            name += '_'
        self.taken.add(name)
        return name

    @staticmethod
    def lookup(node, base, bindings, tables):
        contract = getattr(node, '_bcopt_prepared_lookup', None)
        if not contract or contract[1] not in {'int', 'float', 'number'}:
            return False
        indices = []
        root = node
        while isinstance(root, ast.Subscript) and isinstance(root.ctx, ast.Load):
            indices.append(root.slice)
            root = root.value
        if not isinstance(root, ast.Name) or root.id not in tables or len(indices) != contract[0]:
            return False
        for index in indices:
            if isinstance(index, ast.Constant) and type(index.value) is int:
                continue
            if not isinstance(index, ast.Name):
                return False
            if index.id in base:
                continue
            if not getattr(index, '_bcopt_prepared_integer_index', False) or bindings[index.id]:
                return False
        return True

    def rewrite(self, version, producer, slots, tables):
        route, item, base, fields = version._bcopt_base_prefix_site
        if (not isinstance(version, ast.If) or not getattr(version, '_bcopt_prepared_dispatch', False)
                or len(fields) != len(base)+1 or fields.count(item) != 1 or item in base
                or fields[0] == item or fields[-1] == item):
            return
        bindings = writes(producer)
        if any(bindings[name] for name in base):
            return
        region = ast.Module(body=version.body, type_ignores=[])
        updates = [n for n in ast.walk(region) if getattr(n, '_bcopt_ordered_update', None)]
        if not updates or not all(isinstance(n, ast.AugAssign) and isinstance(n.target, ast.Name) for n in updates):
            return
        accumulator = updates[0].target.id
        if any(n.target.id != accumulator or not isinstance(n.op, ast.Add) for n in updates):
            return
        sequences = [value for parent in ast.walk(region) for _, value in ast.iter_fields(parent)
                     if isinstance(value, list) and updates[0] in value]
        if len(sequences) != 1:
            return
        sequence = sequences[0]
        first = sequence.index(updates[0])
        starts = [i for i, n in enumerate(sequence[:first]) if isinstance(n, ast.Assign)
                  and len(n.targets) == 1 and named(n.targets[0], accumulator)]
        if len(starts) != 1:
            return
        start = starts[0]
        if not self.lookup(sequence[start].value, base, bindings, tables):
            return
        end, additions, repeats, guard_slots = start+1, 0, [], set()
        while end < len(sequence):
            node = sequence[end]
            if isinstance(node, ast.AugAssign) and named(node.target, accumulator) and isinstance(node.op, ast.Add):
                if self.lookup(node.value, base, bindings, tables):
                    pass
                elif isinstance(node.value, ast.Name) and node.value.id in guard_slots:
                    pass
                else:
                    break
                additions += 1
            elif isinstance(node, ast.If) and getattr(node, '_bcopt_base_edge_guard', None):
                slot, table, a, b = node._bcopt_base_edge_guard
                expected = ast.parse(f'if {slot} is None:\n    {slot} = {table}[{a}][{b}]').body[0]
                if (slots.get(slot) != (table, a, b) or a not in base or b not in base
                        or ast.dump(node) != ast.dump(expected)
                        or not self.lookup(node.body[0].value, base, bindings, tables)):
                    return
                guard_slots.add(slot)
            elif (isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name)
                  and isinstance(node.value, ast.Constant) and type(node.value.value) is int
                  and node.targets[0].id not in {accumulator, item, route, *base}):
                # Width-local housekeeping remains assigned on hits too.
                repeats.append(copy.deepcopy(node))
            else:
                return
            end += 1
        if (not additions or end == len(sequence) or sequence[end] not in updates
                or not any(named(n, item) for n in ast.walk(sequence[end].value))):
            return
        # No cached-slot assignment may differ from its emitted immutable lookup.
        for slot in guard_slots:
            expected = ast.parse(f'{slots[slot][0]}[{slots[slot][1]}][{slots[slot][2]}]', mode='eval').body
            assignments = [n for n in ast.walk(producer) if isinstance(n, ast.Assign)
                           and any(named(t, slot) for t in n.targets)]
            if not assignments or any(ast.dump(n.value) != ast.dump(expected) for n in assignments):
                return
        saved = self.fresh()
        guard = ast.parse(f'if {saved} is None:\n    pass\nelse:\n    {accumulator} = {saved}').body[0]
        guard.body = [*sequence[start:end], *ast.parse(f'{saved} = {accumulator}').body]
        guard.orelse = [*repeats, *guard.orelse]
        sequence[start:end] = [guard]
        return saved

    def apply(self, tree):
        if 'insertion-base-prefix-scalars' in self.options.disabled:
            return tree
        self.taken = used_names(tree)
        for consumer in tree.body:
            if not getattr(consumer, '_bcopt_fused_consumer', False):
                continue
            bindings = writes(consumer)
            tables = {n.targets[0].id for n in consumer.body if isinstance(n, ast.Assign)
                      and getattr(n, '_bcopt_prepared_table', False) and getattr(n, '_bcopt_snapshot_hoisted', False)
                      and len(n.targets) == 1 and isinstance(n.targets[0], ast.Name) and bindings[n.targets[0].id] == 1}
            for branch in list(ast.walk(consumer)):
                slots = getattr(branch, '_bcopt_base_edge_slots', None)
                if slots is None or not isinstance(branch, ast.If):
                    continue
                producer = branch.body[-1]
                if not isinstance(producer, ast.For) or not getattr(producer, '_bcopt_fused_insertion', None):
                    continue
                # The preceding emitter owns slot initialization for this base.
                if any(not any(isinstance(n, ast.Assign) and len(n.targets) == 1 and named(n.targets[0], slot)
                               and isinstance(n.value, ast.Constant) and n.value.value is None
                               for n in branch.body[:-1]) for slot in slots):
                    continue
                versions = [n for n in ast.walk(producer) if getattr(n, '_bcopt_base_prefix_site', None)]
                for version in versions:
                    saved = self.rewrite(version, producer, slots, tables)
                    if saved:
                        branch.body.insert(-1, ast.parse(f'{saved} = None').body[0])
                        self.changes.append(Change('insertion-base-prefix-scalars', version.lineno,
                            'repeated base-invariant sequential prefix', 'lazy base-local prefix with unchanged first-use arithmetic'))
        return ast.fix_missing_locations(tree)
