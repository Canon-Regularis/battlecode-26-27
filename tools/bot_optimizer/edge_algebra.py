"""Exact insertion-tour totals for certified private integer edge sequences.

Emitter-owned insertion and immutable-snapshot facts authorize algebra only after
a bounded runtime nonnegative-table certificate and per-base index checks. The
base total is computed lazily at the original edge evaluation point. Original
rolling lists remain the fallback for rejected certificates and invalid indices.
"""

import ast
from collections import Counter
import copy

from .model import Change
from .records import used_names


class EdgeAlgebra:
    def __init__(self, options):
        self.options, self.changes = options, []
        self.taken = set()

    def fresh(self, stem):
        name = '_bcopt_algebra_'+stem
        while name in self.taken:
            name += '_'
        self.taken.add(name)
        return name

    def rewrite(self, consumer, producer, stable):
        insertion = producer._bcopt_fused_insertion
        if set(insertion) != {'base', 'item', 'position', 'route', 'size'}:
            return
        parents = {child: parent for parent in ast.walk(producer) for child in ast.iter_child_nodes(parent)}
        updates = [node for node in ast.walk(producer) if getattr(node, '_bcopt_edge_algebra', None)]
        candidates = []
        for update in updates:
            parent = parents[update]
            while parent is not producer:
                if getattr(parent, '_bcopt_prepared_dispatch', False):
                    if update in {part for node in parent.body for part in ast.walk(node)}:
                        candidates.append((update, parent))
                    break
                parent = parents[parent]
        if len(candidates) != 1:
            return
        update, version = candidates[0]
        fact = update._bcopt_edge_algebra
        if set(fact) != {'route', 'position', 'legs', 'terminals', 'matrix', 'axis'}:
            return
        if (fact['route'] != insertion['route'] or fact['position'] != insertion['position']
                or {fact['terminals'], fact['matrix']} - stable):
            return
        axis = ast.parse(fact['axis'], mode='eval').body
        if not isinstance(axis, (ast.Name, ast.Constant)):
            return
        if isinstance(axis, ast.Name) and any(isinstance(node, ast.Name) and node.id == axis.id
                and isinstance(node.ctx, (ast.Store, ast.Del)) for node in ast.walk(producer)):
            return
        if len(version.body) != 1 or not isinstance(version.body[0], ast.Try):
            return
        protected = version.body[0]
        if update not in protected.body:
            return
        index = protected.body.index(update)
        if not index or not getattr(protected.body[index-1], '_bcopt_edge_cache_read', False):
            return
        read = protected.body[index-1]
        # Verify the original emitter-owned list construction still agrees with
        # the algebra contract. This also rejects context-changing edge caches.
        if (not isinstance(update, ast.If) or not isinstance(update.test, ast.BoolOp)
                or len(update.test.values) != 2 or len(update.body) != 3
                or not getattr(update.body[0], '_bcopt_incremental_edges', False)
                or not getattr(update.body[1], '_bcopt_incremental_extension', False)):
            return
        binding, extension = update.body[:2]
        legs = fact['legs']
        if (len(binding.targets) != 1 or not isinstance(binding.targets[0], ast.Name)
                or binding.targets[0].id != legs or not isinstance(binding.value, ast.List)
                or len(binding.value.elts) != 2 or not isinstance(extension.value, ast.Call)
                or len(extension.value.args) != 1 or not isinstance(extension.value.args[0], ast.ListComp)):
            return
        first, last = binding.value.elts
        comp = extension.value.args[0]
        for endpoint in (first, last):
            if (not isinstance(endpoint, ast.Subscript) or not isinstance(endpoint.value, ast.Subscript)
                    or not isinstance(endpoint.value.value, ast.Name) or endpoint.value.value.id != fact['terminals']
                    or ast.dump(endpoint.value.slice) != ast.dump(axis)):
                return
        if (not isinstance(comp.elt, ast.Subscript) or not isinstance(comp.elt.value, ast.Subscript)
                or not isinstance(comp.elt.value.value, ast.Name) or comp.elt.value.value.id != fact['matrix']):
            return
        ignored = set(ast.walk(update)) | set(ast.walk(read))
        sums, firsts, rejects, allowed = [], [], [], set()
        for node in ast.walk(protected):
            if node in ignored:
                continue
            if (isinstance(node, ast.Call) and getattr(node, '_bcopt_numeric_native', None) == 'sum'
                    and len(node.args) == 1 and not node.keywords and isinstance(node.args[0], ast.Name)
                    and node.args[0].id == legs):
                sums.append(node)
                allowed.add(node.args[0])
            if (isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name) and node.value.id == legs
                    and isinstance(node.ctx, ast.Load) and isinstance(node.slice, ast.Constant)
                    and type(node.slice.value) is int and node.slice.value == 0):
                firsts.append(node)
                allowed.add(node.value)
            if (isinstance(node, ast.IfExp) and getattr(node, '_bcopt_numeric_native', None) == 'any'
                    and isinstance(node.test, ast.Name) and node.test.id == legs
                    and isinstance(node.orelse, ast.Constant) and node.orelse.value is False
                    and isinstance(node.body, ast.Compare) and len(node.body.ops) == 1
                    and isinstance(node.body.ops[0], ast.Lt) and len(node.body.comparators) == 1
                    and isinstance(node.body.comparators[0], ast.Constant) and type(node.body.comparators[0].value) is int
                    and node.body.comparators[0].value == 0 and isinstance(node.body.left, ast.Call)
                    and not node.body.left.keywords and len(node.body.left.args) == 1
                    and isinstance(node.body.left.args[0], ast.Name) and node.body.left.args[0].id == legs):
                rejects.append(node)
                allowed.update((node.test, node.body.left.args[0]))
        if (not sums or not rejects or any(node not in allowed | ignored for node in ast.walk(version.body[0])
                if isinstance(node, ast.Name) and node.id == legs)):
            return
        # No list reads outside this protected region in the prepared branch.
        if any(node not in set(ast.walk(protected)) for statement in version.body for node in ast.walk(statement)
               if isinstance(node, ast.Name) and node.id == legs):
            return
        names = {stem: self.fresh(stem) for stem in ('cert', 'n', 'valid', 'base_total', 'fast', 'first', 'total', 'a', 'z', 'item')}
        names.update(insertion)
        names.update(fact)
        b = self.builtins
        n, cert = names['n'], names['cert']
        trusted = (getattr(binding, '_bcopt_edge_integer_tables', False)
                   and 'insertion-edge-native-certificate' not in self.options.disabled)
        setup = ast.parse(f"{n} = {b}.len({fact['matrix']})\n{cert} = {self.certify}({fact['matrix']}, {fact['terminals']}, {trusted!r})").body
        initialize = ast.parse(f"{names['valid']} = None\n{names['base_total']} = None").body
        # Every interpolation is an emitter-owned identifier or checked scalar
        # axis expression. No input-source spelling authorizes this transform.
        base, item, position, route, size = (names[key] for key in ('base', 'item', 'position', 'route', 'size'))
        matrix, terminal = fact['matrix'], f"{fact['terminals']}[{fact['axis']}]"
        valid, total0, fast, first0, total, a, z = (names[key] for key in ('valid', 'base_total', 'fast', 'first', 'total', 'a', 'z'))
        check_item = self.fresh('index')
        text = f'''
if {valid} is None:
    {valid} = ({cert} and {size} > 1 and 0 <= {fact['axis']} < {b}.len({fact['terminals']})
        and {b}.all(-{n} <= {check_item} < {n} for {check_item} in {base}))
{fast} = {valid} and -{n} <= {item} < {n}
if {fast}:
    if {total0} is None:
        {total0} = {terminal}[{base}[0]] + {terminal}[{base}[-1]]
        for {a}, {z} in {b}.zip({base}, {base}[1:]):
            {total0} += {matrix}[{a}][{z}]
    {first0} = {terminal}[{route}[0]]
    if {position} == 0:
        {total} = {total0} - {terminal}[{base}[0]] + {first0} + {matrix}[{item}][{base}[0]]
    elif {position} == {size} - 1:
        {total} = {total0} - {terminal}[{base}[-1]] + {terminal}[{item}] + {matrix}[{base}[-1]][{item}]
    else:
        {a}, {z} = {base}[{position}-1], {base}[{position}]
        {total} = {total0} - {matrix}[{a}][{z}] + {matrix}[{a}][{item}] + {matrix}[{item}][{z}]
else:
    pass
'''
        replacement = ast.parse(text).body
        replacement[-1]._bcopt_integer_edge_fast = dict(names, builtins=b, check_item=check_item)
        replacement[-1].orelse = [read, update]
        replacements = {node: ast.IfExp(test=ast.Name(id=fast, ctx=ast.Load()),
            body=ast.Name(id=total if node in sums else first0, ctx=ast.Load()), orelse=node) for node in [*sums, *firsts]}
        replacements.update({node: ast.BoolOp(op=ast.And(), values=[ast.UnaryOp(op=ast.Not(), operand=ast.Name(id=fast, ctx=ast.Load())), node]) for node in rejects})
        class Reads(ast.NodeTransformer):
            def visit(self, node):
                return replacements[node] if node in replacements else super().visit(node)
        Reads().visit(protected)
        protected.body[index-1:index+1] = replacement
        producer._bcopt_edge_algebra_init = initialize
        self.changes.append(Change('insertion-edge-algebra', update.lineno,
            'private integer edge materialization and scans', 'certified nonnegative insertion-tour algebra with lazy base total'))
        if trusted:
            self.changes.append(Change('insertion-edge-native-certificate', update.lineno,
                'per-element snapshot validation', 'native minima on emitter-proven homogeneous integer tables'))
        return setup

    def apply(self, tree):
        if 'insertion-edge-algebra' in self.options.disabled:
            return tree
        self.taken = used_names(tree)
        self.builtins, self.certify = self.fresh('builtins'), self.fresh('certify')
        for consumer in tree.body:
            if not getattr(consumer, '_bcopt_fused_consumer', False):
                continue
            writes = Counter(node.id for node in ast.walk(consumer) if isinstance(node, ast.Name)
                             and isinstance(node.ctx, (ast.Store, ast.Del)))
            stable = {part.id for node in consumer.body if isinstance(node, ast.Assign)
                      and getattr(node, '_bcopt_snapshot_hoisted', False)
                      for target in node.targets for part in ast.walk(target)
                      if isinstance(part, ast.Name) and writes[part.id] == 1}
            setups = []
            for producer in list(ast.walk(consumer)):
                if isinstance(producer, ast.For) and getattr(producer, '_bcopt_fused_insertion', None):
                    setup = self.rewrite(consumer, producer, stable)
                    if setup:
                        setups.extend(setup)
            if setups:
                index = max(i for i, node in enumerate(consumer.body) if getattr(node, '_bcopt_snapshot_hoisted', False)) + 1
                consumer.body[index:index] = setups
                class Initialize(ast.NodeTransformer):
                    def visit_For(self, node):
                        self.generic_visit(node)
                        init = getattr(node, '_bcopt_edge_algebra_init', None)
                        return [*init, node] if init else node
                Initialize().visit(consumer)
        if self.changes:
            b = self.builtins
            helper = ast.parse(f'''
import builtins as {b}
def {self.certify}(matrix, terminals, trusted=False):
    if {b}.type(matrix) is not {b}.tuple or {b}.type(terminals) is not {b}.tuple:
        return False
    size = {b}.len(matrix)
    if not 0 < size <= 64:
        return False
    count = 0
    for table in (matrix, terminals):
        for row in table:
            if {b}.type(row) is not {b}.tuple or {b}.len(row) < size:
                return False
            count += {b}.len(row)
            if count > 4096 or ({b}.min(row) < 0 if trusted else not {b}.all({b}.type(value) is {b}.int and value >= 0 for value in row)):
                return False
    return True
''').body
            index = 1 if tree.body and isinstance(tree.body[0], ast.Expr) and isinstance(tree.body[0].value, ast.Constant) else 0
            while index < len(tree.body) and isinstance(tree.body[index], ast.ImportFrom) and tree.body[index].module == '__future__':
                index += 1
            tree.body[index:index] = helper
        return ast.fix_missing_locations(tree)
