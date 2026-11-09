"""Corrected paired readout report, allocation checks and immutable inventory."""
import json
from pathlib import Path
import subprocess
from .protocol import ROOT, LOCAL, OUT
from ..audit import immutable_json
from ..data import digest


def run():
    info = json.loads((OUT / 'U01.json').read_text())
    evaluation = json.loads((OUT / 'U01-evaluation-v2.json').read_text())
    control = json.loads((OUT / 'U00-evaluation-v2.json').read_text())
    diagnosis = json.loads((OUT / 'U01-diagnosis-v2.json').read_text())
    a, b = [v['results']['validation']['all'] for v in (control, evaluation)]
    ac, bc = [{row['action']: row for row in v['per_category']} for v in (a, b)]
    am, bm = [v['movement_contexts'] for v in (a, b)]
    change_gain = bm['change']['conditional_correct'] / bm['change']['rows'] - am['change']['conditional_correct'] / am['change']['rows']
    continuation_gain = bm['continue']['conditional_correct'] / bm['continue']['rows'] - am['continue']['conditional_correct'] / am['continue']['rows']
    targeting = {key: bc[key]['all_true_family_parameter_accuracy'] - ac[key]['all_true_family_parameter_accuracy']
                 for key in ('attack', 'cast_0', 'cast_1')}
    checks = dict(command_NLL_lower=b['joint_nll'] < a['joint_nll'],
        change_conditional_NLL_lower=bm['change']['conditional_nll'] < am['change']['conditional_nll'],
        change_conditional_gain_at_least_01=change_gain >= .01,
        change_joint_not_lower=bm['change']['joint_correct'] >= am['change']['joint_correct'],
        continuation_conditional_drop_within_005=continuation_gain >= -.005,
        overall_strict_not_lower=b['strict_correct'] >= a['strict_correct'],
        attack_cast_conditional_drop_within_02=all(value >= -.02 for value in targeting.values()))
    allocation = dict(checks=checks, passes_all=all(checks.values()),
        change_conditional_accuracy_difference=change_gain,
        continuation_conditional_accuracy_difference=continuation_gain,
        targeting_differences=targeting,
        meaning='Original pre-fit exploratory allocation criterion versus matched U00 only. '
                'Not original success, promotion, robustness or strategic-intent certification.')
    immutable_json(OUT / 'U01-allocation.json', allocation)
    pair = evaluation['comparisons']['U00']['categories']['overall']
    lines = ['# U01: dynamic versus mean geometry with a common frozen upstream', '',
        'Both fits train identical copies of the existing execution readout. The L02 forecaster, '
        'representations, priors and baseline causal filtering are shared and frozen. Only the '
        'named projection geometry varies: dynamic causal predictions versus TRAIN means. This '
        'tests incremental geometry under fixed upstream state, not a fully retrained persistent policy.', '',
        '| Original DEV measure | U00 mean | U01 dynamic |', '| --- | ---: | ---: |']
    for label, key, fmt in [('Complete commands /14,439', 'strict_correct', 'd'),
                            ('Exact joint accuracy', 'joint_accuracy', '.6f'),
                            ('Action macro F1', 'macro_f1', '.6f'), ('Observed joint NLL', 'joint_nll', '.6f')]:
        lines.append(f'| {label} | {a[key]:{fmt}} | {b[key]:{fmt}} |')
    lines += ['', f"U01 rescues{pair['rescues']} and regresses{pair['regressions']} commands against U00.", '',
              '| Movement context | Conditional U00 / U01 | Joint U00 / U01 | Support |',
              '| --- | ---: | ---: | ---: |']
    for key in ('move', 'blocked', 'continue', 'change', 'startup'):
        lines.append(f"| {key} | {am[key]['conditional_correct']} / {bm[key]['conditional_correct']} | "
                     f"{am[key]['joint_correct']} / {bm[key]['joint_correct']} | {bm[key]['rows']} |")
    lines += ['', '| Category | Joint U00 / U01 | Conditional parameter U00 / U01 | U01 type TP / FP |',
              '| --- | ---: | ---: | ---: |']
    for name, row in bc.items():
        old = ac[name]
        values = [r['all_true_family_parameter_accuracy'] for r in (old, row)]
        text = ' / '.join(f'{value:.4f}' if value is not None else 'N/A' for value in values)
        lines.append(f"| {name} | {old['joint_correct']} / {row['joint_correct']} of{row['support']} | "
                     f"{text} | {row['type_TP']} / {row['type_FP']} |")
    lines += ['', 'Conditional coordinates/ranks/parameter losses supply the recorded family after '
        'forecasting only for diagnosis. Complete commands use predicted families and the original '
        'probability-consistent joint decoder. B00 comparisons reconstruct archived family_commands; '
        'chosen-command coordinates are not misrepresented as true-family diagnostics.', '',
        f"Exploratory allocation checks: `{checks}`; all pass: `{allocation['passes_all']}`. "
        'These gates were frozen before fitting and do not replace any original success target.', '',
        'TRAIN and natural-membership fitting, DEV direction conditional NLL/ranks/probabilities, '
        'paired targeting/category losses and initial-readout comparisons are in the versioned '
        'evaluation/diagnosis. Natural membership retains the common augmented filtering cadence; '
        'TRAIN remains in-sample. No isolated group-shift or observation-sufficiency inference.', '',
        'Paired intervals use2,000 whole-group draws, seed20261106. Accuracy differences are '
        'fractions, macro-F1 differences are score units, NLL differences are nats per decision. '
        'Five repeatedly reused DEV groups and selected checkpoints are not untouched or '
        'selection-adjusted evidence. One seed does not establish robustness.', '',
        f"Selected round{info['selected_round']} of{len(info['trace'])}, updates "
        f"{info['selected_updates']} selected /{info['completed_updates']} completed. "
        'Original .0001 NLL improvement/patience6/max35 rule retained. Initialization, RNG/order, '
        'upstream and frozen-tensor contracts are in U01-pair-contract.json. No epoch0 replacement.', '',
        'The supplemental fixed-weight mean-geometry sensitivity was registered during fitting '
        'after early NLLs, before selected-checkpoint analysis; it is not claimed as a before-fit '
        'preregistration. It changes no trained checkpoint or primary prediction and removes only '
        'the named projection variability, retaining other geometry/goal pathways.', '',
        'No promotion, repeated seeds or Fish-intent claim. Original90%-per-supported-category, '
        'macro.65, movement.6520745131244708, likelihood, targeting and three-seed goals remain '
        'binding. Fixed P05 modes and missing shop arguments remain hard configuration limits. '
        'All43DEV shops are unassessed strict failures; purchase likelihood is absent. Sparse '
        'altar/teleport/submit, entity identity, full legality/calibration remain uncertified. '
        'Successful-move mask rejection is separate from blocked-attempt outcome diagnostics.', '',
        'Model research only; both75-game reservations sealed. No matches, downloads, bot/runtime '
        'work or deployment. PR11DRAFT/open/unmerged/no-auto-merge/queue. Fresh Solxhigh review '
        'follows; continuing research is not stopped by completion of this comparison.', '']
    report = OUT / 'U01-REPORT-v2.md'
    assert not report.exists()
    report.write_text('\n'.join(lines))
    protocol = json.loads((OUT / 'protocol.json').read_text())
    for name, expected in protocol['sources'].items():
        assert digest(Path(__file__).parent / name) == expected
    files = list((LOCAL / 'runs/U01').glob('*')) + list(Path(__file__).parent.glob('*.py'))
    files += [p for p in OUT.glob('U01*') if p.name != 'U01-completion-v2.json']
    files += [OUT / name for name in ('protocol.json', 'upstream-ready.json', 'preflight-v2.json',
        'interface-recovery-plan.json', 'U00-evaluation-v2.json', 'U00-diagnosis-v2.json',
        'U00-review.json', 'U00-review-response.json', 'U00-review-followup.json', 'U00-fresh-evaluator-parity.json')]
    for split in ('train', 'validation'):
        files += list((LOCAL / f'upstream/{split}').glob('*.npy'))
    files += list((LOCAL / 'sensitivity/U01-geometry-mean').glob('*.npz'))
    files += [ROOT / name for name in evaluation['bindings']]
    files += [ROOT / name for name in diagnosis['bindings']]
    files += [ROOT / name for name in protocol['bindings']]
    for name in ('U00', 'U01'):
        files += list((LOCAL / f'initial-v2/{name}').glob('*.npz'))
    immutable_json(OUT / 'U01-completion-v2.json', dict(fit_source_commit=info['source_commit'],
        inventory_commit=subprocess.run(['git', 'rev-parse', 'HEAD'], capture_output=True, text=True, check=True).stdout.strip(),
        selected_round=info['selected_round'], selected_updates=info['selected_updates'],
        completed_updates=info['completed_updates'],
        bindings={str(p.relative_to(ROOT)): digest(p) for p in sorted(set(files))},
        commands=['.venv-action-predictor/Scripts/python.exe -m tools.action_predictor.goal_readout.' + value
                  for value in ('fit_interface U01', 'evaluate_fresh U01', 'diagnose U01',
                                'sensitivity --freeze', 'sensitivity', 'pair_contract', 'finalize')],
        shared_prerequisites=['protocol', 'cache', 'interface_protocol', 'preflight_v2'],
        sensitivity_registration='Supplemental during-fit registration, not original pre-fit protocol.',
        new_fits=0, reserved_opened=0, promoted=False, three_seed_confirmed=False))


if __name__ == '__main__':
    run()
