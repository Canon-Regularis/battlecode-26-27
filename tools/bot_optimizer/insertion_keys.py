"""Share insertion-invariant primitive keys in closed producer/consumer loops.

Contracts originate in the solved consumer type/effect proof and the original
generator's tuple-insertion expression. Public generators stay unchanged; a
private clone carries keys alongside each freshly allocated yielded tuple.
"""

import ast
import copy

from .analysis import Bindings, arguments
from .model import Change
from .records import used_names
from .producer_fusion import certify_producer


def shapes(proof, node):
    return {shape for cell in proof.expressions.get(node, ()) for shape in cell.shapes}


def primitive_tuple(proof, node):
    values = shapes(proof, node)
    return bool(values) and all(value.kind == 'tuple' and len(value.items) == 1
        and all(item.kind == 'int' for item in value.items[0].shapes) for value in values)


def contains_set(cell, seen=None):
    seen = set() if seen is None else seen
    if id(cell) in seen:
        return False
    seen.add(id(cell))
    return any(shape.kind == 'frozenset' or any(contains_set(item, seen) for item in shape.items)
               for shape in cell.shapes)


def sets_unobserved(proof):
    if contains_set(proof.consumer_result):
        return False
    # Set contents can be hashed, compared by native equality and used as private
    # dictionary keys. Iteration order and container identity are not invariant.
    for node in proof.expressions:
        if isinstance(node, ast.Compare):
            for op, left, right in zip(node.ops, [node.left, *node.comparators], node.comparators):
                if isinstance(op, (ast.Is, ast.IsNot)):
                    if any(isinstance(part, ast.Constant) and part.value is None for part in (left, right)):
                        continue
                    if any(contains_set(cell) for part in (left, right) for cell in proof.expressions.get(part, ())):
                        return False
        iterables = []
        if isinstance(node, ast.Call):
            # Conservatively reject every call that receives a set except native
            # len. Dict get is safe; record/helper calls may otherwise expose it.
            for arg in node.args:
                if any(value.kind == 'frozenset' for value in shapes(proof, arg)):
                    callee = shapes(proof, node.func)
                    if not callee or any(not (value.kind == 'native' and value.name == 'len'
                        or value.kind == 'bound-native' and value.name == 'get') for value in callee):
                        return False
        if isinstance(node, (ast.ListComp, ast.DictComp, ast.GeneratorExp)):
            iterables.extend(generator.iter for generator in node.generators)
        if any(any(value.kind == 'frozenset' for value in shapes(proof, part)) for part in iterables):
            return False
    # For statements are not expression entries; inspect each proved body.
    functions = [proof.consumer_node, *(proof.builder.methods[name] for name in proof.methods)]
    functions += [proof.program.functions[name].node for name in proof.functions]
    return not any(isinstance(node, ast.For) and any(value.kind == 'frozenset' for value in shapes(proof, node.iter))
                   for function in functions for node in ast.walk(function))


