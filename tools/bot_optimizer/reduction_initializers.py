"""Prove that integer reduction initializers can move into the original loop.

This helper is intentionally separate from arithmetic emission. It accepts only
an intact emitter-owned private integer cache lookup/publication and a contiguous
initializer/key/lookup/reduction sequence. Both the cache hit and the new guarded
integer-total path overwrite every output; the original loop keeps its original
initializers, including partial-error state.
"""

import ast

from .base_edge_scalars import named


def initialization_site(region, group, outputs, private_caches):
    sequences = [body for parent in ast.walk(region) for _, body in ast.iter_fields(parent)
                 if isinstance(body, list) and group in body]
    if len(sequences) != 1:
        return
    sequence = sequences[0]
    index = sequence.index(group)
    width = len(outputs)
    if index < width+2:
        return
    initializers = sequence[index-width-2:index-2]
    for node, output in zip(initializers, outputs):
        if (not getattr(node, '_bcopt_group_init', False) or not isinstance(node, ast.Assign)
                or len(node.targets) != 1 or not named(node.targets[0], output)
                or not isinstance(node.value, ast.Constant)
                or not (node.value.value is None or type(node.value.value) is int and node.value.value == 0)):
            return
    key, lookup = sequence[index-2:index]
    if (not getattr(key, '_bcopt_group_key', False) or not isinstance(key, ast.Assign)
            or len(key.targets) != 1 or not isinstance(key.targets[0], ast.Name)
            or not isinstance(key.value, ast.Name) or not getattr(key.value, '_bcopt_integer_multiset_key', False)
            or not getattr(lookup, '_bcopt_group_lookup', False) or not isinstance(lookup, ast.Assign)
            or len(lookup.targets) != 1 or not isinstance(lookup.targets[0], ast.Name)
            or not isinstance(lookup.value, ast.Call) or not isinstance(lookup.value.func, ast.Attribute)
            or not isinstance(lookup.value.func.value, ast.Name)):
        return
    cache = lookup.value.func.value.id
    key_name, value = key.targets[0].id, lookup.targets[0].id
    expected = ast.parse(f'{value} = {cache}.get({key_name}, {cache})').body[0]
    if cache not in private_caches or ast.dump(lookup) != ast.dump(expected):
        return
    if any(named(n, output) for node in (key, lookup) for n in ast.walk(node) for output in outputs):
        return
    expected_test = ast.parse(f'{value} is {cache}', mode='eval').body
    expected_hit = ast.parse(f'{", ".join(outputs)}, = {value}').body
    if (ast.dump(group.test) != ast.dump(expected_test)
            or ast.dump(ast.Module(body=group.orelse, type_ignores=[])) != ast.dump(ast.Module(body=expected_hit, type_ignores=[]))
            or len(group.body) != 2):
        return
    publication = group.body[1]
    if (not getattr(publication, '_bcopt_integer_cache_publish', False)
            or not isinstance(publication, ast.If) or publication.orelse
            or not isinstance(publication.test, ast.Compare) or not isinstance(publication.test.left, ast.Call)
            or not isinstance(publication.test.left.func, ast.Attribute)
            or not isinstance(publication.test.left.func.value, ast.Name)):
        return
    builtins = publication.test.left.func.value.id
    expected_save = ast.parse(f'if {builtins}.len({cache}) < 4096:\n    {cache}[{key_name}] = ({", ".join(outputs)},)').body[0]
    if ast.dump(publication) != ast.dump(expected_save):
        return
    return sequence, initializers
