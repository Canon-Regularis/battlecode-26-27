"""General record specialisation; no bot-specific names or algorithms.

Exact ordinary frozen dataclasses can populate their dict in one native update.
Subclasses retain the original per-field object.__setattr__ semantics. A separate
small escape analysis removes a record used only by the immediately next return.
"""

import ast
import copy

from .analysis import Bindings, Fact, UNKNOWN, annotation_fact, arguments, infer
from .model import Change


def used_names(tree):
    result = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
    result.update(n.arg for n in ast.walk(tree) if isinstance(n, ast.arg))
    result.update(n.name for n in ast.walk(tree)
                  if isinstance(n, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)))
    result.update(a.asname or a.name for n in ast.walk(tree)
                  if isinstance(n, (ast.Import, ast.ImportFrom)) for a in n.names)
    result.update(Bindings(tree.body).counts)
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            result.update(Bindings(node.body).counts)
    return result


class RecordSpecializer(ast.NodeTransformer):
    def __init__(self, program, module, options):
        self.program, self.module, self.options = program, module, options
        self.changes = []
        self.names = used_names(program.modules[module].tree)
        self.helpers = {}
        self.function = None
        self.locals = []

    def fresh(self, stem):
        index = 0
        while f"_bcopt_{stem}_{index}" in self.names:
            index += 1
        name = f"_bcopt_{stem}_{index}"
        self.names.add(name)
        return name

    def helper(self, name):
        if name not in self.helpers:
            self.helpers[name] = self.fresh(name)
        return ast.Name(id=self.helpers[name], ctx=ast.Load())

    def visit_Module(self, node):
        node = self.generic_visit(node)
        if self.helpers:
            imports = ast.ImportFrom(module="builtins", names=[
                ast.alias(name=name, asname=alias) for name, alias in self.helpers.items()
            ], level=0)
            index = 0
            if (node.body and isinstance(node.body[0], ast.Expr)
                    and isinstance(node.body[0].value, ast.Constant) and isinstance(node.body[0].value.value, str)):
                index = 1
            while (index < len(node.body) and isinstance(node.body[index], ast.ImportFrom)
                   and node.body[index].module == "__future__"):
                index += 1
            node.body.insert(index, imports)
        return node

    def visit_ClassDef(self, node):
        if node.type_params:
            return node
        record = self.program.records.get(f"{self.module}.{node.name}")
        # The index contains top-level classes only, never a same-named nested class.
        indexed = record is not None and record.node is node
        node = self.generic_visit(node)
        if (not indexed or not record.simple or not record.frozen
                or len(record.fields) < self.options.min_bulk_fields
                or "record-bulk-init" in self.options.disabled):
            return node
        before = ast.unparse(node)
        receiver = ast.Name(id="self", ctx=ast.Load())
        dictionary = ast.Attribute(value=copy.deepcopy(receiver), attr="__dict__", ctx=ast.Load())
        update = ast.Expr(value=ast.Call(
            func=ast.Attribute(value=dictionary, attr="update", ctx=ast.Load()),
            args=[ast.Dict(keys=[ast.Constant(name) for name in record.fields],
                           values=[ast.Name(id=name, ctx=ast.Load()) for name in record.fields])], keywords=[],
        ))
        fallback = [ast.Expr(value=ast.Call(
            func=ast.Attribute(value=self.helper("object"), attr="__setattr__", ctx=ast.Load()),
            args=[copy.deepcopy(receiver), ast.Constant(name), ast.Name(id=name, ctx=ast.Load())], keywords=[],
        )) for name in record.fields]
        condition = ast.Compare(
            left=ast.Call(func=self.helper("type"), args=[copy.deepcopy(receiver)], keywords=[]),
            ops=[ast.Is()], comparators=[ast.Name(id="__class__", ctx=ast.Load())],
        )
        initializer = ast.FunctionDef(
            name="__init__", args=ast.arguments(posonlyargs=[], args=[ast.arg(arg="self"),
                *(ast.arg(arg=name) for name in record.fields)], vararg=None,
                kwonlyargs=[], kw_defaults=[], kwarg=None, defaults=[]),
            body=[ast.If(test=condition, body=[update], orelse=fallback)],
            decorator_list=[], returns=None, type_params=[],
        )
        node.body.append(initializer)
        # Populate metadata inside the class, before @dataclass inspects the
        # signature/docstring. Use actual field annotations (including future
        # strings), never evaluate their source expressions a second time.
        annotations = ast.Assign(targets=[ast.Attribute(value=ast.Name(id="__init__", ctx=ast.Load()),
            attr="__annotations__", ctx=ast.Store())], value=ast.Dict(
                keys=[*(ast.Constant(name) for name in record.fields), ast.Constant("return")],
                values=[*(ast.Subscript(value=ast.Name(id="__annotations__", ctx=ast.Load()),
                    slice=ast.Constant(name), ctx=ast.Load())
                    for name in record.fields), ast.Constant(None)],
            ))
        node.body.append(ast.copy_location(annotations, node))
        after = ast.unparse(ast.fix_missing_locations(node))
        self.changes.append(Change("record-bulk-init", node.lineno, before, after))
        return node

    def visit_FunctionDef(self, node):
        if node.type_params:
            return node
        saved = self.function
        self.function = node
        bindings = Bindings(node.body)
        local = set(bindings.counts) | bindings.external | {arg.arg for arg in arguments(node)}
        self.locals.append(local)
        node = self.generic_visit(node)
        if "scalar-record" not in self.options.disabled:
            body = []
            index = 0
            escaped = {name for child in ast.walk(node) if isinstance(child, ast.Nonlocal) for name in child.names}
            facts = {}
            if self.options.trust_annotations:
                facts.update({arg.arg: annotation_fact(arg.annotation, lambda n: self.program.resolve(self.module, n))
                              for arg in arguments(node) if arg.annotation and not bindings.counts[arg.arg]
                              and arg.arg not in bindings.external | escaped})
            while index < len(node.body):
                replacement = (self.scalar_pair(node, node.body[index], node.body[index + 1], bindings, facts)
                               if index + 1 < len(node.body) else None)
                if replacement:
                    body.extend(replacement)
                    index += 2
                else:
                    statement = node.body[index]
                    body.append(statement)
                    if isinstance(statement, (ast.Assign, ast.AnnAssign)):
                        value = statement.value
                        targets = statement.targets if isinstance(statement, ast.Assign) else [statement.target]
                        fact = self.primitive_fact(value, facts)
                        for target in targets:
                            if (isinstance(target, ast.Name) and bindings.counts[target.id] == 1
                                    and target.id not in bindings.external | escaped):
                                facts[target.id] = fact
                    index += 1
            node.body = body
        self.locals.pop()
        self.function = saved
        return node

    def visit_AsyncFunctionDef(self, node):
        return node

    def primitive_fact(self, node, facts):
        if isinstance(node, ast.Constant) and type(node.value) in {float, bool, str, bytes, complex, type(None)}:
            return Fact("primitive")
        def resolve(expression):
            root = expression
            while isinstance(root, ast.Attribute):
                root = root.value
            if isinstance(root, ast.Name) and any(root.id in scope for scope in self.locals):
                return None
            return self.program.resolve(self.module, expression)
        return infer(node, facts, resolve)

    def scalar_pair(self, function, assignment, consumer, bindings, facts):
        if (not isinstance(assignment, ast.Assign) or len(assignment.targets) != 1
                or not isinstance(assignment.targets[0], ast.Name)
                or not isinstance(assignment.value, ast.Call) or not isinstance(consumer, ast.Return)):
            return None
        target = assignment.targets[0]
        name = target.id
        if (name.startswith("__") or bindings.counts[name] != 1 or name in bindings.external
                or name in {arg.arg for arg in arguments(function)}):
            return None
        call = assignment.value
        root = call.func
        while isinstance(root, ast.Attribute):
            root = root.value
        if not isinstance(root, ast.Name) or any(root.id in scope for scope in self.locals):
            return None
        record = self.program.records.get(self.program.resolve(self.module, call.func))
        if (record is None or not record.simple
                or not self.program.available(self.module, call.func, function.lineno)):
            return None
        bound = record.signature.bind(call)
        if bound is None or set(bound) != set(record.fields):
            return None
        # Removing a record can change finalizer/refcount-observable lifetimes of
        # arbitrary field objects. Only finalizer-free primitive values qualify.
        for value in bound.values():
            fact = self.primitive_fact(value, facts)
            if fact.kind not in {"int", "primitive"} and not (fact.kind == "tuple" and fact.item == "int"):
                return None
        if any(isinstance(n, (ast.Lambda, ast.GeneratorExp, ast.ListComp, ast.SetComp, ast.DictComp))
               for n in ast.walk(consumer)):
            return None
        accesses = [n for n in ast.walk(consumer) if isinstance(n, ast.Attribute)
                    and isinstance(n.value, ast.Name) and n.value.id == name
                    and isinstance(n.ctx, ast.Load) and n.attr in record.fields]
        if not accesses:
            return None
        allowed = {id(target), *(id(n.value) for n in accesses)}
        # Includes nested scopes: captures, aliasing, later reads and finally/
        # exception uses all make this record escape and prohibit elimination.
        if any(isinstance(n, ast.Name) and n.id == name and id(n) not in allowed for n in ast.walk(function)):
            return None
        locals_by_field = {field: self.fresh("field") for field in record.fields}
        evaluations = []
        ordered = [*zip(record.fields, call.args), *((kw.arg, kw.value) for kw in call.keywords)]
        for field, value in ordered:
            evaluations.append(ast.copy_location(ast.Assign(
                targets=[ast.Name(id=locals_by_field[field], ctx=ast.Store())],
                value=copy.deepcopy(value),
            ), assignment))

        class Replace(ast.NodeTransformer):
            def visit_Attribute(self, node):
                if isinstance(node.value, ast.Name) and node.value.id == name:
                    return ast.copy_location(ast.Name(id=locals_by_field[node.attr], ctx=ast.Load()), node)
                return self.generic_visit(node)

        replacement = [*evaluations, Replace().visit(copy.deepcopy(consumer))]
        before = ast.unparse(ast.Module(body=[assignment, consumer], type_ignores=[]))
        after = ast.unparse(ast.fix_missing_locations(ast.Module(body=replacement, type_ignores=[])))
        self.changes.append(Change("scalar-record", assignment.lineno, before, after))
        return replacement
