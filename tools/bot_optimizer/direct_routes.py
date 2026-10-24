"""Construct fresh insertion tuples directly from certified primitive base slots.

Width specialization proves the exact base length. The original buffer producer
proves native tuple construction and private insert/delete behavior; the late
pass rechecks every buffer use before replacing that roundtrip. Original outer
buffer allocation/cleanup and all consumer control flow remain in place.
"""

import ast
import copy

from .model import Change
from .records import used_names


def named(node, value):
    return isinstance(node, ast.Name) and node.id == value


class DirectRoutes:
    def __init__(self, options):
        self.options, self.changes = options, []
        self.taken = set()
        self.items = []

    def fresh(self, stem):
        value = '_bcopt_direct_'+stem
        while value in self.taken:
            value += '_'
        self.taken.add(value)
        return value

    def rewrite(self, branch):
        width = branch._bcopt_width_specialization
        if type(width) is not int or not 2 <= width <= 12 or len(branch.body) != 1:
            return
        producer = branch.body[0]
        fact = getattr(producer, '_bcopt_fused_insertion', None)
        if (not isinstance(producer, ast.For) or not fact
                or set(fact) != {'base', 'item', 'position', 'route', 'size'}
                or not named(producer.target, fact['item'])
                or not isinstance(branch.test, ast.Compare) or not named(branch.test.left, fact['size'])
                or len(branch.test.ops) != 1 or not isinstance(branch.test.ops[0], ast.Eq)
                or len(branch.test.comparators) != 1 or not isinstance(branch.test.comparators[0], ast.Constant)
                or type(branch.test.comparators[0].value) is not int or branch.test.comparators[0].value != width):
            return
        loops = [node for node in ast.walk(producer) if isinstance(node, ast.For)
                 and named(node.target, fact['position'])]
        if len(loops) != 1:
            return
        loop = loops[0]
        natives = getattr(loop, '_bcopt_tuple_buffer_loop', None)
        if not isinstance(natives, tuple) or len(natives) != 3 or loop.orelse or len(loop.body) != 2:
            return
        native_tuple, native_range, native_len = natives
        insertion, protected = loop.body
        if (not isinstance(insertion, ast.Expr) or not isinstance(insertion.value, ast.Call)
                or not isinstance(insertion.value.func, ast.Attribute) or insertion.value.func.attr != 'insert'
                or not isinstance(insertion.value.func.value, ast.Name) or insertion.value.keywords
                or len(insertion.value.args) != 2 or not named(insertion.value.args[0], fact['position'])
                or not named(insertion.value.args[1], fact['item'])
                or not isinstance(protected, ast.Try) or protected.handlers or protected.orelse
                or len(protected.finalbody) != 1 or not protected.body):
            return
        work = insertion.value.func.value.id
        cleanup = protected.finalbody[0]
        if (not isinstance(cleanup, ast.Delete) or len(cleanup.targets) != 1
                or not isinstance(cleanup.targets[0], ast.Subscript) or not named(cleanup.targets[0].value, work)
                or not named(cleanup.targets[0].slice, fact['position'])):
            return
        route = protected.body[0]
        if (not isinstance(route, ast.Assign) or len(route.targets) != 1 or not named(route.targets[0], fact['route'])
                or not isinstance(route.value, ast.Call) or not named(route.value.func, native_tuple)
                or route.value.keywords or len(route.value.args) != 1 or not named(route.value.args[0], work)):
            return
        if sum(named(node, work) for node in ast.walk(producer)) != 3:
            return
        # Check the original index sequence; no arbitrary or skipped positions.
        iterator = loop.iter
        if (not isinstance(iterator, ast.Call) or not named(iterator.func, native_range)
                or iterator.keywords or len(iterator.args) != 1
                or not isinstance(iterator.args[0], ast.BinOp) or not isinstance(iterator.args[0].op, ast.Add)
                or not isinstance(iterator.args[0].right, ast.Constant) or type(iterator.args[0].right.value) is not int
                or iterator.args[0].right.value != 1):
            return
        length = iterator.args[0].left
        if (not isinstance(length, ast.Call) or not named(length.func, native_len)
                or length.keywords or len(length.args) != 1
                or not named(length.args[0], fact['base'])):
            return
        values = self.items[:width-1]
        unpack = ast.Assign(targets=[ast.Tuple(elts=[ast.Name(id=value, ctx=ast.Store()) for value in values], ctx=ast.Store())],
                            value=ast.Name(id=fact['base'], ctx=ast.Load()))
        unpack._bcopt_direct_base = (fact['base'], tuple(values))
        def dispatch(low, high):
            if low == high:
                fields = values[:low]+[fact['item']]+values[low:]
                result = ast.Assign(targets=copy.deepcopy(route.targets), value=ast.Tuple(
                    elts=[ast.Name(id=value, ctx=ast.Load()) for value in fields], ctx=ast.Load()))
                result._bcopt_direct_tuple = (fact['route'], fact['item'], tuple(fields))
                return [result]
            mid = (low+high)//2
            return [ast.If(test=ast.Compare(left=ast.Name(id=fact['position'], ctx=ast.Load()),
                ops=[ast.LtE()], comparators=[ast.Constant(mid)]), body=dispatch(low,mid), orelse=dispatch(mid+1,high))]
        loop.body = [*dispatch(0,width-1), *protected.body[1:]]
        loop._bcopt_direct_positions = (width, fact['size'])
        branch.body.insert(0, unpack)
        self.changes.append(Change('insertion-direct-routes', producer.lineno,
            'private insertion buffer tuple roundtrip', f'fresh direct tuple via balanced dispatch at width {width}'))

    def apply(self, tree):
        if 'insertion-direct-routes' in self.options.disabled:
            return tree
        self.taken = used_names(tree)
        self.items = [self.fresh(f'item_{index}') for index in range(11)]
        for consumer in tree.body:
            if not getattr(consumer, '_bcopt_fused_consumer', False):
                continue
            for branch in list(ast.walk(consumer)):
                if isinstance(branch, ast.If) and getattr(branch, '_bcopt_width_specialization', None):
                    self.rewrite(branch)
        return ast.fix_missing_locations(tree)
