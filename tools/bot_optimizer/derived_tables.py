"""Precompute pure snapshot expressions over finite index domains.

Tables belong to one validated consumer epoch. They contain only primitives;
failed preparation leaves the original expression in use. Native index retry
still handles invalid runtime indices, including negative indices.
"""

import ast
import copy

from .analysis import arguments
from .incremental_edges import certify_edges
from .ordered_folds import certify_pair_fold
from .group_scalars import annotate_group_scalars


class DerivedTables:
    def __init__(self, builder, entry, builtins, memoize=False, native_projection=False):
        self.builder, self.entry = builder, entry
        self.builtins = builtins
        self.root = arguments(entry.function)[0].arg
        self.tables = []
        self.memoize = memoize
        self.caches = []
        self.native_projection = native_projection
        self.getter = None

    def collect_projection(self, node):
        """Collect only prepared primitive values; keep the native reduction."""
        if (not self.native_projection or not isinstance(node, ast.Call)
                or getattr(node, '_bcopt_numeric_native', None) != 'sum'
                or node.keywords or len(node.args) != 1
                or not isinstance(node.args[0], ast.ListComp)):
            return node
        comp = node.args[0]
        if len(comp.generators) != 1:
            return node
        gen, choice = comp.generators[0], comp.elt
        if (gen.is_async or gen.ifs or not isinstance(gen.target, ast.Name)
                or not isinstance(gen.iter, ast.Name)
                or getattr(gen.iter, '_bcopt_numeric_kind', None) != 'tuple'
                or not isinstance(choice, ast.IfExp)
                or not getattr(choice, '_bcopt_prepared_projection', False)
                or not isinstance(choice.orelse, ast.Subscript)
                or not isinstance(choice.orelse.value, ast.Name)
                or not isinstance(choice.orelse.slice, ast.Name)
                or choice.orelse.slice.id != gen.target.id):
            return node
        # This exact one-dimensional table and its None test were emitted here.
        table = choice.orelse.value
        if table.id not in {local for local, _, _, domains, _ in self.tables if len(domains) == 1}:
            return node
        if self.getter is None:
            self.getter = self.builder.fresh('projection_getter')
        original, short = copy.deepcopy(comp), copy.deepcopy(comp)
        original.elt, short.elt = copy.deepcopy(choice.body), copy.deepcopy(choice.orelse)
        native = ast.Call(func=ast.Call(func=ast.Name(id=self.getter, ctx=ast.Load()),
            args=[ast.Starred(value=copy.deepcopy(gen.iter), ctx=ast.Load())], keywords=[]),
            args=[copy.deepcopy(table)], keywords=[])
        test = ast.Compare(left=ast.Call(func=ast.Attribute(value=ast.Name(id=self.builtins, ctx=ast.Load()),
            attr='len', ctx=ast.Load()), args=[copy.deepcopy(gen.iter)], keywords=[]),
            ops=[ast.Gt()], comparators=[ast.Constant(1)])
        node.args = [ast.IfExp(test=copy.deepcopy(choice.test), body=original,
            orelse=ast.IfExp(test=test, body=native, orelse=short))]
        node._bcopt_prepared_native_sum = True
        return node

    def memoized_loop(self, node, aliases):
        contract = getattr(node, '_bcopt_integer_reductions', None)
        if not self.memoize or contract is None:
            return None
        base = self.expand(contract['base'], aliases)
        route, outputs = contract['route'], contract['outputs']
        stores = {part.id for part in ast.walk(node) if isinstance(part, ast.Name) and isinstance(part.ctx, ast.Store)}
        if (not self.projection(base)
                or any(isinstance(part, ast.Name) and part.id != self.root for part in ast.walk(base))
                or not isinstance(route, ast.Name) or getattr(route, '_bcopt_numeric_kind', None) != 'tuple'
                or ast.dump(route) != ast.dump(node.iter) or not set(outputs) <= stores):
            return None
        cache, key, values = (self.builder.fresh(name) for name in ('reduction_cache', 'reduction_key', 'reduction_values'))
        self.caches.append(cache)
        # The complete sorted tuple is a multiset key: duplicate and negative
        # indices remain distinct. Only exact-integer sums/extrema are reused.
        prefix = ast.parse(f'{key} = {self.builtins}.tuple({self.builtins}.sorted({route.id}))\n'
                           f'{values} = {cache}.get({key}, {cache})\n').body
        prefix[0].value._bcopt_multiset_key = True
        prefix[0]._bcopt_group_key = True
        prefix[1]._bcopt_group_lookup = True
        condition = ast.parse(f'''if {values} is {cache}:
    pass
else:
    {", ".join(outputs)} = {values}
''').body[0]
        save = ast.parse(f'''if {self.builtins}.len({cache}) < 4096:
    {cache}[{key}] = ({", ".join(outputs)},)
''').body
        save[0]._bcopt_integer_cache_publish = True
        condition.body = [node, *save]
        condition._bcopt_group_reductions = True
        return [*prefix, condition]

    def inline_temporaries(self, body):
        """Fold single-use total numeric temporaries into the next expression.

        Index reads may fail, but the enclosing numeric entry retries IndexError
        through the original method. Other operations preceding the replacement
        must be total, so moving those reads cannot expose a different exception.
        """
        nodes = list(ast.walk(self.entry.function))
        index = 0
        while index + 1 < len(body):
            binding, consumer = body[index:index+2]
            if (isinstance(binding, ast.Assign) and len(binding.targets) == 1
                    and isinstance(binding.targets[0], ast.Name)
                    and isinstance(binding.value, ast.BinOp)
                    and getattr(binding.value, '_bcopt_numeric_total', False)
                    and isinstance(consumer, (ast.Assign, ast.AugAssign))
                    and isinstance(consumer.value, ast.BinOp)):
                name = binding.targets[0].id
                uses = [node for node in nodes if isinstance(node, ast.Name) and node.id == name]
                loads = [node for node in uses if isinstance(node.ctx, ast.Load)]
                stores = [node for node in uses if isinstance(node.ctx, ast.Store)]
                if len(loads) == len(stores) == 1 and loads[0] in set(ast.walk(consumer.value)):
                    def prefix_total(node):
                        if node is loads[0]:
                            return True
                        if isinstance(node, ast.BinOp):
                            if loads[0] in set(ast.walk(node.left)):
                                return prefix_total(node.left)
                            return getattr(node.left, '_bcopt_numeric_total', False) and prefix_total(node.right)
                        return False
                    if prefix_total(consumer.value):
                        class Substitute(ast.NodeTransformer):
                            def visit_Name(self, node):
                                return copy.deepcopy(binding.value) if node is loads[0] else node
                        consumer.value = Substitute().visit(consumer.value)
                        body.pop(index)
                        continue
            index += 1
        for statement in list(body):
            if isinstance(statement, (ast.For, ast.If)):
                self.inline_temporaries(statement.body)
                self.inline_temporaries(statement.orelse)

    def expand(self, node, aliases):
        if isinstance(node, ast.Name) and node.id in aliases:
            return copy.deepcopy(aliases[node.id])
        node = copy.deepcopy(node)
        for field, value in ast.iter_fields(node):
            if isinstance(value, ast.AST):
                setattr(node, field, self.expand(value, aliases))
            elif isinstance(value, list):
                setattr(node, field, [self.expand(item, aliases) if isinstance(item, ast.AST) else item for item in value])
        if (isinstance(node, ast.Subscript) and isinstance(node.value, (ast.List, ast.Tuple))
                and isinstance(node.slice, ast.Constant) and type(node.slice.value) is int
                and 0 <= node.slice.value < len(node.value.elts)):
            # A certified owned list can only append/extend. Its known positive
            # prefix stays fixed; negative indices could refer to a later tail.
            return copy.deepcopy(node.value.elts[node.slice.value])
        return node

    def projection(self, node):
        if isinstance(node, ast.Name):
            return node.id == self.root
        return (isinstance(node, ast.Subscript) and self.projection(node.value)
                and (isinstance(node.slice, ast.Name) or isinstance(node.slice, ast.Constant) and type(node.slice.value) is int
                     or self.input_projection(node.slice)))

    def input_projection(self, node):
        if (not isinstance(node, ast.Subscript) or not isinstance(node.value, ast.Name)
                or getattr(node.value, '_bcopt_numeric_kind', None) != 'tuple'
                or getattr(node, '_bcopt_numeric_kind', None) != 'int'):
            return False
        try:
            return type(ast.literal_eval(node.slice)) is int
        except (ValueError, TypeError):
            return False

    def candidate(self, node, aliases):
        if not isinstance(node, ast.BinOp) or getattr(node, '_bcopt_numeric_kind', None) not in {'int', 'float', 'number'}:
            return None
        expanded = self.expand(node, aliases)
        indices, index_names = {}, {}
        owner = self
        class IndexExpressions(ast.NodeTransformer):
            def visit_Subscript(self, part):
                self.generic_visit(part)
                if owner.input_projection(part.slice):
                    key = ast.dump(part.slice)
                    if key not in index_names:
                        name = owner.builder.fresh('derived_index')
                        index_names[key] = name
                        indices[name] = copy.deepcopy(part.slice)
                    part.slice = ast.Name(id=index_names[key], ctx=ast.Load())
                return part
        expanded = IndexExpressions().visit(expanded)
        domains = {}
        def valid(part):
            if isinstance(part, ast.Constant):
                return type(part.value) in {int, float, bool}
            if isinstance(part, ast.BinOp):
                return isinstance(part.op, (ast.Add, ast.Sub, ast.Mult, ast.Div)) and valid(part.left) and valid(part.right)
            if not isinstance(part, ast.Subscript) or not self.projection(part):
                return False
            for access in ast.walk(part):
                if isinstance(access, ast.Subscript) and isinstance(access.slice, ast.Name):
                    domains.setdefault(access.slice.id, []).append(copy.deepcopy(access.value))
            return True
        if (not valid(expanded) or len(domains) > 2
                or not any(isinstance(part, ast.Name) and part.id == self.root for part in ast.walk(expanded))):
            return None
        # Independent rectangular domains only. Dynamic rows are checked below,
        # but a dimension's representative must be an immutable root path.
        sizes = {}
        for name, bases in domains.items():
            static = [base for base in bases if not any(isinstance(n, ast.Name) and n.id != self.root for n in ast.walk(base))]
            if not static:
                return None
            sizes[name] = static[0]
        return expanded, domains, sizes, indices

    def expression(self, node, aliases):
        if isinstance(node, (ast.ListComp, ast.GeneratorExp)):
            nested = dict(aliases)
            for generator in node.generators:
                names = {item.id for item in ast.walk(generator.target) if isinstance(item, ast.Name)}
                for name, expression in list(nested.items()):
                    if name in names or any(isinstance(item, ast.Name) and item.id in names for item in ast.walk(expression)):
                        nested.pop(name, None)
            node.elt = self.expression(node.elt, nested)
            return node
        found = self.candidate(node, aliases)
        if found is not None:
            expanded, domains, sizes, indices = found
            local = self.builder.fresh('derived')
            prepare = self.builder.fresh('derive')
            self.tables.append((local, prepare, expanded, domains, sizes))
            lookup = ast.Name(id=local, ctx=ast.Load())
            for name in domains:
                lookup = ast.Subscript(value=lookup, slice=copy.deepcopy(indices.get(name, ast.Name(id=name, ctx=ast.Load()))), ctx=ast.Load())
                lookup.slice._bcopt_prepared_integer_index = True
            lookup._bcopt_prepared_lookup = (len(domains), getattr(node, '_bcopt_numeric_kind', None))
            result = ast.copy_location(ast.IfExp(test=ast.Compare(left=ast.Name(id=local, ctx=ast.Load()),
                ops=[ast.Is()], comparators=[ast.Constant(None)]), body=node, orelse=lookup), node)
            result._bcopt_prepared_projection = True
            result.test._bcopt_prepared_test = True
            return result
        for field, value in ast.iter_fields(node):
            if isinstance(value, ast.expr):
                setattr(node, field, self.expression(value, aliases))
            elif isinstance(value, list):
                setattr(node, field, [self.expression(item, aliases) if isinstance(item, ast.expr) else item for item in value])
        return self.collect_projection(node)

    def block(self, body, aliases):
        def invalidate(names):
            for name, expression in list(aliases.items()):
                if name in names or any(isinstance(node, ast.Name) and node.id in names for node in ast.walk(expression)):
                    aliases.pop(name, None)
        for statement in list(body):
            if isinstance(statement, (ast.Assign, ast.AnnAssign)):
                index = body.index(statement)
                if index + 1 < len(body):
                    certify_edges(self, statement, body[index+1], aliases)
                expanded = self.expand(statement.value, aliases)
                statement.value = self.expression(statement.value, aliases)
                def bind(target, value):
                    if isinstance(target, ast.Name):
                        invalidate({target.id})
                        prefix = (isinstance(value, (ast.List, ast.Tuple)) and value.elts
                                  and all(self.projection(item) or isinstance(item, ast.Constant)
                                          and type(item.value) in {int, float, bool} for item in value.elts))
                        if (self.projection(value) or prefix or self.input_projection(value)) and not any(isinstance(n, ast.Name) and n.id == target.id for n in ast.walk(value)):
                            aliases[target.id] = value
                    elif isinstance(target, (ast.Tuple, ast.List)):
                        if isinstance(value, (ast.Tuple, ast.List)) and len(target.elts) == len(value.elts):
                            for left, right in zip(target.elts, value.elts):
                                bind(left, right)
                        else:
                            for item in target.elts:
                                bind(item, ast.Constant(None))
                for target in statement.targets if isinstance(statement, ast.Assign) else [statement.target]:
                    bind(target, expanded)
            elif isinstance(statement, ast.AugAssign):
                statement.value = self.expression(statement.value, aliases)
                if isinstance(statement.target, ast.Name):
                    invalidate({statement.target.id})
            elif isinstance(statement, (ast.If, ast.For)):
                memo = self.memoized_loop(statement, aliases) if isinstance(statement, ast.For) else None
                nested = dict(aliases)
                if isinstance(statement, ast.For):
                    for node in ast.walk(statement):
                        if isinstance(node, ast.Name):
                            if isinstance(node.ctx, ast.Store):
                                for name, expression in list(nested.items()):
                                    if name == node.id or any(isinstance(n, ast.Name) and n.id == node.id for n in ast.walk(expression)):
                                        nested.pop(name, None)
                self.block(statement.body, nested)
                self.block(statement.orelse, dict(aliases))
                if isinstance(statement, ast.For):
                    certify_pair_fold(self, statement)
                # Do not propagate branch/loop-local aliases beyond a join.
                stores = {node.id for node in ast.walk(statement) if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store)}
                invalidate(stores)
                if memo is not None:
                    index = body.index(statement)
                    body[index:index+1] = memo
        annotate_group_scalars(self, body)

    def apply(self):
        if any(isinstance(node, ast.Name) and node.id == self.root and isinstance(node.ctx, ast.Store)
               for node in ast.walk(self.entry.function)):
            return [], []
        if getattr(self.entry.function, '_bcopt_index_retry', None) is not None:
            self.inline_temporaries(self.entry.function.body)
        self.block(self.entry.function.body, {})
        if not self.tables and not self.caches:
            return [], []
        helpers, preparations, loads = [], [], []
        if self.getter is not None:
            helpers.append(ast.ImportFrom(module='_operator', names=[ast.alias(name='itemgetter', asname=self.getter)], level=0))
        offset = len(self.builder.owner.fields)
        for index, (local, prepare, expression, domains, sizes) in enumerate(self.tables):
            size_names = {name: self.builder.fresh('dimension') for name in domains}
            lines = [f'def {prepare}({self.root}):', '    try:']
            for name, base in sizes.items():
                lines.append(f'        {size_names[name]} = {self.builtins}.len({ast.unparse(base)})')
            if size_names:
                lines.extend([f'        if {" * ".join(size_names.values())} > 4096:', '            return None'])
            checked = set()
            for name, bases in domains.items():
                for base in bases:
                    key = ast.dump(base), size_names[name]
                    if key in checked or ast.dump(base) == ast.dump(sizes[name]):
                        continue
                    checked.add(key)
                    # Snapshot paths are immutable. Check each distinct length
                    # only over the indices it depends on, not a Cartesian
                    # product of unrelated dimensions.
                    dependencies = {part.id for part in ast.walk(base) if isinstance(part, ast.Name)}
                    depth = 2
                    for dependency in domains:
                        if dependency in dependencies:
                            lines.append('    '*depth + f'for {dependency} in {self.builtins}.range({size_names[dependency]}):')
                            depth += 1
                    lines.append('    '*depth + f'if {self.builtins}.len({ast.unparse(base)}) != {size_names[name]}:')
                    lines.append('    '*(depth+1) + 'return None')
            value = ast.unparse(expression)
            for name in reversed(domains):
                value = f'[{value} for {name} in {self.builtins}.range({size_names[name]})]'
            lines.extend([f'        return {value}', f'    except ({self.builtins}.IndexError, {self.builtins}.TypeError, {self.builtins}.ArithmeticError):', '        return None'])
            helpers.extend(ast.parse('\n'.join(lines)).body)
            preparations.append(prepare)
            load = ast.parse(f'{local} = {self.root}[{offset+index}]').body[0]
            load._bcopt_prepared_table = True
            loads.append(load)
        for index, local in enumerate(self.caches, start=len(self.tables)):
            prepare = self.builder.fresh('reduction_prepare')
            helpers.extend(ast.parse(f'def {prepare}({self.root}):\n    return {{}}\n').body)
            preparations.append(prepare)
            load = ast.parse(f'{local} = {self.root}[{offset+index}]').body[0]
            load._bcopt_private_integer_cache = True
            loads.append(load)
        self.entry.function.body[:0] = loads
        return helpers, preparations
