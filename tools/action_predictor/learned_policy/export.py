"""Export an explicitly selected checkpoint, retaining all upstream artifacts."""
import json
import sys
import numpy as np
import torch
from .sequence_data import WORK, REPORT
from ..data import digest
from ..audit import immutable_json
from .. import reliable_train as rt


def run(identifier):
    info = json.loads((REPORT / f'{identifier}.json').read_text())
    path = WORK / f"runs/{identifier}/round-{info['selected_round']:02d}.pt"
    assert digest(path) == info['checkpoint_sha256']
    saved = torch.load(path, weights_only=False, map_location='cpu')
    directory = WORK / f'exports/{identifier}'
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / 'policy.npz'
    assert not target.exists(), 'Retain the existing export'
    np.savez(target, **{k: v.numpy() for k, v in saved['state'].items()})
    metadata = dict(config=saved['config'], persistent=saved['persistent'], labels=rt.LABELS,
                    mean=saved['mean'].tolist(), std=saved['std'].tolist(),
                    checkpoint_sha256=digest(path), weights_sha256=digest(target),
                    selected_round=saved['round'], source_commit=saved['source_commit'],
                    design_sha256=saved['design_sha256'],
                    runtime='Independent NumPy inference for the goal-conditioned core only. Whole host pipeline still uses Torch in the reused P05/input adapter until separately ported. Does not establish WASI compatibility or a complete SDK observation/draft/purchase bridge.',
                    priority='Reuse frozen P05 conditional as a separately bound personal-PRE component, not current recorded integer; full P05 native export is still required',
                    new_fits=0, reserved_opened=0)
    immutable_json(directory / 'policy.json', metadata)
    immutable_json(REPORT / f'{identifier}-export.json', dict(
        **metadata, exporter_sha256=digest(__file__),
        portable_source_sha256=digest(__file__.replace('export.py', 'portable.py'))))


if __name__ == '__main__':
    run(sys.argv[1])
