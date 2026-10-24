"""Discover, guard, and emit source-derived numeric consumer specializations."""

import ast
import copy

from .analysis import Bindings, arguments
from .consumer_regions import ConsumerProof
from .effects import CallbackEffects
from .model import Change
from .numeric_regions import NumericClones, Unsupported, emit_argument_guards
from .program import Signature
from .records import used_names
from .region_types import RegionSchemas, SnapshotEmitter


def reference(program, module, qualified):
    """Find an existing lexical binding, never add a speculative source import."""
    info = program.modules[module]
    for name in info.declarations:
        if f'{module}.{name}' == qualified:
            return name
    for name, (target, _) in info.imports.items():
        if qualified == target or qualified.startswith(target+'.'):
            return name+qualified[len(target):]
    raise Unsupported(f'missing region dependency binding: {qualified}')


class NumericRegions:
    def __init__(self, program, options):
        self.program, self.options = program, options
        self.schemas, self.effects = RegionSchemas(program), CallbackEffects(program)
        self.changes = {name: [] for name in program.modules}
        self.rejections = []

    def apply(self):
        if 'numeric-consumer-regions' in self.options.disabled:
            return
        # Discovery runs on pristine source before ordinary passes mutate methods.
        sites = []
        for module, info in self.program.modules.items():
            for function in ast.walk(info.tree):
                if not isinstance(function, ast.FunctionDef) or not function.body:
                    continue
                tail = function.body[-1]
                if not (isinstance(tail, ast.Return) and isinstance(tail.value, ast.Call)
                        and isinstance(tail.value.func, ast.Attribute) and isinstance(tail.value.func.value, ast.Name)):
                    continue
                call, local = tail.value, tail.value.func.value.id
                if Bindings(function.body).counts[local] != 1:
                    continue
                constructor = next((statement.value for statement in function.body[:-1]
                                    if isinstance(statement, ast.Assign) and len(statement.targets) == 1
                                    and isinstance(statement.targets[0], ast.Name) and statement.targets[0].id == local
                                    and isinstance(statement.value, ast.Call)), None)
                if constructor is None:
                    continue
                qualified = self.program.resolve(module, constructor.func)
                owner = self.schemas.owner(qualified) if qualified else None
                if owner is not None:
                    sites.append((module, function, tail, owner))
        for module, function, tail, owner in sites:
            try:
                generated = self.prepare(module, function, tail.value, owner)
            except Unsupported as error:
                self.rejections.append((module, function.name, str(error)))
                continue
            if generated is None:
                continue
            builder, consumer, callback_node, owner_nodes, caller_nodes, replacement = generated
            owner_tree = self.program.modules[builder.module].tree
            declaration = self.schemas.declaration(owner.name)[1]
            index = owner_tree.body.index(declaration)+1
            owner_tree.body[index:index] = owner_nodes
            caller_tree = self.program.modules[module].tree
            index = caller_tree.body.index(callback_node)+1
            caller_tree.body[index:index] = caller_nodes
            before = ast.unparse(tail.value)
            tail.value = ast.copy_location(replacement, tail.value)
            detail = (f'{owner.name}.{consumer}: AST-derived numeric methods {sorted(builder.required_methods)}, '
                      f'{len(builder.accesses)} access obligations, {builder.fusions} reduction fusions')
            self.changes[builder.module].append(Change('numeric-consumer-regions', declaration.lineno, detail,
                                                       f'guarded primitive-copy consumer {owner_nodes[-1].name} with original fallback'))
            self.changes[module].append(Change('numeric-consumer-regions', tail.lineno, before, ast.unparse(replacement)))
        for info in self.program.modules.values():
            ast.fix_missing_locations(info.tree)

    def prepare(self, module, caller, call, owner):
        owner_module, declaration = self.schemas.declaration(owner.name)
        methods = {node.name: node for node in declaration.body if isinstance(node, ast.FunctionDef)}
        consumer = methods.get(call.func.attr)
        if consumer is None:
            return None
        signature = Signature.from_function(consumer, method=True)
        bound = signature.bind(call) if signature else None
        if bound is None:
            raise Unsupported('consumer callsite signature')
        # Each value must have been explicitly supplied. No default is re-evaluated.
        supplied = {id(value) for value in [*call.args, *(kw.value for kw in call.keywords)]}
        params = [arg.arg for arg in arguments(consumer)[1:]]
        if set(bound) != set(params) or any(id(value) not in supplied for value in bound.values()):
            raise Unsupported('consumer callsite omits arguments')
        callback = None
        for name, expression in bound.items():
            qualified = self.program.resolve(module, expression)
            effect = self.effects.false_continuation(qualified) if qualified else None
            if effect:
                if callback:
                    raise Unsupported('multiple region callbacks')
                callback = name, expression, effect
        if callback is None:
            return None
        callback_name, callback_expression, effect = callback
        callback_info = self.program.functions[effect.function]
        if callback_info.module != module or callback_info.node not in self.program.modules[module].tree.body:
            raise Unsupported('callback must have a local unconditional definition')
        local_names = set(Bindings(caller.body).counts) | {arg.arg for arg in arguments(caller)}
        if Bindings(caller.body).external or any(isinstance(node, ast.Nonlocal) for node in ast.walk(caller)):
            raise Unsupported('consumer callsite has externally rebound locals')
        for expression in bound.values():
            resolved = self.program.resolve(module, expression)
            inert_literal = isinstance(expression, ast.Constant) and type(expression.value) in {int, float, bool, type(None)}
            retained_local = isinstance(expression, ast.Name) and expression.id in local_names
            if not (inert_literal or retained_local or resolved == effect.function or resolved in self.program.constants):
                # The dispatch wrapper must not extend a new arbitrary argument's
                # lifetime across its original callee. Local arguments remain
                # owned by the suspended source caller; constants/functions are
                # stable module-owned objects under the closed-world contract.
                raise Unsupported('consumer callsite creates an unowned argument temporary')
        root = callback_expression
        while isinstance(root, ast.Attribute):
            root = root.value
        if not isinstance(root, ast.Name) or root.id in local_names:
            raise Unsupported('callback binding is locally shadowed')
        # Candidate names come only from owner method loads in the consumer.
        candidates = {node.attr for node in ast.walk(consumer) if isinstance(node, ast.Attribute)
                      and isinstance(node.value, ast.Name) and node.value.id == arguments(consumer)[0].arg}
        for method in sorted(candidates & methods.keys()):
            try:
                taken = used_names(self.program.modules[owner_module].tree)
                builder = NumericClones(self.program, self.schemas, owner, taken)
                entry = builder.entry(method)
                proof = ConsumerProof(builder, entry).consumer(consumer.name, callback_name)
                return self.emit(module, call, builder, entry, proof, consumer, callback_name, callback_info.node, effect)
            except Unsupported as error:
                self.rejections.append((owner.name, method, str(error)))
        return None

    def emit(self, module, call, builder, entry, proof, consumer, callback_name, callback_node, effect):
        # Numeric calls have inert argument loads. Guarding them cannot duplicate
        # producer calls, mutations, or reference-count-sensitive temporaries.
        for node in proof.numeric_calls:
            if any(not isinstance(value, (ast.Name, ast.Constant))
                   for value in [*node.args, *(kw.value for kw in node.keywords)]):
                raise Unsupported('numeric dispatch arguments require prior binding')
        refs = {}
        def collect(schema):
            if schema.kind in {'owner', 'record'}:
                refs[schema.name] = reference(self.program, builder.module, schema.name)
            for item in schema.items:
                collect(item)
        collect(builder.owner)
        extra = []
        for name in sorted(proof.records):
            schema = self.schemas.record(name)
            if schema is None:
                raise Unsupported('consumer record namespace cannot be guarded')
            extra.append(schema)
            collect(schema)
        snapshots = SnapshotEmitter(builder.taken, refs)
        root, failed, validators = snapshots.emit(builder.owner, extra)
        builder.taken.update(snapshots.taken)
        prepare, check, params, guards = emit_argument_guards(builder, entry, types_proven=True)
        builtins, method_type = builder.fresh('builtins'), builder.fresh('method_type')
        enter, clone_name = builder.fresh('enter'), builder.fresh('consumer')
        state, data, bounds, live = (builder.fresh(name) for name in ('state', 'data', 'limits', 'live'))
        index_error = builder.fresh('index_error')
        entry.function._bcopt_index_retry = (index_error, failed)
        owner_ref = refs[builder.owner.name]
        captured = {name: builder.fresh('method') for name in sorted(proof.methods)}
        functions = {name: (reference(self.program, builder.module, name), builder.fresh('function'))
                     for name in sorted(proof.functions)}
        declaration = self.schemas.declaration(builder.owner.name)[1]
        for ref in [*refs.values(), *(ref for ref, _ in functions.values())]:
            expression = ast.parse(ref, mode='eval').body
            root_name = ref.split('.')[0]
            imported = self.program.modules[builder.module].imports.get(root_name)
            schema_class = self.schemas.declaration(self.program.resolve(builder.module, expression))
            class_available = schema_class is not None and imported and imported[1] < declaration.end_lineno+1
            if not (class_available or self.program.available(builder.module, expression, declaration.end_lineno+1)):
                raise Unsupported('region dependency is defined after its emission point')
        prelude = f'import builtins as {builtins}\nfrom types import MethodType as {method_type}\n'
        prelude += f'{index_error}={builtins}.IndexError\n'
        prelude += ''.join(f'{alias}={owner_ref}.{name}\n' for name, alias in captured.items())
        prelude += ''.join(f'{alias}={ref}\n' for ref, alias in functions.values())
        guard_source = f'''def {enter}(original,_type={builtins}.type,_get={builtins}.type.__getattribute__,_object={builtins}.object):
    if _type(original) is not {method_type} or original.__func__ is not {captured[consumer.name]}:
        return None
    owner=original.__self__
    data={root}(owner)
    if data is {failed}:
        return None
    namespace=_get({owner_ref},'__dict__')
    instance=_object.__getattribute__(owner,'__dict__')
'''
        for name, alias in captured.items():
            guard_source += f'    if namespace.get({name!r}) is not {alias} or {name!r} in instance:\n        return None\n'
        for ref, alias in functions.values():
            guard_source += f'    if {ref} is not {alias}:\n        return None\n'
        guard_source += f'    return data,{prepare}(data)\n'
        clone = copy.deepcopy(proof.consumer_node)
        clone.name, clone.returns, clone.type_comment = clone_name, None, None
        for arg in arguments(clone):
            arg.annotation = arg.type_comment = None
        clone.args.defaults = []
        clone.args.kw_defaults = [None for _ in clone.args.kwonlyargs]
        clone.args.kwonlyargs.append(ast.arg(arg=state))
        clone.args.kw_defaults.append(None)
        numeric_locations = {(node.lineno, node.col_offset) for node in proof.numeric_calls}
        callback_locations = {(node.lineno, node.col_offset) for node in proof.callback_tests}
        signature = Signature.from_function(builder.methods[entry.method], method=True)
        class Dispatch(ast.NodeTransformer):
            def visit_Assign(self, node):
                if (isinstance(node.value, ast.Call) and (node.value.lineno, node.value.col_offset) in numeric_locations
                        and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name)):
                    original = copy.deepcopy(node.value)
                    fast = ast.Call(func=ast.Name(id=entry.name, ctx=ast.Load()),
                                    args=[ast.Name(id=data, ctx=ast.Load()), *copy.deepcopy(original.args)],
                                    keywords=copy.deepcopy(original.keywords))
                    node.value = ast.IfExp(test=ast.Name(id=live, ctx=ast.Load()), body=fast, orelse=original)
                    target = node.targets[0].id
                    retry = ast.If(test=ast.BoolOp(op=ast.And(), values=[ast.Name(id=live, ctx=ast.Load()),
                        ast.Compare(left=ast.Name(id=target, ctx=ast.Load()), ops=[ast.Is()],
                                    comparators=[ast.Name(id=failed, ctx=ast.Load())])]),
                        body=[ast.Assign(targets=copy.deepcopy(node.targets), value=copy.deepcopy(original))], orelse=[])
                    return [node, ast.copy_location(retry, node)]
                return self.generic_visit(node)
            def visit_Call(self, node):
                if (node.lineno, node.col_offset) not in numeric_locations:
                    return self.generic_visit(node)
                arguments_ = signature.bind(node)
                condition = ast.BoolOp(op=ast.And(), values=[ast.Name(id=live, ctx=ast.Load()),
                    ast.Call(func=ast.Name(id=check, ctx=ast.Load()),
                             args=[ast.Name(id=bounds, ctx=ast.Load()), *(copy.deepcopy(arguments_[name]) for name in params)], keywords=[])])
                fast = ast.Call(func=ast.Name(id=entry.name, ctx=ast.Load()),
                               args=[ast.Name(id=data, ctx=ast.Load()), *copy.deepcopy(node.args)], keywords=copy.deepcopy(node.keywords))
                return ast.copy_location(ast.IfExp(test=condition, body=fast, orelse=node), node)
            def visit_If(self, node):
                self.generic_visit(node)
                if (node.lineno, node.col_offset) in callback_locations:
                    node.body[:0] = ast.parse(f'{live}=False').body
                return node
        clone = Dispatch().visit(clone)
        clone.body[:0] = ast.parse(f'{data},{bounds}={state}\n{live}=True\n').body
        owner_nodes = [*ast.parse(prelude).body, *validators.body, *guards.body,
                       *ast.parse(guard_source).body, *(value.function for value in builder.clones.values()), clone]
        # A callsite wrapper evaluates the original bound method and every source
        # argument exactly once, in source order, before doing any speculation.
        caller_taken = used_names(self.program.modules[module].tree) | builder.taken
        def fresh(stem):
            index = 0
            while f'_bcopt_region_{stem}_{index}' in caller_taken:
                index += 1
            name = f'_bcopt_region_{stem}_{index}'
            caller_taken.add(name)
            return name
        dispatcher, caller_builtins = fresh('dispatch'), fresh('builtins')
        import_source = f'import builtins as {caller_builtins}\n'
        if module != builder.module:
            import_source += f'from {builder.module} import {enter}, {clone_name}\n'
        values = [*call.args, *(keyword.value for keyword in call.keywords)]
        replacements = {id(value): f'arg{index}' for index, value in enumerate(values)}
        bound = Signature.from_function(consumer, method=True).bind(call)
        forwarded = ','.join([*(replacements[id(value)] for value in call.args),
                              *(f'{kw.arg}={replacements[id(kw.value)]}' for kw in call.keywords)])
        callback_value = replacements[id(bound[callback_name])]
        callback_ref = reference(self.program, module, effect.function)
        defaults = [f'_callback={callback_ref}', f'_type={caller_builtins}.type']
        conditions = [f'{callback_value} is _callback']
        for name in effect.constants:
            conditions.append(f'_type({reference(self.program, module, name)}) is {caller_builtins}.int')
        for index, name in enumerate(effect.sdk_calls):
            ref = reference(self.program, module, name)
            defaults.append(f'_sdk{index}={ref}')
            conditions.append(f'{ref} is _sdk{index}')
        for param in arguments(consumer)[1:]:
            if param.arg == callback_name:
                continue
            schema = self.schemas.annotation(builder.module, param.annotation)
            conditions.append(f'_type({replacements[id(bound[param.arg])]}) is {caller_builtins}.{schema.kind}')
        args = ','.join(['original', *replacements.values(), *defaults])
        source = f'''def {dispatcher}({args}):
    if {' and '.join(conditions)}:
        state={enter}(original)
        if state is not None:
            return {clone_name}(original.__self__,{forwarded},{state}=state)
    return original({forwarded})
'''
        caller_nodes = ast.parse(import_source+source).body
        replacement = ast.Call(func=ast.Name(id=dispatcher, ctx=ast.Load()),
                               args=[copy.deepcopy(call.func), *copy.deepcopy(values)], keywords=[])
        return builder, consumer.name, callback_node, owner_nodes, caller_nodes, replacement


def finish_numeric_regions(tree):
    """After ordinary passes, add exception-only native index fallback.

    The numeric emitter's obligations make every moved operation total except
    native indexed access. Certified clones cannot mutate borrowed data or invoke
    callbacks. Retrying the original on IndexError therefore restores its error
    order and list/tuple error wording, including a skipped short-circuit access.
    Consumer type proofs remain mandatory; this is not a custom-index fallback.
    """
    for node in tree.body:
        contract = getattr(node, '_bcopt_index_retry', None)
        if contract is None:
            continue
        exception, failed = contract
        node.body = [ast.Try(body=node.body, handlers=[ast.ExceptHandler(
            type=ast.Name(id=exception, ctx=ast.Load()), name=None,
            body=[ast.Return(value=ast.Name(id=failed, ctx=ast.Load()))])], orelse=[], finalbody=[])]
    return ast.fix_missing_locations(tree)
