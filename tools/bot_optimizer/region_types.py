"""Candidate schemas for runtime-guarded primitive graph snapshots.

Annotations select checks to attempt; they never establish runtime facts. A
consumer may use a schema only after its complete validator succeeds, and must
prevent projected containers from escaping or changing exception behaviour.
"""

import ast
from dataclasses import dataclass

from .analysis import Bindings, arguments
from .program import body_without_docstring


@dataclass(frozen=True)
class Schema:
    kind: str
    name: str = ''
    items: tuple = ()
    fields: tuple[str, ...] = ()


class RegionSchemas:
    def __init__(self, program):
        self.program = program
        self.cache = {}
        self.active = set()

    def annotation(self, module, node):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            try:
                node = ast.parse(node.value, mode='eval').body
            except SyntaxError:
                return None
        if isinstance(node, ast.Constant) and node.value is None:
            return Schema('none')
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
            left, right = self.annotation(module, node.left), self.annotation(module, node.right)
            if left and right:
                if left.kind == 'none':
                    return Schema('optional', items=(right,))
                if right.kind == 'none':
                    return Schema('optional', items=(left,))
            return None
        if isinstance(node, ast.Subscript):
            base = self.program.resolve(module, node.value)
            if base not in {'list', 'tuple', 'builtins.list', 'builtins.tuple'}:
                return None
            values = node.slice.elts if isinstance(node.slice, ast.Tuple) else [node.slice]
            if base.endswith('list') and len(values) == 1:
                item = self.annotation(module, values[0])
                return Schema('list', items=(item,)) if item else None
            if base.endswith('tuple'):
                if len(values) == 2 and isinstance(values[1], ast.Constant) and values[1].value is Ellipsis:
                    item = self.annotation(module, values[0])
                    return Schema('tuple', items=(item,)) if item else None
                items = tuple(self.annotation(module, value) for value in values)
                return Schema('fixed-tuple', items=items) if all(items) else None
            return None
        name = self.program.resolve(module, node)
        scalar = {'int': 'int', 'float': 'float', 'bool': 'bool'}
        for spelling, kind in scalar.items():
            if name in {spelling, f'builtins.{spelling}'}:
                return Schema(kind)
        return self.record(name) if name else None

    def declaration(self, qualified):
        module, _, name = qualified.rpartition('.')
        owner = self.program.modules.get(module)
        node = owner.declarations.get(name) if owner else None
        if (not isinstance(node, ast.ClassDef) or node.bases or node.keywords or node.type_params
                or self.program.dynamic_modules or self.program._cyclic_imports()):
            return None
        return module, node

    def inert_default(self, module, node):
        if isinstance(node, ast.Constant):
            return type(node.value) in {int, float, bool, type(None)}
        if not isinstance(node, ast.Name):
            return False
        tree = self.program.modules[module].tree
        if Bindings(tree.body).counts[node.id] != 1 or any(
                isinstance(n, ast.Global) and node.id in n.names for n in ast.walk(tree)):
            return False
        for statement in tree.body:
            if isinstance(statement, (ast.Assign, ast.AnnAssign)):
                targets = statement.targets if isinstance(statement, ast.Assign) else [statement.target]
                if len(targets) == 1 and isinstance(targets[0], ast.Name) and targets[0].id == node.id:
                    return isinstance(statement.value, ast.Constant) and type(statement.value.value) in {int, float, bool, type(None)}
        return False

    def record(self, qualified):
        if qualified in self.cache:
            return self.cache[qualified]
        if qualified in self.active or len(self.active) >= 8:
            return None
        self.active.add(qualified)
        try:
            result = self._record(qualified)
        finally:
            self.active.remove(qualified)
        self.cache[qualified] = result
        return result

    def _record(self, qualified):
        declaration = self.declaration(qualified)
        if declaration is None or 'dataclasses' in self.program.modules:
            return None
        module, node = declaration
        if len(node.decorator_list) != 1:
            return None
        decorator = node.decorator_list[0]
        if not isinstance(decorator, ast.Call) or self.program.resolve(module, decorator.func) != 'dataclasses.dataclass':
            return None
        if decorator.args or any(keyword.arg is None or not isinstance(keyword.value, ast.Constant)
                                 or type(keyword.value.value) is not bool for keyword in decorator.keywords):
            return None
        flags = {keyword.arg: keyword.value.value for keyword in decorator.keywords}
        if not flags.get('frozen') or not flags.get('init', True) or flags.get('slots', False):
            return None
        fields, schemas = [], []
        for statement in body_without_docstring(node.body):
            if isinstance(statement, ast.Pass):
                continue
            if isinstance(statement, ast.FunctionDef) and statement.name == '__post_init__':
                # Permit validation-only post-init, not custom lookup, class
                # construction, descriptor installation, or attribute stores.
                if statement.decorator_list or any(isinstance(n, (
                        ast.Assign, ast.AnnAssign, ast.AugAssign, ast.Delete, ast.Global,
                        ast.Nonlocal, ast.Import, ast.ImportFrom, ast.ClassDef, ast.Lambda,
                        ast.Yield, ast.YieldFrom, ast.Await, ast.NamedExpr))
                        or isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n is not statement
                        for n in ast.walk(statement)):
                    return None
                for child in ast.walk(statement):
                    if isinstance(child, ast.stmt) and not isinstance(child, (
                            ast.FunctionDef, ast.If, ast.Raise, ast.Pass, ast.Expr)):
                        return None
                    if isinstance(child, ast.Call):
                        if not (isinstance(child.func, ast.Name) and child.func.id in {'ValueError', 'TypeError'}
                                and self.program.resolve(module, child.func) == child.func.id
                                and all(isinstance(arg, ast.Constant) for arg in child.args) and not child.keywords):
                            return None
                continue
            if not isinstance(statement, ast.AnnAssign) or not isinstance(statement.target, ast.Name):
                return None
            field = statement.target.id
            if field.startswith('__') or field in fields or statement.value is not None and not self.inert_default(module, statement.value):
                return None
            schema = self.annotation(module, statement.annotation)
            if schema is None:
                return None
            fields.append(field)
            schemas.append(schema)
        return Schema('record', qualified, tuple(schemas), tuple(fields)) if fields else None

    def owner(self, qualified):
        declaration = self.declaration(qualified)
        if declaration is None:
            return None
        module, node = declaration
        if node.decorator_list:
            return None
        members = body_without_docstring(node.body)
        if any(not isinstance(member, (ast.FunctionDef, ast.Pass)) for member in members):
            return None
        methods = [member for member in members if isinstance(member, ast.FunctionDef)]
        if any(method.decorator_list or method.name.startswith('__') and method.name != '__init__' for method in methods):
            return None
        if len({method.name for method in methods}) != len(methods):
            return None
        constructors = [method for method in methods if method.name == '__init__']
        if len(constructors) != 1:
            return None
        init = constructors[0]
        params = arguments(init)
        if not params or init.args.vararg or init.args.kwarg:
            return None
        receiver = params[0].arg
        annotations = {arg.arg: arg.annotation for arg in params[1:]}
        fields, schemas = [], []
        for statement in body_without_docstring(init.body):
            if not (isinstance(statement, ast.Assign) and len(statement.targets) == 1
                    and isinstance(statement.targets[0], ast.Attribute)
                    and isinstance(statement.targets[0].value, ast.Name)
                    and statement.targets[0].value.id == receiver and isinstance(statement.value, ast.Name)):
                return None
            target = statement.targets[0].attr
            if target.startswith('__') or target in fields or target in {method.name for method in methods}:
                return None
            annotation = annotations.get(statement.value.id)
            schema = self.annotation(module, annotation) if annotation is not None else None
            if schema is None:
                return None
            fields.append(target)
            schemas.append(schema)
        return Schema('owner', qualified, tuple(schemas), tuple(fields)) if fields else None


