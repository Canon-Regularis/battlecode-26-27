"""Lower proven primitive graph methods to private snapshot-based numeric clones.

This module emits obligations, not public dispatch. Callers must validate the
complete graph, method identities, argument types and indexed-access obligations
before invoking a clone. Unknown operations decline the entire specialization.
"""

import ast
import copy
from dataclasses import dataclass, replace

from .analysis import Bindings, arguments
from .program import Signature, body_without_docstring
from .region_types import Schema
from .records import used_names


INT = Schema('int')
FLOAT = Schema('float')
BOOL = Schema('bool')
NONE = Schema('none')
NUMERIC = {'int', 'float', 'bool', 'number'}
SEQUENCES = {'list', 'tuple', 'fixed-tuple', 'iterator'}


class Unsupported(ValueError):
    pass


@dataclass(frozen=True)
class Value:
    schema: Schema
    path: tuple | None = None
    domain: tuple | None = None
    projected: bool = False
    owned: bool = False
    minimum: int = 0
    parts: tuple = ()
    total: bool = True


@dataclass(frozen=True)
class Access:
    path: tuple
    domain: tuple


@dataclass
class Clone:
    name: str
    method: str
    function: ast.FunctionDef
    arguments: dict
    result: Schema | None = None


def merge(left, right):
    if left == right:
        return left
    if left.kind in NUMERIC and right.kind in NUMERIC:
        return Schema('number')
    if left.kind == 'none':
        return Schema('optional', items=(right,))
    if right.kind == 'none':
        return Schema('optional', items=(left,))
    if left.kind == 'optional' and right in left.items:
        return left
    if right.kind == 'optional' and left in right.items:
        return right
    raise Unsupported('incompatible branch types')


class NumericClones:
    def __init__(self, program, schemas, owner, taken=()):
        self.program, self.schemas, self.owner = program, schemas, owner
        declaration = schemas.declaration(owner.name)
        if declaration is None:
            raise Unsupported('unknown owner')
        self.module, node = declaration
        self.methods = {n.name: copy.deepcopy(n) for n in node.body if isinstance(n, ast.FunctionDef)}
        self.taken = set(taken) | used_names(program.modules[self.module].tree)
        self.clones = {}
        self.active = set()
        self.accesses = set()
        self.required_methods = set()
        self.fusions = 0
        self.inlined_helpers = 0

    def fresh(self, stem):
        index = 0
        while f'_bcopt_region_{stem}_{index}' in self.taken:
            index += 1
        name = f'_bcopt_region_{stem}_{index}'
        self.taken.add(name)
        return name

    def entry(self, method):
        source = self.methods.get(method)
        if source is None:
            raise Unsupported('unknown method')
        params = arguments(source)
        if not params:
            raise Unsupported('missing receiver')
        facts = {params[0].arg: Value(self.owner, ('root',), projected=True)}
        for param in params[1:]:
            schema = self.schemas.annotation(self.module, param.annotation) if param.annotation else None
            if schema is None or schema.kind not in {'int', 'float', 'bool', 'tuple'}:
                raise Unsupported('unsupported argument schema')
            if schema.kind == 'tuple' and schema.items != (INT,):
                raise Unsupported('only integer tuple arguments are supported')
            domain = ('items', param.arg) if schema.kind == 'tuple' else ('scalar', param.arg)
            facts[param.arg] = Value(schema, ('arg', param.arg), domain=domain)
        entry = self.compile(method, facts)
        self.inlined_helpers = inline_numeric_helpers(self, entry)
        return entry

    def compile(self, method, facts):
        # Parameters are borrowed even when the caller owns a fresh temporary.
        # A helper that mutates one is not a pure numeric call for region reuse.
        def borrowed(value):
            return replace(value, owned=False, parts=tuple(borrowed(part) for part in value.parts))
        facts = {name: borrowed(value) for name, value in facts.items()}
        key = method, tuple(facts.items())
        if key in self.active:
            raise Unsupported('recursive numeric method')
        if key in self.clones:
            return self.clones[key]
        source = self.methods.get(method)
        if (source is None or source.decorator_list or source.type_params
                or source.args.vararg or source.args.kwarg):
            raise Unsupported('unsupported method signature')
        if any(not isinstance(default, ast.Constant) or type(default.value) not in {int, float, bool, type(None)}
               for default in [*source.args.defaults, *(value for value in source.args.kw_defaults if value is not None)]):
            raise Unsupported('effectful or mutable method default')
        if set(facts) != {arg.arg for arg in arguments(source)}:
            raise Unsupported('incomplete method binding')
        self.active.add(key)
        self.required_methods.add(method)
        clone = Clone(self.fresh('numeric'), method, copy.deepcopy(source), dict(facts))
        clone.function.name = clone.name
        clone.function._bcopt_numeric_clone = True
        clone.function.returns = None
        clone.function.type_comment = None
        for parameter in arguments(clone.function):
            parameter.annotation = None
            parameter.type_comment = None
        lower = Lower(self, clone)
        try:
            clone.function.body, _, terminated = lower.block(body_without_docstring(source.body), dict(facts))
            if not terminated:
                lower.returns.append(NONE)
            if not lower.returns:
                raise Unsupported('no numeric result')
            result = lower.returns[0]
            for other in lower.returns[1:]:
                result = merge(result, other)
            clone.result = result
            self.fusions += fuse_integer_reductions(self, clone.function)
            ast.fix_missing_locations(clone.function)
            self.clones[key] = clone
            return clone
        finally:
            self.active.remove(key)


