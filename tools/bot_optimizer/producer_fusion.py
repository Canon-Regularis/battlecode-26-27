"""Fuse certified private primitive insertion producers into closed consumers.

Source certification excludes observable generator effects and nonprimitive local
lifetimes. Only emitter-created metadata crosses the private yield boundary.
Fresh route tuples, evaluation order and protected buffer cleanup are retained.
"""

import ast
import copy

from .analysis import Bindings, arguments
from .model import Change
from .program import body_without_docstring
from .records import used_names


def certify_producer(builder, proof, function, matches):
    body = body_without_docstring(function.body)
    if (len(matches) != 1 or len(body) != 1 or not isinstance(body[0], ast.For)
            or function.args.defaults or any(function.args.kw_defaults)
            or function.args.vararg or function.args.kwarg or function.args.kwonlyargs):
        return
    inner, (base, item, position) = matches[0]
    outer = body[0]
    params = {arg.arg for arg in arguments(function)}
    if (not isinstance(outer.target, ast.Name) or outer.target.id != item
            or outer.orelse or not isinstance(outer.iter, ast.Call) or outer.iter.keywords
            or not isinstance(outer.iter.func, ast.Name) or outer.iter.func.id in params | {item, position}
            or builder.program.resolve(builder.module, outer.iter.func) not in {'range', 'builtins.range'}
            or not 1 <= len(outer.iter.args) <= 3 or base not in params
            or item in params or position in params or item == position):
        return
    # Only checked scalar parameters and literal integer bounds. Reading any
    # external mutable state during generator resumption would need another proof.
    for bound in outer.iter.args:
        values = {shape for cell in proof.expressions.get(bound, ()) for shape in cell.shapes}
        if not values or any(shape.kind != 'int' for shape in values):
            return
        if isinstance(bound, ast.Name) and bound.id in params:
            continue
        try:
            value = ast.literal_eval(bound)
        except (ValueError, TypeError):
            return
        if type(value) is not int:
            return
    if params != {base, *(bound.id for bound in outer.iter.args if isinstance(bound, ast.Name))}:
        return  # Even an unused argument could otherwise extend an observable lifetime.
    if outer.body[-1] is not inner or len(outer.body) > 2:
        return
    if len(outer.body) == 2:
        skip = outer.body[0]
        if (not isinstance(skip, ast.If) or skip.orelse or len(skip.body) != 1
                or not isinstance(skip.body[0], ast.Continue) or not isinstance(skip.test, ast.Compare)
                or len(skip.test.ops) != 1 or not isinstance(skip.test.ops[0], (ast.In, ast.NotIn))
                or not isinstance(skip.test.left, ast.Name) or skip.test.left.id != item
                or len(skip.test.comparators) != 1 or not isinstance(skip.test.comparators[0], ast.Name)
                or skip.test.comparators[0].id != base):
            return
    function._bcopt_primitive_insertion_source = base


