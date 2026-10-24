"""Roll private integer edge lists across certified insertion positions."""

import ast
import copy
from collections import Counter

from .model import Change
from .records import used_names


def certify_edges(tables, binding, extension, aliases):
    """Certify before lowering erases numeric types and alias provenance."""
    if (not isinstance(binding, ast.Assign) or len(binding.targets) != 1
            or not isinstance(binding.targets[0], ast.Name) or not isinstance(binding.value, ast.List)
            or len(binding.value.elts) != 2 or not isinstance(extension, ast.Expr)
            or not isinstance(extension.value, ast.Call) or not isinstance(extension.value.func, ast.Attribute)
            or extension.value.func.attr != 'extend' or not isinstance(extension.value.func.value, ast.Name)
            or extension.value.func.value.id != binding.targets[0].id or len(extension.value.args) != 1):
        return
    name, call = binding.targets[0].id, extension.value
    comp = call.args[0]
    if (not isinstance(comp, ast.ListComp) or len(comp.generators) != 1
            or any(getattr(value, '_bcopt_numeric_kind', None) != 'int' for value in [*binding.value.elts, comp.elt])):
        return
    gen = comp.generators[0]
    if (gen.ifs or gen.is_async or not isinstance(gen.target, ast.Tuple) or len(gen.target.elts) != 2
            or any(not isinstance(item, ast.Name) for item in gen.target.elts)
            or not isinstance(gen.iter, ast.Call) or gen.iter.keywords or len(gen.iter.args) != 2
            or tables.builder.program.resolve(tables.builder.module, gen.iter.func) not in {'zip', 'builtins.zip'}):
        return
    route, tail = gen.iter.args
    if (not isinstance(route, ast.Name) or getattr(route, '_bcopt_numeric_kind', None) != 'tuple'
            or not isinstance(tail, ast.Subscript) or not isinstance(tail.value, ast.Name) or tail.value.id != route.id
            or not isinstance(tail.slice, ast.Slice) or tail.slice.upper is not None or tail.slice.step is not None
            or not isinstance(tail.slice.lower, ast.Constant) or type(tail.slice.lower.value) is not int
            or tail.slice.lower.value != 1):
        return
    edge = comp.elt
    if (not isinstance(edge, ast.Subscript) or not isinstance(edge.value, ast.Subscript)
            or not isinstance(edge.value.value, ast.Name)
            or not isinstance(edge.value.slice, ast.Name) or edge.value.slice.id != gen.target.elts[0].id
            or not isinstance(edge.slice, ast.Name) or edge.slice.id != gen.target.elts[1].id):
        return
    def static_snapshot(node):
        expanded = tables.expand(node, aliases)
        return tables.projection(expanded) and all(part.id == tables.root for part in ast.walk(expanded)
                                                   if isinstance(part, ast.Name))
    if not static_snapshot(edge.value.value):
        return
    first, last = binding.value.elts
    if (not isinstance(first, ast.Subscript) or not isinstance(last, ast.Subscript)
            or not isinstance(first.value, ast.Subscript) or not isinstance(last.value, ast.Subscript)
            or not isinstance(first.value.value, ast.Name)
            or ast.dump(first.value) != ast.dump(last.value) or not static_snapshot(first.value.value)
            or not isinstance(first.value.slice, (ast.Name, ast.Constant))
            or getattr(first.value.slice, '_bcopt_numeric_kind', None) != 'int'):
        return
    for value, index in ((first.slice, 0), (last.slice, -1)):
        expanded = tables.expand(value, aliases)
        if (not isinstance(expanded, ast.Subscript) or not isinstance(expanded.value, ast.Name)
                or expanded.value.id != route.id):
            return
        try:
            actual = ast.literal_eval(expanded.slice)
        except (ValueError, TypeError):
            return
        if type(actual) is not int or actual != index:
            return
    # No aliases, later mutation, or escaping list uses. Original primitive
    # reads may become native extrema/reduction calls in subsequent passes.
    parents = {child: parent for parent in ast.walk(tables.entry.function) for child in ast.iter_child_nodes(parent)}
    stores = [node for node in parents if isinstance(node, ast.Name) and node.id == name
              and isinstance(node.ctx, (ast.Store, ast.Del))]
    if stores != binding.targets:
        return
    for node, parent in parents.items():
        if not isinstance(node, ast.Name) or node.id != name or not isinstance(node.ctx, ast.Load):
            continue
        if parent is call.func:
            continue
        if isinstance(parent, ast.Subscript) and parent.value is node and isinstance(parent.ctx, ast.Load):
            continue
        if isinstance(parent, ast.comprehension) and parent.iter is node:
            continue
        if isinstance(parent, ast.Call) and node in parent.args:
            if getattr(parent, '_bcopt_numeric_native', None) in {'sum', 'min', 'max', 'any', 'all'}:
                continue
            if tables.builder.program.resolve(tables.builder.module, parent.func) in {'len', 'builtins.len'}:
                continue
        return
    binding._bcopt_incremental_edges = True
    binding._bcopt_edge_integer_tables = all(
        getattr(value.value, '_bcopt_numeric_kind', None) in {'list', 'tuple'}
        and getattr(value.value.value, '_bcopt_numeric_kind', None) in {'list', 'tuple'}
        for value in (first, last, edge))
    extension._bcopt_incremental_extension = True


