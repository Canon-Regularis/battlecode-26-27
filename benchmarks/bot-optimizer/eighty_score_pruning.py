"""Research-only elimination of total risk arithmetic for provably losing records.

Fresh result objects and all original field stores remain, preserving shared-key
history. Only a closed, unobserved losing result receives inert risk fields. The
guard requires prepared primitive tables, bounded positive denominators, valid
indices, nonnegative base score and a multiplier constrained to [0, 1].
"""

import argparse
import ast
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import tools.bot_optimizer.compare as measurement
from tools.bot_optimizer.records import used_names


def transform(folder, risk_bound=False, certified_domain=False):
    path = folder/'src/planner.py'
    tree = ast.parse(path.read_text())
    consumer, = [node for node in tree.body if isinstance(node, ast.FunctionDef)
                 and node.name.startswith('_bcopt_region_consumer_')]
    assert not any(name.startswith('_bcopt_prune80_') for name in used_names(tree))
    setup = ast.parse('''
import builtins as _bcopt_prune80_b
_bcopt_prune80_n = _bcopt_prune80_b.len(_bcopt_entry_local_34)
_bcopt_prune80_m = _bcopt_prune80_b.len(_bcopt_entry_local_30)
_bcopt_prune80_ready = (_bcopt_entry_prepared_ready_0 and _bcopt_entry_local_20 is not None
    and _bcopt_prune80_b.len(_bcopt_entry_local_20[1]) >= _bcopt_prune80_m
    and _bcopt_prune80_b.len(_bcopt_entry_local_9) >= _bcopt_prune80_n
    and _bcopt_prune80_b.len(_bcopt_entry_local_6) >= _bcopt_prune80_n
    and _bcopt_prune80_b.len(_bcopt_entry_local_7) >= _bcopt_prune80_n
    and _bcopt_prune80_b.len(_bcopt_entry_local_8) >= _bcopt_prune80_n
    and _bcopt_prune80_b.all(_bcopt_prune80_b.len(row) >= _bcopt_prune80_m for row in _bcopt_entry_local_6)
    and _bcopt_prune80_b.all(_bcopt_prune80_b.len(row) >= _bcopt_prune80_m for row in _bcopt_entry_local_7)
    and _bcopt_prune80_b.all(_bcopt_prune80_b.len(row) >= _bcopt_prune80_n for row in _bcopt_entry_local_8))
''').body
    outer = next(i for i, node in enumerate(consumer.body) if isinstance(node, ast.For))
    consumer.body[outer:outer] = setup
    version, = [node for node in ast.walk(consumer) if isinstance(node, ast.If)
                and isinstance(node.test, ast.Name) and node.test.id == '_bcopt_entry_prepared_ready_0']
    branches = [node for statement in version.body for node in ast.walk(statement) if isinstance(node, ast.If)
                and isinstance(node.test, ast.Compare) and isinstance(node.test.left, ast.Subscript)
                and isinstance(node.test.left.value, ast.Name) and node.test.left.value.id == '_bcopt_region_data_0'
                and isinstance(node.test.left.slice, ast.Constant) and node.test.left.slice.value == 5]
    risk, = branches
    parent = next(node for node in ast.walk(consumer) if isinstance(node, ast.If) and risk in node.orelse)
    body = parent.orelse
    index = body.index(risk)
    before = ast.parse('''
_bcopt_prune80_losing = False
if (_bcopt_prune80_ready and _bcopt_algebra_fast and 0 < _bcopt_entry_local_42 <= 9007199254740992
        and -9007199254740992 <= _bcopt_entry_local_49 + _bcopt_entry_local_42 - _bcopt_entry_local_29 <= 9007199254740992
        and 0.0 <= _bcopt_entry_local_33[5] <= 1.0 and _bcopt_entry_local_31 >= 0.0):
    _bcopt_prune80_previous = candidates_by_altar[altar_index].get(_bcopt_insertion_key_set)
    _bcopt_prune80_losing = (_bcopt_prune80_previous is not None
        and _bcopt_entry_local_31 <= _bcopt_prune80_previous.evaluation.score)
''').body
    risk.test = ast.BoolOp(op=ast.And(), values=[ast.UnaryOp(op=ast.Not(), operand=ast.Name(id='_bcopt_prune80_losing', ctx=ast.Load())), risk.test])
    body[index:index] = before
    if risk_bound:
        # Positive weighted-average inputs admit an absolute forward-error
        # margin far larger than the <=16-term binary64 accumulation error.
        # The bound is research-only pending a generic conservation proof.
        extra = ast.parse('''
_bcopt_prune80_bound_ready = (_bcopt_prune80_ready
    and _bcopt_prune80_b.all(row[3] >= 0 for row in _bcopt_entry_local_32)
    and _bcopt_prune80_b.all(0.0 <= value <= 1.0 for value in _bcopt_entry_local_20[0])
    and _bcopt_prune80_b.all(0.0 <= value <= 1.0 for value in _bcopt_entry_local_20[1]))
''').body
        outer = next(i for i, node in enumerate(consumer.body) if isinstance(node, ast.For))
        consumer.body[outer:outer] = extra
        producer, = [node for node in ast.walk(consumer) if isinstance(node, ast.For)
                     and isinstance(node.target, ast.Name) and node.target.id == '_bcopt_fused_camp_index']
        producer.body.insert(0, ast.parse('_bcopt_prune80_upper = None').body[0])
        check = before[1]
        compare = check.body[-1]
        assert isinstance(compare, ast.Assign) and isinstance(compare.value, ast.BoolOp)
        check.body[-1:-1] = ast.parse('''
_bcopt_prune80_bound = _bcopt_entry_local_31
if (_bcopt_prune80_bound_ready and _bcopt_fused_size <= 16
        and _bcopt_entry_local_49 >= 0 and _bcopt_entry_local_46 >= 0):
    if _bcopt_prune80_upper is None:
        _bcopt_prune80_minimum = _bcopt_prune80_b.min(_bcopt_entry_local_20[0][item] for item in route)
        _bcopt_prune80_minimum = _bcopt_prune80_b.min(_bcopt_prune80_minimum, _bcopt_entry_local_20[1][altar_index])
        _bcopt_prune80_lower = _bcopt_prune80_b.max(0.0, _bcopt_prune80_minimum - 2.0**-40)
        _bcopt_prune80_upper = _bcopt_prune80_b.min(1.0, 1.0 - (1.0 - _bcopt_entry_local_33[5]) * _bcopt_prune80_lower + 2.0**-40)
    _bcopt_prune80_bound = _bcopt_entry_local_31 * _bcopt_prune80_upper
''').body
        compare.value.values[-1].left = ast.Name(id='_bcopt_prune80_bound', ctx=ast.Load())
        score, = [node for node in body if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name)
                  and node.targets[0].id == '_bcopt_entry_local_28']
        # A losing record must still lose the original downstream comparison.
        # The tighter bound can be below the previous score while base_score is
        # above it; using base_score as its inert field would promote a loser.
        score.value = ast.IfExp(test=ast.Name(id='_bcopt_prune80_losing', ctx=ast.Load()),
                               body=ast.Name(id='_bcopt_prune80_bound', ctx=ast.Load()), orelse=score.value)
        if certified_domain:
            extra = ast.parse('''
_bcopt_prune80_domain = (_bcopt_prune80_bound_ready
    and 0.0 <= _bcopt_entry_local_33[3] <= 1000000.0
    and 0.0 <= _bcopt_entry_local_33[4] <= 1000000.0
    and 0.0 <= _bcopt_entry_local_33[5] <= 1.0
    and _bcopt_prune80_b.all(0 <= row[1] <= 1099511627776 and 0 <= row[2] <= 1099511627776
        and 0 <= row[3] <= 1099511627776 and 1 <= row[4] <= 1099511627776 for row in _bcopt_entry_local_32)
    and _bcopt_prune80_b.all(0 <= value <= 1099511627776 for value in _bcopt_entry_local_47)
    and _bcopt_prune80_b.all(row and _bcopt_prune80_b.min(row) >= 0 and _bcopt_prune80_b.max(row) <= 1099511627776 for row in _bcopt_entry_local_34)
    and _bcopt_prune80_b.all(row and _bcopt_prune80_b.min(row) >= 0 and _bcopt_prune80_b.max(row) <= 1099511627776 for row in _bcopt_entry_local_30))
''').body
            outer = next(i for i, node in enumerate(consumer.body) if isinstance(node, ast.For))
            consumer.body[outer:outer] = extra
            check.test = ast.parse('_bcopt_prune80_domain and _bcopt_algebra_fast and _bcopt_fused_size <= 16', mode='eval').body
            bounds, = [node for node in check.body if isinstance(node, ast.If)]
            offset = check.body.index(bounds)
            check.body[offset:offset+1] = bounds.body
    source = ast.unparse(ast.fix_missing_locations(tree))+'\n'
    compile(source, str(path), 'exec')
    path.write_text(source)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('bot', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--risk-bound', action='store_true')
    parser.add_argument('--certified-domain', action='store_true')
    args = parser.parse_args()
    assert not args.certified_domain or args.risk_bound
    original = measurement.optimize_folder
    def compile_variant(bot, output, options):
        report = original(bot, output, options)
        if not options.disabled:
            transform(output, risk_bound=args.risk_bound, certified_domain=args.certified_domain)
            report['pass_counts']['experiment-score-pruning'] = 1
        return report
    measurement.optimize_folder = compile_variant
    report = measurement.compare(args.bot, args.output, target='draft_planner:DraftPlanner.build',
                                 maps=('collision',), repeats=1, output_prefix='SQUAD_LOOPS_DATA ')
    report['experimental_post_compile_transform'] = 'bounded losing-record risk arithmetic elimination, research only'
    report['risk_bound'] = args.risk_bound
    report['certified_domain'] = args.certified_domain
    (args.output/'results.json').write_text(json.dumps(report, indent=2)+'\n')
    for row in report['comparisons']:
        print(row['map'], row['side'], row['reduction_percent'])


if __name__ == '__main__':
    main()
