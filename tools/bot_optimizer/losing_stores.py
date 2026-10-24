"""Omit private losing-result stores while preserving allocations and key history.

The solved consumer proof certifies the exact selection suffix, owned dictionary,
primitive keys/comparison, complete same-type previous records, and no other uses
of the result. Only a prepared inlined numeric return can use that certificate.
Object allocation and dictionary materialization stay at their original points.
The first winner receives all stores; later losers cannot introduce shared keys
not already present (or permanently excluded by exhausted shared-key capacity).
"""

import ast
import copy

from .model import Change
from .records import used_names


def name(node, value=None):
    return isinstance(node, ast.Name) and (value is None or node.id == value)


def assignment(node):
    return isinstance(node, ast.Assign) and len(node.targets) == 1 and name(node.targets[0])


def none_test(node, variable):
    return (isinstance(node, ast.Compare) and name(node.left, variable) and len(node.ops) == 1
            and isinstance(node.ops[0], ast.Is) and len(node.comparators) == 1
            and isinstance(node.comparators[0], ast.Constant) and node.comparators[0].value is None)


def fresh_buckets(consumer, loop, bucket, lookup, key, publish):
    """Only this selection suffix can populate initially empty private buckets.

    Merely having the right record type is insufficient: a borrowed record could
    have a replaced combined __dict__ that never populated the type's shared keys.
    Require fresh bucket origins and no aliases before the whole producer nest.
    """
    root = bucket.value.value.id
    writes = [node for node in ast.walk(consumer) if name(node, root) and isinstance(node.ctx, (ast.Store, ast.Del))]
    if len(writes) != 1:
        return False
    parents = {child: parent for parent in ast.walk(consumer) for child in ast.iter_child_nodes(parent)}
    init = parents[writes[0]]
    if not assignment(init):
        return False
    def empty(node):
        return isinstance(node, ast.Dict) and not node.keys
    if isinstance(init.value, ast.DictComp):
        if not empty(init.value.value):
            return False
    elif isinstance(init.value, ast.Dict):
        if not init.value.values or not all(empty(value) for value in init.value.values):
            return False
    else:
        return False
    parent = parents[init]
    sequences = [value for _, value in ast.iter_fields(parent) if isinstance(value, list) and init in value]
    if len(sequences) != 1:
        return False
    sequence = sequences[0]
    top = loop
    while top in parents and parents[top] is not parent:
        top = parents[top]
    if top not in sequence or sequence.index(top) <= sequence.index(init):
        return False
    region = sequence[sequence.index(init)+1:sequence.index(top)+1]
    if any(node is not bucket.value.value for statement in region for node in ast.walk(statement) if name(node, root)):
        return False
    bucket_allowed = {bucket.targets[0], lookup.value.func.value, publish.targets[0].value}
    key_allowed = {key.targets[0], lookup.value.args[0], publish.targets[0].slice}
    return (all(node in bucket_allowed for node in ast.walk(consumer) if name(node, bucket.targets[0].id))
            and all(node in key_allowed for node in ast.walk(consumer) if name(node, key.targets[0].id)))


