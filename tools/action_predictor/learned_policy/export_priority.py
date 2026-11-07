"""Export the immutable P05 component; no new fit or labels/vocabulary."""
import json
import numpy as np
import torch
from .sequence_data import ROOT, BASE, WORK, REPORT
from ..data import digest
from ..audit import immutable_json


def run():
    reports = ROOT / 'tools/action_predictor/experiments'
    mp = BASE / 'runs/M01/model.pt'; pp = BASE.parent / 'v8/runs/P05/model.pt'
    assert digest(mp) == json.loads((reports / 'v5/M01.json').read_text())['checkpoint_sha256']
    assert digest(pp) == json.loads((reports / 'v8/P05.json').read_text())['checkpoint_sha256']
    m = torch.load(mp, weights_only=True); p = torch.load(pp, weights_only=True)
    weights = {'execution.' + k: v.numpy() for k, v in m['state_dict'].items()
               if k.startswith(('current.', 'history.', 'combine.'))}
    weights.update({'priority.' + k: v.numpy() for k, v in p['head_state'].items() if k.startswith('linear.')})
    # PortablePriority.linear expects the direct linear weight/bias suffix.
    for suffix in ('weight', 'bias'):
        weights['priority.' + suffix] = weights.pop('priority.linear.' + suffix)
    for key in ('absolute', 'residual'): weights[key] = p['head_state'][key].numpy()
    for key in ('extra_mean', 'extra_std'): weights[key] = p[key].numpy()
    directory = WORK / 'exports/P05'; directory.mkdir(parents=True, exist_ok=True)
    target = directory / 'priority.npz'
    assert not target.exists(), 'Retain existing exported component'
    np.savez(target, **weights)
    metadata = dict(config=m['config'], mean=m['mean'].tolist(), std=m['std'].tolist(),
                    M01_checkpoint_sha256=digest(mp), P05_checkpoint_sha256=digest(pp),
                    weights_sha256=digest(target), learned_weight_scalars=sum(int(v.size) for k, v in weights.items() if k.endswith(('weight', 'bias', 'weight_ih_l0', 'weight_hh_l0', 'bias_ih_l0', 'bias_hh_l0'))),
                    source_sha256=digest(__file__),
                    meaning='Frozen M01 priority-context encoder plus frozen P05 integer mixture, exact int64 anchors and original TRAIN vocabularies. No new priority fitting or strategy.',
                    new_fits=0, reserved_opened=0)
    immutable_json(directory / 'priority.json', metadata)
    immutable_json(REPORT / 'P05-portable-export.json', metadata)
    print('Exported retained P05', metadata['learned_weight_scalars'], flush=True)


if __name__ == '__main__': run()
