"""Research-only scalar forwarding and lazy base-edge loads after position unrolling.

Every floating addition stays in order. Base-edge values are fetched lazily at
their first original use; subsequent uses read a base-local scalar. Original
fallbacks and public fresh tuples are retained. No dictionaries are omitted.
"""

import argparse
import ast
import copy
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import tools.bot_optimizer.compare as measurement
from tools.bot_optimizer import Options


def transform(folder, cache=False, prefix=False):
    path = folder/'src/planner.py'
    tree = ast.parse(path.read_text())
    consumer, = [n for n in tree.body if isinstance(n, ast.FunctionDef)
                 and n.name.startswith('_bcopt_region_consumer_')]
    assert not any(isinstance(n, ast.Name) and n.id.startswith('_bcopt_baseedge80') for n in ast.walk(tree))
    counts = {'positions': 0, 'forwarded': 0, 'cached_loads': 0, 'prefixes': 0}
    for branch in list(ast.walk(consumer)):
        if (not isinstance(branch, ast.If) or not isinstance(branch.test, ast.Compare)
                or not isinstance(branch.test.left, ast.Name) or branch.test.left.id != '_bcopt_fused_size'
                or not isinstance(branch.test.ops[0], ast.Eq)):
            continue
        width = branch.test.comparators[0].value
        unpack, producer = branch.body
        assert isinstance(unpack, ast.Assign) and isinstance(unpack.targets[0], ast.Tuple)
        base = [n.id for n in unpack.targets[0].elts]
        assert len(base) == width-1
        pairs = {(base[i+1], base[i]): f'_bcopt_baseedge80_{i}' for i in range(len(base)-1)}
        prefix_names = []
        wrappers = [n for n in ast.walk(producer) if isinstance(n, ast.For)
                    and isinstance(n.target, ast.Name) and n.target.id == '_bcopt_position_once']
        assert len(wrappers) == width
        for wrapper in wrappers:
            route = wrapper.body[0]
            assert isinstance(route, ast.Assign) and route.targets[0].id == 'route'
            assert isinstance(route.value, ast.Tuple) and len(route.value.elts) == width
            values = route.value.elts
            ready, = [n for n in ast.walk(wrapper) if isinstance(n, ast.If)
                      and isinstance(n.test, ast.Name) and n.test.id == '_bcopt_entry_prepared_ready_0']
            prepared, = ready.body
            assert isinstance(prepared, ast.Try)
            aliases = {f'_bcopt_ordered_item_{i}': value for i, value in enumerate(values)}
            class Forward(ast.NodeTransformer):
                def visit_Assign(self, node):
                    if (len(node.targets) == 1 and isinstance(node.targets[0], ast.Tuple)
                            and all(isinstance(n, ast.Name) and n.id in aliases for n in node.targets[0].elts)
                            and isinstance(node.value, ast.Name) and node.value.id == 'route'):
                        assert len(node.targets[0].elts) == width
                        return None
                    return self.generic_visit(node)

                def visit_Name(self, node):
                    if isinstance(node.ctx, ast.Load) and node.id in aliases:
                        counts['forwarded'] += 1
                        return copy.deepcopy(aliases[node.id])
                    return node

                def visit_Subscript(self, node):
                    self.generic_visit(node)
                    if isinstance(node.value, ast.Name) and node.value.id == 'route':
                        try:
                            index = ast.literal_eval(node.slice)
                        except (ValueError, TypeError):
                            return node
                        if type(index) is int and -width <= index < width:
                            counts['forwarded'] += 1
                            return copy.deepcopy(values[index])
                    return node

                def visit_AugAssign(self, node):
                    self.generic_visit(node)
                    value = node.value
                    if (cache and isinstance(node.op, ast.Add) and isinstance(value, ast.Subscript)
                            and isinstance(value.value, ast.Subscript)
                            and isinstance(value.value.value, ast.Name) and value.value.value.id == '_bcopt_entry_local_8'
                            and isinstance(value.slice, ast.Name) and isinstance(value.value.slice, ast.Name)):
                        pair = value.value.slice.id, value.slice.id
                        if pair in pairs:
                            name = pairs[pair]
                            guard = ast.parse(f'if {name} is None:\n    {name} = None').body[0]
                            guard.body[0].value = value
                            node.value = ast.Name(id=name, ctx=ast.Load())
                            counts['cached_loads'] += 1
                            return [guard, node]
                    return node
            Forward().visit(prepared)
            if prefix:
                position, = [i for i, value in enumerate(values) if value.id == '_bcopt_fused_camp_index']
                if 0 < position < width-1:
                    saved = f'_bcopt_baseedge80_prefix_{position}'
                    prefix_names.append(saved)
                    found = 0
                    for parent in ast.walk(prepared):
                        for _, body in ast.iter_fields(parent):
                            if not isinstance(body, list):
                                continue
                            starts = [i for i, n in enumerate(body) if isinstance(n, ast.Assign)
                                      and len(n.targets) == 1 and isinstance(n.targets[0], ast.Name)
                                      and n.targets[0].id == '_bcopt_entry_local_16'
                                      and isinstance(n.value, ast.Subscript)]
                            if not starts:
                                continue
                            start, = starts
                            end = start+1
                            while end < len(body):
                                n = body[end]
                                if (isinstance(n, ast.AugAssign) and isinstance(n.value, ast.Subscript)
                                        and isinstance(n.value.value, ast.Subscript)
                                        and isinstance(n.value.value.value, ast.Name)
                                        and n.value.value.value.id == '_bcopt_entry_local_8'
                                        and any(isinstance(x, ast.Name) and x.id == '_bcopt_fused_camp_index'
                                                for x in ast.walk(n.value))):
                                    break
                                end += 1
                            assert end < len(body) and end > start+1
                            block = body[start:end]
                            assert all(isinstance(n, (ast.Assign, ast.AugAssign, ast.If)) for n in block)
                            guard = ast.parse(f'if {saved} is None:\n    pass\nelse:\n    _bcopt_entry_local_16 = {saved}').body[0]
                            guard.body = [*block, *ast.parse(f'{saved} = _bcopt_entry_local_16').body]
                            body[start:end] = [guard]
                            found += 1
                    assert found == 1, found
                    counts['prefixes'] += 1
            counts['positions'] += 1
        initializers = [*(pairs.values() if cache else ()), *prefix_names]
        if initializers:
            branch.body[1:1] = ast.parse('\n'.join(f'{name} = None' for name in initializers)).body
    assert counts['positions'] == 77, counts
    assert counts['forwarded'] > 0 and (not cache or counts['cached_loads'] > 0), counts
    source = ast.unparse(ast.fix_missing_locations(tree))+'\n'
    compile(source, str(path), 'exec')
    path.write_text(source)
    return counts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('bot', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--cache', action='store_true')
    parser.add_argument('--prefix', action='store_true')
    parser.add_argument('--maps', default='collision')
    args = parser.parse_args()
    original = measurement.optimize_folder
    counts = {}
    def compile_variant(bot, output, options):
        report = original(bot, output, options)
        if options.disabled == frozenset({'insertion-base-edge-scalars', 'insertion-base-prefix-scalars'}):
            counts.update(transform(output, cache=args.cache, prefix=args.prefix))
            report['pass_counts']['experiment-base-edge-scalars'] = 1
        return report
    measurement.optimize_folder = compile_variant
    report = measurement.compare(args.bot, args.output, target='draft_planner:DraftPlanner.build',
        maps=tuple(args.maps.split(',')), repeats=1, output_prefix='SQUAD_LOOPS_DATA ',
        options=Options(disabled=frozenset({'insertion-base-edge-scalars', 'insertion-base-prefix-scalars'})))
    report['experimental_post_compile_transform'] = dict(base_edge_scalars=counts, cache=args.cache, prefix=args.prefix)
    (args.output/'results.json').write_text(json.dumps(report, indent=2)+'\n')
    for row in report['comparisons']:
        print(row['map'], row['side'], row['reduction_percent'])


if __name__ == '__main__':
    main()