def producer_loops(builder, proof, function):
    parameters = {arg.arg for arg in arguments(function)}
    local = set(Bindings(function.body).counts) | parameters
    owners = parameters - set(Bindings(function.body).counts)
    def builtin(node, name):
        return (isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id not in local
                and builder.program.resolve(builder.module, node.func) in {name, 'builtins.'+name}
                and len(node.args) == 1 and not node.keywords)
    matches, covered = [], set()
    for loop in ast.walk(function):
        if (not isinstance(loop, ast.For) or loop.orelse or not isinstance(loop.target, ast.Name)
                or not builtin(loop.iter, 'range') or len(loop.body) != 1
                or not isinstance(loop.body[0], ast.Expr) or not isinstance(loop.body[0].value, ast.Yield)):
            continue
        bound = loop.iter.args[0]
        if (not isinstance(bound, ast.BinOp) or not isinstance(bound.op, ast.Add)
                or not isinstance(bound.right, ast.Constant) or type(bound.right.value) is not int
                or bound.right.value != 1 or not builtin(bound.left, 'len')
                or not isinstance(bound.left.args[0], ast.Name) or bound.left.args[0].id not in owners):
            continue
        owner, position = bound.left.args[0].id, loop.target.id
        yielded = loop.body[0].value
        value = yielded.value
        if (not isinstance(value, ast.BinOp) or not isinstance(value.op, ast.Add)
                or not isinstance(value.left, ast.BinOp) or not isinstance(value.left.op, ast.Add)
                or not isinstance(value.left.right, ast.Tuple) or len(value.left.right.elts) != 1):
            continue
        prefix, item, suffix = value.left.left, value.left.right.elts[0], value.right
        item_shapes = shapes(proof, item)
        if (not isinstance(item, ast.Name) or item.id == position or not item_shapes
                or any(shape.kind != 'int' for shape in item_shapes)):
            continue
        valid = True
        for part, before in ((prefix, True), (suffix, False)):
            if (not isinstance(part, ast.Subscript) or not isinstance(part.value, ast.Name)
                    or part.value.id != owner or not primitive_tuple(proof, part.value)
                    or not isinstance(part.slice, ast.Slice) or part.slice.step is not None):
                valid = False
                break
            cut = part.slice.upper if before else part.slice.lower
            empty = part.slice.lower if before else part.slice.upper
            if empty is not None or not isinstance(cut, ast.Name) or cut.id != position:
                valid = False
                break
        if valid:
            matches.append((loop, (owner, item.id, position)))
            covered.add(yielded)
    yields = {node for node in ast.walk(function) if isinstance(node, ast.Yield)}
    return matches if covered and covered == yields and len(matches) <= 16 else []


def annotate_insertion_keys(builder, proof):
    """Attach non-source-spellable facts before ordinary AST transformations."""
    safe_sets = sets_unobserved(proof)
    for loop in ast.walk(proof.consumer_node):
        if (not isinstance(loop, ast.For) or not isinstance(loop.target, ast.Name)
                or not isinstance(loop.iter, ast.Call) or not isinstance(loop.iter.func, ast.Name)):
            continue
        name = builder.program.resolve(builder.module, loop.iter.func)
        if name not in proof.functions:
            continue
        info = builder.program.functions[name]
        if info.module != builder.module:
            continue
        matches = producer_loops(builder, proof, info.node)
        if not matches:
            continue
        for producer_loop, contract in matches:
            producer_loop._bcopt_insertion_key_loop = contract
        certify_producer(builder, proof, info.node, matches)
        loop._bcopt_insertion_key_consumer = (info.node.name, safe_sets)
    if safe_sets:
        for node in ast.walk(proof.consumer_node):
            if (isinstance(node, ast.Call) and len(node.args) == 1 and not node.keywords
                    and primitive_tuple(proof, node.args[0])):
                values = shapes(proof, node.func)
                if values and all(value.kind == 'native' and value.name == 'frozenset' for value in values):
                    node._bcopt_index_set = True


