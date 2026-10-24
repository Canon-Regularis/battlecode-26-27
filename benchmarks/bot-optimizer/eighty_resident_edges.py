"""Research-only retention of rolling edge lists in the fused consumer frame."""

import argparse
import ast
import copy
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import tools.bot_optimizer.compare as measurement
from tools.bot_optimizer.model import Options


def transform(folder):
    path = folder/'src/planner.py'
    tree = ast.parse(path.read_text())
    consumer, = [node for node in tree.body if isinstance(node, ast.FunctionDef)
                 and node.name.startswith('_bcopt_region_consumer_')]
    parents = {child: parent for parent in ast.walk(consumer) for child in ast.iter_child_nodes(parent)}
    changes, regions, lists = [], [], set()
    for node in ast.walk(consumer):
        if (not isinstance(node, ast.If) or not isinstance(node.test, ast.BoolOp)
                or len(node.test.values) != 2 or not isinstance(node.test.values[0], ast.Compare)
                or not isinstance(node.test.values[0].left, ast.Name)
                or not node.test.values[0].left.id.startswith('_bcopt_edge_state')):
            continue
        state = node.test.values[0].left.id
        publication = node.body[-1]
        assert isinstance(publication, ast.Assign) and isinstance(publication.targets[0], ast.Name)
        assert isinstance(publication.value, ast.List) and len(publication.value.elts) == 2
        position, edges = publication.value.elts
        assert isinstance(position, ast.Name) and isinstance(edges, ast.Name)
        cache = publication.targets[0].id
        restore = node.orelse[0]
        assert isinstance(restore, ast.Assign) and restore.targets[0].id == edges.id
        assert isinstance(restore.value, ast.Subscript) and restore.value.value.id == state and restore.value.slice.value == 1
        last = node.orelse[-1]
        assert isinstance(last, ast.Assign) and isinstance(last.targets[0], ast.Subscript)
        assert last.targets[0].value.id == state and last.targets[0].slice.value == 0
        parent = parents[node]
        while parent is not consumer:
            if (isinstance(parent, ast.If) and isinstance(parent.test, ast.Name)
                    and parent.test.id.startswith('_bcopt_entry_prepared_ready')):
                regions.append(parent)
                break
            parent = parents[parent]
        else:
            raise AssertionError('missing invariant prepared selector')
        writes = [part for part in ast.walk(consumer) if isinstance(part, ast.Name)
                  and isinstance(part.ctx, (ast.Store, ast.Del)) and part.id == parent.test.id]
        assert len(writes) == 1 and parents[writes[0]] in consumer.body
        lists.add(edges.id)
        changes.append((node, publication, restore, last, state, cache, position))
    assert len(changes) == 2 and len(set(regions)) == 1
    allowed = {part for node, *_ in changes for part in ast.walk(node)}
    assert all(part in allowed for part in ast.walk(consumer) if isinstance(part, ast.Name)
               and isinstance(part.ctx, (ast.Store, ast.Del)) and part.id in lists)
    for node, publication, restore, last, state, cache, position in changes:
        publication.value = copy.deepcopy(position)
        node.orelse.remove(restore)
        last.targets = [ast.Name(id=cache, ctx=ast.Store())]
        class Position(ast.NodeTransformer):
            def visit_Subscript(self, part):
                if isinstance(part.value, ast.Name) and part.value.id == state:
                    assert isinstance(part.slice, ast.Constant) and part.slice.value == 0
                    return ast.Name(id=state, ctx=ast.Load())
                return self.generic_visit(part)
        Position().visit(node)
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
        if options.disabled == frozenset({'insertion-resident-edges'}):
            transform(output)
            report['pass_counts']['experiment-resident-edges'] = 1
        return report
    measurement.optimize_folder = compile_variant
    report = measurement.compare(args.bot, args.output, target='draft_planner:DraftPlanner.build',
                                 maps=('collision',), repeats=1, output_prefix='SQUAD_LOOPS_DATA ',
                                 options=Options(disabled=frozenset({'insertion-resident-edges'})))
    report['experimental_post_compile_transform'] = 'resident private rolling edge lists, research only'
    (args.output/'results.json').write_text(json.dumps(report, indent=2)+'\n')
    for row in report['comparisons']:
        print(row['map'], row['side'], row['reduction_percent'])


if __name__ == '__main__':
    main()