class Lower:
    def __init__(self, builder, clone):
        self.builder, self.clone = builder, clone
        self.returns = []
        self.locals = set(Bindings(clone.function.body).counts) | {arg.arg for arg in arguments(clone.function)}

    def tagged(self, node, value):
        node._bcopt_numeric_kind = value.schema.kind
        node._bcopt_numeric_total = value.total
        node._bcopt_numeric_minimum = value.minimum
        return node, value

    def item(self, value):
        if value.schema.kind not in SEQUENCES:
            raise Unsupported('unknown iterable')
        if value.schema.kind == 'fixed-tuple':
            if not value.schema.items or len(set(value.schema.items)) != 1:
                raise Unsupported('heterogeneous tuple iteration')
            schema = value.schema.items[0]
        else:
            schema = value.schema.items[0]
        path = (*value.path, '*') if value.path else None
        if schema.kind == 'fixed-tuple' and value.parts and value.schema.kind == 'iterator':
            return Value(schema, parts=value.parts, projected=value.projected)
        return Value(schema, path, value.domain, value.projected)

    def bind(self, target, value, facts):
        if isinstance(target, ast.Name):
            facts[target.id] = replace(value, total=True)
            target._bcopt_bound_kind = value.schema.kind
            return
        if isinstance(target, (ast.Tuple, ast.List)) and value.schema.kind == 'fixed-tuple':
            if len(target.elts) != len(value.schema.items):
                raise Unsupported('unpacking shape')
            for index, (child, schema) in enumerate(zip(target.elts, value.schema.items)):
                item = value.parts[index] if value.parts else Value(schema, projected=value.projected)
                self.bind(child, item, facts)
            return
        raise Unsupported('nonlocal mutation or unknown unpacking')

    def numeric(self, op, left, right):
        if left.schema.kind not in NUMERIC or right.schema.kind not in NUMERIC:
            raise Unsupported('nonnumeric arithmetic')
        floating = 'float' in {left.schema.kind, right.schema.kind}
        mixed = 'number' in {left.schema.kind, right.schema.kind}
        if isinstance(op, (ast.Add, ast.Sub, ast.Mult)):
            # Converting a huge integer in mixed float arithmetic can overflow.
            total = left.total and right.total and not mixed and not (floating and left.schema != right.schema)
            return Value(FLOAT if floating else Schema('number') if mixed else INT, total=total)
        if isinstance(op, ast.Div):
            return Value(FLOAT, total=False)
        if isinstance(op, (ast.FloorDiv, ast.Mod)):
            return Value(FLOAT if floating else Schema('number') if mixed else INT, total=False)
        if isinstance(op, (ast.BitAnd, ast.BitOr, ast.BitXor, ast.LShift, ast.RShift)) and not floating and not mixed:
            return Value(INT, total=left.total and right.total and not isinstance(op, (ast.LShift, ast.RShift)))
        raise Unsupported('unsupported numeric operator')

    def expr(self, original, facts):
        node = copy.deepcopy(original)
        if isinstance(node, ast.Constant):
            kind = {int: INT, float: FLOAT, bool: BOOL, type(None): NONE}.get(type(node.value))
            if kind is None:
                raise Unsupported('nonnumeric literal')
            return self.tagged(node, Value(kind))
        if isinstance(node, ast.Name):
            if node.id not in facts:
                if node.id in self.locals:
                    raise Unsupported('uninitialized local')
                qualified = self.builder.program.resolve(self.builder.module, node)
                if (qualified in self.builder.program.constants and self.builder.program.available(
                        self.builder.module, node, self.clone.function.lineno)):
                    return self.tagged(node, Value(INT))
                raise Unsupported('unproven local or global value')
            return self.tagged(node, replace(facts[node.id], total=True))
        if isinstance(node, ast.Attribute):
            base, value = self.expr(node.value, facts)
            if value.schema.kind not in {'owner', 'record'} or node.attr not in value.schema.fields:
                raise Unsupported('unknown attribute or optional dereference')
            index = value.schema.fields.index(node.attr)
            schema = value.schema.items[index]
            path = (*value.path, index) if value.path else None
            if not value.projected:
                raise Unsupported('record lookup without snapshot proof')
            result = ast.copy_location(ast.Subscript(value=base, slice=ast.Constant(index), ctx=ast.Load()), node)
            return self.tagged(result, Value(schema, path, projected=True, total=value.total))
        if isinstance(node, (ast.Tuple, ast.List)):
            parts = [self.expr(item, facts) for item in node.elts]
            node.elts = [item for item, _ in parts]
            values = tuple(value for _, value in parts)
            if isinstance(node, ast.Tuple):
                schema = Schema('fixed-tuple', items=tuple(value.schema for value in values))
            else:
                if not values or len({value.schema for value in values}) != 1:
                    raise Unsupported('unknown list element type')
                schema = Schema('list', items=(values[0].schema,))
            return self.tagged(node, Value(schema, owned=True, minimum=len(values), parts=values,
                                          total=all(value.total for value in values)))
        if isinstance(node, ast.Subscript):
            base, value = self.expr(node.value, facts)
            if value.schema.kind not in SEQUENCES - {'iterator'}:
                raise Unsupported('unproven indexable value')
            node.value = base
            if isinstance(node.slice, ast.Slice):
                for bound in (node.slice.lower, node.slice.upper, node.slice.step):
                    if bound is not None and not (isinstance(bound, ast.Constant) and type(bound.value) is int):
                        raise Unsupported('dynamic slice')
                if node.slice.step is not None and node.slice.step.value == 0:
                    raise Unsupported('zero slice step')
                bounds = tuple(bound.value if bound is not None else None
                               for bound in (node.slice.lower, node.slice.upper, node.slice.step))
                path = (*value.path, ('slice', *bounds)) if value.path else None
                if value.schema.kind == 'fixed-tuple':
                    selected = slice(*bounds)
                    schema = Schema('fixed-tuple', items=value.schema.items[selected])
                    return self.tagged(node, replace(value, schema=schema, path=path,
                                                     minimum=len(schema.items), parts=value.parts[selected]))
                return self.tagged(node, replace(value, path=path, minimum=0, parts=()))
            index_node, index = self.expr(node.slice, facts)
            node.slice = index_node
            if index.schema != INT:
                raise Unsupported('noninteger index')
            constant = None
            try:
                evaluated = ast.literal_eval(node.slice)
                if type(evaluated) is int:
                    constant = evaluated
            except (ValueError, TypeError):
                pass
            if value.schema.kind == 'fixed-tuple' and constant is not None:
                if not -len(value.schema.items) <= constant < len(value.schema.items):
                    raise Unsupported('invalid fixed tuple index')
                result = value.parts[constant] if value.parts else Value(value.schema.items[constant], projected=value.projected)
                return self.tagged(node, replace(result, total=value.total and index.total))
            if constant is not None and -value.minimum <= constant < value.minimum:
                pass
            elif value.path is not None:
                domain = ('constant', constant) if constant is not None else index.domain
                if domain is None:
                    raise Unsupported('unbounded computed index')
                self.builder.accesses.add(Access(value.path, domain))
            else:
                raise Unsupported('no indexed-access proof')
            result = self.item(value)
            return self.tagged(node, replace(result, total=value.total and index.total))
        if isinstance(node, ast.BinOp):
            node.left, left = self.expr(node.left, facts)
            node.right, right = self.expr(node.right, facts)
            result = self.tagged(node, self.numeric(node.op, left, right))
            if (isinstance(node.op, ast.Mult) and isinstance(node.left, ast.BinOp)
                    and isinstance(node.left.op, ast.Sub) and isinstance(node.left.left, ast.BinOp)
                    and isinstance(node.left.left.op, ast.Add)
                    and all(getattr(part, '_bcopt_numeric_kind', None) == 'int'
                            for part in (node.left.left.left, node.left.left.right, node.left.right))
                    and right.schema.kind in {'int', 'float', 'number'}):
                node._bcopt_integer_cancel_product = True
            return result
        if isinstance(node, ast.UnaryOp):
            node.operand, value = self.expr(node.operand, facts)
            if isinstance(node.op, ast.Not) and value.schema.kind in NUMERIC | SEQUENCES | {'none', 'optional'}:
                return self.tagged(node, Value(BOOL, total=value.total))
            if isinstance(node.op, (ast.UAdd, ast.USub)) and value.schema.kind in NUMERIC:
                return self.tagged(node, Value(value.schema if value.schema.kind in {'float', 'number'} else INT, total=value.total))
            raise Unsupported('unsupported unary operation')
        if isinstance(node, ast.Compare):
            parts = [self.expr(part, facts) for part in [node.left, *node.comparators]]
            for op, (_, left), (_, right) in zip(node.ops, parts, parts[1:]):
                if isinstance(op, (ast.Is, ast.IsNot)):
                    if left.schema != NONE and right.schema != NONE:
                        raise Unsupported('identity of projected values')
                elif not (isinstance(op, (ast.Eq, ast.NotEq, ast.Lt, ast.LtE, ast.Gt, ast.GtE))
                          and left.schema.kind in NUMERIC and right.schema.kind in NUMERIC):
                    raise Unsupported('custom comparison')
            node.left, node.comparators = parts[0][0], [part for part, _ in parts[1:]]
            return self.tagged(node, Value(BOOL, total=all(value.total for _, value in parts)))
        if isinstance(node, ast.BoolOp):
            parts = [self.expr(part, facts) for part in node.values]
            if not all(value.schema == BOOL for _, value in parts):
                raise Unsupported('nonboolean short circuit')
            node.values = [part for part, _ in parts]
            return self.tagged(node, Value(BOOL, total=all(value.total for _, value in parts)))
        if isinstance(node, (ast.GeneratorExp, ast.ListComp)):
            if len(node.generators) != 1:
                raise Unsupported('nested comprehension')
            comp = node.generators[0]
            if comp.is_async or comp.ifs:
                raise Unsupported('filtered comprehension')
            comp.iter, iterable = self.expr(comp.iter, facts)
            nested = dict(facts)
            self.bind(comp.target, self.item(iterable), nested)
            node.elt, element = self.expr(node.elt, nested)
            value = Value(Schema('iterator' if isinstance(node, ast.GeneratorExp) else 'list', items=(element.schema,)),
                          owned=True, minimum=iterable.minimum, total=iterable.total and element.total)
            return self.tagged(node, value)
        if isinstance(node, ast.Call):
            return self.call(node, facts)
        raise Unsupported(f'unsupported expression {type(node).__name__}')

    def call(self, node, facts):
        if any(isinstance(arg, ast.Starred) for arg in node.args) or any(kw.arg is None for kw in node.keywords):
            raise Unsupported('dynamic call arguments')
        if isinstance(node.func, ast.Attribute):
            receiver_node, receiver = self.expr(node.func.value, facts)
            if receiver.schema.kind == 'owner' and receiver.projected:
                method = self.builder.methods.get(node.func.attr)
                if method is None:
                    raise Unsupported('unknown helper method')
                signature = Signature.from_function(method, method=True)
                bound = signature.bind(node) if signature else None
                if bound is None:
                    raise Unsupported('helper argument binding')
                bound_facts = {arguments(method)[0].arg: receiver}
                replacements = {}
                for name, expression in bound.items():
                    replacement, value = self.expr(expression, facts)
                    bound_facts[name] = replace(value, total=True)
                    replacements[id(expression)] = replacement
                clone = self.builder.compile(method.name, bound_facts)
                result = ast.Call(func=ast.Name(id=clone.name, ctx=ast.Load()),
                                  args=[receiver_node, *(replacements[id(arg)] for arg in node.args)],
                                  keywords=[ast.keyword(arg=kw.arg, value=replacements[id(kw.value)]) for kw in node.keywords])
                return self.tagged(ast.copy_location(result, node), Value(clone.result, total=False))
            if receiver.owned and receiver.schema.kind == 'list' and node.func.attr in {'append', 'extend'}:
                if len(node.args) != 1 or node.keywords:
                    raise Unsupported('list mutation signature')
                argument, value = self.expr(node.args[0], facts)
                item = self.item(value) if node.func.attr == 'extend' else value
                if item.schema != receiver.schema.items[0] or item.schema.kind not in NUMERIC:
                    raise Unsupported('list mutation element')
                if isinstance(argument, ast.GeneratorExp):
                    def aliases(value):
                        return value == receiver or any(aliases(part) for part in value.parts)
                    if any(isinstance(child, ast.Name) and child.id in facts and aliases(facts[child.id])
                           for child in ast.walk(node.args[0])):
                        raise Unsupported('extend producer observes its mutable receiver')
                    argument = ast.ListComp(elt=argument.elt, generators=argument.generators)
                node.func.value, node.args = receiver_node, [argument]
                return self.tagged(node, Value(NONE, total=False))
            raise Unsupported('unknown method effects')
        if not isinstance(node.func, ast.Name) or node.func.id in facts or node.func.id in self.locals:
            raise Unsupported('unknown callable')
        name = self.builder.program.resolve(self.builder.module, node.func)
        name = name.removeprefix('builtins.') if name else name
        parts = [self.expr(arg, facts) for arg in node.args]
        if node.keywords:
            record = self.builder.program.records.get(name)
            if record is None:
                raise Unsupported('unsupported native keywords')
        else:
            record = self.builder.program.records.get(name)
        if record:
            bound = record.signature.bind(node)
            if not (record.simple and record.frozen and bound is not None):
                raise Unsupported('effectful constructor')
            keywords = [(kw, self.expr(kw.value, facts)) for kw in node.keywords]
            values = [value for _, value in parts] + [value for _, (_, value) in keywords]
            if any(value.schema.kind not in NUMERIC | {'none'} for value in values):
                raise Unsupported('projected container or record escape')
            fields = tuple(bound)
            field_types = tuple(self.expr(bound[field], facts)[1].schema for field in fields)
            node.args = [part for part, _ in parts]
            node.keywords = [ast.keyword(arg=kw.arg, value=part) for kw, (part, _) in keywords]
            return self.tagged(node, Value(Schema('result-record', name, field_types, fields), total=False))
        if node.keywords:
            raise Unsupported('native keyword arguments')
        node.args = [part for part, _ in parts]
        values = [value for _, value in parts]
        if name == 'len' and len(values) == 1 and values[0].schema.kind in SEQUENCES - {'iterator'}:
            return self.tagged(node, Value(INT, total=values[0].total))
        if name == 'zip' and values and all(value.schema.kind in SEQUENCES for value in values):
            elements = tuple(self.item(value) for value in values)
            return self.tagged(node, Value(Schema('iterator', items=(Schema('fixed-tuple', items=tuple(v.schema for v in elements)),)),
                                          parts=elements, total=all(v.total for v in values)))
        if name in {'sum', 'min', 'max', 'any', 'all'} and len(values) == 1:
            element = self.item(values[0])
            if element.schema.kind not in {'int', 'float', 'bool'}:
                raise Unsupported('nonnumeric reduction')
            if name in {'any', 'all'} and not values[0].total:
                raise Unsupported('short-circuit producer may raise')
            if isinstance(node.args[0], ast.GeneratorExp):
                gen = node.args[0]
                node.args[0] = ast.copy_location(ast.ListComp(elt=gen.elt, generators=gen.generators), gen)
            kind = BOOL if name in {'any', 'all'} else INT if name == 'sum' and element.schema == BOOL else element.schema
            if name == 'sum' and element.schema == FLOAT and not values[0].minimum:
                # Native sum returns the integer zero for an empty iterable.
                # Subsequent arithmetic must not assume an exact float.
                kind = Schema('number')
            node._bcopt_numeric_native = name
            return self.tagged(node, Value(kind, total=False))
        if name in {'min', 'max'} and len(values) == 2 and all(v.schema.kind in NUMERIC for v in values):
            if values[0].schema != values[1].schema:
                raise Unsupported('mixed scalar extrema result')
            node._bcopt_numeric_native = name
            return self.tagged(node, Value(values[0].schema, total=all(v.total for v in values)))
        if name == 'math.ceil' and 'math' not in self.builder.program.modules and len(values) == 1 and values[0].schema.kind in NUMERIC:
            node._bcopt_numeric_scalar_call = True
            return self.tagged(node, Value(INT, total=False))
        raise Unsupported(f'unknown native call {name}')

    def refined(self, test, facts, truth):
        result = dict(facts)
        if (isinstance(test, ast.Compare) and len(test.ops) == 1 and isinstance(test.left, ast.Name)
                and isinstance(test.comparators[0], ast.Constant) and test.comparators[0].value is None
                and isinstance(test.ops[0], (ast.Is, ast.IsNot)) and test.left.id in facts):
            name = test.left.id
            value = facts[name]
            is_none = truth == isinstance(test.ops[0], ast.Is)
            if value.schema.kind == 'optional':
                result[name] = replace(value, schema=NONE if is_none else value.schema.items[0])
        name = test.id if isinstance(test, ast.Name) else (
            test.operand.id if isinstance(test, ast.UnaryOp) and isinstance(test.op, ast.Not)
            and isinstance(test.operand, ast.Name) else None)
        if name in facts and facts[name].schema.kind in SEQUENCES:
            positive = truth if isinstance(test, ast.Name) else not truth
            if positive:
                result[name] = replace(facts[name], minimum=max(1, facts[name].minimum))
        return result

    def block(self, statements, facts):
        output = []
        for original in statements:
            node = copy.deepcopy(original)
            if isinstance(node, (ast.Assign, ast.AnnAssign)):
                if node.value is None:
                    raise Unsupported('uninitialized annotation')
                node.value, value = self.expr(node.value, facts)
                if value.schema.kind == 'iterator':
                    raise Unsupported('stored lazy iterator can outlive its lexical facts')
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                for target in targets:
                    self.bind(target, value, facts)
            elif isinstance(node, ast.AugAssign) and isinstance(node.target, ast.Name):
                if node.target.id not in facts:
                    raise Unsupported('uninitialized augmented assignment')
                node.value, value = self.expr(node.value, facts)
                facts[node.target.id] = replace(self.numeric(node.op, facts[node.target.id], value), total=True)
            elif isinstance(node, ast.Expr):
                node.value, _ = self.expr(node.value, facts)
            elif isinstance(node, ast.Return):
                if node.value is None:
                    value = Value(NONE)
                else:
                    node.value, value = self.expr(node.value, facts)
                if value.schema.kind not in NUMERIC | {'none', 'result-record'}:
                    raise Unsupported('snapshot-derived result escape')
                self.returns.append(value.schema)
                output.append(node)
                return output, facts, True
            elif isinstance(node, ast.If):
                node.test, condition = self.expr(node.test, facts)
                if condition.schema.kind not in NUMERIC | SEQUENCES | {'none', 'optional'}:
                    raise Unsupported('unknown truth conversion')
                node.body, yes, yt = self.block(original.body, self.refined(original.test, facts, True))
                node.orelse, no, nt = self.block(original.orelse, self.refined(original.test, facts, False))
                if yt and nt:
                    output.append(node)
                    return output, facts, True
                if yt:
                    facts = no
                elif nt:
                    facts = yes
                else:
                    joined = {}
                    for name in yes.keys() & no.keys():
                        if yes[name] == no[name]:
                            joined[name] = yes[name]
                        else:
                            schema = merge(yes[name].schema, no[name].schema)
                            joined[name] = Value(schema, projected=yes[name].projected or no[name].projected,
                                                 owned=yes[name].owned and no[name].owned,
                                                 minimum=min(yes[name].minimum, no[name].minimum))
                    facts = joined
            elif isinstance(node, ast.For) and not node.orelse:
                node.iter, iterable = self.expr(node.iter, facts)
                nested = dict(facts)
                self.bind(node.target, self.item(iterable), nested)
                before = dict(nested)
                node.body, after, terminated = self.block(node.body, nested)
                if terminated:
                    raise Unsupported('early return in numeric loop')
                for name, value in before.items():
                    if name not in after or after[name] != value:
                        raise Unsupported('numeric loop changes a loop-carried fact')
                for name in list(facts):
                    if name in after and after[name] != facts[name]:
                        schema = merge(facts[name].schema, after[name].schema)
                        facts[name] = Value(schema, projected=facts[name].projected or after[name].projected,
                                            owned=facts[name].owned and after[name].owned,
                                            minimum=min(facts[name].minimum, after[name].minimum))
            elif isinstance(node, ast.Pass):
                pass
            else:
                raise Unsupported(f'unsupported statement {type(node).__name__}')
            output.append(node)
        return output, facts, False


