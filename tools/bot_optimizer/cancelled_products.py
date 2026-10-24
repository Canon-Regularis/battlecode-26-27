"""Cache invariant products after certified exact-integer cancellation.

For integer (a+b-c)*d, object identity b is c proves exact cancellation to a*d.
Only emitter-certified insertion-group scalar a and immutable snapshot factor d
qualify. The first multiplication stays at its original point; nonidentical
operands retain the original expression, including every floating operation.
"""

import ast
import copy

from .base_edge_scalars import named, writes
from .model import Change
from .records import used_names


class CancelledProducts:
    def __init__(self, options):
        self.options, self.changes = options, []

    def apply(self, tree):
        if 'insertion-cancelled-products' in self.options.disabled:
            return tree
        taken = used_names(tree)
        for consumer in tree.body:
            if not getattr(consumer, '_bcopt_fused_consumer', False):
                continue
            bindings = writes(consumer)
            snapshots = {part.id for node in consumer.body if isinstance(node, ast.Assign)
                         and getattr(node, '_bcopt_snapshot_hoisted', False)
                         for target in node.targets for part in ast.walk(target)
                         if isinstance(part, ast.Name) and bindings[part.id] == 1}
            for producer in [n for n in ast.walk(consumer) if isinstance(n, ast.For)
                             and getattr(n, '_bcopt_fused_insertion', None)]:
                local_writes = writes(producer)
                def invariant_projection(node):
                    if isinstance(node, ast.Name):
                        return node.id in snapshots
                    if not isinstance(node, ast.Subscript) or not invariant_projection(node.value):
                        return False
                    index = node.slice
                    return (isinstance(index, ast.Constant) and type(index.value) is int
                            or isinstance(index, ast.Name) and not local_writes[index.id])
                for version in [n for n in ast.walk(producer) if getattr(n, '_bcopt_prepared_dispatch', False)]:
                    region = ast.Module(body=version.body, type_ignores=[])
                    region_writes = writes(region)
                    parents = {child: parent for parent in ast.walk(region) for child in ast.iter_child_nodes(parent)}
                    for update in [n for n in ast.walk(region) if isinstance(n, ast.AugAssign)
                                   and getattr(n.value, '_bcopt_integer_cancel_product', False)]:
                        product = update.value
                        if (not isinstance(update.target, ast.Name) or not isinstance(update.op, ast.Add)
                                or not isinstance(product, ast.BinOp) or not isinstance(product.op, ast.Mult)
                                or not isinstance(product.left, ast.BinOp) or not isinstance(product.left.op, ast.Sub)
                                or not isinstance(product.left.left, ast.BinOp) or not isinstance(product.left.left.op, ast.Add)):
                            continue
                        a, b, c, d = product.left.left.left, product.left.left.right, product.left.right, product.right
                        if not all(isinstance(n, ast.Name) for n in (a, b, c, d)):
                            continue
                        reads = [n for n in ast.walk(region) if isinstance(n, ast.Assign)
                                 and a.id in getattr(n, '_bcopt_resident_scalar_outputs', ())]
                        if len(reads) != 1 or not isinstance(reads[0].value, ast.Name):
                            continue
                        cache = reads[0].value.id
                        initializers = [n for n in producer.body if isinstance(n, ast.Assign)
                                        and getattr(n, '_bcopt_scalar_cache_init', False)
                                        and any(named(t, cache) for t in n.targets)
                                        and isinstance(n.value, ast.Constant) and n.value.value is None]
                        if len(initializers) != 1:
                            continue
                        assignments = [n for n in ast.walk(region) if isinstance(n, ast.Assign)
                                       and len(n.targets) == 1 and named(n.targets[0], d.id)]
                        if (len(assignments) != 1 or region_writes[d.id] != 1
                                or not invariant_projection(assignments[0].value)):
                            continue
                        # Recheck the resident scalar's writes remain inside its
                        # emitter-owned miss regions, including their publication.
                        guarded = {n for guard in ast.walk(region) if isinstance(guard, ast.If)
                                   and getattr(guard, '_bcopt_group_scalar_miss', False)
                                   for statement in guard.body for n in ast.walk(statement)}
                        if any(n not in guarded for n in ast.walk(region) if named(n, a.id)
                               and isinstance(n.ctx, (ast.Store, ast.Del))):
                            continue
                        # The factor's binding must precede the product in the
                        # same straight-line block; no effectful joins qualify.
                        parent = parents[update]
                        sequences = [value for _, value in ast.iter_fields(parent)
                                     if isinstance(value, list) and update in value and assignments[0] in value]
                        if len(sequences) != 1 or sequences[0].index(assignments[0]) >= sequences[0].index(update):
                            continue
                        slot = '_bcopt_cancelled_product'
                        while slot in taken:
                            slot += '_'
                        taken.add(slot)
                        init = ast.parse(f'{slot} = None').body[0]
                        producer.body.insert(producer.body.index(initializers[0])+1, init)
                        replacement = ast.parse(f'''if {b.id} is {c.id}:
    if {slot} is None:
        {slot} = {a.id} * {d.id}
    {update.target.id} += {slot}
else:
    pass
''').body[0]
                        replacement.orelse = [copy.deepcopy(update)]
                        sequence = sequences[0]
                        sequence[sequence.index(update)] = replacement
                        self.changes.append(Change('insertion-cancelled-products', update.lineno,
                            'integer cancellation followed by repeated invariant product',
                            'identity-guarded exact cancellation with lazy group-local multiplication'))
        return ast.fix_missing_locations(tree)
