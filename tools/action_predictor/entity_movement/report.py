"""Additive saved-result summary; never fits, selects, or rewrites artifacts."""
import argparse
import json
from ..audit import immutable_json
from ..data import digest
from .protocol import ROOT, REPORT


def summarize(result):
    values = result['results']['validation']['all']
    overall, contexts = values['overall'], values['contexts']
    categories = {row['action']: row for row in overall['per_category']}
    return dict(complete=overall['strict_correct'], rows=overall['rows'],
        macro_f1=overall['macro_f1'], joint_nll=overall['joint_nll'],
        movement={key: dict(rows=contexts[key]['rows'], complete=contexts[key]['strict_correct'])
                  for key in ('move', 'continue', 'change', 'startup', 'blocked')},
        categories={key: dict(support=row['support'], complete=row['joint_correct'],
            conditional_accuracy=row['all_true_family_parameter_accuracy'], type_f1=row['type_F1'])
                    for key, row in categories.items()})


def contrast(new, old):
    def delta(key):
        return new['movement'][key]['complete'] - old['movement'][key]['complete']
    n = new['movement']['continue']['rows']
    guards = dict(joint_move_gain_at_least24=delta('move') >= 24,
        joint_change_gain_at_least12=delta('change') >= 12,
        lower_full_DEV_NLL=new['joint_nll'] < old['joint_nll'],
        continuation_loss_at_most_half_point=delta('continue') / n >= -.005 if n else None)
    targeting = {}
    for key in ('attack', 'cast_0', 'cast_1'):
        a = new['categories'][key]['conditional_accuracy']
        b = old['categories'][key]['conditional_accuracy']
        targeting[key] = dict(delta_percentage_points=100*(a-b) if a is not None and b is not None else None,
            passes_two_point_guard=(a-b >= -.02) if a is not None and b is not None else None)
    return dict(complete_gain=new['complete']-old['complete'],
        movement_gains={key: delta(key) for key in new['movement']},
        joint_nll_delta=new['joint_nll']-old['joint_nll'], macro_f1_delta=new['macro_f1']-old['macro_f1'],
        numerical_guards=guards, targeting_guards=targeting,
        remaining_gate='Inspect every original category and all stronger retained comparisons; these numerical guards alone do not certify the full gate, reliability, three-seed robustness or strategy.')


def run(arm):
    if arm not in ('E00', 'E01'): raise ValueError('Unknown arm')
    path = REPORT/f'{arm}.json'
    result = json.loads(path.read_text())
    # Check the result against every retained fit artifact before summarizing.
    for key, expected in result['bindings'].items():
        if digest(ROOT/key) != expected: raise RuntimeError('Changed result binding: '+key)
    summary = summarize(result)
    refs = {'H01': ROOT/'tools/action_predictor/experiments/v30/H01.json'}
    if arm == 'E01': refs['E00'] = REPORT/'E00.json'
    comparisons = {name: contrast(summary, summarize(json.loads(ref.read_text()))) for name, ref in refs.items()}
    immutable_json(REPORT/f'{arm}-summary.json', dict(arm=arm, result_sha256=digest(path),
        source_sha256=digest(__file__), selected_round=result['selected_round'],
        selected_updates=result['selected_updates'], completed_updates=result['completed_updates'],
        summary=summary, comparisons=comparisons,
        reference_hashes={name: digest(ref) for name, ref in refs.items()},
        stronger_comparisons='Full result JSON includes paired G00/L02/JP02 comparisons; E01 includes E00.',
        limits='Five repeatedly reused DEV groups, single seed, observed earlier actions; no autonomous strategy or untouched-test evidence.',
        new_fits=0, reserved_opened=0, promoted=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('arm', choices=['E00', 'E01'])
    run(parser.parse_args().arm)