class InsertionKeys:
    def __init__(self, options):
        self.options, self.changes = options, []
        self.taken = set()

    def fresh(self, stem):
        name = '_bcopt_insertion_key_'+stem
        while name in self.taken:
            name += '_'
        self.taken.add(name)
        return name

    def apply(self, tree):
        if 'insertion-invariant-keys' in self.options.disabled:
            return tree
        self.taken = used_names(tree)
        functions = {node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)}
        additions = []
        for consumer in list(tree.body):
            if not getattr(consumer, '_bcopt_numeric_consumer', None):
                continue
            for loop in list(ast.walk(consumer)):
                contract = getattr(loop, '_bcopt_insertion_key_consumer', None)
                if contract is None or not isinstance(loop, ast.For) or not isinstance(loop.target, ast.Name):
                    continue
                name, safe_sets = contract
                if name not in functions or not isinstance(loop.iter, ast.Call) or not isinstance(loop.iter.func, ast.Name):
                    continue
                route = loop.target.id
                if any(isinstance(node, ast.Name) and node.id == route and isinstance(node.ctx, (ast.Store, ast.Del))
                       for statement in loop.body for node in ast.walk(statement)):
                    continue
                keys = [node for statement in loop.body for node in ast.walk(statement)
                        if isinstance(node, ast.Call) and getattr(node, '_bcopt_multiset_key', False)
                        and len(node.args) == 1 and isinstance(node.args[0], ast.Call)
                        and len(node.args[0].args) == 1 and isinstance(node.args[0].args[0], ast.Name)
                        and node.args[0].args[0].id == route]
                sets = [node for statement in loop.body for node in ast.walk(statement)
                        if safe_sets and isinstance(node, ast.Call) and getattr(node, '_bcopt_index_set', False)
                        and len(node.args) == 1 and isinstance(node.args[0], ast.Name) and node.args[0].id == route]
                if not keys:
                    continue
                producer = copy.deepcopy(functions[name])
                producer.name = self.fresh('producer')
                producer.returns = producer.type_comment = None
                for arg in arguments(producer):
                    arg.annotation = arg.type_comment = None
                key, members, builtins, joined = (self.fresh(stem) for stem in ('sorted', 'set', 'builtins', 'joined'))
                output_names = [key, *([members] if sets else [])]
                unique_keys = bool(sets) and 'insertion-unique-keys' not in self.options.disabled
                changed = []
                class Producer(ast.NodeTransformer):
                    def generic_visit(self, node):
                        fact = getattr(node, '_bcopt_insertion_key_loop', None)
                        if fact is not None and isinstance(node, (ast.For, ast.If)):
                            owner, item, position = fact
                            code = f'{joined} = (*{owner}, {item})\n'
                            multiset = f'{builtins}.tuple({builtins}.sorted({joined}))'
                            if unique_keys:
                                # Equality of cardinalities proves multiplicity
                                # one, including for negative integer indices.
                                # Only this private reduction key changes type.
                                code += f'{members} = {builtins}.frozenset({joined})\n'
                                code += f'{key} = {members} if {builtins}.len({members}) == {builtins}.len({joined}) else {multiset}\n'
                            else:
                                code += f'{key} = {multiset}\n'
                                if sets:
                                    # Use insertion order, not sorted order,
                                    # even though the closed proof forbids observation.
                                    code += f'{members} = {builtins}.frozenset({joined})\n'
                            code += f'del {joined}\n'
                            for part in ast.walk(node):
                                if isinstance(part, ast.Yield):
                                    part._bcopt_insertion_position = position
                                    part.value = ast.Tuple(elts=[part.value, *(ast.Name(id=n, ctx=ast.Load())
                                        for n in output_names)], ctx=ast.Load())
                            changed.append(node)
                            prefix = ast.parse(code).body
                            prefix[0]._bcopt_insertion_group_begin = True
                            return [*prefix, node]
                        return super().generic_visit(node)
                Producer().visit(producer)
                if not changed:
                    continue
                replacements = {id(node): key for node in keys}
                replacements.update({id(node): members for node in sets})
                class Replace(ast.NodeTransformer):
                    def visit_Call(self, node):
                        if id(node) in replacements:
                            result = ast.copy_location(ast.Name(id=replacements[id(node)], ctx=ast.Load()), node)
                            if node in keys:
                                result._bcopt_integer_multiset_key = True
                            return result
                        return self.generic_visit(node)
                before = ast.unparse(loop)
                Replace().visit(loop)
                loop.iter.func = ast.Name(id=producer.name, ctx=ast.Load())
                loop.target = ast.Tuple(elts=[loop.target, *(ast.Name(id=n, ctx=ast.Store())
                    for n in output_names)], ctx=ast.Store())
                loop._bcopt_keyed_producer = producer.name
                additions.append((consumer, [ast.Import(names=[ast.alias(name='builtins', asname=builtins)]), producer]))
                self.changes.append(Change('insertion-invariant-keys', loop.lineno,
                    before, ast.unparse(ast.fix_missing_locations(loop))))
                if unique_keys:
                    self.changes.append(Change('insertion-unique-keys', loop.lineno,
                        'private sorted multiset key', 'private frozenset key when cardinalities match; full multiset fallback'))
        for consumer, nodes in additions:
            index = tree.body.index(consumer)
            tree.body[index:index] = nodes
        return ast.fix_missing_locations(tree)
