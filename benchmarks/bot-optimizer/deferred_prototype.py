"""REJECTED research prototype: deferred record allocation changes shared keys.

Preserved for reproducibility; this is not invoked by the compiler. Exact primitive
guards do not suffice: skipped allocations change shared dictionary-key history,
observable when a retained record later receives finalizer-bearing field values.
"""

import ast
import copy

from tools.bot_optimizer.analysis import Bindings, arguments
from tools.bot_optimizer.model import Change
from tools.bot_optimizer.records import used_names


class DeferredRecords:
    def __init__(self, program, module, options):
        self.program, self.module, self.options = program, module, options
        self.names = used_names(program.modules[module].tree)
        self.changes = []
        self.helpers = []
        self.type_name = self.fresh('type')
        self.method_name = self.fresh('method_type')
        self.primitive_names = {name: self.fresh(name) for name in
                                ('int', 'float', 'bool', 'str', 'bytes', 'complex', 'tuple')}

    def fresh(self, stem):
        index = 0
        while f'_bcopt_defer_{stem}_{index}' in self.names:
            index += 1
        name = f'_bcopt_defer_{stem}_{index}'
        self.names.add(name)
        return name

    def apply(self, tree):
        if ('deferred-record' in self.options.disabled or 'types' in self.program.modules
                or self.program.dynamic_modules or self.program._cyclic_imports()):
            return tree
        for owner in tree.body:
            if (not isinstance(owner, ast.ClassDef) or owner.bases or owner.keywords
                    or owner.decorator_list or owner.type_params
                    or self.program.modules[self.module].declarations.get(owner.name) is not owner):
                continue
            class_bindings = Bindings(owner.body)
            methods = {n.name: n for n in owner.body if isinstance(n, ast.FunctionDef)
                       and not n.decorator_list and not n.type_params and class_bindings.counts[n.name] == 1}
            for caller in list(methods.values()):
                self.transform(owner, caller, methods)
        if not self.changes:
            return tree
        helpers = ast.parse(f'from builtins import type as {self.type_name}\n'
                            f'from types import MethodType as {self.method_name}\n').body + self.helpers
        helpers.insert(0, ast.ImportFrom(module='builtins', names=[
            ast.alias(name=name, asname=alias) for name, alias in self.primitive_names.items()], level=0))
        index = 0
        if (tree.body and isinstance(tree.body[0], ast.Expr)
                and isinstance(tree.body[0].value, ast.Constant)
                and isinstance(tree.body[0].value.value, str)):
            index = 1
        while index < len(tree.body) and isinstance(tree.body[index], ast.ImportFrom) and tree.body[index].module == '__future__':
            index += 1
        tree.body[index:index] = helpers
        return tree

    def producer(self, node):
        if (node.args.defaults or any(value is not None for value in node.args.kw_defaults)
                or node.args.vararg or node.args.kwarg or not node.body
                or any(arg.arg.startswith('__') and not arg.arg.endswith('__') for arg in arguments(node))
                or not isinstance(node.body[-1], ast.Return)):
            return None
        parts = list(ast.walk(node))
        if any(isinstance(n, (ast.Global, ast.Nonlocal, ast.Delete, ast.NamedExpr,
                              ast.Yield, ast.YieldFrom, ast.Await, ast.Lambda, ast.ClassDef,
                              ast.AsyncFunctionDef, ast.Try, ast.TryStar)) or isinstance(n, ast.FunctionDef) and n is not node
               for n in parts):
            return None
        if any(isinstance(n, ast.Name) and (n.id.startswith('__') or n.id == 'super')
               or isinstance(n, ast.Attribute) and n.attr.startswith('__') for n in parts):
            return None  # Includes __class__/super closure and class name mangling.
        returns = [n for n in parts if isinstance(n, ast.Return)
                   and n.value is not None and not (isinstance(n.value, ast.Constant) and n.value.value is None)]
        if len(returns) != 1 or returns[0] is not node.body[-1] or not isinstance(returns[0].value, ast.Call):
            return None
        call = returns[0].value
        bindings = Bindings(node.body)
        locals_ = set(bindings.counts) | {arg.arg for arg in arguments(node)}
        root = call.func
        while isinstance(root, ast.Attribute):
            root = root.value
        if not isinstance(root, ast.Name) or root.id in locals_:
            return None
        record = self.program.records.get(self.program.resolve(self.module, call.func))
        if (record is None or not record.simple or not record.frozen or not 4 <= len(record.fields) <= 20
                or not self.program.available(self.module, call.func, node.lineno)):
            return None
        primitives = {}
        for statement in record.node.body:
            if not isinstance(statement, ast.AnnAssign):
                continue
            annotation = statement.annotation
            if isinstance(annotation, ast.Constant) and isinstance(annotation.value, str):
                try:
                    annotation = ast.parse(annotation.value, mode='eval').body
                except SyntaxError:
                    return None
            resolved = self.program.resolve(record.module, annotation)
            if resolved and resolved.startswith('builtins.'):
                resolved = resolved.removeprefix('builtins.')
            if resolved not in {'int', 'float', 'bool', 'str', 'bytes', 'complex'}:
                return None
            primitives[statement.target.id] = resolved
        if set(primitives) != set(record.fields):
            return None
        bound = record.signature.bind(call)
        if bound is None or set(bound) != set(record.fields):
            return None
        # Local reads known bound on reaching this final return cannot be changed
        # by a callback (no escaping cells/reflection). One other expression may
        # be evaluated first into a temporary; there are no later failing reads.
        definite = {arg.arg for arg in arguments(node)}
        for statement in node.body[:-1]:
            if isinstance(statement, ast.Assign):
                for target in statement.targets:
                    definite.update(n.id for n in ast.walk(target)
                                    if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store))
            elif isinstance(statement, ast.AnnAssign) and statement.value is not None and isinstance(statement.target, ast.Name):
                definite.add(statement.target.id)
        effectful = []
        for value in [*call.args, *(kw.value for kw in call.keywords)]:
            if isinstance(value, ast.Name):
                if value.id not in definite:
                    return None
            elif not isinstance(value, ast.Constant):
                effectful.append(value)
        if len(effectful) > 1:
            return None
        return record, call, bound, effectful, primitives

    def transform(self, owner, caller, methods):
        bindings = Bindings(caller.body)
        locals_ = set(bindings.counts) | {arg.arg for arg in arguments(caller)}
        if owner.name in locals_ or bindings.external:
            return
        parts = list(ast.walk(caller))
        if any(isinstance(n, (ast.Nonlocal, ast.Global, ast.NamedExpr)) for n in parts):
            return
        parents = {child: parent for parent in parts for child in ast.iter_child_nodes(parent)}
        for binding in caller.body:
            if (not isinstance(binding, ast.Assign) or len(binding.targets) != 1
                    or not isinstance(binding.targets[0], ast.Name)
                    or not isinstance(binding.value, ast.Attribute)
                    or not isinstance(binding.value.value, ast.Name)):
                continue
            alias = binding.targets[0].id
            producer = methods.get(binding.value.attr)
            if producer is None or producer is caller or bindings.counts[alias] != 1:
                continue
            description = self.producer(producer)
            if description is None:
                continue
            record, construction, bound, effectful, primitives = description
            loads = [n for n in parts if isinstance(n, ast.Name) and n.id == alias and isinstance(n.ctx, ast.Load)]
            if len(loads) != 1:
                continue
            invoke = parents.get(loads[0])
            assignment = parents.get(invoke)
            if (not isinstance(invoke, ast.Call) or invoke.func is not loads[0]
                    or not isinstance(assignment, ast.Assign) or assignment.value is not invoke
                    or len(assignment.targets) != 1 or not isinstance(assignment.targets[0], ast.Name)):
                continue
            result = assignment.targets[0].id
            loop = parents.get(assignment)
            if not isinstance(loop, ast.For) or assignment not in loop.body or bindings.counts[result] != 1:
                continue
            index = loop.body.index(assignment)
            if index + 1 >= len(loop.body):
                continue
            check = loop.body[index + 1]
            if not (isinstance(check, ast.If) and not check.orelse and len(check.body) == 1
                    and isinstance(check.body[0], ast.Continue) and isinstance(check.test, ast.Compare)
                    and isinstance(check.test.left, ast.Name) and check.test.left.id == result
                    and len(check.test.ops) == 1 and isinstance(check.test.ops[0], ast.Is)
                    and isinstance(check.test.comparators[0], ast.Constant) and check.test.comparators[0].value is None):
                continue
            tail = ast.Module(body=loop.body[index:], type_ignores=[])
            allowed = set(ast.walk(tail))
            if any(isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda,
                                  ast.For, ast.While, ast.Try, ast.With, ast.Match,
                                  ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)) for n in allowed):
                continue
            accesses, escapes = [], []
            valid = True
            for use in (n for n in parts if isinstance(n, ast.Name) and n.id == result and isinstance(n.ctx, ast.Load)):
                parent = parents.get(use)
                if use not in allowed:
                    valid = False
                    break
                if parent is check.test:
                    continue
                if isinstance(parent, ast.Attribute) and parent.value is use and parent.attr in record.fields and isinstance(parent.ctx, ast.Load):
                    accesses.append(parent)
                    continue
                call = parent if isinstance(parent, ast.Call) else parents.get(parent) if isinstance(parent, ast.keyword) else None
                statement = parents.get(call)
                if isinstance(call, ast.Call) and isinstance(statement, ast.Assign) and statement.value is call:
                    sink = self.program.records.get(self.program.resolve(self.module, call.func))
                    root = call.func
                    while isinstance(root, ast.Attribute):
                        root = root.value
                    if (sink and sink.simple and sink.frozen and isinstance(root, ast.Name)
                            and root.id not in locals_ and sink.signature.bind(call) is not None):
                        escapes.append(statement)
                        continue
                valid = False
                break
            if not valid or len(escapes) != 1 or not accesses:
                continue
            escape = escapes[0]
            if any((n.lineno, n.col_offset) >= (escape.lineno, escape.col_offset) for n in accesses):
                continue
            # Only conditional retention is profitable; never rewrite an always
            # materialized result, which loses in the guest allocation fixtures.
            parent = parents.get(escape)
            if not isinstance(parent, ast.If) or escape not in parent.body:
                continue
            before = ast.unparse(caller)
            flag = self.fresh('fast')
            carrier_flag = self.fresh('carrier')
            clone_name, unpack_name, packed = self.fresh('producer'), self.fresh('unpack'), self.fresh('packed')
            clone = copy.deepcopy(producer)
            clone.name, clone.decorator_list, clone.returns = clone_name, [], None
            for arg in arguments(clone):
                arg.annotation = None
            values = {field: copy.deepcopy(value) for field, value in bound.items()}
            extra = []
            if effectful:
                temporary = self.fresh('value')
                extra = [ast.Assign(targets=[ast.Name(id=temporary, ctx=ast.Store())], value=copy.deepcopy(effectful[0]))]
                for field, value in bound.items():
                    if value is effectful[0]:
                        values[field] = ast.Name(id=temporary, ctx=ast.Load())
            # An instance's shared dict-key order can differ from declaration
            # order. Do not scalarize finalizer-bearing payloads: annotations
            # select runtime checks, never supply trusted type facts.
            checks = []
            for primitive in dict.fromkeys(primitives.values()):
                fields = [field for field in record.fields if primitives[field] == primitive]
                types = [ast.Call(func=ast.Name(id=self.type_name, ctx=ast.Load()),
                                  args=[copy.deepcopy(values[field])], keywords=[]) for field in fields]
                checks.append(ast.Compare(left=types[0], ops=[ast.Is() for _ in fields],
                    comparators=[*types[1:], ast.Name(id=self.primitive_names[primitive], ctx=ast.Load())]))
            condition = checks[0] if len(checks) == 1 else ast.BoolOp(op=ast.And(), values=checks)
            clone.body[-1:] = [*extra, ast.If(test=condition, body=[ast.Return(value=ast.Tuple(
                elts=[copy.deepcopy(values[field]) for field in reversed(record.fields)], ctx=ast.Load()))], orelse=[]),
                ast.Return(value=ast.Call(func=copy.deepcopy(construction.func),
                    args=[copy.deepcopy(values[field]) for field in record.fields], keywords=[]))]
            arguments_ = [ast.Subscript(value=ast.Name(id=packed, ctx=ast.Load()),
                                       slice=ast.Constant(-i - 1), ctx=ast.Load()) for i in range(len(record.fields))]
            unpack = ast.FunctionDef(name=unpack_name, args=ast.arguments(posonlyargs=[], args=[ast.arg(arg=packed)],
                vararg=None, kwonlyargs=[], kw_defaults=[], kwarg=None, defaults=[]),
                body=[ast.Return(value=ast.Call(func=copy.deepcopy(construction.func), args=arguments_, keywords=[]))],
                decorator_list=[], returns=None, type_params=[])
            self.helpers.extend([clone, ast.copy_location(ast.fix_missing_locations(unpack), producer)])
            guard = ast.parse(f'{flag} = {self.type_name}({alias}) is {self.method_name} and '
                              f'{alias}.__func__ is {owner.name}.{producer.name}\n'
                              f'if {flag}:\n    {alias} = {self.method_name}({clone_name}, {alias}.__self__)\n').body
            at = caller.body.index(binding)
            caller.body[at + 1:at + 1] = guard
            loop.body.insert(index + 2, ast.parse(f'{carrier_flag} = {flag} and '
                f'{self.type_name}({result}) is {self.primitive_names["tuple"]}').body[0])
            selected = set(accesses)

            class Consumer(ast.NodeTransformer):
                def visit_Attribute(self, node):
                    if node not in selected:
                        return self.generic_visit(node)
                    return ast.copy_location(ast.IfExp(test=ast.Name(id=carrier_flag, ctx=ast.Load()),
                        body=ast.Subscript(value=ast.Name(id=result, ctx=ast.Load()),
                            slice=ast.Constant(-record.fields.index(node.attr) - 1), ctx=ast.Load()),
                        orelse=copy.deepcopy(node)), node)

                def visit_Assign(self, node):
                    if node is not escape:
                        return self.generic_visit(node)
                    materialize = ast.parse(f'if {carrier_flag}:\n    {result} = {unpack_name}({result})\n').body[0]
                    return [ast.copy_location(materialize, node), node]

            Consumer().visit(caller)
            self.changes.append(Change('deferred-record', assignment.lineno, before,
                                       ast.unparse(ast.fix_missing_locations(caller))))
            return  # One guarded producer per caller for this deliberately narrow pass.
