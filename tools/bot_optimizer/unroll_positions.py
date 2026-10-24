"""Bounded unrolling of certified primitive insertion positions.

Single-iteration loops preserve consumer continues. Every escaping source break
has the fusion emitter's halt flag; an immediate halt test exits the enclosing
item loop after that iteration. Nested loops and their control flow remain intact.
Only exact emitter-owned integer position/size values are constant-folded.
"""

import ast
import copy

from .model import Change
from .records import used_names


class Constants(ast.NodeTransformer):
    def __init__(self, values):
        self.values = values

    def visit_Name(self, node):
        if isinstance(node.ctx, ast.Load) and node.id in self.values:
            return ast.copy_location(ast.Constant(self.values[node.id]), node)
        return node

    def visit_BinOp(self, node):
        self.generic_visit(node)
        if (isinstance(node.left, ast.Constant) and type(node.left.value) is int
                and isinstance(node.right, ast.Constant) and type(node.right.value) is int):
            if isinstance(node.op, ast.Add):
                return ast.Constant(node.left.value+node.right.value)
            if isinstance(node.op, ast.Sub):
                return ast.Constant(node.left.value-node.right.value)
        return node

    def visit_Compare(self, node):
        self.generic_visit(node)
        if (len(node.ops) == 1 and isinstance(node.left, ast.Constant) and type(node.left.value) is int
                and isinstance(node.comparators[0], ast.Constant) and type(node.comparators[0].value) is int):
            a, b = node.left.value, node.comparators[0].value
            operations = {ast.Eq:a==b, ast.NotEq:a!=b, ast.Lt:a<b, ast.LtE:a<=b, ast.Gt:a>b, ast.GtE:a>=b}
            if type(node.ops[0]) in operations:
                return ast.Constant(operations[type(node.ops[0])])
        return node

    def visit_If(self, node):
        self.generic_visit(node)
        if isinstance(node.test, ast.Constant) and type(node.test.value) is bool:
            return node.body if node.test.value else node.orelse
        return node


def safe_breaks(body, halt):
    for index, node in enumerate(body):
        if isinstance(node, ast.Break):
            if not index:
                return False
            prior = body[index-1]
            if (not isinstance(prior, ast.Assign) or len(prior.targets) != 1
                    or not isinstance(prior.targets[0], ast.Name) or prior.targets[0].id != halt
                    or not isinstance(prior.value, ast.Constant) or prior.value.value is not True):
                return False
        if isinstance(node, (ast.For, ast.While)):
            if not safe_breaks(node.orelse, halt):
                return False
            continue
        if isinstance(node, ast.Try):
            if any(not safe_breaks(handler.body, halt) for handler in node.handlers):
                return False
        for _, value in ast.iter_fields(node):
            if isinstance(value, list) and value and all(isinstance(part, ast.stmt) for part in value):
                if not safe_breaks(value, halt):
                    return False
    return True


class UnrollPositions:
    def __init__(self, options):
        self.options, self.changes = options, []

    def apply(self, tree):
        if 'insertion-unroll-positions' in self.options.disabled:
            return tree
        taken = used_names(tree)
        once = '_bcopt_position_once'
        while once in taken:
            once += '_'
        for consumer in tree.body:
            if not getattr(consumer, '_bcopt_fused_consumer', False):
                continue
            loops = [node for node in ast.walk(consumer) if isinstance(node, ast.For)
                     and getattr(node, '_bcopt_direct_positions', None)]
            count = sum(1 for _ in ast.walk(consumer))
            candidates = []
            for loop in loops:
                width, size = loop._bcopt_direct_positions
                halt = getattr(loop, '_bcopt_fused_halt', None)
                if (type(width) is not int or not 2 <= width <= 12 or not isinstance(loop.target, ast.Name)
                        or not isinstance(halt, str) or not halt or loop.orelse or not safe_breaks(loop.body, halt)):
                    continue
                position = loop.target.id
                if any(isinstance(node, ast.Name) and node.id in {size, position}
                       and isinstance(node.ctx, (ast.Store, ast.Del)) for statement in loop.body for node in ast.walk(statement)):
                    continue
                count += (width-1)*sum(1 for _ in ast.walk(loop))+width*20
                candidates.append((loop,width,size,position,halt))
            # A function-wide bound avoids accepting an arbitrary partial subset.
            if count > 262144:
                continue
            replacements = {}
            for loop,width,size,position,halt in candidates:
                expanded = []
                for index in range(width):
                    body = Constants({position:index,size:width}).visit(
                        ast.Module(body=copy.deepcopy(loop.body),type_ignores=[])).body
                    expanded.append(ast.Assign(targets=[ast.Name(id=position,ctx=ast.Store())],value=ast.Constant(index)))
                    expanded.append(ast.For(target=ast.Name(id=once,ctx=ast.Store()),
                        iter=ast.Tuple(elts=[ast.Constant(None)],ctx=ast.Load()),body=body,orelse=[]))
                    expanded[-1]._bcopt_unrolled_position = (width, index, size)
                    expanded.append(ast.If(test=ast.Name(id=halt,ctx=ast.Load()),body=[ast.Break()],orelse=[]))
                replacements[loop] = expanded
                self.changes.append(Change('insertion-unroll-positions',loop.lineno,
                    'bounded insertion position loop',f'{width} primitive positions with preserved break/continue boundaries'))
            class Replace(ast.NodeTransformer):
                def visit_For(self,node):
                    return replacements[node] if node in replacements else self.generic_visit(node)
            Replace().visit(consumer)
        return ast.fix_missing_locations(tree)
