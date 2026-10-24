"""Research-only reuse of invariant reductions and dependent scalar arithmetic.

Compute native operations at their original points on the first successful path;
cache primitive results only after all invariant computations have succeeded.
The private insertion group fixes the input multiset and immutable snapshot.
"""

import argparse
import ast
import copy
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tools.bot_optimizer.records import used_names
from tools.bot_optimizer.model import Options
import tools.bot_optimizer.compare as measurement


def transform(folder):
    path = folder/'src/planner.py'
    tree = ast.parse(path.read_text())
    producer, = [node for node in tree.body if isinstance(node, ast.FunctionDef)
                 and node.name.startswith('_bcopt_insertion_key_producer')]
    consumer, = [node for node in tree.body if isinstance(node, ast.FunctionDef)
                 and node.name.startswith('_bcopt_region_consumer_')]
    slot, state = '_bcopt_scalar80_slot', '_bcopt_scalar80_state'
    assert not {slot, state} & used_names(tree)
    outer, = [node for node in ast.walk(producer) if isinstance(node, ast.For)
              and isinstance(node.target, ast.Name) and node.target.id == 'camp_index']
    outer.body.insert(0, ast.parse(f'{slot} = [None, None]').body[0])
    for node in ast.walk(producer):
        if isinstance(node, ast.Yield):
            node.value.elts.append(ast.Name(id=slot, ctx=ast.Load()))
    route_loop, = [node for node in ast.walk(consumer) if isinstance(node, ast.For)
                   and isinstance(node.target, ast.Tuple) and node.target.elts[0].id == 'route']
    route_loop.target.elts.append(ast.Name(id=slot, ctx=ast.Store()))
    changes = []
    class Scalars(ast.NodeTransformer):
        def generic_visit(self, node):
            node = super().generic_visit(node)
            for _, body in ast.iter_fields(node):
                if not isinstance(body, list) or not body or not isinstance(body[0], ast.stmt):
                    continue
                for index, assignment in enumerate(body):
                    if (not isinstance(assignment, ast.Assign) or not isinstance(assignment.value, ast.Call)
                            or not isinstance(assignment.value.func, ast.Name) or assignment.value.func.id != 'ceil'):
                        continue
                    branch = body[index-1]
                    assert isinstance(branch, ast.If) and len(branch.orelse) == 1
                    unpack = branch.orelse[0]
                    assert isinstance(unpack, ast.Assign) and isinstance(unpack.targets[0], ast.Tuple)
                    reductions = [part.id for part in unpack.targets[0].elts]
                    assert len(reductions) == 4
                    start = index-7
                    assert start >= 0
                    for init in body[start:start+4]:
                        assert isinstance(init, ast.Assign) and init.targets[0].id in reductions
                    ceiling = assignment.targets[0].id
                    maximum = body[index+3]
                    reward = body[index+6]
                    assert isinstance(maximum, ast.Assign) and isinstance(maximum.value, ast.IfExp)
                    assert isinstance(reward, ast.Assign) and isinstance(reward.value, ast.BinOp)
                    assert isinstance(reward.value.op, ast.Add) and reward.value.left.id == reductions[0]
                    assert isinstance(reward.value.right, ast.BinOp) and reward.value.right.right.id == reductions[1]
                    outputs = [*reductions, ceiling, maximum.targets[0].id, reward.targets[0].id]
                    cache_index = len(changes)
                    statements = copy.deepcopy(body[start:index+1])
                    load = ast.parse(f'{state} = {slot}[{cache_index}]\nif {state} is None:\n    pass\nelse:\n    '+', '.join(outputs)+f' = {state}').body
                    load[1].body = statements
                    # Keep the original points for potentially failing max and
                    # reward arithmetic. A hit implies they already succeeded.
                    max_guard = ast.If(test=ast.Compare(left=ast.Name(id=state, ctx=ast.Load()),
                        ops=[ast.Is()], comparators=[ast.Constant(None)]), body=[maximum], orelse=[])
                    reward_guard = ast.If(test=copy.deepcopy(max_guard.test), body=[reward,
                        *ast.parse(f'{slot}[{cache_index}] = ({", ".join(outputs)},)').body], orelse=[])
                    body[index+3] = max_guard
                    body[index+6] = reward_guard
                    body[start:index+1] = load
                    changes.append(cache_index)
                    break
            return node
    Scalars().visit(consumer)
    assert len(changes) == 2, changes
    source = ast.unparse(ast.fix_missing_locations(tree))+'\n'
    compile(source, str(path), 'exec')
    path.write_text(source)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('bot', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    original = measurement.optimize_folder
    def compile_variant(bot, output, options):
        report = original(bot, output, options)
        if options.disabled == frozenset({'insertion-group-scalars', 'numeric-ordered-folds'}):
            transform(output)
            report['pass_counts']['experiment-group-scalars'] = 1
        return report
    measurement.optimize_folder = compile_variant
    report = measurement.compare(args.bot, args.output, target='draft_planner:DraftPlanner.build',
                                 maps=('collision',), repeats=1, output_prefix='SQUAD_LOOPS_DATA ',
                                 options=Options(disabled=frozenset({'insertion-group-scalars', 'numeric-ordered-folds'})))
    report['experimental_post_compile_transform'] = 'insertion-group invariant scalar reuse, research only'
    (args.output/'results.json').write_text(json.dumps(report, indent=2)+'\n')
    for row in report['comparisons']:
        print(row['map'], row['side'], row['reduction_percent'])


if __name__ == '__main__':
    main()
