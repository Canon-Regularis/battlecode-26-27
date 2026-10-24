"""Reuse exact integer base reductions on certified insertion-cache misses.

The numeric emitter proves fixed integer fields and the original total extrema;
late checks require immutable snapshot roots, native index bounds and the intact
reduction/cache shapes. Only cache misses change. Original lookup/publication,
invalid-index fallback, and final reduction locals remain in place.
"""

import ast
import copy

from .base_edge_scalars import named, writes
from .model import Change
from .records import used_names
from .reduction_initializers import initialization_site


class BaseIntegerTotals:
    def __init__(self, options):
        self.options, self.changes = options, []
        self.taken = set()

    def fresh(self, stem):
        name = '_bcopt_base_total_'+stem
        while name in self.taken:
            name += '_'
        self.taken.add(name)
        return name

    def certify(self, loop, route, snapshots, tables):
        fields = getattr(loop, '_bcopt_integer_fields', None)
        extremum = getattr(loop, '_bcopt_integer_extremum', None)
        if (not getattr(loop, '_bcopt_integer_reductions', None) or not isinstance(fields, tuple)
                or not 2 <= len(fields) <= 4 or any(type(field) is not int for field in fields)
                or extremum not in {'min', 'max'} or not isinstance(loop, ast.For)
                or loop.orelse or not named(loop.iter, route) or not isinstance(loop.target, ast.Name)
                or len(loop.body) != len(fields)+3):
            return
        first, *tail = loop.body
        if (not isinstance(first, ast.Assign) or len(first.targets) != 1 or not isinstance(first.targets[0], ast.Name)
                or not isinstance(first.value, ast.Subscript) or not isinstance(first.value.value, ast.Name)
                or first.value.value.id not in snapshots or not named(first.value.slice, loop.target.id)):
            return
        row, data = first.targets[0].id, first.value.value.id
        sums = []
        for field, addition in zip(fields, tail):
            if (not isinstance(addition, ast.AugAssign) or not isinstance(addition.op, ast.Add)
                    or not isinstance(addition.target, ast.Name) or not isinstance(addition.value, ast.Subscript)
                    or not named(addition.value.value, row) or not isinstance(addition.value.slice, ast.Constant)
                    or type(addition.value.slice.value) is not int or addition.value.slice.value != field):
                return
            sums.append(addition.target.id)
        value, choose = tail[-2:]
        if (not isinstance(value, ast.Assign) or len(value.targets) != 1 or not isinstance(value.targets[0], ast.Name)
                or not isinstance(value.value, ast.Subscript) or not isinstance(value.value.value, ast.Name)
                or value.value.value.id not in tables or not named(value.value.slice, loop.target.id)
                or getattr(value.value, '_bcopt_prepared_lookup', None) != (1, 'int')
                or not isinstance(choose, ast.If) or choose.orelse or len(choose.body) != 1
                or not isinstance(choose.body[0], ast.Assign) or len(choose.body[0].targets) != 1
                or not isinstance(choose.body[0].targets[0], ast.Name)):
            return
        peak, best = value.targets[0].id, choose.body[0].targets[0].id
        operator = '>' if extremum == 'max' else '<'
        expected = ast.parse(f'if {best} is None or {peak} {operator} {best}:\n    {best} = {peak}').body[0]
        if ast.dump(choose) != ast.dump(expected):
            return
        names = (loop.target.id, row, *sums, peak, best)
        if len(set(names)) != len(names) or set(names) & {data, value.value.value.id, route}:
            return
        return data, value.value.value.id, fields, tuple(sums), loop.target.id, row, peak, best, operator

    def rewrite(self, branch, snapshots, tables, private_caches):
        width = branch._bcopt_width_specialization
        if not isinstance(branch, ast.If) or type(width) is not int or not 2 <= width <= 12:
            return
        producer = branch.body[-1]
        fact = getattr(producer, '_bcopt_fused_insertion', None)
        if not isinstance(producer, ast.For) or not fact or not named(producer.target, fact['item']):
            return
        unpack = branch.body[0]
        origin = getattr(unpack, '_bcopt_direct_base', None)
        if (not origin or origin[0] != fact['base'] or len(origin[1]) != width-1
                or not isinstance(unpack, ast.Assign) or len(unpack.targets) != 1
                or not isinstance(unpack.targets[0], ast.Tuple) or not named(unpack.value, fact['base'])
                or tuple(getattr(n, 'id', None) for n in unpack.targets[0].elts) != origin[1]
                or not isinstance(branch.test, ast.Compare) or not named(branch.test.left, fact['size'])
                or len(branch.test.ops) != 1 or not isinstance(branch.test.ops[0], ast.Eq)
                or len(branch.test.comparators) != 1 or not isinstance(branch.test.comparators[0], ast.Constant)
                or type(branch.test.comparators[0].value) is not int or branch.test.comparators[0].value != width):
            return
        bindings = writes(producer)
        if bindings[fact['base']] or bindings[fact['item']] != 1:
            return
        sites, signatures = [], set()
        for version in [n for n in ast.walk(producer) if getattr(n, '_bcopt_prepared_dispatch', False)]:
            region = ast.Module(body=version.body, type_ignores=[])
            groups = [n for n in ast.walk(region) if getattr(n, '_bcopt_group_reductions', False)]
            if len(groups) != 1 or not isinstance(groups[0], ast.If) or not groups[0].body:
                return
            group = groups[0]
            loop = group.body[0]
            signature = self.certify(loop, fact['route'], snapshots, tables)
            if signature is None:
                return
            data, peaks, fields, sums, index, row, peak, best, operator = signature
            region_bindings = writes(region)
            if any(region_bindings[name] != 3 for name in (*sums, best)):
                return
            # Existing reduction results must start at zero/None on every miss.
            inits = [n for n in ast.walk(region) if getattr(n, '_bcopt_group_init', False)]
            for name, initial in [*((name, 0) for name in sums), (best, None)]:
                found = [n for n in inits if isinstance(n, ast.Assign) and len(n.targets) == 1 and named(n.targets[0], name)]
                if (len(found) != 1 or not isinstance(found[0].value, ast.Constant)
                        or type(found[0].value.value) is not type(initial) or found[0].value.value != initial):
                    return
            if bindings[data] or bindings[peaks]:
                return
            sink = (initialization_site(region, group, (*sums, best), private_caches)
                    if 'insertion-sink-integer-initializers' not in self.options.disabled else None)
            sites.append((group, loop, sink))
            signatures.add(signature)
        if len(signatures) != 1 or not sites:
            return
        data, peaks, fields, sums, index, row, peak, best, operator = signatures.pop()
        names = {name: self.fresh(name) for name in ('valid', 'ready', 'n', 'index', 'row', 'value', 'peak')}
        totals = [self.fresh(f'sum_{i}') for i in range(len(sums))]
        n, base, item, b = names, fact['base'], fact['item'], self.builtins
        setup = ast.parse(f'{n["valid"]} = None\n{n["ready"]} = False').body
        branch.body[-1:-1] = setup
        for group, loop, sink in sites:
            lines = [f'if {n["valid"]} is None:', f'    {n["n"]} = {b}.len({data})',
                f'    {n["valid"]} = {b}.len({peaks}) == {n["n"]} and {b}.all(-{n["n"]} <= {n["index"]} < {n["n"]} for {n["index"]} in {base})',
                f'if {n["valid"]} and -{n["n"]} <= {item} < {n["n"]}:', f'    if not {n["ready"]}:']
            lines.extend(f'        {total} = 0' for total in totals)
            lines.extend([f'        {n["peak"]} = None', f'        for {n["index"]} in {base}:',
                          f'            {n["row"]} = {data}[{n["index"]}]'])
            lines.extend(f'            {total} += {n["row"]}[{field}]' for total, field in zip(totals, fields))
            lines.extend([f'            {n["value"]} = {peaks}[{n["index"]}]',
                f'            if {n["peak"]} is None or {n["value"]} {operator} {n["peak"]}:',
                f'                {n["peak"]} = {n["value"]}', f'        {n["ready"]} = True',
                f'    {n["row"]} = {data}[{item}]'])
            lines.extend(f'    {out} = {total} + {n["row"]}[{field}]' for out, total, field in zip(sums, totals, fields))
            lines.extend([f'    {n["value"]} = {peaks}[{item}]',
                f'    {best} = {n["value"]} if {n["value"]} {operator} {n["peak"]} else {n["peak"]}',
                f'    {index} = {fact["route"]}[-1]', f'    {row} = {data}[{index}]', f'    {peak} = {peaks}[{index}]',
                'else:', '    pass'])
            replacement = ast.parse('\n'.join(lines)).body
            replacement[-1].orelse = [loop]
            if sink is not None:
                sequence, initializers = sink
                replacement[-1].orelse[:0] = initializers
                for initializer in initializers:
                    sequence.remove(initializer)
                self.changes.append(Change('insertion-sink-integer-initializers', group.lineno,
                    'overwritten primitive reduction initializers',
                    'initializers retained only before the original fallback loop'))
            group.body[:1] = replacement
        return len(sites)

    def apply(self, tree):
        if 'insertion-base-integer-totals' in self.options.disabled:
            return tree
        self.taken = used_names(tree)
        self.builtins = self.fresh('builtins')
        for consumer in tree.body:
            if not getattr(consumer, '_bcopt_fused_consumer', False):
                continue
            bindings = writes(consumer)
            snapshots, tables, private_caches = set(), set(), set()
            for node in consumer.body:
                if not isinstance(node, ast.Assign) or not getattr(node, '_bcopt_snapshot_hoisted', False):
                    continue
                names = {n.id for target in node.targets for n in ast.walk(target) if isinstance(n, ast.Name)}
                names = {name for name in names if bindings[name] == 1}
                snapshots.update(names)
                if getattr(node, '_bcopt_prepared_table', False):
                    tables.update(names)
                if getattr(node, '_bcopt_private_integer_cache', False):
                    private_caches.update(names)
            owner = self
            class Rewrite(ast.NodeTransformer):
                def visit_If(self, node):
                    self.generic_visit(node)
                    if getattr(node, '_bcopt_width_specialization', None):
                        clone = copy.copy(node)
                        clone.body = copy.deepcopy(node.body)
                        count = owner.rewrite(clone, snapshots, tables, private_caches)
                        if count:
                            owner.changes.append(Change('insertion-base-integer-totals', node.lineno,
                                'full integer reductions on multiset-cache misses', f'{count} guarded base-local exact integer reductions'))
                            return clone
                    return node
            Rewrite().visit(consumer)
        if self.changes:
            index = 1 if tree.body and isinstance(tree.body[0], ast.Expr) else 0
            while index < len(tree.body) and isinstance(tree.body[index], ast.ImportFrom) and tree.body[index].module == '__future__':
                index += 1
            tree.body[index:index] = ast.parse(f'import builtins as {self.builtins}').body
        return ast.fix_missing_locations(tree)