class IncrementalEdges:
    def __init__(self, options):
        self.options, self.changes = options, []
        self.taken = set()
        self.slots = {}

    def fresh(self, stem):
        name = '_bcopt_edge_'+stem
        while name in self.taken:
            name += '_'
        self.taken.add(name)
        return name

    def apply(self, tree):
        if 'insertion-incremental-edges' in self.options.disabled:
            return tree
        self.taken = used_names(tree)
        self.length = self.fresh('len')
        functions = {node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)}
        for consumer in list(tree.body):
            if not getattr(consumer, '_bcopt_numeric_consumer', None):
                continue
            writes = Counter(node.id for node in ast.walk(consumer) if isinstance(node, ast.Name)
                             and isinstance(node.ctx, (ast.Store, ast.Del)))
            stable = {part.id for node in consumer.body if isinstance(node, ast.Assign)
                      and getattr(node, '_bcopt_snapshot_hoisted', False)
                      for target in node.targets for part in ast.walk(target)
                      if isinstance(part, ast.Name) and writes[part.id] == 1}
            for loop in list(ast.walk(consumer)):
                producer_name = getattr(loop, '_bcopt_keyed_producer', None)
                if producer_name not in functions or not isinstance(loop, ast.For) or not isinstance(loop.target, ast.Tuple):
                    continue
                producer = functions[producer_name]
                starts = [node for node in ast.walk(producer) if getattr(node, '_bcopt_insertion_group_begin', False)]
                yields = [node for node in ast.walk(producer) if isinstance(node, ast.Yield)]
                if not starts or not yields or any(not hasattr(node, '_bcopt_insertion_position') for node in yields):
                    continue
                group, position = self.fresh('group'), self.fresh('position')
                route = loop.target.elts[0].id
                loop_writes = {part.id for statement in loop.body for part in ast.walk(statement)
                               if isinstance(part, ast.Name) and isinstance(part.ctx, (ast.Store, ast.Del))}
                loop_writes.update(part.id for part in ast.walk(loop.target) if isinstance(part, ast.Name))
                owner, changed = self, []
                class Edges(ast.NodeTransformer):
                    def generic_visit(self, node):
                        node = super().generic_visit(node)
                        for field, body in ast.iter_fields(node):
                            if not isinstance(body, list) or not body or not isinstance(body[0], ast.stmt):
                                continue
                            for index in range(len(body)-1):
                                binding, extension = body[index:index+2]
                                if (not getattr(binding, '_bcopt_incremental_edges', False)
                                        or not getattr(extension, '_bcopt_incremental_extension', False)):
                                    continue
                                result = owner.replacement(binding, extension, route, group, position,
                                                           stable=stable, loop_writes=loop_writes)
                                if result is not None:
                                    body[index:index+2] = result
                                    changed.append(binding)
                                    break
                        return node
                Edges().visit(loop)
                if not changed:
                    continue
                # Each certified sequence gets a distinct state slot; duplicated
                # ready/fallback versions also remain independent.
                count = len(changed)
                class Start(ast.NodeTransformer):
                    def visit_Assign(self, node):
                        if node in starts:
                            init = ast.parse(f'{group} = [None] * {count}').body[0]
                            init._bcopt_private_cache_slots = True
                            return [init, node]
                        return self.generic_visit(node)
                Start().visit(producer)
                for yielded in yields:
                    yielded.value.elts.extend([ast.Name(id=group, ctx=ast.Load()),
                        ast.Name(id=yielded._bcopt_insertion_position, ctx=ast.Load())])
                loop.target.elts.extend([ast.Name(id=group, ctx=ast.Store()), ast.Name(id=position, ctx=ast.Store())])
                self.changes.append(Change('insertion-incremental-edges', loop.lineno,
                    'certified private edge sequences', ast.unparse(ast.fix_missing_locations(loop))))
        if self.changes:
            index = 1 if tree.body and isinstance(tree.body[0], ast.Expr) and isinstance(tree.body[0].value, ast.Constant) else 0
            while index < len(tree.body) and isinstance(tree.body[index], ast.ImportFrom) and tree.body[index].module == '__future__':
                index += 1
            tree.body.insert(index, ast.ImportFrom(module='builtins', names=[ast.alias(name='len', asname=self.length)], level=0))
        return ast.fix_missing_locations(tree)

    def replacement(self, binding, extension, route, group, position, *, stable=frozenset(), loop_writes=None):
        # Earlier passes can change shape without preserving applicability.
        if (not isinstance(binding, ast.Assign) or len(binding.targets) != 1 or not isinstance(binding.targets[0], ast.Name)
                or not isinstance(binding.value, ast.List) or len(binding.value.elts) != 2
                or not isinstance(extension, ast.Expr) or not isinstance(extension.value, ast.Call)
                or len(extension.value.args) != 1):
            return None
        first, last = binding.value.elts
        comp = extension.value.args[0]
        if (not isinstance(comp, ast.ListComp) or len(comp.generators) != 1
                or not isinstance(comp.generators[0].iter, ast.Call)
                or not isinstance(comp.generators[0].iter.args[0], ast.Name)
                or comp.generators[0].iter.args[0].id != route
                or not isinstance(first, ast.Subscript) or not isinstance(first.value, ast.Subscript)
                or not isinstance(first.value.value, ast.Name)
                or not isinstance(first.value.slice, (ast.Name, ast.Constant))
                or not isinstance(comp.elt, ast.Subscript) or not isinstance(comp.elt.value, ast.Subscript)
                or not isinstance(comp.elt.value.value, ast.Name)):
            return None
        # Fresh slot per static sequence, including cloned prepared/fallback paths.
        slot = self.slots.get(group, 0)
        self.slots[group] = slot + 1
        state, left, right = (self.fresh(stem) for stem in ('state', 'left', 'right'))
        legs, table, axis, matrix = binding.targets[0].id, first.value.value.id, ast.unparse(first.value.slice), comp.elt.value.value.id
        context, checks = [], []
        for value in (table, matrix):
            if value not in stable:
                checks.append(f'{state}[{2+len(context)}] is not {value}')
                context.append(value)
        axis_stable = (isinstance(first.value.slice, ast.Constant)
                       or loop_writes is not None and axis not in loop_writes)
        if not axis_stable:
            checks.append(f'{state}[{2+len(context)}] != {axis}')
            context.append(axis)
        guard = ''.join(' or '+check for check in checks)
        text = f'''{state} = {group}[{slot}]
if {state} is None or {position} != {state}[0] + 1{guard}:
    pass
else:
    {legs} = {state}[1]
    {left}, {right} = {route}[{position} - 1], {route}[{position}]
    if {position} == 1:
        {legs}[0] = {ast.unparse(first)}
    else:
        {legs}[{position}] = {matrix}[{route}[{position} - 2]][{left}]
    {legs}[{position} + 1] = {matrix}[{left}][{right}]
    if {position} == {self.length}({route}) - 1:
        {legs}[1] = {ast.unparse(last)}
    else:
        {legs}[{position} + 2] = {matrix}[{right}][{route}[{position} + 1]]
    {state}[0] = {position}
'''
        result = ast.parse(text).body
        result[0]._bcopt_edge_cache_read = True
        result[1]._bcopt_edge_cache_update = True
        if not context:
            result[1]._bcopt_edge_algebra = dict(route=route, position=position, legs=legs,
                                                terminals=table, matrix=matrix, axis=axis)
        for node in ast.walk(ast.Module(body=result, type_ignores=[])):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == self.length:
                node._bcopt_known_len = True
        saved_context = ''.join(', '+value for value in context)
        result[1].body = [copy.deepcopy(binding), copy.deepcopy(extension),
            *ast.parse(f'{group}[{slot}] = [{position}, {legs}{saved_context}]').body]
        return result
