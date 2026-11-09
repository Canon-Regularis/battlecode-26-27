"""Consume shared frozen PRE features; recorded answers are separate targets."""
import json
import numpy as np
import torch
from .protocol import ROOT, BASE, LOCAL, OUT, V16, V17, V16_REPORT
from ..learned_policy.analysis import read
from ..data import digest


def load(split):
    ready = json.loads((OUT / 'upstream-ready.json').read_text())
    row = ready['results'][split]
    directory = LOCAL / f'upstream/{split}'
    cache = {}
    for key, expected in row['files'].items():
        path = directory / f'{key}.npy'
        assert digest(path) == expected, str(path)
        cache[key] = np.load(path, mmap_mode='r')
    dataset = BASE / 'combined-train.npz' if split == 'train' else BASE.parent / 'v4/validation.npz'
    bindings = json.loads((V16_REPORT / 'policy-input-bindings.json').read_text())['files']
    assert digest(dataset) == bindings[str(dataset.relative_to(ROOT))]
    required = [V16 / f'{split}-sequences.npz',
                BASE.parent / f'v9/runs/G00/{split}-predictions.npz',
                BASE.parent / f'v13/{split}-modes.npy',
                BASE.parent / f'v13/{split}-mode-logq.npy',
                BASE.parent / f'v14/{split}-type-logp.npy']
    required += [BASE.parent / f'v7/{split}-{name}.npy'
                 for name in ('direction', 'available', 'near_obstacle')]
    for path in required:
        assert digest(path) == bindings[str(path.relative_to(ROOT))], str(path)
    report = json.loads((V16_REPORT / 'L02.json').read_text())
    baseline_path = V16 / f'runs/L02/{split}-predictions.npz'
    assert digest(baseline_path) == report['predictions_sha256'][split]
    raw = read(dataset)
    assert len(raw['y']) == row['rows']
    seq = read(V16 / f'{split}-sequences.npz')
    sequences = [seq['order'][a:b] for a, b in zip(seq['offsets'][:-1], seq['offsets'][1:])]
    baseline = read(baseline_path)
    g00 = read(BASE.parent / f'v9/runs/G00/{split}-predictions.npz')
    modes = np.load(BASE.parent / f'v13/{split}-modes.npy', mmap_mode='r')
    mode_logq = np.load(BASE.parent / f'v13/{split}-mode-logq.npy', mmap_mode='r')
    type_logp = np.load(BASE.parent / f'v14/{split}-type-logp.npy', mmap_mode='r')
    return dict(raw=raw, cache=cache, sequences=sequences, baseline=baseline,
        grid=torch.from_numpy(raw['grid']), valid=torch.from_numpy(raw['valid']),
        rules=torch.from_numpy(np.column_stack((raw['attack_range'], raw['ability_range'], raw['ability_mask']))).float(),
        priority_parameter_nll=g00['param_nll'], priority_mode=np.array(modes[:, 9, 2]),
        priority_mode_logp=np.array(mode_logq[:, 9] - type_logp[:, 9]),
        direction=np.load(BASE.parent / f'v7/{split}-direction.npy'),
        available=np.load(BASE.parent / f'v7/{split}-available.npy'),
        near=np.load(BASE.parent / f'v7/{split}-near_obstacle.npy'))


def inputs(d, ix):
    return {key: torch.from_numpy(np.array(value[ix])) for key, value in d['cache'].items()}


def geometry(d, ix):
    return dict(grid=d['grid'][ix].float(), valid=d['valid'][ix], rules=d['rules'][ix])


def targets(d, ix):
    return dict(y=torch.from_numpy(d['raw']['y'][ix]).long(),
                py=torch.from_numpy(d['raw']['py'][ix]).long(),
                priority_parameter_nll=torch.from_numpy(d['priority_parameter_nll'][ix]))


def geometry_reference():
    return json.loads((V17 / 'Q01-L02-reference.json').read_text())['reference']['geometry_known']
