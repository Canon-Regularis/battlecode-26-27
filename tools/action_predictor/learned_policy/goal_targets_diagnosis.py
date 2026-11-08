"""Reproduce target support/displacement receipt; no optimizer or predictions."""
import numpy as np
from .sequence_data import BASE, WORK, REPORT
from ..audit import immutable_json
from ..data import digest


def run():
    out = {}
    for split in ('train', 'validation'):
        p = WORK / f'{split}-goals.npz'
        with np.load(p) as z: g = {k:z[k] for k in z.files}
        with np.load(BASE / 'combined-train.npz' if split == 'train' else BASE.parent / 'v4/validation.npz') as z:
            rounds, group, y = z['round'], z['group'], z['y']
        masks = {'all':np.ones(len(y), bool)}
        if split == 'train': masks['natural'] = np.load(BASE.parent / 'v9/frequency/natural-mask.npy')
        vals = {}
        for name, m in masks.items():
            ix = np.flatnonzero(m & g['goal_target_available'])
            dist = np.abs(g['achieved_position'][ix] - g['position'][ix]).max(-1) * 32
            elapsed = rounds[g['future_row'][ix]] - rounds[ix]
            vals[name] = dict(rows=int(m.sum()), goal_target_support=len(ix),
                demonstrated_same_position=int((dist == 0).sum()),
                demonstrated_same_position_fraction=float((dist == 0).mean()),
                chebyshev_tile_displacement_quantiles=np.quantile(dist, [0,.25,.5,.75,.9,1]).tolist(),
                round_horizon_quantiles=np.quantile(elapsed, [0,.1,.5,.9,1]).tolist(),
                support_by_group={str(int(k)):int((group[ix] == k).sum()) for k in np.unique(group)})
        out[split] = dict(sampling=vals, targets_sha256=digest(p))
    immutable_json(REPORT / 'goal-target-support.json', dict(results=out,
        interpretation='Achieved future PRE positions are goal-forecast supervision, not verified intent. Stationary targets cannot by themselves establish strategic objective recovery. This diagnostic does not revise the frozen horizon, loss, checkpoints, budgets or denominator.',
        new_fits=0, reserved_opened=0))


if __name__ == '__main__': run()
