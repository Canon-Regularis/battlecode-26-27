"""Research-only direct reduction-cache slot shared by insertion positions."""

import argparse
import ast
import copy
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tools.bot_optimizer.records import used_names
import tools.bot_optimizer.compare as measurement


def transform(folder):
    path = folder/'src/planner.py'
    tree = ast.parse(path.read_text())
    producer, = [node for node in tree.body if isinstance(node, ast.FunctionDef)
                 and node.name.startswith('_bcopt_insertion_key_producer')]
    consumer, = [node for node in tree.body if isinstance(node, ast.FunctionDef)
                 and node.name.startswith('_bcopt_region_consumer_')]
    slot = '_bcopt_group80_reduction'
    assert slot not in used_names(tree)
    outer, = [node for node in ast.walk(producer) if isinstance(node, ast.For)
              and isinstance(node.target, ast.Name) and node.target.id == 'camp_index']
    outer.body.insert(0, ast.parse(f'{slot} = [None]').body[0])
    for node in ast.walk(producer):
        if isinstance(node, ast.Yield):
            node.value.elts.append(ast.Name(id=slot, ctx=ast.Load()))
    route_loop, = [node for node in ast.walk(consumer) if isinstance(node, ast.For)
                   and isinstance(node.target, ast.Tuple) and node.target.elts[0].id == 'route']
    key = route_loop.target.elts[1].id
    route_loop.target.elts.append(ast.Name(id=slot, ctx=ast.Store()))
    changes = []
    class Cache(ast.NodeTransformer):
        def generic_visit(self, node):
            node = super().generic_visit(node)
            for field, body in ast.iter_fields(node):
                if not isinstance(body, list) or not body or not isinstance(body[0], ast.stmt):
                    continue
                for index in range(len(body)-1):
                    assignment, branch = body[index:index+2]
                    if (not isinstance(assignment, ast.Assign) or not isinstance(assignment.value, ast.Call)
                            or not isinstance(assignment.value.func, ast.Attribute) or assignment.value.func.attr != 'get'
                            or len(assignment.value.args) != 2 or not isinstance(branch, ast.If)):
                        continue
                    call = assignment.value
                    assert isinstance(call.args[0], ast.Name)  # The memo key is copied from the yielded invariant.
                    binding = next((part for part in body[:index] if isinstance(part, ast.Assign)
                                    and isinstance(part.targets[0], ast.Name) and part.targets[0].id == call.args[0].id), None)
                    if binding is None or not isinstance(binding.value, ast.Name) or binding.value.id != key:
                        continue
                    values = assignment.targets[0].id
                    assert isinstance(branch.test, ast.Compare) and branch.test.left.id == values
                    save, = [part for part in ast.walk(branch) if isinstance(part, ast.Assign)
                             and isinstance(part.targets[0], ast.Subscript) and isinstance(part.value, ast.Tuple)]
                    branch.body.append(ast.Assign(targets=[ast.Subscript(value=ast.Name(id=slot, ctx=ast.Load()),
                        slice=ast.Constant(0), ctx=ast.Store())], value=copy.deepcopy(save.value)))
                    prefix = ast.parse(f'{values} = {slot}[0]\nif {values} is None:\n    pass').body
                    prefix[1].body = [assignment, *ast.parse(f'{slot}[0] = {values}').body]
                    body[index:index+1] = prefix
                    changes.append(assignment.lineno)
                    break
            return node
    Cache().visit(consumer)
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
        if not options.disabled:
            transform(output)
            report['pass_counts']['experiment-group-cache'] = 1
        return report
    measurement.optimize_folder = compile_variant
    report = measurement.compare(args.bot, args.output, target='draft_planner:DraftPlanner.build',
                                 maps=('collision',), repeats=1, output_prefix='SQUAD_LOOPS_DATA ')
    report['experimental_post_compile_transform'] = 'direct insertion-group reduction slot, not production integrated'
    (args.output/'results.json').write_text(json.dumps(report, indent=2)+'\n')
    for row in report['comparisons']:
        print(row['map'], row['side'], row['reduction_percent'])


if __name__ == '__main__':
    main()