def annotate_losing_stores(builder, proof):
    from .insertion_keys import shapes
    schema = proof.entry.result
    if schema.kind == 'optional':
        schema = schema.items[0]
    if (schema.kind != 'result-record' or not schema.fields
            or any(item.kind not in {'int', 'float', 'number', 'bool'} for item in schema.items)):
        return
    record = builder.program.records.get(schema.name)
    if not record or tuple(record.fields) != schema.fields:
        return
    consumer = proof.consumer_node
    for loop in ast.walk(consumer):
        if not isinstance(loop, ast.For) or loop.orelse or len(loop.body) < 6:
            continue
        entry, absent, key, bucket, lookup, select = loop.body[-6:]
        if not assignment(entry) or entry.value not in proof.numeric_calls:
            continue
        result = entry.targets[0].id
        if (not isinstance(absent, ast.If) or not none_test(absent.test, result) or absent.orelse
                or len(absent.body) != 1 or not isinstance(absent.body[0], ast.Continue)
                or not all(assignment(node) for node in (key, bucket, lookup))):
            continue
        if (not isinstance(key.value, ast.Call) or len(key.value.args) != 1 or key.value.keywords
                or not name(key.value.args[0]) or not shapes(proof, key.value.func)
                or any(s.kind != 'native' or s.name != 'frozenset' for s in shapes(proof, key.value.func))
                or not isinstance(bucket.value, ast.Subscript) or not name(bucket.value.value)
                or not name(bucket.value.slice)):
            continue
        previous = lookup.targets[0].id
        call = lookup.value
        if (not isinstance(call, ast.Call) or call.keywords or len(call.args) != 1
                or not name(call.args[0], key.targets[0].id) or not isinstance(call.func, ast.Attribute)
                or call.func.attr != 'get' or not name(call.func.value, bucket.targets[0].id)
                or not isinstance(select, ast.If) or select.orelse or len(select.body) != 1
                or not isinstance(select.test, ast.BoolOp) or not isinstance(select.test.op, ast.Or)
                or len(select.test.values) != 2 or not none_test(select.test.values[0], previous)):
            continue
        compare = select.test.values[1]
        if (not isinstance(compare, ast.Compare) or len(compare.ops) != 1
                or not isinstance(compare.ops[0], ast.Gt) or len(compare.comparators) != 1
                or not isinstance(compare.left, ast.Attribute) or not name(compare.left.value, result)):
            continue
        old = compare.comparators[0]
        if (not isinstance(old, ast.Attribute) or old.attr != compare.left.attr
                or not isinstance(old.value, ast.Attribute) or not name(old.value.value, previous)):
            continue
        prior = shapes(proof, old.value)
        buckets = shapes(proof, bucket.value)
        if (not prior or any(s.kind != 'record' or s.name != schema.name or s.fields != schema.fields
                             for s in prior) or not buckets
                or any(s.kind != 'dict' or not s.owned for s in buckets)):
            continue
        publish = select.body[0]
        if (not isinstance(publish, ast.Assign) or len(publish.targets) != 1
                or not isinstance(publish.targets[0], ast.Subscript)
                or not name(publish.targets[0].value, bucket.targets[0].id)
                or not name(publish.targets[0].slice, key.targets[0].id)
                or not isinstance(publish.value, ast.Call)):
            continue
        callee = shapes(proof, publish.value.func)
        if not callee or any(s.kind != 'constructor' for s in callee):
            continue
        uses = [node for node in ast.walk(publish.value) if name(node, result)]
        if len(uses) != 1 or uses[0] not in [*publish.value.args, *(kw.value for kw in publish.value.keywords)]:
            continue
        if not fresh_buckets(consumer, loop, bucket, lookup, key, publish):
            continue
        allowed = {entry.targets[0], absent.test.left, compare.left.value, uses[0]}
        if any(node not in allowed for node in ast.walk(consumer) if name(node, result)):
            continue
        # No arbitrary key construction can be moved before the numeric return.
        # The insertion-key pass must later replace it by an existing scalar.
        token = (entry.lineno, entry.col_offset)
        entry._bcopt_losing_entry = dict(token=token, result=result, record=schema.name,
            fields=schema.fields, score=compare.left.attr, nested=old.value.attr)
        for node, role in ((key, 'key'), (bucket, 'bucket'), (lookup, 'lookup'), (select, 'select')):
            node._bcopt_losing_role = (token, role)


