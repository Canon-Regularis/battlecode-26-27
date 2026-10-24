"""Short-tuple specialization of certified prepared ordered pair reductions.

Unpack immutable primitive tuples once; retain every numeric addition in source
order. Long tuples and nonprepared paths keep their original protected loops.
"""

import ast
from collections import Counter
import copy

from .model import Change
from .records import used_names


def certify_pair_fold(tables, loop):
    if (not isinstance(loop, ast.For) or loop.orelse or len(loop.body) != 1
            or not isinstance(loop.target, ast.Tuple) or len(loop.target.elts) != 2
            or any(not isinstance(part, ast.Name) for part in loop.target.elts)
            or not isinstance(loop.iter, ast.Call) or len(loop.iter.args) != 2 or loop.iter.keywords
            or tables.builder.program.resolve(tables.builder.module, loop.iter.func) not in {'zip', 'builtins.zip'}):
        return
    route, tail = loop.iter.args
    if (not isinstance(route, ast.Name) or getattr(route, '_bcopt_numeric_kind', None) != 'tuple'
            or not isinstance(tail, ast.Subscript) or not isinstance(tail.value, ast.Name) or tail.value.id != route.id
            or not isinstance(tail.slice, ast.Slice) or tail.slice.upper is not None or tail.slice.step is not None
            or not isinstance(tail.slice.lower, ast.Constant) or type(tail.slice.lower.value) is not int
            or tail.slice.lower.value != 1):
        return
    update = loop.body[0]
    if (not isinstance(update, ast.AugAssign) or not isinstance(update.target, ast.Name)
            or not isinstance(update.op, ast.Add) or not isinstance(update.value, ast.IfExp)
            or not getattr(update.value, '_bcopt_prepared_projection', False)):
        return
    lookup = update.value.orelse
    targets = {part.id for part in loop.target.elts}
    if (len(targets) != 2 or update.target.id in targets | {route.id}
            or not isinstance(lookup, ast.Subscript) or not isinstance(lookup.value, ast.Subscript)
            or not isinstance(lookup.value.value, ast.Name)
            or lookup.value.value.id not in {local for local, _, _, domains, _ in tables.tables if len(domains) == 2}
            or not isinstance(lookup.slice, ast.Name) or not isinstance(lookup.value.slice, ast.Name)
            or {lookup.slice.id, lookup.value.slice.id} != targets):
        return
    loop._bcopt_ordered_pair_fold = True


class OrderedFolds:
    def __init__(self, options):
        self.options, self.changes = options, []
        self.taken = set()

    def fresh(self, stem):
        name = '_bcopt_ordered_'+stem
        while name in self.taken:
            name += '_'
        self.taken.add(name)
        return name

    def apply(self, tree):
        if 'numeric-ordered-folds' in self.options.disabled:
            return tree
        self.taken = used_names(tree)
        length = self.fresh('len')
        for consumer in list(tree.body):
            if not getattr(consumer, '_bcopt_numeric_consumer', None):
                continue
            writes = Counter(node.id for node in ast.walk(consumer) if isinstance(node, ast.Name)
                             and isinstance(node.ctx, (ast.Store, ast.Del)))
            tables = {node.targets[0].id for node in consumer.body if isinstance(node, ast.Assign)
                      and getattr(node, '_bcopt_prepared_table', False) and getattr(node, '_bcopt_snapshot_hoisted', False)
                      and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name) and writes[node.targets[0].id] == 1}
            owner = self
            class Fold(ast.NodeTransformer):
                def visit_If(self, node):
                    if (not getattr(node, '_bcopt_ordered_pair_fold', False) or len(node.orelse) != 1
                            or not isinstance(node.orelse[0], ast.For)):
                        return self.generic_visit(node)
                    loop = node.orelse[0]
                    if (len(loop.body) != 1 or not isinstance(loop.body[0], ast.AugAssign)
                            or not isinstance(loop.target, ast.Tuple) or len(loop.target.elts) != 2
                            or not isinstance(loop.iter, ast.Call) or not isinstance(loop.iter.args[0], ast.Name)):
                        return self.generic_visit(node)
                    update, route = loop.body[0], loop.iter.args[0]
                    lookup = update.value
                    if (not isinstance(lookup, ast.Subscript) or not isinstance(lookup.value, ast.Subscript)
                            or not isinstance(lookup.value.value, ast.Name) or lookup.value.value.id not in tables):
                        return self.generic_visit(node)
                    # The nonprepared version still has its IfExp and fails the
                    # shape test above. Source tuples contain only checked ints.
                    left, right = [part.id for part in loop.target.elts]
                    maximum = 12
                    items = [owner.fresh(f'item_{i}') for i in range(maximum)]
                    size = owner.fresh('size')
                    fallback = [node]
                    for count in reversed(range(2, maximum+1)):
                        body = ast.parse(', '.join(items[:count])+f' = {route.id}').body
                        body[0]._bcopt_ordered_unpack = (route.id, tuple(items[:count]), lookup.value.value.id)
                        for a, b in zip(items, items[1:count]):
                            class Substitute(ast.NodeTransformer):
                                def visit_Name(self, part):
                                    if part.id in {left, right}:
                                        part.id = a if part.id == left else b
                                    return part
                            addition = Substitute().visit(copy.deepcopy(update))
                            addition._bcopt_ordered_update = lookup.value.value.id
                            body.append(addition)
                        final = ast.parse(f'{left}, {right} = {items[count-2]}, {items[count-1]}').body[0]
                        for part in final.targets[0].elts:
                            part._bcopt_bound_kind = 'int'
                        body.append(final)
                        fallback = [ast.If(test=ast.Compare(left=ast.Name(id=size, ctx=ast.Load()),
                            ops=[ast.Eq()], comparators=[ast.Constant(count)]), body=body, orelse=fallback)]
                    result = [*ast.parse(f'{size} = {length}({route.id})').body, *fallback]
                    result[0].value._bcopt_known_len = True
                    result[0].targets[0]._bcopt_bound_kind = 'int'
                    result[0]._bcopt_private_integer_assignment = True
                    result[1]._bcopt_ordered_width_dispatch = (size, route.id, maximum)
                    owner.changes.append(Change('numeric-ordered-folds', node.lineno,
                        ast.unparse(node), ast.unparse(ast.fix_missing_locations(ast.Module(body=result, type_ignores=[])))))
                    return result
            Fold().visit(consumer)
        if self.changes:
            index = 1 if tree.body and isinstance(tree.body[0], ast.Expr) and isinstance(tree.body[0].value, ast.Constant) else 0
            while index < len(tree.body) and isinstance(tree.body[index], ast.ImportFrom) and tree.body[index].module == '__future__':
                index += 1
            tree.body.insert(index, ast.ImportFrom(module='builtins', names=[ast.alias(name='len', asname=length)], level=0))
        return ast.fix_missing_locations(tree)
