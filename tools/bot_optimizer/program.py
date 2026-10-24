"""Read-only whole-folder symbol/signature index. Bot modules are never imported.

This is intentionally not Python's dynamic import machinery: ambiguous imports,
rebinding, decorators, inheritance and unsupported record layouts stay unknown.
"""

import ast
from dataclasses import dataclass, field

from .analysis import Bindings, arguments, infer


def body_without_docstring(body):
    if (body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant)
            and isinstance(body[0].value.value, str)):
        return body[1:]
    return body


@dataclass
class Signature:
    positional: tuple[str, ...]
    posonly: int = 0
    kwonly: tuple[str, ...] = ()
    optional: frozenset[str] = frozenset()
    variadic: bool = False

    @classmethod
    def from_function(cls, node, *, method=False):
        args = node.args
        positional = tuple(arg.arg for arg in [*args.posonlyargs, *args.args])
        posonly = len(args.posonlyargs)
        optional = set(positional[len(positional) - len(args.defaults):]) if args.defaults else set()
        optional.update(arg.arg for arg, value in zip(args.kwonlyargs, args.kw_defaults) if value is not None)
        if method:
            if not positional:
                return None
            positional = positional[1:]
            posonly = max(0, posonly - 1)
        return cls(positional, posonly, tuple(arg.arg for arg in args.kwonlyargs),
                   frozenset(optional), bool(args.vararg or args.kwarg))

    def bind(self, call):
        """Map valid, explicit arguments to parameters; do not repair invalid calls."""
        if (self.variadic or len(call.args) > len(self.positional)
                or any(isinstance(arg, ast.Starred) for arg in call.args)
                or any(kw.arg is None for kw in call.keywords)):
            return None
        result = dict(zip(self.positional, call.args))
        allowed = set(self.positional[self.posonly:]) | set(self.kwonly)
        for keyword in call.keywords:
            if keyword.arg not in allowed or keyword.arg in result:
                return None
            result[keyword.arg] = keyword.value
        required = (set(self.positional) | set(self.kwonly)) - self.optional
        return result if required <= result.keys() else None


@dataclass
class Function:
    name: str
    module: str
    node: ast.FunctionDef
    signature: Signature
    expression: ast.expr | None = None


@dataclass
class Record:
    name: str
    module: str
    node: ast.ClassDef
    fields: tuple[str, ...]
    signature: Signature
    frozen: bool
    simple: bool


@dataclass
class IntegerConstant:
    module: str
    node: ast.AST
    value: int


@dataclass
class Module:
    name: str
    tree: ast.Module
    package: bool = False
    symbols: dict[str, str | None] = field(default_factory=dict)
    imports: dict[str, tuple[str, int]] = field(default_factory=dict)
    declarations: dict[str, ast.AST] = field(default_factory=dict)


