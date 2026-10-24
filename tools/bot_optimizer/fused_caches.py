"""Scalar replacement of emitter-owned primitive caches in fused consumers."""

import ast

from .model import Change
from .records import used_names


class FusedCaches:
    def __init__(self, options):
        self.options, self.changes = options, []
        self.taken = set()

    def fresh(self):
        name = '_bcopt_cache_slot'
        index = 0
        while f'{name}_{index}' in self.taken:
            index += 1
        name = f'{name}_{index}'
        self.taken.add(name)
        return name

    def scalarize(self, consumer):
        parents = {child: parent for parent in ast.walk(consumer) for child in ast.iter_child_nodes(parent)}
        slots, assignments = {}, {}
        for node in ast.walk(consumer):
            if (not getattr(node, '_bcopt_private_cache_slots', False) or not isinstance(node, ast.Assign)
                    or len(node.targets) != 1 or not isinstance(node.targets[0], ast.Name)
                    or not isinstance(node.value, ast.BinOp) or not isinstance(node.value.op, ast.Mult)
                    or not isinstance(node.value.left, ast.List) or len(node.value.left.elts) != 1
                    or not isinstance(node.value.left.elts[0], ast.Constant) or node.value.left.elts[0].value is not None
                    or not isinstance(node.value.right, ast.Constant) or type(node.value.right.value) is not int):
                continue
            size, name = node.value.right.value, node.targets[0].id
            if not 0 < size <= 16 or name in slots:
                continue
            uses = [(part, parent) for part, parent in parents.items()
                    if isinstance(part, ast.Name) and part.id == name and part is not node.targets[0]]
            if any(not isinstance(parent, ast.Subscript) or parent.value is not part
                   or not isinstance(parent.slice, ast.Constant) or type(parent.slice.value) is not int
                   or not 0 <= parent.slice.value < size for part, parent in uses):
                continue
            slots[name] = assignments[node] = [self.fresh() for _ in range(size)]
        class Replace(ast.NodeTransformer):
            def visit_Assign(self, node):
                if node in assignments:
                    result = ast.Assign(targets=[ast.Name(id=name, ctx=ast.Store()) for name in assignments[node]], value=ast.Constant(None))
                    result._bcopt_scalar_cache_init = True
                    return ast.copy_location(result, node)
                return self.generic_visit(node)
            def visit_Subscript(self, node):
                if isinstance(node.value, ast.Name) and node.value.id in slots:
                    result = ast.Name(id=slots[node.value.id][node.slice.value], ctx=node.ctx)
                    result._bcopt_scalar_cache_slot = True
                    return ast.copy_location(result, node)
                return self.generic_visit(node)
        Replace().visit(consumer)
        if slots:
            self.changes.append(Change('insertion-fused-cache-slots', consumer.lineno,
                'private fixed-size primitive caches', f'{len(slots)} constant-index caches replaced by locals'))

    def resident(self, consumer):
        parents = {child: parent for parent in ast.walk(consumer) for child in ast.iter_child_nodes(parent)}
        groups = {}
        for node in ast.walk(consumer):
            if (not getattr(node, '_bcopt_group_scalar_read', False) or not isinstance(node, ast.Assign)
                    or not isinstance(node.value, ast.Name) or not getattr(node.value, '_bcopt_scalar_cache_slot', False)):
                continue
            parent = parents[node]
            while parent is not consumer:
                if isinstance(parent, ast.If) and getattr(parent, '_bcopt_prepared_dispatch', False):
                    groups.setdefault(parent, []).append(node)
                    break
                parent = parents[parent]
        for version, reads in groups.items():
            if len(reads) != 2 or not isinstance(version.test, ast.Name):
                continue
            writes = [node for node in ast.walk(consumer) if isinstance(node, ast.Name)
                      and isinstance(node.ctx, (ast.Store, ast.Del)) and node.id == version.test.id]
            if len(writes) != 1 or parents[writes[0]] not in consumer.body:
                continue
            branches = [{node for statement in branch for node in ast.walk(statement)} for branch in (version.body, version.orelse)]
            if not all(sum(read in branch for read in reads) == 1 for branch in branches):
                continue
            states = {node.targets[0].id for node in reads}
            caches = {node.value.id for node in reads}
            guards = [node for node in ast.walk(version) if isinstance(node, ast.If)
                      and getattr(node, '_bcopt_group_scalar_miss', False)
                      and isinstance(node.test, ast.Compare) and isinstance(node.test.left, ast.Name)
                      and node.test.left.id in states and len(node.test.ops) == 1 and isinstance(node.test.ops[0], ast.Is)
                      and len(node.test.comparators) == 1 and isinstance(node.test.comparators[0], ast.Constant)
                      and node.test.comparators[0].value is None]
            unpack = [node.orelse[0] for node in guards if len(node.orelse) == 1]
            if (len(unpack) != 2 or any(not isinstance(node, ast.Assign) or len(node.targets) != 1
                    or not isinstance(node.targets[0], ast.Tuple)
                    or any(not isinstance(part, ast.Name) for part in node.targets[0].elts)
                    or not isinstance(node.value, ast.Name) or node.value.id not in states for node in unpack)):
                continue
            ordered = [tuple(part.id for part in node.targets[0].elts) for node in unpack]
            if ordered[0] != ordered[1]:
                continue
            outputs = set(ordered[0])
            allowed = {part for node in guards for part in ast.walk(node)
                       if isinstance(part, ast.Name) and isinstance(part.ctx, ast.Store)}
            if any(node not in allowed for node in ast.walk(consumer) if isinstance(node, ast.Name)
                   and isinstance(node.ctx, (ast.Store, ast.Del)) and node.id in outputs):
                continue
            publications = [node for node in ast.walk(version) if isinstance(node, ast.Assign)
                            and getattr(node, '_bcopt_group_scalar_publish', False)
                            and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name)
                            and node.targets[0].id in caches and isinstance(node.value, ast.Tuple)]
            if (len(publications) != 2 or any(tuple(part.id if isinstance(part, ast.Name) else None
                    for part in node.value.elts) != ordered[0] for node in publications)):
                continue
            # The ready flags must not become numeric operands, returned values,
            # or observable identities anywhere in the consumer.
            valid = True
            for node, parent in parents.items():
                if not isinstance(node, ast.Name):
                    continue
                if node.id in states:
                    valid &= (parent in reads or parent in unpack or
                              any(parent is guard.test and node is guard.test.left for guard in guards))
                if node.id in caches:
                    valid &= (parent in reads or parent in publications or
                              isinstance(parent, ast.Assign) and getattr(parent, '_bcopt_scalar_cache_init', False))
            if not valid:
                continue
            for node in publications:
                node.value = ast.Constant(True)
            for node in reads:
                node._bcopt_resident_scalar_outputs = ordered[0]
            for node in guards:
                if node.orelse:
                    node.orelse = []
            self.changes.append(Change('insertion-resident-scalars', version.lineno,
                'private scalar tuple publication and unpacking', 'immutable-version cache outputs retained in fused locals'))

    def resident_edges(self, consumer):
        parents = {child: parent for parent in ast.walk(consumer) for child in ast.iter_child_nodes(parent)}
        groups = {}
        for node in ast.walk(consumer):
            if not isinstance(node, ast.If) or not getattr(node, '_bcopt_edge_cache_update', False):
                continue
            parent = parents[node]
            while parent is not consumer:
                if isinstance(parent, ast.If) and getattr(parent, '_bcopt_prepared_dispatch', False):
                    groups.setdefault(parent, []).append(node)
                    break
                parent = parents[parent]
        for version, updates in groups.items():
            if len(updates) != 2 or not isinstance(version.test, ast.Name):
                continue
            writes = [node for node in ast.walk(consumer) if isinstance(node, ast.Name)
                      and isinstance(node.ctx, (ast.Store, ast.Del)) and node.id == version.test.id]
            if len(writes) != 1 or parents[writes[0]] not in consumer.body:
                continue
            branches = [{node for statement in branch for node in ast.walk(statement)} for branch in (version.body, version.orelse)]
            if not all(sum(update in branch for update in updates) == 1 for branch in branches):
                continue
            sites = []
            for node in updates:
                if (not isinstance(node.test, ast.BoolOp) or not isinstance(node.test.op, ast.Or) or len(node.test.values) != 2
                        or not isinstance(node.test.values[0], ast.Compare)
                        or not isinstance(node.test.values[0].left, ast.Name) or not node.orelse
                        or len(node.test.values[0].ops) != 1 or not isinstance(node.test.values[0].ops[0], ast.Is)
                        or len(node.test.values[0].comparators) != 1
                        or not isinstance(node.test.values[0].comparators[0], ast.Constant)
                        or node.test.values[0].comparators[0].value is not None):
                    break  # Additional context guards require retaining the original state.
                state = node.test.values[0].left.id
                reads = [part for part in ast.walk(consumer) if isinstance(part, ast.Assign)
                         and getattr(part, '_bcopt_edge_cache_read', False)
                         and len(part.targets) == 1 and isinstance(part.targets[0], ast.Name) and part.targets[0].id == state]
                if len(reads) != 1:
                    break
                read, = reads
                if not isinstance(read.value, ast.Name) or not getattr(read.value, '_bcopt_scalar_cache_slot', False):
                    break
                cache = read.value.id
                publication, restore, last = node.body[-1], node.orelse[0], node.orelse[-1]
                if (not isinstance(publication, ast.Assign) or len(publication.targets) != 1
                        or not isinstance(publication.targets[0], ast.Name) or publication.targets[0].id != cache
                        or not isinstance(publication.value, ast.List) or len(publication.value.elts) != 2
                        or any(not isinstance(part, ast.Name) for part in publication.value.elts)):
                    break
                position, edges = publication.value.elts
                if (not isinstance(restore, ast.Assign) or len(restore.targets) != 1
                        or not isinstance(restore.targets[0], ast.Name) or restore.targets[0].id != edges.id
                        or not isinstance(restore.value, ast.Subscript) or not isinstance(restore.value.value, ast.Name)
                        or restore.value.value.id != state or not isinstance(restore.value.slice, ast.Constant)
                        or type(restore.value.slice.value) is not int or restore.value.slice.value != 1
                        or not isinstance(last, ast.Assign) or len(last.targets) != 1
                        or not isinstance(last.targets[0], ast.Subscript) or not isinstance(last.targets[0].value, ast.Name)
                        or last.targets[0].value.id != state or not isinstance(last.targets[0].slice, ast.Constant)
                        or type(last.targets[0].slice.value) is not int or last.targets[0].slice.value != 0
                        or not isinstance(last.value, ast.Name) or last.value.id != position.id):
                    break
                allowed_state = {read.targets[0], node.test.values[0].left, restore.value.value, last.targets[0].value}
                for part in ast.walk(node.test.values[1]):
                    if (isinstance(part, ast.Subscript) and isinstance(part.value, ast.Name) and part.value.id == state
                            and isinstance(part.slice, ast.Constant) and type(part.slice.value) is int and part.slice.value == 0):
                        allowed_state.add(part.value)
                if any(part not in allowed_state for part in parents if isinstance(part, ast.Name) and part.id == state):
                    break
                if any(parent not in (read, publication) and not (isinstance(parent, ast.Assign)
                       and getattr(parent, '_bcopt_scalar_cache_init', False))
                       for part, parent in parents.items() if isinstance(part, ast.Name) and part.id == cache):
                    break
                sites.append((node, publication, restore, last, state, cache, position, edges.id))
            if len(sites) != 2:
                continue
            lists = {site[-1] for site in sites}
            allowed = {part for node in updates for part in ast.walk(node)}
            if any(part not in allowed for part in parents if isinstance(part, ast.Name)
                   and isinstance(part.ctx, (ast.Store, ast.Del)) and part.id in lists):
                continue
            for node, publication, restore, last, state, cache, position, _ in sites:
                publication.value = ast.Name(id=position.id, ctx=ast.Load())
                node.orelse.remove(restore)
                last.targets = [ast.Name(id=cache, ctx=ast.Store())]
                class Position(ast.NodeTransformer):
                    def visit_Subscript(self, part):
                        if isinstance(part.value, ast.Name) and part.value.id == state:
                            return ast.Name(id=state, ctx=ast.Load())
                        return self.generic_visit(part)
                Position().visit(node.test)
            self.changes.append(Change('insertion-resident-edges', version.lineno,
                'private position/list state', 'rolling edge list retained in fused local with position-only cache'))

    def apply(self, tree):
        if 'insertion-fused-cache-slots' in self.options.disabled:
            return tree
        self.taken = used_names(tree)
        for consumer in tree.body:
            if not getattr(consumer, '_bcopt_fused_consumer', False):
                continue
            self.scalarize(consumer)
            if 'insertion-resident-scalars' not in self.options.disabled:
                self.resident(consumer)
            if 'insertion-resident-edges' not in self.options.disabled:
                self.resident_edges(consumer)
        return ast.fix_missing_locations(tree)
