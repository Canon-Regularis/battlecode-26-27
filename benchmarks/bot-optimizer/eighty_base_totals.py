"""Research-only base-local integer reductions plus one inserted contribution.

Keep the existing multiset cache and its publication. On misses, guarded exact
integer fields and maxima can use base reductions computed lazily once. Invalid
indices retain the original reduction loop and error order. Floating arithmetic
and all public allocations remain unchanged.
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


def transform(folder, wait_term=False):
    path = folder/'src/planner.py'
    tree = ast.parse(path.read_text())
    consumer, = [n for n in tree.body if isinstance(n, ast.FunctionDef)
                 and n.name.startswith('_bcopt_region_consumer_')]
    assert not any(isinstance(n, ast.Name) and n.id.startswith('_bcopt_totals80') for n in ast.walk(tree))
    count = 0
    wait_count = 0
    for branch in list(ast.walk(consumer)):
        if (not isinstance(branch, ast.If) or not isinstance(branch.test, ast.Compare)
                or not isinstance(branch.test.left, ast.Name) or branch.test.left.id != '_bcopt_fused_size'
                or not isinstance(branch.test.ops[0], ast.Eq)):
            continue
        producer = branch.body[-1]
        assert isinstance(producer, ast.For) and producer.target.id == '_bcopt_fused_camp_index'
        if wait_term:
            class Reset(ast.NodeTransformer):
                def visit_Assign(self, node):
                    if (isinstance(node.value, ast.Constant) and node.value.value is None
                            and any(isinstance(t, ast.Name) and t.id == '_bcopt_cache_slot_3' for t in node.targets)):
                        return [node, *ast.parse('_bcopt_totals80_wait_term = None').body]
                    return node
            Reset().visit(producer)
        branch.body[-1:-1] = ast.parse('_bcopt_totals80_valid = None\n_bcopt_totals80_ready = False').body
        versions = [n for n in ast.walk(producer) if isinstance(n, ast.If)
                    and isinstance(n.test, ast.Name) and n.test.id == '_bcopt_entry_prepared_ready_0']
        for version in versions:
            prepared, = version.body
            loops = [n for n in ast.walk(prepared) if isinstance(n, ast.For)
                     and isinstance(n.target, ast.Name) and n.target.id == '_bcopt_entry_local_11'
                     and isinstance(n.iter, ast.Name) and n.iter.id == 'route']
            loop, = loops
            assert len(loop.body) == 6
            assert [ast.unparse(n) for n in loop.body[:4]] == [
                '_bcopt_entry_local_24 = _bcopt_entry_local_32[_bcopt_entry_local_11]',
                '_bcopt_entry_local_37 += _bcopt_entry_local_24[1]',
                '_bcopt_entry_local_38 += _bcopt_entry_local_24[2]',
                '_bcopt_entry_local_46 += _bcopt_entry_local_24[3]']
            replacement = ast.parse('''
if _bcopt_totals80_valid is None:
    _bcopt_totals80_n = _bcopt_region_builtins_1.len(_bcopt_entry_local_32)
    _bcopt_totals80_valid = _bcopt_region_builtins_1.len(_bcopt_entry_local_5) == _bcopt_totals80_n and all(-_bcopt_totals80_n <= _bcopt_totals80_i < _bcopt_totals80_n for _bcopt_totals80_i in _bcopt_fused_route)
if _bcopt_totals80_valid and -_bcopt_totals80_n <= _bcopt_fused_camp_index < _bcopt_totals80_n:
    if not _bcopt_totals80_ready:
        _bcopt_totals80_a = _bcopt_totals80_b = _bcopt_totals80_c = 0
        _bcopt_totals80_peak = None
        for _bcopt_totals80_i in _bcopt_fused_route:
            _bcopt_totals80_row = _bcopt_entry_local_32[_bcopt_totals80_i]
            _bcopt_totals80_a += _bcopt_totals80_row[1]
            _bcopt_totals80_b += _bcopt_totals80_row[2]
            _bcopt_totals80_c += _bcopt_totals80_row[3]
            _bcopt_totals80_value = _bcopt_entry_local_5[_bcopt_totals80_i]
            if _bcopt_totals80_peak is None or _bcopt_totals80_value > _bcopt_totals80_peak:
                _bcopt_totals80_peak = _bcopt_totals80_value
        _bcopt_totals80_ready = True
    _bcopt_totals80_row = _bcopt_entry_local_32[_bcopt_fused_camp_index]
    _bcopt_entry_local_37 = _bcopt_totals80_a + _bcopt_totals80_row[1]
    _bcopt_entry_local_38 = _bcopt_totals80_b + _bcopt_totals80_row[2]
    _bcopt_entry_local_46 = _bcopt_totals80_c + _bcopt_totals80_row[3]
    _bcopt_totals80_value = _bcopt_entry_local_5[_bcopt_fused_camp_index]
    _bcopt_entry_local_4 = _bcopt_totals80_value if _bcopt_totals80_value > _bcopt_totals80_peak else _bcopt_totals80_peak
    _bcopt_entry_local_11 = route[-1]
    _bcopt_entry_local_24 = _bcopt_entry_local_32[_bcopt_entry_local_11]
    _bcopt_entry_local_25 = _bcopt_entry_local_5[_bcopt_entry_local_11]
else:
    pass
''').body
            replacement[-1].orelse = [copy.deepcopy(loop)]
            class Replace(ast.NodeTransformer):
                def visit_For(self, node):
                    return replacement if node is loop else self.generic_visit(node)
            Replace().visit(prepared)
            if wait_term:
                term, = [n for n in ast.walk(prepared) if isinstance(n, ast.AugAssign)
                         and ast.unparse(n) == '_bcopt_entry_local_16 += (_bcopt_entry_local_49 + _bcopt_entry_local_42 - _bcopt_entry_local_29) * _bcopt_entry_local_12']
                alternate = ast.parse('''
if _bcopt_entry_local_42 is _bcopt_entry_local_29:
    if _bcopt_totals80_wait_term is None:
        _bcopt_totals80_wait_term = _bcopt_entry_local_49 * _bcopt_entry_local_12
    _bcopt_entry_local_16 += _bcopt_totals80_wait_term
else:
    pass
''').body[0]
                alternate.orelse = [copy.deepcopy(term)]
                class Wait(ast.NodeTransformer):
                    def visit_AugAssign(self, node):
                        return alternate if node is term else node
                Wait().visit(prepared)
                wait_count += 1
            count += 1
    assert count == 77, count
    assert not wait_term or wait_count == 77
    source = ast.unparse(ast.fix_missing_locations(tree))+'\n'
    compile(source, str(path), 'exec')
    path.write_text(source)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('bot', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--maps', default='collision')
    parser.add_argument('--wait-term', action='store_true')
    args = parser.parse_args()
    original = measurement.optimize_folder
    def compile_variant(bot, output, options):
        report = original(bot, output, options)
        if options.disabled == frozenset({'insertion-base-integer-totals', 'insertion-cancelled-products', 'losing-record-lookup-reuse', 'insertion-retained-integer-edges', 'numeric-dead-primitive-slots'}):
            transform(output, wait_term=args.wait_term)
            report['pass_counts']['experiment-base-integer-totals'] = 1
        return report
    measurement.optimize_folder = compile_variant
    report = measurement.compare(args.bot, args.output, target='draft_planner:DraftPlanner.build',
        maps=tuple(args.maps.split(',')), repeats=1, output_prefix='SQUAD_LOOPS_DATA ',
        options=Options(disabled=frozenset({'insertion-base-integer-totals', 'insertion-cancelled-products', 'losing-record-lookup-reuse', 'insertion-retained-integer-edges', 'numeric-dead-primitive-slots'})))
    report['experimental_post_compile_transform'] = 'base-local exact integer reductions, research only'
    report['wait_term'] = args.wait_term
    (args.output/'results.json').write_text(json.dumps(report, indent=2)+'\n')
    for row in report['comparisons']:
        print(row['map'], row['side'], row['reduction_percent'])


if __name__ == '__main__':
    main()