def fuse_integer_reductions(builder, function):
    """Fuse total indexed integer reductions under the emitted obligations.

    Empty extrema still raise at their original statement. Rebinding a captured
    table/route or crossing control flow prevents cross-gap maximum fusion.
    """
    def reduction(statement, names):
        if not (isinstance(statement, ast.Assign) and len(statement.targets) == 1
                and isinstance(statement.targets[0], ast.Name) and isinstance(statement.value, ast.Call)
                and isinstance(statement.value.func, ast.Name) and len(statement.value.args) == 1
                and not statement.value.keywords):
            return None
        consumer = builder.program.resolve(builder.module, statement.value.func)
        consumer = consumer.removeprefix('builtins.') if consumer else consumer
        if consumer not in names:
            return None
        comp = statement.value.args[0]
        if not (isinstance(comp, ast.ListComp) and len(comp.generators) == 1
                and isinstance(comp.generators[0].target, ast.Name) and not comp.generators[0].ifs
                and getattr(comp.elt, '_bcopt_numeric_kind', None) == 'int'
                and getattr(comp.elt, '_bcopt_numeric_total', False)):
            return None
        return consumer, comp

    def field(node, index):
        if (isinstance(node, ast.Subscript) and isinstance(node.slice, ast.Constant)
                and type(node.slice.value) is int and isinstance(node.value, ast.Subscript)
                and isinstance(node.value.slice, ast.Name) and node.value.slice.id == index):
            return node.value.value
        return None

    body, changed, index = function.body, 0, 0
    while index < len(body):
        group = []
        for statement in body[index:index+4]:
            match = reduction(statement, {'sum'})
            if match is None:
                break
            _, comp = match
            iterator = comp.generators[0]
            base = field(comp.elt, iterator.target.id)
            if base is None or not isinstance(iterator.iter, ast.Name):
                break
            key = ast.dump(base), ast.dump(iterator.iter)
            if group and key != group[0][3]:
                break
            group.append((statement, comp, base, key))
        if len(group) < 2:
            index += 1
            continue
        targets = [statement.targets[0].id for statement, _, _, _ in group]
        base, route = group[0][2], group[0][1].generators[0].iter
        captured = {n.id for root in (base, route) for n in ast.walk(root) if isinstance(n, ast.Name)}
        if len(set(targets)) != len(targets) or captured & set(targets):
            index += 1
            continue
        maximum = None
        for position in range(index+len(group), len(body)):
            statement = body[position]
            match = reduction(statement, {'min', 'max'})
            if match:
                consumer, comp = match
                iterator = comp.generators[0]
                expression = comp.elt
                if (isinstance(expression, ast.BinOp) and isinstance(expression.op, (ast.Add, ast.Sub, ast.Mult))
                        and ast.dump(iterator.iter) == ast.dump(route)
                        and all((candidate := field(part, iterator.target.id)) is not None
                                and ast.dump(candidate) == ast.dump(base) for part in (expression.left, expression.right))):
                    maximum = position, statement, consumer, comp
                break
            if not isinstance(statement, (ast.Assign, ast.AugAssign)) or captured & set(Bindings([statement]).counts):
                break
            # Do not cross mutation of even a fresh local alias.
            if any(isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) for n in ast.walk(statement)):
                break
        item, row = builder.fresh('index'), builder.fresh('row')
        source = '\n'.join(f'{target}=0' for target in targets)+'\n'
        if maximum:
            best, value = builder.fresh('best'), builder.fresh('value')
            source += f'{best}=None\n'
        source += f'for {item} in {ast.unparse(route)}:\n    {row}={ast.unparse(base)}[{item}]\n'
        for target, (_, comp, _, _) in zip(targets, group):
            source += f'    {target}+={row}[{comp.elt.slice.value!r}]\n'
        if maximum:
            position, statement, consumer, comp = maximum
            class RowAccess(ast.NodeTransformer):
                def visit_Subscript(self, node):
                    if (isinstance(node.slice, ast.Name) and node.slice.id == comp.generators[0].target.id
                            and ast.dump(node.value) == ast.dump(base)):
                        return ast.Name(id=row, ctx=ast.Load())
                    return self.generic_visit(node)
            expression = RowAccess().visit(copy.deepcopy(comp.elt))
            source += f'    {value}={ast.unparse(expression)}\n'
            source += f'    if {best} is None or {value} {">" if consumer == "max" else "<"} {best}:\n        {best}={value}\n'
            target = statement.targets[0].id
            replacement = ast.parse(f'{target}={ast.unparse(statement.value.func)}(()) if {best} is None else {best}\n').body[0]
            replacement._bcopt_group_extremum = True
            replacement.value.body._bcopt_numeric_scalar_call = True
            body[position] = ast.copy_location(replacement, statement)
        replacement = ast.parse(source).body
        for initialization in replacement[:-1]:
            initialization._bcopt_group_init = True
        if maximum:
            for node in ast.walk(replacement[-1]):
                if (isinstance(node, ast.Assign) and len(node.targets) == 1
                        and isinstance(node.targets[0], ast.Name) and node.targets[0].id == value):
                    node.value = copy.deepcopy(expression)
        replacement[-1]._bcopt_integer_reductions = {
            'base': copy.deepcopy(base), 'route': copy.deepcopy(route),
            'outputs': [*targets, *([best] if maximum else [])],
        }
        replacement[-1]._bcopt_integer_fields = tuple(comp.elt.slice.value for _, comp, _, _ in group)
        replacement[-1]._bcopt_integer_extremum = maximum[2] if maximum else None
        for statement in replacement:
            ast.copy_location(statement, group[0][0])
        body[index:index+len(group)] = replacement
        changed += 1
        index += len(replacement)
    return changed


