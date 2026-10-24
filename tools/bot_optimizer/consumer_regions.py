"""Closed-world effect proofs for consumers of guarded numeric methods.

Annotations never prove consumer types. Facts originate in a validated owner,
checked scalar arguments, native constructors, or the numeric emitter's result
contract. Mutable container cells carry aliasing through branches and loops. A
worklist solves their element types before accepting the whole consumer epoch.
Unknown calls, borrowed mutation, and custom operators reject specialization.
"""

import ast
from dataclasses import dataclass

from .analysis import Bindings, arguments
from .numeric_regions import Unsupported
from .program import Signature, body_without_docstring


@dataclass(frozen=True)
class Shape:
    kind: str
    name: str = ''
    items: tuple = ()
    fields: tuple = ()
    owned: bool = False


class Cell:
    def __init__(self, *shapes):
        self.shapes = set(shapes)


SCALARS = {'int', 'float', 'bool', 'none'}
NUMBERS = SCALARS - {'none'}
SEQUENCES = {'list', 'tuple', 'set', 'frozenset', 'iterator'}


class ConsumerProof:
    def __init__(self, builder, entry):
        self.builder, self.entry = builder, entry
        self.program, self.module = builder.program, builder.module
        self.rules = []
        self.changed = False
        self.methods = set(builder.required_methods)
        self.functions = set()
        self.records = set()
        self.callback_tests = set()
        self.numeric_calls = set()
        self.active = set()
        self.schema_cache = {}
        self.consumer_node = None

    def add(self, cell, *shapes):
        previous = len(cell.shapes)
        cell.shapes.update(shapes)
        self.changed |= previous != len(cell.shapes)

    def flow(self, source, destination, exclude=()):
        self.rules.append(lambda: self.add(destination, *(shape for shape in source.shapes if shape.kind not in exclude)))

    def joined(self, *sources):
        result = Cell()
        for source in sources:
            self.flow(source, result)
        return result

    def schema(self, schema):
        if schema in self.schema_cache:
            return self.schema_cache[schema]
        result = Cell()
        self.schema_cache[schema] = result
        if schema.kind == 'optional':
            self.flow(self.schema(schema.items[0]), result)
            self.add(result, Shape('none'))
        elif schema.kind == 'number':
            self.add(result, Shape('int'), Shape('float'))
        elif schema.kind == 'fixed-tuple':
            result.shapes.add(Shape('tuple', items=(self.joined(*(self.schema(item) for item in schema.items)),)))
        else:
            kind = 'record' if schema.kind == 'result-record' else schema.kind
            if kind == 'record':
                self.records.add(schema.name)
            result.shapes.add(Shape(kind, schema.name, tuple(self.schema(item) for item in schema.items), schema.fields))
        return result

    def elements(self, iterable):
        result = Cell()
        def rule():
            for shape in tuple(iterable.shapes):
                if shape.kind in SEQUENCES | {'dict'}:
                    self.add(result, *shape.items[0].shapes)
                elif shape.kind == 'pair':
                    self.add(result, *(item for cell in shape.items for item in cell.shapes))
                else:
                    raise Unsupported('consumer custom iteration')
        self.rules.append(rule)
        return result

    def require(self, value, kinds, reason):
        def rule():
            if any(shape.kind not in kinds for shape in value.shapes):
                raise Unsupported(reason)
        self.rules.append(rule)

    def scalar(self, kind):
        return Cell(Shape(kind))

    def solve(self):
        for _ in range(128):
            self.changed = False
            previous = len(self.rules)
            for rule in tuple(self.rules):
                rule()
            if not self.changed and previous == len(self.rules):
                return
            if len(self.rules) > 10000:
                break
        raise Unsupported('consumer type worklist budget')

    def consumer(self, method, callback):
        node = self.builder.methods[method]
        self.consumer_node = node
        facts = {}
        params = arguments(node)
        for parameter in params:
            if parameter is params[0]:
                facts[parameter.arg] = self.schema(self.builder.owner)
            elif parameter.arg == callback:
                facts[parameter.arg] = Cell(Shape('callback'))
            else:
                schema = self.builder.schemas.annotation(self.module, parameter.annotation) if parameter.annotation else None
                if schema is None or schema.kind not in NUMBERS:
                    raise Unsupported('unchecked consumer parameter')
                facts[parameter.arg] = self.schema(schema)
        self.analyze(node, self.module, facts, method=method)
        self.solve()
        if not self.numeric_calls or not self.callback_tests:
            raise Unsupported('no repeated numeric/callback consumer')
        return self

    def analyze(self, node, module, facts, method=None):
        key = module, node.name
        if key in self.active or len(self.active) > 12:
            raise Unsupported('recursive consumer helper')
        if node.decorator_list or node.type_params or node.args.vararg or node.args.kwarg:
            raise Unsupported('consumer helper signature')
        if node is not self.consumer_node and any(
                not isinstance(default, ast.Constant) or type(default.value) not in {int, float, bool, type(None)}
                for default in [*node.args.defaults, *(value for value in node.args.kw_defaults if value is not None)]):
            raise Unsupported('consumer helper has a shared or effectful default')
        if method:
            self.methods.add(method)
        self.active.add(key)
        result, yielded = Cell(), Cell()
        scope = Scope(self, module, node, result, yielded)
        _, terminated = scope.block(body_without_docstring(node.body), facts)
        if not terminated:
            self.add(result, Shape('none'))
        self.active.remove(key)
        if any(isinstance(n, ast.Yield) for n in ast.walk(node)):
            return Cell(Shape('iterator', items=(yielded,)))
        return result


