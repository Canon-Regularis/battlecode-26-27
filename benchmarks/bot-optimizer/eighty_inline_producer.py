"""Research-only fusion of a private primitive insertion producer and consumer.

Fresh public route tuples remain. Private metadata travels in locals instead of
yielded tuples. A halt flag propagates consumer breaks through producer loops;
private buffer removal is finally-protected across consumer continue/break.
"""

import argparse
import ast
import copy
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import tools.bot_optimizer.compare as measurement
from tools.bot_optimizer.analysis import Bindings, arguments
from tools.bot_optimizer.records import used_names
from tools.bot_optimizer.model import Options


def transform(folder, invariants=False):
    path = folder/'src/planner.py'
    tree = ast.parse(path.read_text())
    producer, = [node for node in tree.body if isinstance(node, ast.FunctionDef)
                 and node.name.startswith('_bcopt_insertion_key_producer')]
    consumer, = [node for node in tree.body if isinstance(node, ast.FunctionDef)
                 and node.name.startswith('_bcopt_region_consumer_')]
    loop, = [node for node in ast.walk(consumer) if isinstance(node, ast.For)
             and isinstance(node.iter, ast.Call) and isinstance(node.iter.func, ast.Name)
             and node.iter.func.id == producer.name]
    assert not loop.orelse and isinstance(loop.target, ast.Tuple)
    taken = used_names(tree)
    def fresh(stem):
        name = '_bcopt_fused80_'+stem
        while name in taken:
            name += '_'
        taken.add(name)
        return name
    halted = fresh('halted')
    producer = copy.deepcopy(producer)
    names = set(Bindings(producer.body).counts) | {arg.arg for arg in arguments(producer)}
    rename = {name: fresh(name) for name in sorted(names)}
    yields = [node for node in ast.walk(producer) if isinstance(node, ast.Yield)]
    assert len(yields) == 2
    # Metadata outputs are private names with the same lifetime for the whole
    # group, except the insertion position, which is already a loop target.
    for yielded in yields:
        assert isinstance(yielded.value, ast.Tuple)
        assert len(yielded.value.elts) == len(loop.target.elts)
        for value, target in zip(yielded.value.elts[1:], loop.target.elts[1:]):
            assert isinstance(value, ast.Name) and isinstance(target, ast.Name)
            rename[value.id] = target.id
    class ExactTuple(ast.NodeTransformer):
        def visit_If(self, node):
            if isinstance(node.test, ast.Name) and node.test.id.startswith('_bcopt_insert_exact_'):
                return node.body
            return self.generic_visit(node)
    ExactTuple().visit(producer)
    class Rename(ast.NodeTransformer):
        def visit_Name(self, node):
            if node.id in rename:
                node.id = rename[node.id]
            return node
    Rename().visit(producer)
    bindings = [ast.Assign(targets=[ast.Name(id=rename[arg.arg], ctx=ast.Store())], value=copy.deepcopy(value))
                for arg, value in zip(arguments(producer), loop.iter.args)]
    assert len(bindings) == len(arguments(producer)) and not loop.iter.keywords
    class Stop(ast.NodeTransformer):
        def visit_For(self, node):
            return node
        def visit_While(self, node):
            return node
        def visit_Break(self, node):
            return [*ast.parse(f'{halted} = True').body, node]
    consumer_body = Stop().visit(ast.Module(body=copy.deepcopy(loop.body), type_ignores=[])).body
    if invariants:
        size = fresh('size')
        bindings.extend(ast.parse(f'{size} = len({rename[arguments(producer)[0].arg]}) + 1').body)
        class Invariants(ast.NodeTransformer):
            def visit_Call(self, node):
                if (isinstance(node.func, ast.Name) and node.func.id.startswith(
                        ('_bcopt_ordered_len', '_bcopt_edge_len', '_bcopt_compensated_len'))
                        and len(node.args) == 1 and isinstance(node.args[0], ast.Name)
                        and node.args[0].id == loop.target.elts[0].id and not node.keywords):
                    return ast.Name(id=size, ctx=ast.Load())
                return self.generic_visit(node)
            def visit_If(self, node):
                if (isinstance(node.test, ast.UnaryOp) and isinstance(node.test.op, ast.Not)
                        and isinstance(node.test.operand, ast.Name)
                        and node.test.operand.id == loop.target.elts[0].id):
                    return [self.visit(part) for part in node.orelse]
                return self.generic_visit(node)
        consumer_body = Invariants().visit(ast.Module(body=consumer_body, type_ignores=[])).body
    class Fuse(ast.NodeTransformer):
        def visit_For(self, node):
            contains = any(isinstance(part, ast.Yield) for part in ast.walk(node))
            if not contains:
                return node
            yielded = next((i for i, part in enumerate(node.body)
                            if isinstance(part, ast.Expr) and isinstance(part.value, ast.Yield)), None)
            if yielded is not None:
                value = node.body[yielded].value.value.elts[0]
                prefix, suffix = node.body[:yielded], node.body[yielded+1:]
                assert not suffix or len(suffix) == 1 and isinstance(suffix[0], ast.Delete)
                body = [ast.Assign(targets=[copy.deepcopy(loop.target.elts[0])], value=value),
                        *copy.deepcopy(consumer_body)]
                if suffix:
                    body = [ast.Try(body=body, handlers=[], orelse=[], finalbody=suffix)]
                node.body = [*prefix, *body]
            else:
                self.generic_visit(node)
                node.body.extend(ast.parse(f'if {halted}:\n    break').body)
            return node
    Fuse().visit(producer)
    assert not any(isinstance(node, ast.Yield) for node in ast.walk(producer))
    body = producer.body
    if isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
        body = body[1:]
    replacement = [*bindings, *ast.parse(f'{halted} = False').body, *body]
    class Replace(ast.NodeTransformer):
        def visit_For(self, node):
            return replacement if node is loop else self.generic_visit(node)
    Replace().visit(consumer)
    source = ast.unparse(ast.fix_missing_locations(tree))+'\n'
    compile(source, str(path), 'exec')
    path.write_text(source)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('bot', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--invariants', action='store_true')
    args = parser.parse_args()
    original = measurement.optimize_folder
    def compile_variant(bot, output, options):
        report = original(bot, output, options)
        if options.disabled == frozenset({'insertion-producer-fusion'}):
            transform(output, invariants=args.invariants)
            report['pass_counts']['experiment-inline-producer'] = 1
        return report
    measurement.optimize_folder = compile_variant
    report = measurement.compare(args.bot, args.output, target='draft_planner:DraftPlanner.build',
                                 maps=('collision',), repeats=1, output_prefix='SQUAD_LOOPS_DATA ',
                                 options=Options(disabled=frozenset({'insertion-producer-fusion'})))
    report['experimental_post_compile_transform'] = 'private insertion producer fusion, research only'
    report['producer_invariants'] = args.invariants
    (args.output/'results.json').write_text(json.dumps(report, indent=2)+'\n')
    for row in report['comparisons']:
        print(row['map'], row['side'], row['reduction_percent'])


if __name__ == '__main__':
    main()
