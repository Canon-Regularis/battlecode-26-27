"""Saved-output PC01 population contrast; fixed final checkpoints only."""
import json
from pathlib import Path

import numpy as np

from ..audit import immutable_json
from ..data import digest
from ..priority_capacity.data import load as control_data
from .experiment import ROOT, LOCAL, OUT


def run():
    current_path = OUT / 'PC01.json'
    current = json.loads(current_path.read_text())
    old_path = ROOT / 'tools/action_predictor/experiments/v19/PC00.json'
    old = json.loads(old_path.read_text())
    controls = control_data()
    with np.load(LOCAL / 'PC01-cohort.npz') as z:
        controls['broad_fit'] = {key:z[key] for key in z.files}
    controls['original_fit'] = controls.pop('fit')
    bindings = {str(current_path.relative_to(ROOT)):digest(current_path),
                str(old_path.relative_to(ROOT)):digest(old_path),
                str(Path(__file__).relative_to(ROOT)):digest(Path(__file__))}
    result = {}
    for name, data in controls.items():
        target = np.asarray(data['target'])
        group = np.asarray(data['group'])
        paths = dict(initial=LOCAL/f'runs/PC01/{name}-step-0000-predictions.npz',
                     broad_final=LOCAL/f'runs/PC01/{name}-step-2000-predictions.npz')
        if name != 'broad_fit':
            previous = 'fit' if name == 'original_fit' else name
            paths['small_final'] = ROOT/f'.cambc/action-predictor/v19/runs/PC00/{previous}-step-2000-predictions.npz'
        archives = {}
        for label, path in paths.items():
            expected = (old if label == 'small_final' else current)['bindings'][str(path.relative_to(ROOT))]
            assert digest(path) == expected, path
            bindings[str(path.relative_to(ROOT))] = expected
            with np.load(path) as z:
                archives[label] = {key:z[key] for key in z.files}
        groups = np.unique(group)
        support = np.array([(group == g).sum() for g in groups])
        rng = np.random.default_rng(20261106)
        draws = np.stack([np.bincount(rng.integers(len(groups), size=len(groups)),
                                    minlength=len(groups)) for _ in range(2000)])
        denominator = draws @ support
        result[name] = dict(rows=len(target), groups=len(groups), comparisons={})
        after = archives['broad_final']
        for reference in ('initial', 'small_final'):
            if reference not in archives:
                continue
            before = archives[reference]
            correct_before = before['integer'] == target
            correct_after = after['integer'] == target
            delta = correct_after.astype(int) - correct_before
            loss = after['nll'] - before['nll']
            gains = np.array([delta[group == g].sum() for g in groups])
            losses = np.array([loss[group == g].sum() for g in groups])
            result[name]['comparisons'][reference] = dict(
                rescues=int((~correct_before & correct_after).sum()),
                regressions=int((correct_before & ~correct_after).sum()),
                net=int(delta.sum()), mean_NLL_difference=float(loss.mean()),
                rows_with_NLL_increase=int((loss > 0).sum()),
                paired_whole_group_accuracy_interval=np.quantile(draws @ gains / denominator, [.025,.975]).tolist(),
                paired_whole_group_NLL_interval=np.quantile(draws @ losses / denominator, [.025,.975]).tolist(),
                group_net_commands=dict(zip(map(str,groups),map(int,gains))))
    immutable_json(OUT / 'PC01-analysis.json', dict(cohorts=result, bindings=bindings,
        uncertainty='2000paired whole-group resamples seed20261106. Controls pre-exposed to encoder/warm head; '
                    'not untouched generalization. Broad/original fit in-sample. Small cohorts and '
                    'selection/exposure limitations remain.',
        units=dict(accuracy='Accuracy fraction difference', NLL='Mean integer NLL difference in nats'),
        fixed_final_step=2000, new_fits=0, reserved_opened=0))
    print(json.dumps({name:r['comparisons'] for name,r in result.items()}, indent=2))


if __name__ == '__main__':
    run()