class Scope:
    def __init__(self, proof, module, node, result, yielded):
        self.p, self.module, self.node = proof, module, node
        self.result, self.yielded = result, yielded
        self.locals = set(Bindings(node.body).counts) | {arg.arg for arg in arguments(node)}
        self.callback_test = None
        self.loops = []

    def resolve(self, node):
        root = node
        while isinstance(root, ast.Attribute):
            root = root.value
        if not isinstance(root, ast.Name) or root.id in self.locals:
            return None
        return self.p.program.resolve(self.module, node)

    def bind(self, target, value, facts):
        if isinstance(target, ast.Name):
            facts[target.id] = value
            return
        if isinstance(target, (ast.Tuple, ast.List)):
            cells = [Cell() for _ in target.elts]
            def rule():
                for shape in value.shapes:
                    if shape.kind != 'pair' or len(shape.items) != len(cells):
                        raise Unsupported('consumer unpacking shape')
                    for source, destination in zip(shape.items, cells):
                        self.p.add(destination, *source.shapes)
            self.p.rules.append(rule)
            for child, cell in zip(target.elts, cells):
                self.bind(child, cell, facts)
            return
        if isinstance(target, ast.Subscript):
            container, key = self.expr(target.value, facts), self.expr(target.slice, facts)
            self.hashable(key)
            def rule():
                for shape in container.shapes:
                    if shape.kind != 'dict' or not shape.owned:
                        raise Unsupported('consumer borrowed container mutation')
                    self.p.add(shape.items[0], *key.shapes)
                    self.p.add(shape.items[1], *value.shapes)
            self.p.rules.append(rule)
            return
        raise Unsupported('consumer nonlocal mutation')

    def hashable(self, value):
        seen = set()
        def check(cell):
            if id(cell) in seen:
                return
            seen.add(id(cell))
            for shape in cell.shapes:
                if shape.kind in NUMBERS | {'none'}:
                    continue
                if shape.kind in {'tuple', 'pair', 'frozenset'}:
                    for item in shape.items:
                        check(item)
                else:
                    raise Unsupported('consumer custom hashing/comparison')
        def rule():
            seen.clear()
            check(value)
        self.p.rules.append(rule)

    def expr(self, node, facts):
        p = self.p
        if isinstance(node, ast.Constant):
            kind = {int: 'int', float: 'float', bool: 'bool', type(None): 'none'}.get(type(node.value))
            if kind is None:
                raise Unsupported('consumer literal type')
            return p.scalar(kind)
        if isinstance(node, ast.Name):
            if node.id in facts:
                return facts[node.id]
            if node.id in self.locals:
                raise Unsupported('uninitialized consumer local')
        qualified = self.resolve(node)
        if qualified in p.program.constants:
            return p.scalar('int')
        if qualified in p.program.records:
            return Cell(Shape('constructor', qualified))
        if qualified in p.program.functions:
            return Cell(Shape('function', qualified))
        if isinstance(node, ast.Name) and qualified in {
                'len', 'range', 'min', 'max', 'sum', 'sorted', 'frozenset', 'tuple', 'list', 'zip'}:
            return Cell(Shape('native', qualified))
        if isinstance(node, ast.Attribute):
            base, result = self.expr(node.value, facts), Cell()
            def rule():
                for shape in base.shapes:
                    if shape.kind in {'owner', 'record'}:
                        if node.attr in shape.fields:
                            p.add(result, *shape.items[shape.fields.index(node.attr)].shapes)
                        elif shape.kind == 'owner' and node.attr in p.builder.methods:
                            p.add(result, Shape('method', node.attr, (base,)))
                        else:
                            raise Unsupported('consumer unknown record attribute')
                    elif shape.kind == 'dict' and node.attr in {'get', 'items', 'values'}:
                        p.add(result, Shape('bound-native', node.attr, (base,)))
                    else:
                        raise Unsupported(f'consumer custom attribute lookup: {ast.unparse(node)} on {shape.kind}')
            p.rules.append(rule)
            return result
        if isinstance(node, (ast.List, ast.Tuple)):
            values = tuple(self.expr(child, facts) for child in node.elts)
            # Keep explicit tuple shapes for destructuring, homogenize on iteration.
            if isinstance(node, ast.Tuple) and len(values) > 1:
                return Cell(Shape('pair', items=values))
            return Cell(Shape('list' if isinstance(node, ast.List) else 'tuple',
                              items=(p.joined(*values),), owned=isinstance(node, ast.List)))
        if isinstance(node, ast.Dict):
            if any(key is None for key in node.keys):
                raise Unsupported('consumer dictionary expansion')
            keys = p.joined(*(self.expr(key, facts) for key in node.keys))
            self.hashable(keys)
            return Cell(Shape('dict', items=(keys, p.joined(*(self.expr(value, facts) for value in node.values))), owned=True))
        if isinstance(node, (ast.DictComp, ast.ListComp, ast.GeneratorExp)):
            nested = dict(facts)
            for generator in node.generators:
                if generator.is_async:
                    raise Unsupported('async consumer comprehension')
                self.bind(generator.target, p.elements(self.expr(generator.iter, nested)), nested)
                for condition in generator.ifs:
                    self.truth(self.expr(condition, nested))
            if isinstance(node, ast.DictComp):
                key, value = self.expr(node.key, nested), self.expr(node.value, nested)
                self.hashable(key)
                return Cell(Shape('dict', items=(key, value), owned=True))
            return Cell(Shape('list' if isinstance(node, ast.ListComp) else 'iterator',
                              items=(self.expr(node.elt, nested),), owned=True))
        if isinstance(node, ast.Subscript):
            base, result = self.expr(node.value, facts), Cell()
            if isinstance(node.slice, ast.Slice):
                for bound in (node.slice.lower, node.slice.upper, node.slice.step):
                    if bound is not None:
                        p.require(self.expr(bound, facts), {'int'}, 'consumer custom slice bound')
                def rule():
                    for shape in base.shapes:
                        if shape.kind not in {'list', 'tuple'}:
                            raise Unsupported('consumer custom slice')
                        p.add(result, shape)
                p.rules.append(rule)
            else:
                key = self.expr(node.slice, facts)
                self.hashable(key)
                def rule():
                    for shape in base.shapes:
                        if shape.kind in {'list', 'tuple'}:
                            if any(k.kind != 'int' for k in key.shapes):
                                raise Unsupported('consumer custom sequence index')
                            p.add(result, *shape.items[0].shapes)
                        elif shape.kind == 'dict':
                            p.add(result, *shape.items[1].shapes)
                        else:
                            raise Unsupported('consumer custom index')
                p.rules.append(rule)
            return result
        if isinstance(node, ast.BinOp):
            left, right, result = self.expr(node.left, facts), self.expr(node.right, facts), Cell()
            elements = Cell()
            sequence = Shape('tuple', items=(elements,))
            def rule():
                for a in left.shapes:
                    for b in right.shapes:
                        if a.kind in NUMBERS and b.kind in NUMBERS:
                            if not isinstance(node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Mod, ast.FloorDiv)):
                                raise Unsupported('consumer numeric operator')
                            p.add(result, Shape('float' if isinstance(node.op, ast.Div) or 'float' in {a.kind, b.kind} else 'int'))
                        elif a.kind == b.kind == 'tuple' and isinstance(node.op, ast.Add):
                            p.add(elements, *a.items[0].shapes, *b.items[0].shapes)
                            p.add(result, sequence)
                        else:
                            raise Unsupported('consumer custom arithmetic')
            p.rules.append(rule)
            return result
        if isinstance(node, ast.UnaryOp):
            value = self.expr(node.operand, facts)
            if isinstance(node.op, ast.Not):
                self.truth(value)
                return p.scalar('bool')
            if isinstance(node.op, (ast.UAdd, ast.USub)):
                p.require(value, NUMBERS, 'consumer custom unary operation')
                return value
        if isinstance(node, ast.Compare):
            values = [self.expr(part, facts) for part in [node.left, *node.comparators]]
            for op, left, right in zip(node.ops, values, values[1:]):
                if isinstance(op, (ast.Is, ast.IsNot)):
                    continue
                if isinstance(op, (ast.In, ast.NotIn)):
                    self.hashable(left)
                    self.hashable(p.elements(right))
                else:
                    p.require(left, NUMBERS, 'consumer custom comparison')
                    p.require(right, NUMBERS, 'consumer custom comparison')
            return p.scalar('bool')
        if isinstance(node, ast.BoolOp):
            values, nested = [], dict(facts)
            for value in node.values:
                values.append(self.expr(value, nested))
                nested = self.refined(value, nested, isinstance(node.op, ast.And))
            for value in values:
                self.truth(value)
            return p.joined(*values)
        if isinstance(node, ast.Call):
            return self.call(node, facts)
        if isinstance(node, ast.Yield):
            p.flow(self.expr(node.value, facts), self.yielded)
            return p.scalar('none')
        raise Unsupported(f'consumer expression {type(node).__name__}')

    def truth(self, value):
        self.p.require(value, SCALARS | SEQUENCES | {'dict', 'pair', 'record', 'owner'}, 'consumer custom truth')

    def call(self, node, facts):
        p = self.p
        if any(isinstance(arg, ast.Starred) for arg in node.args) or any(kw.arg is None for kw in node.keywords):
            raise Unsupported('consumer expanded call')
        callee = self.expr(node.func, facts)
        args = [self.expr(arg, facts) for arg in node.args]
        keywords = {kw.arg: (kw.value if isinstance(kw.value, ast.Lambda) else self.expr(kw.value, facts)) for kw in node.keywords}
        result, seen = Cell(), set()
        callback_test = self.callback_test
        def rule():
            for shape in tuple(callee.shapes):
                if shape in seen:
                    continue
                seen.add(shape)
                if shape.kind == 'callback':
                    def truth_tail(expression):
                        if expression is node:
                            return True
                        if isinstance(expression, ast.BoolOp):
                            choices = expression.values[-1:] if isinstance(expression.op, ast.And) else expression.values
                            return any(truth_tail(value) for value in choices)
                        return False
                    if (args or keywords or callback_test is None or self.node is not p.consumer_node
                            or not truth_tail(callback_test.test)):
                        raise Unsupported('callback outside terminating-condition guard')
                    p.callback_tests.add(callback_test)
                    p.add(result, Shape('bool'))
                elif shape.kind in {'method', 'function'}:
                    if shape.kind == 'method' and shape.name == p.entry.method:
                        signature = Signature.from_function(p.builder.methods[shape.name], method=True)
                        bound = signature.bind(node)
                        if bound is None or self.node is not p.consumer_node:
                            raise Unsupported('numeric consumer call binding')
                        actual = {id(expression): value for expression, value in zip(node.args, args)}
                        actual.update({id(kw.value): keywords[kw.arg] for kw in node.keywords})
                        for name, expression in bound.items():
                            value = actual[id(expression)] if id(expression) in actual else self.expr(expression, facts)
                            expected = p.entry.arguments[name].schema
                            p.require(value, {expected.kind}, 'numeric consumer argument type')
                            if expected.kind == 'tuple':
                                p.require(p.elements(value), {'int'}, 'numeric consumer tuple element type')
                        p.numeric_calls.add(node)
                        p.flow(p.schema(p.entry.result), result)
                        continue
                    if shape.kind == 'method':
                        function, module = p.builder.methods[shape.name], p.module
                    else:
                        info = p.program.functions[shape.name]
                        function, module = info.node, info.module
                        p.functions.add(shape.name)
                    signature = Signature.from_function(function, method=shape.kind == 'method')
                    bound = signature.bind(node) if signature else None
                    if bound is None:
                        raise Unsupported('consumer helper binding')
                    actual = {id(expression): value for expression, value in zip(node.args, args)}
                    actual.update({id(kw.value): keywords[kw.arg] for kw in node.keywords})
                    bound_facts = {name: actual[id(expression)] if id(expression) in actual else self.expr(expression, facts)
                                   for name, expression in bound.items()}
                    if shape.kind == 'method':
                        bound_facts[arguments(function)[0].arg] = shape.items[0]
                    value = p.analyze(function, module, bound_facts, method=shape.name if shape.kind == 'method' else None)
                    p.flow(value, result)
                elif shape.kind == 'constructor':
                    record = p.program.records[shape.name]
                    bound = record.signature.bind(node)
                    if not record.simple or not record.frozen or bound is None:
                        raise Unsupported('consumer effectful record construction')
                    actual = {id(expression): value for expression, value in zip(node.args, args)}
                    actual.update({id(kw.value): keywords[kw.arg] for kw in node.keywords})
                    fields = tuple(bound)
                    values = tuple(actual[id(bound[name])] if id(bound[name]) in actual else self.expr(bound[name], facts)
                                   for name in fields)
                    p.records.add(shape.name)
                    p.add(result, Shape('record', shape.name, values, fields))
                elif shape.kind == 'native':
                    p.flow(self.native(shape.name, args, keywords, facts), result)
                elif shape.kind == 'bound-native':
                    base = shape.items[0]
                    def bound_rule(shape=shape, base=base):
                        for container in base.shapes:
                            if container.kind != 'dict' or keywords:
                                raise Unsupported('consumer native method')
                            if shape.name == 'get' and len(args) in {1, 2}:
                                p.add(result, *container.items[1].shapes)
                                p.add(result, *(args[1].shapes if len(args) == 2 else {Shape('none')}))
                            elif shape.name in {'items', 'values'} and not args:
                                element = container.items[1] if shape.name == 'values' else Cell(Shape('pair', items=container.items))
                                # Cache the shape: worklist rounds must not allocate new cells.
                                cached = getattr(bound_rule, 'cached', {})
                                if container not in cached:
                                    cached[container] = Shape('iterator', items=(element,))
                                bound_rule.cached = cached
                                p.add(result, cached[container])
                            else:
                                raise Unsupported('consumer native method signature')
                    if shape.name == 'get' and args:
                        self.hashable(args[0])
                    p.rules.append(bound_rule)
                else:
                    raise Unsupported('unknown consumer callable')
        p.rules.append(rule)
        return result

    def native(self, name, args, keywords, facts):
        p = self.p
        if name == 'len' and len(args) == 1 and not keywords:
            p.require(args[0], SEQUENCES - {'iterator'} | {'dict', 'pair'}, 'consumer custom length')
            return p.scalar('int')
        if name == 'range' and 1 <= len(args) <= 3 and not keywords:
            for value in args:
                p.require(value, {'int'}, 'consumer custom range argument')
            return Cell(Shape('iterator', items=(p.scalar('int'),)))
        if name in {'frozenset', 'tuple', 'list'} and len(args) == 1 and not keywords:
            elements = p.elements(args[0])
            if name == 'frozenset':
                self.hashable(elements)
            return Cell(Shape(name, items=(elements,), owned=name == 'list'))
        if name in {'min', 'max', 'sum'} and args and set(keywords) <= {'default'}:
            values = p.elements(args[0]) if len(args) == 1 else p.joined(*args)
            p.require(values, NUMBERS, 'consumer custom reduction')
            return p.joined(values, *keywords.values(), *([p.scalar('int')] if name == 'sum' else []))
        if name == 'sorted' and len(args) == 1 and set(keywords) <= {'key', 'reverse'}:
            values = p.elements(args[0])
            if 'reverse' in keywords:
                p.require(keywords['reverse'], {'bool'}, 'consumer custom sort flag')
            if 'key' in keywords:
                key = keywords['key']
                if not isinstance(key, ast.Lambda) or len(arguments(key)) != 1:
                    raise Unsupported('consumer custom sorting callback')
                nested = dict(facts)
                nested[arguments(key)[0].arg] = values
                values_for_order = self.expr(key.body, nested)
            else:
                values_for_order = values
            p.require(values_for_order, NUMBERS, 'consumer custom sorting key')
            return Cell(Shape('list', items=(values,), owned=True))
        raise Unsupported(f'consumer unsupported native {name}')

    def refined(self, test, facts, truth):
        result = dict(facts)
        if (isinstance(test, ast.Compare) and len(test.ops) == 1 and isinstance(test.left, ast.Name)
                and isinstance(test.comparators[0], ast.Constant) and test.comparators[0].value is None
                and isinstance(test.ops[0], (ast.Is, ast.IsNot)) and test.left.id in facts):
            name = test.left.id
            is_none = truth == isinstance(test.ops[0], ast.Is)
            if not is_none:
                result[name] = Cell()
                self.p.flow(facts[name], result[name], exclude={'none'})
            else:
                result[name] = self.p.scalar('none')
        return result

    def block(self, statements, facts):
        p = self.p
        for node in statements:
            if isinstance(node, (ast.Assign, ast.AnnAssign)):
                value = self.expr(node.value, facts)
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                for target in targets:
                    self.bind(target, value, facts)
            elif isinstance(node, ast.AugAssign) and isinstance(node.target, ast.Name):
                value = self.expr(ast.BinOp(left=ast.Name(id=node.target.id, ctx=ast.Load()), op=node.op, right=node.value), facts)
                self.bind(node.target, value, facts)
            elif isinstance(node, ast.Expr):
                self.expr(node.value, facts)
            elif isinstance(node, ast.If):
                previous, self.callback_test = self.callback_test, node
                self.truth(self.expr(node.test, facts))
                self.callback_test = previous
                yes, yt = self.block(node.body, self.refined(node.test, dict(facts), True))
                no, nt = self.block(node.orelse, self.refined(node.test, dict(facts), False))
                if yt and nt:
                    return facts, True
                if yt:
                    facts = no
                elif nt:
                    facts = yes
                else:
                    facts = {name: p.joined(yes[name], no[name]) for name in yes.keys() & no.keys()}
            elif isinstance(node, ast.For) and not node.orelse:
                assigned = set(Bindings(node.body).counts) | set(Bindings([node.target]).counts)
                nested = dict(facts)
                carried = {name: p.joined(facts[name]) for name in assigned & facts.keys()}
                nested.update(carried)
                self.bind(node.target, p.elements(self.expr(node.iter, facts)), nested)
                self.loops.append([])
                after, _ = self.block(node.body, nested)
                exits = self.loops.pop()
                for name, cell in carried.items():
                    for state in [after, *exits]:
                        if name in state:
                            p.flow(state[name], cell)
                    facts[name] = cell
            elif isinstance(node, ast.Return):
                p.flow(self.expr(node.value, facts) if node.value else p.scalar('none'), self.result)
                return facts, True
            elif isinstance(node, (ast.Break, ast.Continue)):
                if not self.loops:
                    raise Unsupported('consumer jump outside loop')
                self.loops[-1].append(dict(facts))
                return facts, True
            elif not isinstance(node, ast.Pass):
                raise Unsupported(f'consumer statement {type(node).__name__}')
        return facts, False
