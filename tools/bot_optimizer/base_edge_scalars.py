"""Forward certified route slots and lazily reuse immutable base-edge values.

Only direct-tuple/unrolled-position and prepared ordered-fold emitter contracts
authorize this pass. Each cached table lookup is first executed at its original
point, and every numeric addition remains in source order. Cache slots reset per
base traversal; they hold only primitive snapshot values, never public records.
"""

import ast
from collections import Counter
import copy

from .model import Change
from .records import used_names


def named(node, value):
    return isinstance(node, ast.Name) and node.id == value


def writes(tree):
    return Counter(n.id for n in ast.walk(tree) if isinstance(n, ast.Name)
                   and isinstance(n.ctx, (ast.Store, ast.Del)))


class BaseEdgeScalars:
    def __init__(self, options):
        self.options, self.changes = options, []
        self.taken = set()

    def fresh(self):
        name = '_bcopt_base_edge'
        while name in self.taken:
            name += '_'
        self.taken.add(name)
        return name

    def rewrite(self, branch, tables):
        width = branch._bcopt_width_specialization
        if type(width) is not int or not 2 <= width <= 12 or len(branch.body) != 2:
            return
        unpack, producer = branch.body
        origin = getattr(unpack, '_bcopt_direct_base', None)
        fact = getattr(producer, '_bcopt_fused_insertion', None)
        if (not origin or not fact or not isinstance(producer, ast.For)
                or not isinstance(unpack, ast.Assign) or len(unpack.targets) != 1
                or not isinstance(unpack.targets[0], ast.Tuple)
                or not named(unpack.value, origin[0]) or origin[0] != fact['base']
                or tuple(getattr(n, 'id', None) for n in unpack.targets[0].elts) != origin[1]
                or len(origin[1]) != width-1 or len(set(origin[1])) != width-1
                or not named(producer.target, fact['item'])):
            return
        base = origin[1]
        bindings = writes(producer)
        if any(bindings[n] for n in base) or bindings[fact['item']] != 1:
            return
        wrappers = [n for n in ast.walk(producer) if getattr(n, '_bcopt_unrolled_position', None)]
        if len(wrappers) != width:
            return
        sites = []
        for position, wrapper in enumerate(wrappers):
            if (not isinstance(wrapper, ast.For) or wrapper.orelse or not wrapper.body
                    or wrapper._bcopt_unrolled_position != (width, position, fact['size'])):
                return
            route = wrapper.body[0]
            fields = (*base[:position], fact['item'], *base[position:])
            if (getattr(route, '_bcopt_direct_tuple', None) != (fact['route'], fact['item'], fields)
                    or not isinstance(route, ast.Assign) or len(route.targets) != 1
                    or not named(route.targets[0], fact['route']) or not isinstance(route.value, ast.Tuple)
                    or tuple(getattr(n, 'id', None) for n in route.value.elts) != fields
                    or writes(wrapper)[fact['route']] != 1):
                return
            versions = [n for n in ast.walk(wrapper) if getattr(n, '_bcopt_prepared_dispatch', False)]
            if len(versions) != 1 or not isinstance(versions[0], ast.If):
                return
            version = versions[0]
            region = ast.Module(body=version.body, type_ignores=[])
            ordered = [n for n in ast.walk(region) if getattr(n, '_bcopt_ordered_unpack', None)]
            if len(ordered) != 1:
                return
            ordered = ordered[0]
            route_name, aliases, table = ordered._bcopt_ordered_unpack
            if (route_name != fact['route'] or table not in tables or len(aliases) != width
                    or len(set(aliases)) != width or set(aliases) & set(fields)
                    or not isinstance(ordered, ast.Assign) or len(ordered.targets) != 1
                    or not isinstance(ordered.targets[0], ast.Tuple)
                    or tuple(getattr(n, 'id', None) for n in ordered.targets[0].elts) != aliases
                    or not named(ordered.value, route_name)):
                return
            region_writes = writes(region)
            if any(region_writes[n] != 1 for n in aliases):
                return
            updates = [n for n in ast.walk(region) if getattr(n, '_bcopt_ordered_update', None)]
            if len(updates) != width-1:
                return
            sequences = [value for parent in ast.walk(region) for _, value in ast.iter_fields(parent)
                         if isinstance(value, list) and ordered in value]
            if len(sequences) != 1:
                return
            sequence = sequences[0]
            start = sequence.index(ordered)
            block = sequence[start:start+width+1]
            if len(block) != width+1 or block[1:width] != updates:
                return
            tail = block[-1]
            if (not isinstance(tail, ast.Assign) or len(tail.targets) != 1
                    or not isinstance(tail.targets[0], ast.Tuple) or len(tail.targets[0].elts) != 2
                    or any(not isinstance(n, ast.Name) or n.id in aliases for n in tail.targets[0].elts)
                    or not isinstance(tail.value, ast.Tuple)
                    or tuple(getattr(n, 'id', None) for n in tail.value.elts) != aliases[-2:]):
                return
            allowed = {n for statement in block for n in ast.walk(statement)}
            if any(n not in allowed for n in ast.walk(wrapper) if isinstance(n, ast.Name) and n.id in aliases):
                return
            for update in updates:
                value = update.value if isinstance(update, ast.AugAssign) else None
                if (getattr(update, '_bcopt_ordered_update', None) != table
                        or not isinstance(update, ast.AugAssign) or not isinstance(update.op, ast.Add)
                        or not isinstance(update.target, ast.Name) or update.target.id in aliases
                        or not isinstance(value, ast.Subscript) or not isinstance(value.value, ast.Subscript)
                        or not named(value.value.value, table) or not isinstance(value.slice, ast.Name)
                        or not isinstance(value.value.slice, ast.Name)
                        or value.slice.id not in aliases or value.value.slice.id not in aliases):
                    return
            sites.append((version, ordered, dict(zip(aliases, fields)), fields, set(updates), table))
        slots = {}
        pairs = {(base[i], base[i+1]) for i in range(len(base)-1)}
        pairs |= {(b, a) for a, b in pairs}
        owner = self
        for version, ordered, aliases, fields, updates, table in sites:
            class Forward(ast.NodeTransformer):
                def visit_Assign(self, node):
                    return None if node is ordered else self.generic_visit(node)

                def visit_Name(self, node):
                    if isinstance(node.ctx, ast.Load) and node.id in aliases:
                        return ast.copy_location(ast.Name(id=aliases[node.id], ctx=ast.Load()), node)
                    return node

                def visit_Subscript(self, node):
                    self.generic_visit(node)
                    if named(node.value, fact['route']) and isinstance(node.ctx, ast.Load):
                        try:
                            index = ast.literal_eval(node.slice)
                        except (ValueError, TypeError):
                            return node
                        if type(index) is int and -width <= index < width:
                            return ast.copy_location(ast.Name(id=fields[index], ctx=ast.Load()), node)
                    return node

                def visit_AugAssign(self, node):
                    self.generic_visit(node)
                    if node in updates:
                        lookup = node.value
                        pair = lookup.value.slice.id, lookup.slice.id
                        if pair in pairs:
                            key = table, *pair
                            if key not in slots:
                                slots[key] = owner.fresh()
                            slot = slots[key]
                            guard = ast.parse(f'if {slot} is None:\n    {slot} = None').body[0]
                            guard.body[0].value = lookup
                            guard._bcopt_base_edge_guard = (slot, table, *pair)
                            node.value = ast.Name(id=slot, ctx=ast.Load())
                            return [guard, node]
                    return node
            # Do not visit the nonprepared dispatch fallback.
            region = Forward().visit(ast.Module(body=version.body, type_ignores=[]))
            version.body = region.body
            version._bcopt_base_prefix_site = (fact['route'], fact['item'], base, fields)
        branch.body[1:1] = [ast.Assign(targets=[ast.Name(id=slot, ctx=ast.Store())], value=ast.Constant(None))
                            for slot in slots.values()]
        branch._bcopt_base_edge_slots = {slot: key for key, slot in slots.items()}
        return len(sites), len(slots)

    def apply(self, tree):
        if 'insertion-base-edge-scalars' in self.options.disabled:
            return tree
        self.taken = used_names(tree)
        for consumer in tree.body:
            if not getattr(consumer, '_bcopt_fused_consumer', False):
                continue
            bindings = writes(consumer)
            tables = {n.targets[0].id for n in consumer.body if isinstance(n, ast.Assign)
                      and getattr(n, '_bcopt_prepared_table', False) and getattr(n, '_bcopt_snapshot_hoisted', False)
                      and len(n.targets) == 1 and isinstance(n.targets[0], ast.Name) and bindings[n.targets[0].id] == 1}
            owner = self
            class Rewrite(ast.NodeTransformer):
                def visit_If(self, node):
                    self.generic_visit(node)
                    if getattr(node, '_bcopt_width_specialization', None):
                        # Only this arm changes. Copying the entire orelse width
                        # chain here would repeatedly copy already-verified arms.
                        clone = copy.copy(node)
                        clone.body = copy.deepcopy(node.body)
                        result = owner.rewrite(clone, tables)
                        if result:
                            owner.changes.append(Change('insertion-base-edge-scalars', node.lineno,
                                'repeated route unpack and immutable table loads',
                                f'{result[0]} scalar-forwarded positions and {result[1]} lazy base-edge slots'))
                            return clone
                    return node
            Rewrite().visit(consumer)
        return ast.fix_missing_locations(tree)
