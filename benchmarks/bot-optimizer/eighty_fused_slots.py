"""Research-only scalar replacement of fused private fixed-size cache slots."""

import argparse
import ast
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import tools.bot_optimizer.compare as measurement
from tools.bot_optimizer.records import used_names
from tools.bot_optimizer.model import Options


def transform(folder, resident_scalars=False):
    path = folder/'src/planner.py'
    tree = ast.parse(path.read_text())
    consumer, = [node for node in tree.body if isinstance(node, ast.FunctionDef)
                 and node.name.startswith('_bcopt_region_consumer_')]
    parents = {child: parent for parent in ast.walk(consumer) for child in ast.iter_child_nodes(parent)}
    taken, slots, assignments = used_names(tree), {}, {}
    for node in ast.walk(consumer):
        if (not isinstance(node, ast.Assign) or len(node.targets) != 1 or not isinstance(node.targets[0], ast.Name)
                or not node.targets[0].id.startswith(('_bcopt_edge_group', '_bcopt_compensated_slot', '_bcopt_group_scalar_slot'))
                or not isinstance(node.value, ast.BinOp) or not isinstance(node.value.op, ast.Mult)
                or not isinstance(node.value.left, ast.List) or len(node.value.left.elts) != 1
                or not isinstance(node.value.left.elts[0], ast.Constant) or node.value.left.elts[0].value is not None
                or not isinstance(node.value.right, ast.Constant) or type(node.value.right.value) is not int):
            continue
        size, name = node.value.right.value, node.targets[0].id
        assert 0 < size <= 16 and name not in slots
        for part, parent in parents.items():
            if not isinstance(part, ast.Name) or part.id != name or part is node.targets[0]:
                continue
            assert isinstance(parent, ast.Subscript) and parent.value is part
            assert isinstance(parent.slice, ast.Constant) and type(parent.slice.value) is int and 0 <= parent.slice.value < size
        names = [f'_bcopt_slot80_{len(slots)}_{index}' for index in range(size)]
        assert not set(names) & taken
        taken.update(names)
        slots[name] = names
        assignments[node] = names
    assert len(slots) == 3, slots
    class Scalarize(ast.NodeTransformer):
        def visit_Assign(self, node):
            if node in assignments:
                return ast.Assign(targets=[ast.Name(id=name, ctx=ast.Store()) for name in assignments[node]], value=ast.Constant(None))
            return self.generic_visit(node)
        def visit_Subscript(self, node):
            if isinstance(node.value, ast.Name) and node.value.id in slots:
                return ast.Name(id=slots[node.value.id][node.slice.value], ctx=node.ctx)
            return self.generic_visit(node)
    Scalarize().visit(consumer)
    if resident_scalars:
        # Cached invariant outputs already live in this fused frame. Reuse them
        # directly only if all their writes belong to cache-miss computations,
        # and the prepared/nonprepared version cannot change during the epoch.
        parents = {child: parent for parent in ast.walk(consumer) for child in ast.iter_child_nodes(parent)}
        reads = [node for node in ast.walk(consumer) if isinstance(node, ast.Assign)
                 and isinstance(node.targets[0], ast.Name) and node.targets[0].id.startswith('_bcopt_group_scalar_state')]
        assert len(reads) == 2
        flags = {node.targets[0].id for node in reads}
        conditions = [node for node in ast.walk(consumer) if isinstance(node, ast.If)
                      and isinstance(node.test, ast.Compare) and isinstance(node.test.left, ast.Name)
                      and node.test.left.id in flags and len(node.test.ops) == 1 and isinstance(node.test.ops[0], ast.Is)
                      and len(node.test.comparators) == 1 and isinstance(node.test.comparators[0], ast.Constant)
                      and node.test.comparators[0].value is None]
        unpackings = [node.orelse[0] for node in conditions if node.orelse]
        assert len(unpackings) == 2 and all(isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Tuple) for node in unpackings)
        outputs = {part.id for node in unpackings for part in node.targets[0].elts}
        allowed = {part for node in conditions for part in ast.walk(node) if isinstance(part, ast.Name) and isinstance(part.ctx, ast.Store)}
        assert all(node in allowed for node in ast.walk(consumer)
                   if isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del)) and node.id in outputs)
        versions = set()
        for node in reads:
            parent = parents[node]
            while parent is not consumer:
                if (isinstance(parent, ast.If) and isinstance(parent.test, ast.Name)
                        and parent.test.id.startswith('_bcopt_entry_prepared_ready')):
                    versions.add(parent)
                    break
                parent = parents[parent]
            else:
                raise AssertionError('missing immutable prepared-version dispatch')
        assert len(versions) == 1
        version, = versions
        writes = [node for node in ast.walk(consumer) if isinstance(node, ast.Name)
                  and isinstance(node.ctx, (ast.Store, ast.Del)) and node.id == version.test.id]
        assert len(writes) == 1 and parents[writes[0]] in consumer.body
        cache_names = {node.value.id for node in reads}
        publications = [node for node in ast.walk(consumer) if isinstance(node, ast.Assign)
                        and isinstance(node.targets[0], ast.Name) and node.targets[0].id in cache_names
                        and isinstance(node.value, ast.Tuple)]
        assert len(publications) == 2
        for node in publications:
            assert {part.id for part in node.value.elts} <= outputs
            node.value = ast.Constant(True)
        for node in conditions:
            if node.orelse:
                node.orelse = []
    source = ast.unparse(ast.fix_missing_locations(tree))+'\n'
    compile(source, str(path), 'exec')
    path.write_text(source)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('bot', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--resident-scalars', action='store_true')
    args = parser.parse_args()
    original = measurement.optimize_folder
    def compile_variant(bot, output, options):
        report = original(bot, output, options)
        if options.disabled == frozenset({'insertion-fused-cache-slots', 'insertion-resident-scalars'}):
            transform(output, resident_scalars=args.resident_scalars)
            report['pass_counts']['experiment-fused-slots'] = 1
        return report
    measurement.optimize_folder = compile_variant
    report = measurement.compare(args.bot, args.output, target='draft_planner:DraftPlanner.build',
                                 maps=('collision',), repeats=1, output_prefix='SQUAD_LOOPS_DATA ',
                                 options=Options(disabled=frozenset({'insertion-fused-cache-slots', 'insertion-resident-scalars'})))
    report['experimental_post_compile_transform'] = 'fused private fixed cache scalar replacement, research only'
    report['resident_scalars'] = args.resident_scalars
    (args.output/'results.json').write_text(json.dumps(report, indent=2)+'\n')
    for row in report['comparisons']:
        print(row['map'], row['side'], row['reduction_percent'])


if __name__ == '__main__':
    main()
