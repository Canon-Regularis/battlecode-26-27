"""AB01 review corrections using preserved predictions only; no optimization."""
import json
import numpy as np
from ..audit import immutable_json
from ..data import digest
from ..policy_action_readout.protocol import ROOT, OUT, LOCAL
from ..movement_experts.evaluate import summary


def run():
    completion = json.loads((OUT/'AB01-completion.json').read_text())
    path = LOCAL/'runs/AB01/train-predictions.npz'
    if digest(path) != completion['bindings'][str(path.relative_to(ROOT))]:
        raise RuntimeError('Reviewed predictions changed')
    with np.load(path) as z: p = {k: z[k] for k in z.files}
    path_raw = ROOT/'.cambc/action-predictor/v5/combined-train.npz'
    if digest(path_raw) != '39386010575ad30add064fdae750680f34cfcc732c4fd00fb657875ff4c61ffb':
        raise RuntimeError('Original TRAIN changed')
    with np.load(path_raw) as z: raw = {k: z[k] for k in ('y', 'py', 'priority', 'group')}
    natural_path = ROOT/'.cambc/action-predictor/v9/frequency/natural-mask.npy'
    if digest(natural_path) != '09217d8fc3d5673d980c8b8a4434861aa26dddb37e506bbfa22cbaafc0e525bd':
        raise RuntimeError('Natural membership changed')
    mask = ~np.load(natural_path)
    result = summary(dict(raw=raw), p, mask)
    for code, row in enumerate(result['per_category']):
        m = mask & (raw['y'] == code)
        row['observed_joint_NLL'] = float(p['nll'][m].mean()) if m.any() else None
    immutable_json(OUT/'AB01-closure-correction.json', dict(
        correction='Both AB00 and AB01 are completed. The matched comparison demonstrated no improvement; stale control-alone/next-arm wording in frozen reports is superseded by this addendum. Movement/hierarchy is now the main direction; no further priority-only fits.',
        augmented_only_TRAIN=result,
        interpretation='Different natural/augmentation action/context composition is not a generalization gap. Every augmented row was already included in the original all-TRAIN denominator.',
        reproduction='python -m tools.action_predictor.action_readout_analysis.closure',
        bindings={str(v.relative_to(ROOT)): digest(v) for v in (path, path_raw, natural_path,
            OUT/'AB01-completion.json', OUT/'AB01-review.json', OUT/'AB01-review-delegation.json',
            ROOT/'tools/action_predictor/action_readout_analysis/closure.py')}, new_fits=0, reserved_opened=0))


if __name__ == '__main__': run()
