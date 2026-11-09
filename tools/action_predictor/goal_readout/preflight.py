"""Full DEV initialization parity before fitting; archive before assertions."""
import json
import numpy as np
import torch
from .protocol import ROOT, LOCAL, OUT, V17, ARMS, freeze
from .data import load, geometry_reference
from .model import FrozenGoalReadout
from .inference import infer
from ..learned_policy.pathway_reference import load_model
from ..learned_policy.analysis import read
from ..learned_policy.model import SPATIAL
from ..audit import immutable_json
from ..data import digest


def semantic_equal(a, b):
    same = a['prediction'] == b['prediction']
    spatial = np.isin(a['prediction'], SPATIAL)
    same &= ~spatial | (a['proposed_coordinate'] == b['proposed_coordinate'])
    same &= (a['prediction'] != 9) | (a['priority'] == b['priority'])
    return same


@torch.no_grad()
def run():
    freeze()
    torch.set_num_threads(4)
    upstream, _, checkpoint = load_model('L02')
    d = load('validation')
    outputs, initial, records = {}, {}, {}
    for identifier, dynamic in ARMS.items():
        directory = LOCAL / f'initial/{identifier}'
        assert not directory.exists(), 'Preserve preflight attempt'
        directory.mkdir(parents=True)
        model = FrozenGoalReadout(upstream, geometry_reference(), dynamic)
        initial[identifier] = model.state_dict()
        prediction, diagnostics = infer(model, d)
        np.savez_compressed(directory / 'validation-predictions.npz', **prediction)
        np.savez_compressed(directory / 'validation-diagnostics.npz', **diagnostics)
        outputs[identifier] = prediction
        reference_path = (LOCAL.parent / 'v17/Q01-v2/L02/fixed--geometry_mean-predictions.npz'
                          if not dynamic else LOCAL.parent / 'v16/runs/L02/validation-predictions.npz')
        reference = read(reference_path)
        difference = float(np.abs(prediction['nll'] - reference['nll']).max())
        records[identifier] = dict(semantic_mode_changes=int((~semantic_equal(prediction, reference)).sum()),
            NLL_max_difference=difference, reference_sha256=digest(reference_path),
            predictions_sha256=digest(directory / 'validation-predictions.npz'))
    exact = all(torch.equal(v, initial['U01'][k]) for k, v in initial['U00'].items())
    receipt = dict(results=records, initial_parameter_tensors_identical=exact,
        checkpoint_sha256=digest(checkpoint), upstream_ready_sha256=digest(OUT / 'upstream-ready.json'),
        protocol_sha256=digest(OUT / 'protocol.json'), new_fits=0, reserved_opened=0,
        qualification='Cache/readout initialization check, not independently re-extracted raw PRE or a fitted result. '
                      'All original14439DEV rows; mean branch compared to Q01 fixed-state geometry-mean contrast. '
                      'Original derived-conditional numerical limitation remains disclosed.')
    immutable_json(OUT / 'preflight.json', receipt)
    assert exact
    assert all(row['semantic_mode_changes'] == 0 and row['NLL_max_difference'] <= 2e-5 for row in records.values())
    print('Readout preflight passed', records, flush=True)


if __name__ == '__main__':
    run()