def inline_numeric_helpers(builder, entry, *, helper_limit=600, output_limit=1500):
    """Inline small emitter-owned pure numeric calls, retaining return branches.

    Projected inputs and every local hold only validated primitives, private
    containers of them, or plain frozen results. Retaining renamed temporaries
    until the caller returns cannot retain arbitrary input finalizers. Borrowed
    parameters are never mutated by a certified numeric helper.
    """
    helpers = {clone.name: clone for clone in builder.clones.values() if clone is not entry}
    changed = 0

    def returns(body, target):
        output = []
        for index, statement in enumerate(body):
            if isinstance(statement, ast.Return):
                output.append(ast.copy_location(ast.Assign(targets=[copy.deepcopy(target)],
                              value=statement.value or ast.Constant(None)), statement))
                return output
            if isinstance(statement, ast.If) and any(isinstance(n, ast.Return) for n in ast.walk(statement)):
                statement.body = returns([*statement.body, *copy.deepcopy(body[index+1:])], target)
                statement.orelse = returns([*statement.orelse, *copy.deepcopy(body[index+1:])], target)
                output.append(statement)
                return output
            if any(isinstance(n, ast.Return) for n in ast.walk(statement)):
                raise Unsupported('unsupported numeric inline return control flow')
            output.append(statement)
        output.append(ast.Assign(targets=[copy.deepcopy(target)], value=ast.Constant(None)))
        return output

    class Inline(ast.NodeTransformer):
        def visit_Assign(self, node):
            nonlocal changed
            self.generic_visit(node)
            if not (len(node.targets) == 1 and isinstance(node.targets[0], ast.Name)
                    and isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Name)
                    and node.value.func.id in helpers):
                return node
            helper = helpers[node.value.func.id]
            if sum(1 for _ in ast.walk(helper.function)) > helper_limit:
                return node
            helper_locals = set(Bindings(helper.function.body).counts) | {arg.arg for arg in arguments(helper.function)}
            helper_loads = {child.id for child in ast.walk(helper.function)
                            if isinstance(child, ast.Name) and isinstance(child.ctx, ast.Load)}
            caller_locals = set(Bindings(entry.function.body).counts) | {arg.arg for arg in arguments(entry.function)}
            if (helper_loads-helper_locals) & caller_locals:
                return node  # A helper global would become a caller-local load.
            signature = Signature.from_function(helper.function)
            bound = signature.bind(node.value)
            if bound is None:
                return node
            writes = set(Bindings(helper.function.body).counts)
            names = {name: builder.fresh('local') for name in sorted(writes)}
            prefix = []
            by_expression = {id(expression): name for name, expression in bound.items()}
            ordered = [*node.value.args, *(kw.value for kw in node.value.keywords)]
            supplied = {id(expression) for expression in ordered}
            ordered.extend(expression for expression in bound.values() if id(expression) not in supplied)
            for expression in ordered:
                name = by_expression[id(expression)]
                if isinstance(expression, ast.Name) and name not in writes:
                    names[name] = expression.id
                else:
                    names[name] = builder.fresh('parameter')
                    prefix.append(ast.Assign(targets=[ast.Name(id=names[name], ctx=ast.Store())], value=copy.deepcopy(expression)))
            class Rename(ast.NodeTransformer):
                def __init__(self, mapping):
                    self.mapping = mapping
                def visit_Name(self, child):
                    if child.id in self.mapping:
                        child.id = self.mapping[child.id]
                    return child
                def visit_ListComp(self, child):
                    nested = dict(self.mapping)
                    for generator in child.generators:
                        generator.iter = Rename(nested).visit(generator.iter)
                        nested.update({target.id: builder.fresh('comprehension') for target in ast.walk(generator.target)
                                       if isinstance(target, ast.Name)})
                        generator.target = Rename(nested).visit(generator.target)
                        generator.ifs = [Rename(nested).visit(condition) for condition in generator.ifs]
                    child.elt = Rename(nested).visit(child.elt)
                    return child
                visit_GeneratorExp = visit_ListComp
            body = [Rename(names).visit(copy.deepcopy(statement)) for statement in helper.function.body]
            replacement = [*prefix, *returns(body, node.targets[0])]
            if sum(1 for statement in replacement for _ in ast.walk(statement)) > output_limit:
                return node
            for statement in replacement:
                ast.copy_location(statement, node)
            changed += 1
            return replacement
    entry.function = ast.fix_missing_locations(Inline().visit(entry.function))
    return changed