class SnapshotEmitter:
    """Emit validators that copy only proven primitive values into private tuples.

    The emitted failure sentinel is distinct from a valid optional None. Class
    references must come from resolved declarations, and are captured when the
    helper is defined. Nothing imports or executes bot code during compilation.
    """
    def __init__(self, taken, class_refs):
        self.taken = set(taken)
        self.class_refs = class_refs
        self.helpers = {}
        self.definitions = []
        self.builtins = self.fresh('builtins')
        self.failed = self.fresh('failed')

    def fresh(self, stem):
        index = 0
        while f'_bcopt_region_{stem}_{index}' in self.taken:
            index += 1
        name = f'_bcopt_region_{stem}_{index}'
        self.taken.add(name)
        return name

    def emit(self, schema, guard_schemas=()):
        root = self.helper(schema)
        for extra in guard_schemas:
            self.helper(extra)
        prelude = ast.parse(f'import builtins as {self.builtins}\n{self.failed}={self.builtins}.object()\n').body
        classes = {spec.name: spec for spec in self.helpers if spec.kind in {'record', 'owner'}}
        if classes:
            # Check raw namespaces once before traversing instances. A class
            # changed by earlier callbacks must not run new descriptors during
            # speculative field reads. Exact type + object-only bases make these
            # namespace reads native, not custom metaclass calls.
            entry = self.fresh('snapshot_entry')
            references = '('+','.join('('+self.class_refs[name]+','+repr(spec.fields)+')'
                                     for name, spec in classes.items())+',)'
            guard = ast.parse(f'''def {entry}(value,_classes={references},_type={self.builtins}.type,
                    _get={self.builtins}.type.__getattribute__,_object={self.builtins}.object,
                    _len={self.builtins}.len,_int={self.builtins}.int,
                    _float={self.builtins}.float,_bool={self.builtins}.bool):
    for cls,fields in _classes:
        if _type(cls) is not _type:
            return {self.failed}
        bases=_get(cls,'__bases__')
        if _len(bases)!=1 or bases[0] is not _object:
            return {self.failed}
        namespace=_get(cls,'__dict__')
        if '__getattribute__' in namespace or '__getattr__' in namespace:
            return {self.failed}
        for field in fields:
            default=namespace.get(field,{self.failed})
            if default is not {self.failed} and default is not None and not (
                    _type(default) is _int or _type(default) is _float or _type(default) is _bool):
                return {self.failed}
    return {root}(value)
''').body[0]
            self.definitions.append(guard)
            root = entry
        tree = ast.fix_missing_locations(ast.Module(body=[*prelude, *self.definitions], type_ignores=[]))
        return root, self.failed, tree

    def helper(self, schema):
        if schema.kind not in {'record', 'owner', 'list', 'tuple', 'fixed-tuple',
                               'optional', 'int', 'float', 'number', 'bool', 'none'}:
            raise ValueError(f'Unsupported snapshot schema: {schema.kind}')
        if schema in self.helpers:
            return self.helpers[schema]
        name = self.fresh('snapshot')
        self.helpers[schema] = name
        lines = []
        serial = 0

        def temporary():
            nonlocal serial
            serial += 1
            return f'part_{serial}'

        def reject(condition, indent=1):
            lines.extend(['    '*indent+f'if {condition}:',
                          '    '*(indent+1)+f'return {self.failed}'])

        def project(spec, value, indent=1):
            primitive = {'int': '_int', 'float': '_float', 'bool': '_bool'}
            if spec.kind in primitive:
                reject(f'_type({value}) is not {primitive[spec.kind]}', indent)
                return value
            if spec.kind == 'number':
                reject(f'not (_type({value}) is _int or _type({value}) is _float)', indent)
                return value
            if spec.kind == 'none':
                reject(f'{value} is not None', indent)
                return value
            result = temporary()
            child = self.helper(spec)
            lines.append('    '*indent+f'{result}={child}({value})')
            reject(f'{result} is {self.failed}', indent)
            return result

        if schema.kind in {'record', 'owner'}:
            if schema.name not in self.class_refs:
                raise ValueError(f'Missing resolved class binding: {schema.name}')
            reject('_type(value) is not _record_type')
            fields = [temporary() for _ in schema.fields]
            lines.append('    try:')
            lines.extend(f'        {local}=value.{field}' for local, field in zip(fields, schema.fields))
            lines.extend(['    except _attribute_error:', f'        return {self.failed}'])
            values = [project(spec, local) for local, spec in zip(fields, schema.items)]
            lines.append('    return ('+','.join(values)+',)')
        elif schema.kind in {'list', 'tuple'}:
            reject(f'_type(value) is not _{schema.kind}')
            lines.extend(['    result=[]', '    for item in value:'])
            item = project(schema.items[0], 'item', 2)
            lines.append(f'        result.append({item})')
            lines.append('    return _tuple(result)')
        elif schema.kind == 'fixed-tuple':
            reject(f'_type(value) is not _tuple or _len(value)!={len(schema.items)}')
            values = []
            for index, spec in enumerate(schema.items):
                local = temporary()
                lines.append(f'    {local}=value[{index}]')
                values.append(project(spec, local))
            lines.append('    return ('+','.join(values)+(',' if values else '')+')')
        elif schema.kind == 'optional':
            lines.extend(['    if value is None:', '        return None'])
            value = project(schema.items[0], 'value')
            lines.append(f'    return {value}')
        else:
            value = project(schema, 'value')
            lines.append(f'    return {value}')
        source = f'def {name}(value):\n'+'\n'.join(lines)+'\n'
        function = ast.parse(source).body[0]
        used = {node.id for node in ast.walk(function) if isinstance(node, ast.Name)}
        aliases = {'_type': 'type', '_int': 'int', '_float': 'float', '_bool': 'bool',
                   '_tuple': 'tuple', '_list': 'list', '_len': 'len', '_attribute_error': 'AttributeError'}
        for alias, builtin in aliases.items():
            if alias in used:
                function.args.args.append(ast.arg(arg=alias))
                function.args.defaults.append(ast.Attribute(value=ast.Name(id=self.builtins, ctx=ast.Load()),
                                                            attr=builtin, ctx=ast.Load()))
        if '_record_type' in used:
            function.args.args.append(ast.arg(arg='_record_type'))
            function.args.defaults.append(ast.parse(self.class_refs[schema.name], mode='eval').body)
        self.definitions.append(function)
        return name
