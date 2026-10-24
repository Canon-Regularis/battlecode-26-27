"""Reuse invariant primitive reductions and dependent scalar computations.

Numeric-emitter facts establish purity and immutable snapshot provenance. First
computations remain at their original points; a private insertion-group slot is
published only after the final certified computation succeeds.
"""

import ast
from collections import Counter
import copy

from .model import Change
from .records import used_names


def annotate_group_scalars(tables, body):
    writes = Counter(node.id for node in ast.walk(tables.entry.function) if isinstance(node, ast.Name)
                     and isinstance(node.ctx, (ast.Store, ast.Del)))
    invariant = {tables.root, *(local for local, *_ in tables.tables)}
    active = False
    def pure(node):
        if isinstance(node, ast.Name):
            return node.id in invariant
        if isinstance(node, ast.Constant):
            return type(node.value) in {int, float, bool, type(None)}
        if isinstance(node, ast.Tuple):
            return all(pure(part) for part in node.elts)
        if isinstance(node, ast.Subscript):
            return pure(node.value) and pure(node.slice)
        if isinstance(node, ast.BinOp):
            return isinstance(node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv, ast.Mod)) and pure(node.left) and pure(node.right)
        if isinstance(node, ast.UnaryOp):
            return isinstance(node.op, (ast.UAdd, ast.USub, ast.Not)) and pure(node.operand)
        if isinstance(node, ast.Compare):
            return pure(node.left) and all(pure(part) for part in node.comparators)
        if isinstance(node, ast.BoolOp):
            return all(pure(part) for part in node.values)
        if isinstance(node, ast.IfExp):
            return pure(node.test) and pure(node.body) and pure(node.orelse)
        if isinstance(node, ast.Call):
            return (getattr(node, '_bcopt_numeric_scalar_call', False) and not node.keywords
                    and all(pure(arg) for arg in node.args))
        return False
    for statement in body:
        if getattr(statement, '_bcopt_group_reductions', False):
            unpack = statement.orelse[0]
            invariant.update(part.id for part in unpack.targets[0].elts)
            active = True
            continue
        if isinstance(statement, ast.Assign) and len(statement.targets) == 1 and isinstance(statement.targets[0], ast.Name):
            target = statement.targets[0].id
            valid = pure(statement.value)
            invariant.discard(target)
            if valid:
                invariant.add(target)
            if (active and valid and writes[target] == 1
                    and (getattr(statement.value, '_bcopt_numeric_kind', None) in {'int', 'float', 'number', 'bool'}
                         or getattr(statement, '_bcopt_group_extremum', False))
                    and isinstance(statement.value, (ast.BinOp, ast.Call, ast.IfExp))):
                statement._bcopt_group_scalar = True
        elif isinstance(statement, ast.AugAssign) and isinstance(statement.target, ast.Name):
            invariant.discard(statement.target.id)
        else:
            # Never carry inferred invariance through a control-flow join.
            active = False
            invariant.difference_update(part.id for part in ast.walk(statement) if isinstance(part, ast.Name)
                                        and isinstance(part.ctx, (ast.Store, ast.Del)))