class Program:
    def __init__(self, trees, packages=()):
        self.modules = {name: Module(name, tree, name in packages) for name, tree in trees.items()}
        self.explicit_attribute_mutation = any(
            isinstance(node, ast.Attribute) and node.attr in {'__setattr__', '__delattr__'}
            for tree in trees.values() for node in ast.walk(tree))
        self.functions = {}
        self.records = {}
        self.signatures = {}
        self.return_facts = {}
        self.constants = {}
        for module in self.modules.values():
            self._symbols(module)
        # Module __getattr__ can supply a different callable during cyclic or
        # partial initialisation, including through a re-export chain. Keep the
        # ordinary local passes, but do not claim a closed-world call graph.
        self.dynamic_modules = any("__getattr__" in module.symbols for module in self.modules.values())
        if self.dynamic_modules:
            return
        for module in self.modules.values():
            self._definitions(module)
        self._infer_returns()

    def _infer_returns(self):
        """Implementation-derived return facts, never annotation promises.

        Only straight-line leaf/wrapper functions qualify. Calls still execute in
        place, including their exceptions and effects. A returned immutable value
        or exact SDK wrapper has the same type even if an unrelated call has side
        effects. No mutable container contents or object fields are inferred.
        """
        if self._cyclic_imports():
            return
        for _ in range(len(self.functions)):
            changed = False
            for qualified, function in self.functions.items():
                if qualified in self.return_facts:
                    continue
                node = function.node
                body = body_without_docstring(node.body)
                bindings = Bindings(body)
                local = set(bindings.counts) | {arg.arg for arg in arguments(node)}
                if (bindings.external or not body or not isinstance(body[-1], ast.Return)
                        or any(isinstance(n, (ast.NamedExpr, ast.Yield, ast.YieldFrom, ast.Await))
                               for n in ast.walk(node))):
                    continue

                def resolve(expression):
                    root = expression
                    while isinstance(root, ast.Attribute):
                        root = root.value
                    if isinstance(root, ast.Name) and root.id in local:
                        return None
                    return self.resolve(function.module, expression)

                facts = {}
                valid = True
                for statement in body[:-1]:
                    if isinstance(statement, (ast.Assign, ast.AnnAssign)):
                        targets = statement.targets if isinstance(statement, ast.Assign) else [statement.target]
                        if not all(isinstance(target, ast.Name) for target in targets):
                            valid = False
                            break
                        value = infer(statement.value, facts, resolve, self.return_facts)
                        for target in targets:
                            facts[target.id] = value
                    elif not isinstance(statement, (ast.Expr, ast.Pass)):
                        valid = False
                        break
                if not valid:
                    continue
                result = infer(body[-1].value, facts, resolve, self.return_facts)
                if result.kind not in {'int', 'tuple', 'range', 'board', 'field', 'vec', 'champion'}:
                    continue
                if 'cambc' in self.modules and result.kind in {'board', 'field', 'vec', 'champion'}:
                    continue
                self.return_facts[qualified] = result
                changed = True
            if not changed:
                break

    def _symbols(self, module):
        bindings = Bindings(module.tree.body)
        module.symbols = dict.fromkeys(bindings.counts)
        globals_written = {name for n in ast.walk(module.tree) if isinstance(n, ast.Global) for name in n.names}
        stable = {name for name, count in bindings.counts.items() if count == 1 and name not in globals_written}
        for node in module.tree.body:
            if isinstance(node, (ast.FunctionDef, ast.ClassDef)) and node.name in stable:
                module.symbols[node.name] = f"{module.name}.{node.name}"
                module.declarations[node.name] = node
            elif isinstance(node, (ast.Assign, ast.AnnAssign)):
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                if len(targets) != 1 or not isinstance(targets[0], ast.Name) or targets[0].id not in stable:
                    continue
                try:
                    value = ast.literal_eval(node.value)
                except (ValueError, TypeError, SyntaxError):
                    continue
                if type(value) is int:
                    name = targets[0].id
                    module.symbols[name] = f"{module.name}.{name}"
                    module.declarations[name] = node
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    name = alias.asname or alias.name.split(".")[0]
                    if name in stable:
                        value = alias.name if alias.asname else name
                        module.symbols[name] = value
                        module.imports[name] = (value, node.lineno)
            elif isinstance(node, ast.ImportFrom):
                parent = node.module or ""
                if node.level:
                    package = module.name if module.package else module.name.rpartition(".")[0]
                    parts = package.split(".") if package else []
                    if node.level > len(parts):
                        continue
                    parent = ".".join([*parts[:len(parts) - node.level + 1], *([parent] if parent else [])])
                for alias in node.names:
                    name = alias.asname or alias.name
                    if name in stable and alias.name != "*":
                        value = f"{parent}.{alias.name}" if parent else alias.name
                        module.symbols[name] = value
                        module.imports[name] = (value, node.lineno)

    def canonical(self, name):
        if not name:
            return None
        seen = set()
        while name not in seen:
            seen.add(name)
            parts = name.split(".")
            replacement = None
            for length in range(len(parts) - 1, 0, -1):
                module = self.modules.get(".".join(parts[:length]))
                if module is not None:
                    symbol = module.symbols.get(parts[length])
                    if symbol:
                        replacement = ".".join([symbol, *parts[length + 1:]])
                    break
            if not replacement or replacement == name:
                return name
            name = replacement
        return None  # Import/re-export cycle without a concrete definition.

    def resolve(self, module, node):
        if isinstance(node, ast.Name):
            if node.id.startswith("__") and not node.id.endswith("__"):
                return None  # The spelling may be mangled in a class scope.
            return self.canonical(self.modules[module].symbols.get(node.id, node.id))
        if isinstance(node, ast.Attribute):
            if node.attr.startswith("__") and not node.attr.endswith("__"):
                return None
            parent = self.resolve(module, node.value)
            return self.canonical(f"{parent}.{node.attr}") if parent else None
        return None

    def _definitions(self, module):
        for name, node in module.declarations.items():
            qualified = f"{module.name}.{name}"
            if getattr(node, "type_params", ()):
                continue
            if isinstance(node, ast.FunctionDef) and not node.decorator_list:
                signature = Signature.from_function(node)
                expression = self._arithmetic_expression(node)
                self.functions[qualified] = Function(qualified, module.name, node, signature, expression)
                self.signatures[qualified] = signature
            elif isinstance(node, ast.ClassDef) and not node.bases and not node.keywords:
                record = self._record(module, node, qualified)
                if record:
                    self.records[qualified] = record
                    self.signatures[qualified] = record.signature
                elif not node.decorator_list:
                    methods = {n.name: n for n in node.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
                    init = methods.get("__init__")
                    if (isinstance(init, ast.FunctionDef) and not init.decorator_list
                            and Bindings(node.body).counts["__init__"] == 1
                            and "__new__" not in Bindings(node.body).counts
                            and not any(arg.arg.startswith("__") and not arg.arg.endswith("__")
                                        for arg in arguments(init))):
                        signature = Signature.from_function(init, method=True)
                        if signature:
                            self.signatures[qualified] = signature
            elif isinstance(node, (ast.Assign, ast.AnnAssign)):
                self.constants[qualified] = IntegerConstant(module.name, node, ast.literal_eval(node.value))

    def _record(self, module, node, qualified):
        if "dataclasses" in self.modules:
            return None  # A bot-local module may shadow the stdlib decorator.
        if len(node.decorator_list) != 1:
            return None
        decorator = node.decorator_list[0]
        function = decorator.func if isinstance(decorator, ast.Call) else decorator
        if self.resolve(module.name, function) != "dataclasses.dataclass":
            return None
        flags = {}
        if isinstance(decorator, ast.Call):
            if decorator.args or any(kw.arg is None or not isinstance(kw.value, ast.Constant)
                                     or type(kw.value.value) is not bool for kw in decorator.keywords):
                return None
            flags = {kw.arg: kw.value.value for kw in decorator.keywords}
        if flags.get("init", True) is False or flags.get("kw_only", False):
            return None
        fields, optional = [], set()
        simple = True
        for statement in body_without_docstring(node.body):
            if isinstance(statement, ast.Pass):
                continue
            if not isinstance(statement, ast.AnnAssign) or not isinstance(statement.target, ast.Name):
                # Descriptors, custom lookup, post-init and arbitrary class code
                # are not eligible. They can also replace dataclass defaults or
                # __init__ in ways that invalidate the apparent signature.
                return None
            annotation = statement.annotation
            if isinstance(annotation, ast.Constant) and isinstance(annotation.value, str):
                try:
                    annotation = ast.parse(annotation.value, mode="eval").body
                except SyntaxError:
                    return None
            base = annotation.value if isinstance(annotation, ast.Subscript) else annotation
            annotation_name = self.resolve(module.name, base)
            if annotation_name and annotation_name.rsplit(".", 1)[-1] in {"ClassVar", "InitVar", "KW_ONLY"}:
                return None
            if not self._ordinary_annotation(module.name, annotation):
                # An unknown alias can be ClassVar/InitVar/KW_ONLY even if its
                # spelling looks like a normal type. Do not guess field layout.
                return None
            field_name = statement.target.id
            if field_name.startswith("__") or field_name == "self":
                return None
            if statement.value is not None:
                # field(), factories, descriptors and init=False are deliberately
                # unsupported. Inert literal defaults are signature-only.
                if not isinstance(statement.value, ast.Constant):
                    return None
                optional.add(field_name)
                simple = False
            fields.append(field_name)
        if not fields or len(fields) != len(set(fields)):
            return None
        signature = Signature(tuple(fields), optional=frozenset(optional))
        return Record(qualified, module.name, node, tuple(fields), signature,
                      flags.get("frozen", False), simple and not flags.get("slots", False))

    def _ordinary_annotation(self, module, annotation):
        if isinstance(annotation, ast.Constant) and annotation.value is None:
            return True
        if isinstance(annotation, ast.BinOp) and isinstance(annotation.op, ast.BitOr):
            return self._ordinary_annotation(module, annotation.left) and self._ordinary_annotation(module, annotation.right)
        base = annotation.value if isinstance(annotation, ast.Subscript) else annotation
        name = self.resolve(module, base)
        builtin = {"int", "float", "bool", "str", "bytes", "complex", "object", "tuple", "list", "dict", "set", "frozenset", "type"}
        if name in builtin or name in {f"builtins.{item}" for item in builtin}:
            return True
        if name and name.startswith("cambc.") and "cambc" not in self.modules:
            return True
        if name and "typing" not in self.modules and name in {f"typing.{item}" for item in (
            "Any", "Optional", "Union", "List", "Tuple", "Dict", "Set", "FrozenSet", "Sequence",
            "Mapping", "Callable", "Literal", "Final", "Annotated", "Type", "Iterable", "Iterator",
        )}:
            return True
        for candidate in self.modules.values():
            for local, node in candidate.declarations.items():
                if name != f"{candidate.name}.{local}" or not isinstance(node, ast.ClassDef) or node.bases or node.keywords:
                    continue
                if not node.decorator_list:
                    return True
                if len(node.decorator_list) == 1:
                    decorator = node.decorator_list[0]
                    function = decorator.func if isinstance(decorator, ast.Call) else decorator
                    return self.resolve(candidate.name, function) == "dataclasses.dataclass"
        return False

    @staticmethod
    def _arithmetic_expression(node):
        body = body_without_docstring(node.body)
        if len(body) != 1 or not isinstance(body[0], ast.Return) or body[0].value is None:
            return None
        names = {arg.arg for arg in arguments(node)}
        expression = body[0].value
        nodes = list(ast.walk(expression))
        if len(nodes) > 40:
            return None
        for part in nodes:
            if isinstance(part, ast.Name):
                if part.id not in names:
                    return None
            elif isinstance(part, ast.Constant):
                if type(part.value) is not int:
                    return None
            elif not isinstance(part, (ast.BinOp, ast.UnaryOp, ast.Load, ast.operator, ast.unaryop)):
                return None
        return expression

    def available(self, module_name, expression, before_line):
        """Removing a callee lookup needs an already-bound unconditional name."""
        root = expression
        while isinstance(root, ast.Attribute):
            root = root.value
        if not isinstance(root, ast.Name):
            return False
        module = self.modules[module_name]
        if root.id in module.imports:
            target = self.resolve(module_name, expression)
            definition = self.functions.get(target) or self.records.get(target) or self.constants.get(target)
            if definition is None or "__getattr__" in self.modules[definition.module].declarations:
                return False
            # Cyclic initialisation can expose a module before its declarations
            # are bound. Do not remove lookups across such an import graph.
            if self._cyclic_imports():
                return False
            return module.imports[root.id][1] < before_line
        declaration = module.declarations.get(root.id)
        return declaration is not None and declaration.lineno < before_line

    def _cyclic_imports(self):
        if hasattr(self, "_has_cycles"):
            return self._has_cycles
        graph = {}
        for name, module in self.modules.items():
            targets = set()
            for target, _ in module.imports.values():
                parts = target.split(".")
                for length in range(len(parts), 0, -1):
                    candidate = ".".join(parts[:length])
                    if candidate in self.modules:
                        targets.add(candidate)
                        break
            graph[name] = targets
        active, done = set(), set()

        def visit(name):
            if name in active:
                return True
            if name in done:
                return False
            active.add(name)
            if any(visit(target) for target in graph[name]):
                return True
            active.remove(name)
            done.add(name)
            return False

        self._has_cycles = any(visit(name) for name in graph)
        return self._has_cycles

    def diagnostics(self):
        return {"modules": len(self.modules), "resolved_functions": len(self.functions),
                "resolved_records": len(self.records), "resolved_signatures": len(self.signatures),
                "dynamic_module_attributes": self.dynamic_modules,
                "inferred_returns": len(self.return_facts)}
