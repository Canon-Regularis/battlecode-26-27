"""Reuse certified native compensated sums within private insertion groups.

Only emitter-owned native projections over immutable prepared tables qualify.
The first sum remains native, at its original evaluation point. A bounded binary
grid proves permutation invariance for CPython 3.13's high/low accumulator; this
does not authorize changing ordinary sequential floating-point additions.
"""

import ast
from collections import Counter
import copy

from .model import Change
from .records import used_names


CERTIFICATE = '''def certify(values):
    import sys as _sys
    import builtins as _b
    if (_sys.implementation.name != 'cpython' or _sys.version_info[:2] != (3, 13)
            or _sys.float_info.radix != 2 or _sys.float_info.mant_dig != 53
            or _sys.float_info.rounds != 1 or values is None or _b.len(values) > 4096):
        return False
    ratios = []
    denominator = 1
    for value in values:
        if _b.type(value) is not _b.float or not 0.0 <= value < _b.float('inf'):
            return False
        numerator, divisor = value.as_integer_ratio()
        ratios.append((numerator, divisor))
        denominator = _b.max(denominator, divisor)
    maximum = _b.max((numerator * (denominator // divisor) for numerator, divisor in ratios), default=0)
    return maximum.bit_length() <= 80 and (maximum * 32).bit_length() - (denominator.bit_length() - 1) <= 1023
'''


class CompensatedSums:
    def __init__(self, options):
        self.options, self.changes = options, []
        self.taken = set()

    def fresh(self, stem):
        name = '_bcopt_compensated_' + stem
        while name in self.taken:
            name += '_'
        self.taken.add(name)
        return name

    def projection(self, call, route, tables):
        if (not isinstance(call, ast.Call) or not getattr(call, '_bcopt_prepared_native_sum', False)
                or getattr(call, '_bcopt_numeric_native', None) != 'sum'
                or call.keywords or len(call.args) != 1 or not isinstance(call.args[0], ast.IfExp)):
            return None
        # Only the prepared version's exact projection shape qualifies. The
        # outer None/failure choice in the original version deliberately fails.
        choice = call.args[0]
        if (not isinstance(choice.test, ast.Compare) or len(choice.test.ops) != 1
                or not isinstance(choice.test.ops[0], ast.Gt)
                or not isinstance(choice.body, ast.Call) or len(choice.body.args) != 1
                or not isinstance(choice.body.args[0], ast.Name)
                or choice.body.args[0].id not in tables
                or not isinstance(choice.orelse, ast.ListComp) or len(choice.orelse.generators) != 1):
            return None
        table = choice.body.args[0].id
        comp, gen = choice.orelse, choice.orelse.generators[0]
        if (gen.ifs or gen.is_async or not isinstance(gen.iter, ast.Name) or gen.iter.id != route
                or not isinstance(gen.target, ast.Name) or not isinstance(comp.elt, ast.Subscript)
                or not isinstance(comp.elt.value, ast.Name) or comp.elt.value.id != table
                or not isinstance(comp.elt.slice, ast.Name) or comp.elt.slice.id != gen.target.id):
            return None
        return table

    def apply(self, tree):
        if 'insertion-compensated-sums' in self.options.disabled:
            return tree
        self.taken = used_names(tree)
        certificate, length = self.fresh('certify'), self.fresh('len')
        functions = {node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)}
        for consumer in list(tree.body):
            if not getattr(consumer, '_bcopt_numeric_consumer', None):
                continue
            writes = Counter(node.id for node in ast.walk(consumer) if isinstance(node, ast.Name)
                             and isinstance(node.ctx, (ast.Store, ast.Del)))
            tables = {node.targets[0].id: node for node in consumer.body if isinstance(node, ast.Assign)
                      and getattr(node, '_bcopt_prepared_table', False)
                      and getattr(node, '_bcopt_snapshot_hoisted', False)
                      and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name)
                      and writes[node.targets[0].id] == 1}
            preparations = {}
            for loop in list(ast.walk(consumer)):
                producer_name = getattr(loop, '_bcopt_keyed_producer', None)
                if (producer_name not in functions or not isinstance(loop, ast.For)
                        or not isinstance(loop.target, ast.Tuple) or not isinstance(loop.target.elts[0], ast.Name)):
                    continue
                producer = functions[producer_name]
                starts = [node for node in ast.walk(producer) if getattr(node, '_bcopt_insertion_group_begin', False)]
                yields = [node for node in ast.walk(producer) if isinstance(node, ast.Yield)]
                if (not starts or not yields or any(not hasattr(node, '_bcopt_insertion_position')
                        or not isinstance(node.value, ast.Tuple) for node in yields)):
                    continue
                route, slot = loop.target.elts[0].id, self.fresh('slot')
                sites, owner = [], self
                class Memo(ast.NodeTransformer):
                    def visit_AugAssign(self, node):
                        # Consume the cached scalar immediately in arithmetic;
                        # never expose its shared identity as a returned value.
                        if not isinstance(node.target, ast.Name) or not isinstance(node.op, ast.Add):
                            return self.generic_visit(node)
                        table = owner.projection(node.value, route, tables)
                        if table is None:
                            return self.generic_visit(node)
                        if table not in preparations:
                            preparations[table] = owner.fresh('ready')
                        ready, value, index = preparations[table], owner.fresh('value'), len(sites)
                        call = node.value
                        guard = ast.parse(f'''if {ready} and {length}({route}) <= 16:
    {value} = {slot}[{index}]
    if {value} is None:
        pass
else:
    pass
''').body[0]
                        guard._bcopt_compensated_cache = True
                        for part in ast.walk(guard.test):
                            if isinstance(part, ast.Call) and isinstance(part.func, ast.Name) and part.func.id == length:
                                part._bcopt_known_len = True
                        assignment = ast.Assign(targets=[ast.Name(id=value, ctx=ast.Store())], value=copy.deepcopy(call))
                        guard.body[1].body = [assignment, *ast.parse(f'{slot}[{index}] = {value}').body]
                        guard.orelse = [copy.deepcopy(assignment)]
                        node.value = ast.Name(id=value, ctx=ast.Load())
                        sites.append(node)
                        return [guard, node]
                Memo().visit(loop)
                if not sites:
                    continue
                class Start(ast.NodeTransformer):
                    def visit_Assign(self, node):
                        if node in starts:
                            init = ast.parse(f'{slot} = [None] * {len(sites)}').body[0]
                            init._bcopt_private_cache_slots = True
                            return [init, node]
                        return self.generic_visit(node)
                Start().visit(producer)
                for yielded in yields:
                    yielded.value.elts.append(ast.Name(id=slot, ctx=ast.Load()))
                loop.target.elts.append(ast.Name(id=slot, ctx=ast.Store()))
                self.changes.append(Change('insertion-compensated-sums', loop.lineno,
                    'certified native prepared sums', ast.unparse(ast.fix_missing_locations(loop))))
            for table, ready in preparations.items():
                index = consumer.body.index(tables[table]) + 1
                consumer.body[index:index] = ast.parse(f'{ready} = {certificate}({table})').body
        if self.changes:
            helper = ast.parse(CERTIFICATE).body[0]
            helper.name = certificate
            index = 1 if tree.body and isinstance(tree.body[0], ast.Expr) and isinstance(tree.body[0].value, ast.Constant) else 0
            while index < len(tree.body) and isinstance(tree.body[index], ast.ImportFrom) and tree.body[index].module == '__future__':
                index += 1
            tree.body[index:index] = [ast.ImportFrom(module='builtins', names=[ast.alias(name='len', asname=length)], level=0), helper]
        return ast.fix_missing_locations(tree)