class GroupScalars:
    def __init__(self, options):
        self.options, self.changes = options, []
        self.taken = set()

    def fresh(self, stem):
        name = '_bcopt_group_scalar_'+stem
        while name in self.taken:
            name += '_'
        self.taken.add(name)
        return name

    def apply(self, tree):
        if 'insertion-group-scalars' in self.options.disabled:
            return tree
        self.taken = used_names(tree)
        functions = {node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)}
        for consumer in list(tree.body):
            if not getattr(consumer, '_bcopt_numeric_consumer', None):
                continue
            for loop in list(ast.walk(consumer)):
                producer_name = getattr(loop, '_bcopt_keyed_producer', None)
                if (producer_name not in functions or not isinstance(loop, ast.For)
                        or not isinstance(loop.target, ast.Tuple)):
                    continue
                producer = functions[producer_name]
                starts = [node for node in ast.walk(producer) if getattr(node, '_bcopt_insertion_group_begin', False)]
                yields = [node for node in ast.walk(producer) if isinstance(node, ast.Yield)]
                if not starts or not yields or any(not hasattr(node, '_bcopt_insertion_position') for node in yields):
                    continue
                route = loop.target.elts[0].id
                slot, sites, owner = self.fresh('slot'), [], self
                class Groups(ast.NodeTransformer):
                    def generic_visit(self, node):
                        node = super().generic_visit(node)
                        for _, body in ast.iter_fields(node):
                            if not isinstance(body, list) or not body or not isinstance(body[0], ast.stmt):
                                continue
                            for index, seed in enumerate(body):
                                if not getattr(seed, '_bcopt_group_reductions', False) or index < 2:
                                    continue
                                reduction_loop = seed.body[0]
                                if (not isinstance(reduction_loop, ast.For) or not isinstance(reduction_loop.iter, ast.Name)
                                        or reduction_loop.iter.id != route):
                                    continue
                                if (not getattr(body[index-2], '_bcopt_group_key', False)
                                        or not getattr(body[index-1], '_bcopt_group_lookup', False)):
                                    continue
                                outputs = [part.id for part in seed.orelse[0].targets[0].elts]
                                start = index-2-len(outputs)
                                if start < 0:
                                    continue
                                initial = body[start:index-2]
                                if any(not getattr(part, '_bcopt_group_init', False) or not isinstance(part, ast.Assign)
                                       or not isinstance(part.targets[0], ast.Name) or part.targets[0].id != name
                                       for part, name in zip(initial, outputs)):
                                    continue
                                candidates = []
                                for part in body[index+1:]:
                                    if not isinstance(part, (ast.Assign, ast.AugAssign)):
                                        break
                                    if getattr(part, '_bcopt_group_scalar', False):
                                        candidates.append(part)
                                if not candidates or len(candidates) > 16:
                                    continue
                                outputs.extend(part.targets[0].id for part in candidates)
                                if len(set(outputs)) != len(outputs):
                                    continue
                                state, cache_index = owner.fresh('state'), len(sites)
                                load = ast.parse(f'{state} = {slot}[{cache_index}]\nif {state} is None:\n    pass\nelse:\n    '
                                                 + ', '.join(outputs)+f' = {state}').body
                                load[1].body = body[start:index+1]
                                load[0]._bcopt_group_scalar_read = True
                                load[1]._bcopt_group_scalar_miss = True
                                # Coalesce adjacent invariant computations into
                                # one guard; intervening variant work stays put.
                                selected = set(candidates)
                                tail, position = [], index+1
                                while position < len(body):
                                    part = body[position]
                                    if part not in selected:
                                        tail.append(part)
                                        position += 1
                                        continue
                                    run = []
                                    while position < len(body) and body[position] in selected:
                                        run.append(body[position])
                                        position += 1
                                    if candidates[-1] in run:
                                        publication = ast.parse(f'{slot}[{cache_index}] = ({", ".join(outputs)},)').body[0]
                                        publication._bcopt_group_scalar_publish = True
                                        run.append(publication)
                                    guard = ast.If(test=copy.deepcopy(load[1].test), body=run, orelse=[])
                                    guard._bcopt_group_scalar_miss = True
                                    tail.append(guard)
                                # First adjacent scalars can join the miss block.
                                if tail and isinstance(tail[0], ast.If) and ast.dump(tail[0].test) == ast.dump(load[1].test):
                                    load[1].body.extend(tail.pop(0).body)
                                body[start:] = [*load, *tail]
                                sites.append(seed)
                                break
                        return node
                Groups().visit(loop)
                if not sites:
                    continue
                class Start(ast.NodeTransformer):
                    def visit_Assign(self, node):
                        if node in starts:
                            init = ast.parse(f'{slot} = [None] * {len(sites)}').body[0]
                            init._bcopt_private_cache_slots = True
                            return [init, node]
                        return self.generic_visit(node)
                Start().visit(producer)
                for yielded in yields:
                    yielded.value.elts.append(ast.Name(id=slot, ctx=ast.Load()))
                loop.target.elts.append(ast.Name(id=slot, ctx=ast.Store()))
                self.changes.append(Change('insertion-group-scalars', loop.lineno,
                    'certified invariant scalar regions', ast.unparse(ast.fix_missing_locations(loop))))
        return ast.fix_missing_locations(tree)
