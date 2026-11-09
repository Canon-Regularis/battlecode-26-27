"""Reuse immutable eligible personal-PRE caches; no replay/engine operations."""
import numpy as np
import torch
from ..learned_policy.data import load as previous_load, causal_inputs, geometry, chunks
from ..learned_policy.sequence_data import ROOT, BASE

WORK = ROOT / '.cambc/action-predictor/v30'
REPORT = ROOT / 'tools/action_predictor/experiments/v30'


def load(split, saved):
    d = previous_load(split, saved)
    # The same retained RC01 integer distribution on EVERY row, without gold
    # family routing. It cannot fix the integer-model ceiling in this study.
    directory = BASE.parent / f'v27/forecasts/{split}/JP02'
    d['priority_mode'] = np.load(directory / 'integer.npy')
    d['priority_mode_logp'] = np.load(directory / 'mode_logp.npy')
    with np.load(BASE.parent / f'v27/JP02-{split}-predictions.npz') as z:
        d['priority_parameter_nll'] = np.array(z['param_nll'])
    return d


def targets(d, ids):
    ix = np.asarray(ids)
    return dict(y=d['inputs']['y'][ix], py=d['inputs']['py'][ix],
        priority_value=torch.from_numpy(d['raw']['priority'][ix].astype(np.int64)),
        priority_parameter_nll=torch.from_numpy(d['priority_parameter_nll'][ix]))


def diagnostic_data(d, split):
    directory = BASE.parent / 'v7'
    return dict(raw=d['raw'], direction=np.load(directory / f'{split}-direction.npy'),
        available=np.load(directory / f'{split}-available.npy'),
        near=np.load(directory / f'{split}-near_obstacle.npy'))
