"""Retain integer edges already read by a certified lazy base-tour total.

Width/position and integer-edge emitter contracts must still match the entire
fast block. Cached slots are assigned at the original first base calculation;
the certified immutable tables and in-range indices make subsequent reuse total.
Original guarded fallback and final pair-loop locals are preserved.
"""

import ast

from .base_edge_scalars import named, writes
from .model import Change
from .records import used_names


class RetainedIntegerEdges:
    def __init__(self, options):
        self.options, self.changes = options, []

    def fresh(self, stem):
        name = '_bcopt_retained_edge_'+stem
        while name in self.taken:
            name += '_'
        self.taken.add(name)
        return name

    def rewrite(self, branch, stable, resets):
        width = branch._bcopt_width_specialization
        if type(width) is not int or not 2 <= width <= 12:
            return
        unpack, producer = branch.body[0], branch.body[-1]
        origin = getattr(unpack, '_bcopt_direct_base', None)
        fact = getattr(producer, '_bcopt_fused_insertion', None)
        if (not origin or not fact or not isinstance(producer, ast.For)
                or origin[0] != fact['base'] or len(origin[1]) != width-1
                or not isinstance(unpack, ast.Assign) or len(unpack.targets) != 1
                or not isinstance(unpack.targets[0], ast.Tuple) or not named(unpack.value, fact['base'])
                or tuple(getattr(n, 'id', None) for n in unpack.targets[0].elts) != origin[1]
                or not named(producer.target, fact['item'])):
            return
        base = origin[1]
        bindings = writes(producer)
        if any(bindings[n] for n in (*base, fact['base'])) or bindings[fact['item']] != 1:
            return
        wrappers = [n for n in ast.walk(producer) if getattr(n, '_bcopt_unrolled_position', None)]
        if len(wrappers) != width:
            return
        sites = []
        for position, wrapper in enumerate(wrappers):
            if wrapper._bcopt_unrolled_position != (width, position, fact['size']):
                return
            versions = [n for n in ast.walk(wrapper) if getattr(n, '_bcopt_prepared_dispatch', False)]
            if len(versions) != 1:
                return
            region = ast.Module(body=versions[0].body, type_ignores=[])
            candidates = [n for n in ast.walk(region) if getattr(n, '_bcopt_integer_edge_fast', None)]
            if len(candidates) != 1:
                return
            fast = candidates[0]
            f = fast._bcopt_integer_edge_fast
            if any(f[key] != fact[key] for key in fact) or {f['terminals'], f['matrix']} - stable:
                return
            axis = ast.parse(f['axis'], mode='eval').body
            if not isinstance(axis, (ast.Name, ast.Constant)) or isinstance(axis, ast.Name) and bindings[axis.id]:
                return
            total, a, z, b = f['base_total'], f['a'], f['z'], f['builtins']
            route, item, first, result, matrix = f['base'], f['item'], f['first'], f['total'], f['matrix']
            terminal = f"{f['terminals']}[{f['axis']}]"
            fields = (*base[:position], item, *base[position:])
            if {total, f['valid']} - resets:
                return
            sequences = [body for parent in ast.walk(region) for _, body in ast.iter_fields(parent)
                         if isinstance(body, list) and fast in body]
            if len(sequences) != 1:
                return
            sequence = sequences[0]
            index = sequence.index(fast)
            checks = ast.parse(f'''if {f['valid']} is None:
    {f['valid']} = {f['cert']} and True and (0 <= {f['axis']} < {b}.len({f['terminals']})) and {b}.all(-{f['n']} <= {f['check_item']} < {f['n']} for {f['check_item']} in {route})
{f['fast']} = {f['valid']} and -{f['n']} <= {item} < {f['n']}
''')
            if index < 2 or ast.dump(ast.Module(body=sequence[index-2:index], type_ignores=[])) != ast.dump(checks):
                return
            expected = f'''if {total} is None:
    {total} = {terminal}[{route}[0]] + {terminal}[{route}[-1]]
    for {a}, {z} in {b}.zip({route}, {route}[1:]):
        {total} += {matrix}[{a}][{z}]
{first} = {terminal}[{fields[0]}]
'''
            if position == 0:
                expected += f'{result} = {total} - {terminal}[{route}[0]] + {first} + {matrix}[{item}][{route}[0]]'
            elif position == width-1:
                expected += f'{result} = {total} - {terminal}[{route}[-1]] + {terminal}[{item}] + {matrix}[{route}[-1]][{item}]'
            else:
                expected += f'{a}, {z} = {route}[{position-1}], {route}[{position}]\n'
                expected += f'{result} = {total} - {matrix}[{a}][{z}] + {matrix}[{a}][{item}] + {matrix}[{item}][{z}]'
            if (not isinstance(fast, ast.If) or not named(fast.test, f['fast'])
                    or ast.dump(ast.Module(body=fast.body, type_ignores=[])) != ast.dump(ast.parse(expected))):
                return
            # No other write may invalidate the lazy-total/retained-slot epoch.
            if bindings[total] != 2*width:
                return
            sites.append((fast, f, position))
        first_slot, last_slot = self.fresh('first'), self.fresh('last')
        slots = [self.fresh(str(i)) for i in range(width-2)]
        for fast, f, position in sites:
            initialize = fast.body[0]
            original, loop = initialize.body
            total, matrix, a, z = f['base_total'], f['matrix'], f['a'], f['z']
            setup = ast.parse(f'{first_slot} = None\n{last_slot} = None\n{total} = {first_slot} + {last_slot}').body
            setup[0].value, setup[1].value = original.value.left, original.value.right
            for i, slot in enumerate(slots):
                setup.extend(ast.parse(f'{slot} = {matrix}[{base[i]}][{base[i+1]}]\n{total} += {slot}').body)
            if slots:
                setup.extend(ast.parse(f'{a}, {z} = {base[-2]}, {base[-1]}').body)
            initialize.body = setup
            terminal = f"{f['terminals']}[{f['axis']}]"
            mapping = {f'{terminal}[{f["base"]}[0]]': first_slot,
                       f'{terminal}[{f["base"]}[-1]]': last_slot,
                       f'{terminal}[{base[0]}]': first_slot}
            if 0 < position < width-1:
                mapping[f'{matrix}[{a}][{z}]'] = slots[position-1]
            replacements = {ast.dump(ast.parse(expr, mode='eval').body): slot for expr, slot in mapping.items()}
            class Reuse(ast.NodeTransformer):
                def visit_Subscript(self, node):
                    key = ast.dump(node)
                    return ast.Name(id=replacements[key], ctx=ast.Load()) if key in replacements else self.generic_visit(node)
            fast.body[1:] = Reuse().visit(ast.Module(body=fast.body[1:], type_ignores=[])).body
        return len(sites)

    def apply(self, tree):
        if 'insertion-retained-integer-edges' in self.options.disabled:
            return tree
        self.taken = used_names(tree)
        for consumer in tree.body:
            if not getattr(consumer, '_bcopt_fused_consumer', False):
                continue
            bindings = writes(consumer)
            stable = {part.id for node in consumer.body if isinstance(node, ast.Assign)
                      and getattr(node, '_bcopt_snapshot_hoisted', False)
                      for target in node.targets for part in ast.walk(target)
                      if isinstance(part, ast.Name) and bindings[part.id] == 1}
            parents = {child: parent for parent in ast.walk(consumer) for child in ast.iter_child_nodes(parent)}
            for branch in list(ast.walk(consumer)):
                if isinstance(branch, ast.If) and getattr(branch, '_bcopt_width_specialization', None):
                    top = branch
                    while getattr(parents.get(top), '_bcopt_width_specialization', None):
                        top = parents[top]
                    sequences = [body for _, body in ast.iter_fields(parents[top])
                                 if isinstance(body, list) and top in body]
                    if len(sequences) != 1:
                        continue
                    sequence = sequences[0]
                    index = sequence.index(top)
                    resets = {n.targets[0].id for n in sequence[max(0, index-2):index]
                              if isinstance(n, ast.Assign) and len(n.targets) == 1 and isinstance(n.targets[0], ast.Name)
                              and isinstance(n.value, ast.Constant) and n.value.value is None}
                    count = self.rewrite(branch, stable, resets)
                    if count:
                        self.changes.append(Change('insertion-retained-integer-edges', branch.lineno,
                            'repeated immutable base integer edge reads', f'{count} positions reuse first-read base integer edges'))
        return ast.fix_missing_locations(tree)