def emit_argument_guards(builder, entry, *, types_proven=False):
    """Precompute snapshot bounds per region, then validate original arguments.

    Missing optional subgraphs have no obligations: dereferences were accepted
    only after path refinement in the numeric clone. Minimum lengths across all
    wildcard rows are conservative, including for negative indices.
    """
    params = {name: value for name, value in entry.arguments.items() if value.schema.kind != 'owner'}
    domains = [('items' if value.schema.kind == 'tuple' else 'scalar', name) for name, value in params.items()]
    indices = {domain: index for index, domain in enumerate(domains)}
    arguments_ = {name: f'arg{index}' for index, name in enumerate(params)}
    builtin = builder.fresh('guard_builtins')
    lengths = builder.fresh('lengths')
    prepare = builder.fresh('bounds')
    check = builder.fresh('arguments')
    body = [f'    bounds=[None]*{len(domains)}']
    deferred = []
    for access in sorted(builder.accesses, key=lambda a: repr((a.path, a.domain))):
        if access.path[0] == 'arg':
            if len(access.path) != 2 or access.path[1] not in params or params[access.path[1]].schema.kind != 'tuple':
                raise Unsupported('unsupported argument access path')
            deferred.append(access)
            continue
        if access.path[0] != 'root':
            raise Unsupported('unknown snapshot path')
        path = tuple(None if component == '*' else component for component in access.path[1:])
        body.append(f'    sizes={lengths}(data,{path!r})')
        body.append('    if sizes:')
        if access.domain[0] == 'constant':
            body.extend([f'        if not -min(sizes)<={access.domain[1]!r}<min(sizes):', '            return None'])
        else:
            if access.domain not in indices:
                raise Unsupported('unbound access domain')
            index = indices[access.domain]
            body.extend(['        size=min(sizes)',
                         f'        bounds[{index}]=size if bounds[{index}] is None else min(bounds[{index}],size)'])
    body.append('    return tuple(bounds)')
    nodes = ast.parse(f'''import builtins as {builtin}
def {lengths}(data,path,len={builtin}.len,tuple={builtin}.tuple,type={builtin}.type,slice={builtin}.slice):
    values=[data]
    for component in path:
        following=[]
        for value in values:
            if value is None:
                continue
            if component is None:
                following.extend(value)
            elif type(component) is tuple:
                following.append(value[slice(*component[1:])])
            else:
                following.append(value[component])
        values=following
    return tuple(len(value) for value in values if value is not None)
def {prepare}(data,min={builtin}.min,tuple={builtin}.tuple):
'''+ '\n'.join(body)+'\n').body
    body = ['    if bounds is None:', '        return False']
    if not types_proven:
        for name, value in params.items():
            argument = arguments_[name]
            expected = {'int': 'int', 'float': 'float', 'bool': 'bool', 'tuple': 'tuple'}[value.schema.kind]
            body.extend([f'    if type({argument}) is not {expected}:', '        return False'])
    for index, (domain, name) in enumerate(domains):
        argument = arguments_[name]
        if domain == 'items':
            body.append(f'    bound=bounds[{index}]')
            if types_proven:
                body.extend(['    if bound is not None:', f'        for item in {argument}:',
                             '            if not -bound<=item<bound:', '                return False'])
            else:
                body.extend([f'    for item in {argument}:',
                             '        if type(item) is not int or bound is not None and not -bound<=item<bound:',
                             '            return False'])
        else:
            body.extend([f'    if bounds[{index}] is not None and not -bounds[{index}]<={argument}<bounds[{index}]:',
                         '        return False'])
    for access in deferred:
        sequence = arguments_[access.path[1]]
        domain, name = access.domain
        if domain == 'constant':
            body.extend([f'    if not -len({sequence})<={name!r}<len({sequence}):', '        return False'])
        elif domain == 'scalar' and name in arguments_:
            body.extend([f'    if not -len({sequence})<={arguments_[name]}<len({sequence}):', '        return False'])
        elif domain == 'items' and name in arguments_:
            body.extend([f'    for item in {arguments_[name]}:',
                         f'        if not -len({sequence})<=item<len({sequence}):', '            return False'])
        else:
            raise Unsupported('unknown deferred index domain')
    body.append('    return True')
    used = {node.id for node in ast.walk(ast.parse('\n'.join(line[4:] for line in body))) if isinstance(node, ast.Name)}
    signature = ','.join(['bounds', *arguments_.values(), *(f'{name}={builtin}.{name}'
                          for name in ('type', 'int', 'float', 'bool', 'tuple', 'len') if name in used)])
    nodes.extend(ast.parse(f'def {check}({signature}):\n'+'\n'.join(body)+'\n').body)
    return prepare, check, tuple(params), ast.fix_missing_locations(ast.Module(body=nodes, type_ignores=[]))