class LosingStores:
    def __init__(self, options):
        self.options, self.changes = options, []
        self.taken = set()

    def fresh(self, stem):
        value = '_bcopt_losing_'+stem
        while value in self.taken:
            value += '_'
        self.taken.add(value)
        return value

    def rewrite(self, consumer, entry):
        fact = entry._bcopt_losing_entry
        roles = {}
        for node in ast.walk(consumer):
            tag = getattr(node, '_bcopt_losing_role', None)
            if tag and tag[0] == fact['token']:
                if tag[1] in roles:
                    return
                roles[tag[1]] = node
        if set(roles) != {'key', 'bucket', 'lookup', 'select'}:
            return
        key, bucket, lookup, select = (roles[part] for part in ('key', 'bucket', 'lookup', 'select'))
        parents = {child: parent for parent in ast.walk(consumer) for child in ast.iter_child_nodes(parent)}
        parent = parents[entry]
        sequences = [value for _, value in ast.iter_fields(parent) if isinstance(value, list) and entry in value]
        if len(sequences) != 1:
            return
        sequence = sequences[0]
        start = sequence.index(entry)
        suffix = sequence[start:]
        if len(suffix) != 7 or suffix[-4:] != [key, bucket, lookup, select]:
            return
        if (not isinstance(suffix[1], ast.If) or not isinstance(suffix[2], ast.If)
                or not none_test(suffix[2].test, fact['result'])
                or suffix[2].orelse or len(suffix[2].body) != 1
                or not isinstance(suffix[2].body[0], ast.Continue)):
            return
        if not all(assignment(node) for node in (key, bucket, lookup)) or not name(key.value):
            return
        if (not isinstance(bucket.value, ast.Subscript) or not name(bucket.value.value)
                or not name(bucket.value.slice)):
            return
        expected_lookup = ast.parse(f'{bucket.targets[0].id}.get({key.targets[0].id})', mode='eval').body
        if ast.dump(lookup.value) != ast.dump(expected_lookup):
            return
        versions = [node for node in ast.walk(entry) if getattr(node, '_bcopt_prepared_dispatch', False)]
        if len(versions) != 1:
            return
        version = versions[0]
        allocations = []
        for statement in version.body:
            for node in ast.walk(statement):
                for _, body in ast.iter_fields(node):
                    if not isinstance(body, list):
                        continue
                    for index, part in enumerate(body):
                        if getattr(part, '_bcopt_complete_record', None) == (fact['record'], fact['fields']):
                            allocations.append((body, index))
        if len(allocations) != 1:
            return
        body, index = allocations[0]
        alloc = body[index]
        width = len(fact['fields'])
        block = body[index:index+width+5]
        if len(block) != width+5 or not assignment(alloc):
            return
        materialize, stores = block[1], block[2:2+width]
        row = alloc.targets[0].id
        if (not assignment(materialize) or not isinstance(materialize.value, ast.Attribute)
                or materialize.value.attr != '__dict__' or not name(materialize.value.value, row)):
            return
        dictionary = materialize.targets[0].id
        for field, store in zip(fact['fields'], stores):
            if (not isinstance(store, ast.Assign) or len(store.targets) != 1
                    or not isinstance(store.targets[0], ast.Subscript)
                    or not name(store.targets[0].value, dictionary)
                    or not isinstance(store.targets[0].slice, ast.Constant) or store.targets[0].slice.value != field
                    or not isinstance(store.value, (ast.Name, ast.Constant))):
                return
        expected_tail = ast.parse(f'del {dictionary}\n{fact["result"]} = {row}\ndel {row}').body
        if any(ast.dump(a) != ast.dump(b) for a, b in zip(block[-3:], expected_tail)):
            return
        region = ast.Module(body=version.body, type_ignores=[])
        if (sum(name(node, row) for node in ast.walk(region)) != 4
                or sum(name(node, dictionary) for node in ast.walk(region)) != width+2):
            return
        if not isinstance(select.test, ast.BoolOp) or len(select.test.values) != 2:
            return
        compare = select.test.values[1]
        if (not none_test(select.test.values[0], lookup.targets[0].id)
                or not isinstance(compare, ast.Compare) or len(compare.ops) != 1
                or not isinstance(compare.ops[0], ast.Gt)
                or ast.unparse(compare.left) != f'{fact["result"]}.{fact["score"]}'
                or len(compare.comparators) != 1
                or ast.unparse(compare.comparators[0]) != f'{lookup.targets[0].id}.{fact["nested"]}.{fact["score"]}'):
            return
        score = stores[fact['fields'].index(fact['score'])].value
        fast, keep, previous = (self.fresh(part) for part in ('fast', 'keep', 'previous'))
        setup = ast.parse(f'''
{previous} = {ast.unparse(bucket.value)}.get({key.value.id})
{keep} = {previous} is None or {ast.unparse(score)} > {previous}.{fact['nested']}.{fact['score']}
del {previous}
{fast} = True
if {keep}:
    pass
''').body
        setup[-1].body = stores
        body[index+2:index+2+width] = setup
        select.test = ast.IfExp(test=ast.Name(id=fast, ctx=ast.Load()),
            body=ast.Name(id=keep, ctx=ast.Load()), orelse=select.test)
        entry._bcopt_losing_initialize = ast.parse(f'{fast} = False').body[0]
        self.changes.append(Change('losing-record-stores', entry.lineno,
            'fully populated private losing record', 'preserved allocation and dictionary with certified losing stores omitted'))
        if 'losing-record-lookup-reuse' not in self.options.disabled:
            # The fresh-bucket proof gives this suffix exclusive ownership.
            # After the early lookup only primitive record stores, local alias
            # release and the already-certified selection suffix can execute on
            # a successful prepared return. The bucket still owns the previous
            # record throughout this interval. Keep its alias until the original
            # previous binding, then release before any bucket publication.
            release = setup[2]
            body.remove(release)
            choose = ast.parse(f'if {fast}:\n    {lookup.targets[0].id} = {previous}\nelse:\n    pass').body[0]
            choose.orelse = [lookup]
            end = sequence.index(lookup)
            protected = ast.Try(body=[*sequence[start:end], choose], handlers=[], orelse=[],
                                finalbody=[copy.deepcopy(release)])
            sequence[start:end+1] = [*ast.parse(f'{previous} = None').body, protected]
            self.changes.append(Change('losing-record-lookup-reuse', entry.lineno,
                'second lookup of an unchanged private bucket',
                'reuse previous record with finally-bounded alias before publication'))

    def apply(self, tree):
        if 'losing-record-stores' in self.options.disabled:
            return tree
        self.taken = used_names(tree)
        for consumer in tree.body:
            if not getattr(consumer, '_bcopt_fused_consumer', False):
                continue
            entries = [node for node in ast.walk(consumer) if getattr(node, '_bcopt_losing_entry', None)
                       and getattr(node, '_bcopt_inlined_entry', None)]
            if len(entries) != 1 or not isinstance(entries[0], ast.If):
                continue
            self.rewrite(consumer, entries[0])
            class Initialize(ast.NodeTransformer):
                def visit_If(self, node):
                    self.generic_visit(node)
                    init = getattr(node, '_bcopt_losing_initialize', None)
                    return [init, node] if init else node
            Initialize().visit(consumer)
        return ast.fix_missing_locations(tree)
