"""Archive initialization forecasts before checking the repaired interface."""
import numpy as np
import torch
from .protocol import LOCAL, OUT, ARMS
from .interface_protocol import amend
from .decoder_interface import ReadoutDecoderInterface
from .data import load, geometry_reference
from .inference import infer
from .preflight import semantic_equal
from ..learned_policy.pathway_reference import load_model
from ..learned_policy.analysis import read
from ..audit import immutable_json
from ..data import digest


@torch.no_grad()
def run():
    amend()
    torch.set_num_threads(4)
    upstream, _, checkpoint = load_model('L02')
    d = load('validation')
    initial, records = {}, {}
    for identifier, dynamic in ARMS.items():
        directory = LOCAL / f'initial-v2/{identifier}'
        assert not directory.exists(), 'Preserve attempt'
        directory.mkdir(parents=True)
        model = ReadoutDecoderInterface(upstream, geometry_reference(), dynamic)
        initial[identifier] = model.state_dict()
        prediction, diagnostics = infer(model, d)
        np.savez_compressed(directory / 'validation-predictions.npz', **prediction)
        np.savez_compressed(directory / 'validation-diagnostics.npz', **diagnostics)
        reference_path = (LOCAL.parent / 'v17/Q01-v2/L02/fixed--geometry_mean-predictions.npz'
                          if not dynamic else LOCAL.parent / 'v16/runs/L02/validation-predictions.npz')
        reference = read(reference_path)
        records[identifier] = dict(semantic_mode_changes=int((~semantic_equal(prediction, reference)).sum()),
            NLL_max_difference=float(np.abs(prediction['nll'] - reference['nll']).max()),
            reference_sha256=digest(reference_path),
            predictions_sha256=digest(directory / 'validation-predictions.npz'))
    exact = all(torch.equal(v, initial['U01'][k]) for k, v in initial['U00'].items())
    passed = exact and all(r['semantic_mode_changes'] == 0 and r['NLL_max_difference'] <= 2e-5 for r in records.values())
    immutable_json(OUT / 'preflight-v2.json', dict(results=records, passed=passed,
        initial_parameter_tensors_identical=exact, checkpoint_sha256=digest(checkpoint),
        upstream_ready_sha256=digest(OUT / 'upstream-ready.json'),
        recovery_plan_sha256=digest(OUT / 'interface-recovery-plan.json'),
        new_fits=0, reserved_opened=0,
        qualification='All original14439DEV rows. Cache/readout initialization parity, not '
                      'independent raw extraction. Original derived-conditional numerical '
                      'qualification remains. Unused returned goal diagnostics explicitly None.'))
    assert passed
    print('Readout v2 preflight passed', records, flush=True)


if __name__ == '__main__':
    run()