class ProducerFusion:
    def __init__(self, options):
        self.options, self.changes = options, []
        self.taken = set()

    def fresh(self, stem):
        name = '_bcopt_fused_'+stem
        while name in self.taken:
            name += '_'
        self.taken.add(name)
        return name

    def fuse(self, consumer, loop, producer):
        base = getattr(producer, '_bcopt_primitive_insertion_source', None)
        if (base is None or loop.orelse or not isinstance(loop.target, ast.Tuple)
                or not all(isinstance(part, ast.Name) for part in loop.target.elts)
                or not isinstance(loop.iter, ast.Call) or loop.iter.keywords
                or len(loop.iter.args) != len(arguments(producer))):
            return None
        route, *outputs = [part.id for part in loop.target.elts]
        writes = {node.id for statement in loop.body for node in ast.walk(statement)
                  if isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del))}
        if writes & {route, *outputs}:
            return None
        local = set(Bindings(producer.body).counts) | {arg.arg for arg in arguments(producer)}
        loads = {node.id for node in ast.walk(producer) if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load)}
        caller_local = set(Bindings(consumer.body).counts) | {arg.arg for arg in arguments(consumer)}
        if (loads-local) & caller_local:
            return None
        producer = copy.deepcopy(producer)
        aliases = {name: self.fresh(name) for name in sorted(local)}
        yields = [node for node in ast.walk(producer) if isinstance(node, ast.Yield)]
        if not yields or len(yields) > 2:
            return None
        mapping = {}
        for node in yields:
            if (not hasattr(node, '_bcopt_insertion_position') or not isinstance(node.value, ast.Tuple)
                    or len(node.value.elts) != len(loop.target.elts)):
                return None
            for value, target in zip(node.value.elts[1:], outputs):
                if not isinstance(value, ast.Name) or value.id not in local:
                    return None
                if value.id in mapping and mapping[value.id] != target:
                    return None
                mapping[value.id] = target
        aliases.update(mapping)
        class ExactTuple(ast.NodeTransformer):
            def visit_If(self, node):
                if getattr(node, '_bcopt_insertion_exact_branch', False):
                    return node.body
                return self.generic_visit(node)
        ExactTuple().visit(producer)
        active_yields = [node for node in ast.walk(producer) if isinstance(node, ast.Yield)]
        if len(active_yields) != 1:
            return None
        # Only the emitter's position loop may directly contain the yield. Its
        # sole post-yield action is removal from a private primitive buffer.
        position_loops = [node for node in ast.walk(producer) if isinstance(node, ast.For)
                          and any(isinstance(part, ast.Expr) and isinstance(part.value, ast.Yield) for part in node.body)]
        if len(position_loops) != 1:
            return None
        position_loop = position_loops[0]
        index = next(i for i, part in enumerate(position_loop.body)
                     if isinstance(part, ast.Expr) and isinstance(part.value, ast.Yield))
        suffix = position_loop.body[index+1:]
        if suffix and (len(suffix) != 1 or not isinstance(suffix[0], ast.Delete)
                       or len(suffix[0].targets) != 1 or not isinstance(suffix[0].targets[0], ast.Subscript)):
            return None
        class Rename(ast.NodeTransformer):
            def visit_Name(self, node):
                if node.id in aliases:
                    node.id = aliases[node.id]
                return node
        Rename().visit(producer)
        bindings = [ast.Assign(targets=[ast.Name(id=aliases[arg.arg], ctx=ast.Store())], value=copy.deepcopy(value))
                    for arg, value in zip(arguments(producer), loop.iter.args)]
        halted, size = self.fresh('halted'), self.fresh('size')
        class Control(ast.NodeTransformer):
            def visit_For(self, node):
                return node
            def visit_While(self, node):
                return node
            def visit_Break(self, node):
                return [*ast.parse(f'{halted} = True').body, node]
        body = Control().visit(ast.Module(body=copy.deepcopy(loop.body), type_ignores=[])).body
        class Invariants(ast.NodeTransformer):
            def visit_Call(self, node):
                if (getattr(node, '_bcopt_known_len', False) and len(node.args) == 1 and not node.keywords
                        and isinstance(node.args[0], ast.Name) and node.args[0].id == route):
                    return ast.copy_location(ast.Name(id=size, ctx=ast.Load()), node)
                return self.generic_visit(node)
            def visit_If(self, node):
                if (isinstance(node.test, ast.UnaryOp) and isinstance(node.test.op, ast.Not)
                        and isinstance(node.test.operand, ast.Name) and node.test.operand.id == route):
                    result = []
                    for part in node.orelse:
                        replacement = self.visit(part)
                        result.extend(replacement if isinstance(replacement, list) else [replacement])
                    return result
                return self.generic_visit(node)
        body = Invariants().visit(ast.Module(body=body, type_ignores=[])).body
        bindings.extend(ast.parse(f'{size} = {self.length}({aliases[base]}) + 1\n{halted} = False').body)
        outer_loops = [node for node in ast.walk(producer) if isinstance(node, ast.For)
                       and node is not position_loop and position_loop in ast.walk(node)]
        if len(outer_loops) != 1 or not isinstance(outer_loops[0].target, ast.Name):
            return None
        outer_loops[0]._bcopt_fused_insertion = dict(base=aliases[base], item=outer_loops[0].target.id,
            position=position_loop.target.id, route=route, size=size)
        class Fuse(ast.NodeTransformer):
            def visit_For(self, node):
                if not any(isinstance(part, ast.Yield) for part in ast.walk(node)):
                    return node
                if node is position_loop:
                    node._bcopt_fused_halt = halted
                    value = node.body[index].value.value.elts[0]
                    new_body = [ast.Assign(targets=[ast.Name(id=route, ctx=ast.Store())], value=value), *body]
                    node.body = [*node.body[:index], *( [ast.Try(body=new_body, handlers=[], orelse=[], finalbody=suffix)]
                                                      if suffix else new_body)]
                else:
                    self.generic_visit(node)
                    node.body.extend(ast.parse(f'if {halted}:\n    break').body)
                return node
        Fuse().visit(producer)
        if any(isinstance(node, ast.Yield) for node in ast.walk(producer)):
            return None
        return [*bindings, *body_without_docstring(producer.body)]

    def apply(self, tree):
        if 'insertion-producer-fusion' in self.options.disabled:
            return tree
        self.taken = used_names(tree)
        self.length = self.fresh('len')
        functions = {node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)}
        for consumer in list(tree.body):
            if not getattr(consumer, '_bcopt_numeric_consumer', None):
                continue
            owner = self
            class Consumers(ast.NodeTransformer):
                def visit_For(self, node):
                    producer = functions.get(getattr(node, '_bcopt_keyed_producer', None))
                    if producer is None:
                        return self.generic_visit(node)
                    result = owner.fuse(consumer, node, producer)
                    if result is None:
                        return self.generic_visit(node)
                    owner.changes.append(Change('insertion-producer-fusion', node.lineno,
                        'certified private insertion producer', 'fused primitive loops with fresh routes and protected control flow'))
                    consumer._bcopt_fused_consumer = True
                    return result
            Consumers().visit(consumer)
        if self.changes:
            index = 1 if tree.body and isinstance(tree.body[0], ast.Expr) and isinstance(tree.body[0].value, ast.Constant) else 0
            while index < len(tree.body) and isinstance(tree.body[index], ast.ImportFrom) and tree.body[index].module == '__future__':
                index += 1
            tree.body.insert(index, ast.ImportFrom(module='builtins', names=[ast.alias(name='len', asname=self.length)], level=0))
        return ast.fix_missing_locations(tree)
