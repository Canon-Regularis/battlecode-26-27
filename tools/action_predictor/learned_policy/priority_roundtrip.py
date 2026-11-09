"""Verify the independently ported frozen P05 on all original DEV rows."""
import json
from pathlib import Path
import numpy as np
from .sequence_data import ROOT, BASE, WORK, REPORT
from .portable_priority import PortablePriority
from ..data import digest
from ..audit import immutable_json


def run():
    from ..priority_fit_v3 import context_directory
    old = ROOT / 'tools/action_predictor/experiments'
    directory = WORK / 'exports/P05'
    metadata = json.loads((directory / 'priority.json').read_text())
    path = directory / 'priority.npz'; assert digest(path) == metadata['weights_sha256']
    with np.load(path) as z: weights = {k:z[k] for k in z.files}
    runtime = PortablePriority(weights, metadata['config'])
    with np.load(BASE.parent / 'v4/validation.npz') as z:
        x = (z['x'] - np.array(metadata['mean'], np.float32)) / np.array(metadata['std'], np.float32)
        history = z['history'].copy(); y = z['y']; targets = z['priority'].astype(np.int64)
    spatial = history[:, :, [1,2,3,5,6,7,8,12,13,14]].sum(-1) > 0
    history[:, :, 16:18] *= spatial[:, :, None]
    pp = BASE.parent / 'v8/priority-validation.npz'
    plan = json.loads((old / 'v8/priority-residual-modes-plan.json').read_text())
    assert digest(pp) == plan['priority_validation_sha256']
    with np.load(pp) as z: values = z['values']; phistory = z['history']
    contextpath = context_directory() / 'validation.npy'
    ready = json.loads((old / 'v8/priority-context-ready-v3.json').read_text())
    assert digest(contextpath) == ready['contexts']['validation']
    context = np.load(contextpath, mmap_mode='r')
    modes = np.load(BASE.parent / 'v13/validation-modes.npy', mmap_mode='r')[:, 9, 2]
    oldjoint = np.load(BASE.parent / 'v13/validation-mode-logq.npy', mmap_mode='r')[:, 9]
    oldtypes = np.load(BASE.parent / 'v14/validation-type-logp.npy', mmap_mode='r')[:, 9]
    with np.load(BASE.parent / 'v9/runs/G00/validation-predictions.npz') as z: target_nll = z['param_nll']
    raw_error = 0.; probability_error = 0.; observed_error = 0.; correct = 0
    for start in range(0, len(x), 128):
        end = min(start + 128, len(x)); v = values[start:end]
        c = runtime.base_context(x[start:end], history[start:end])
        raw_error = max(raw_error, float(np.abs(c - context[start:end]).max()))
        np.testing.assert_allclose(c, context[start:end], atol=2e-5, rtol=0)
        raw = runtime.raw(x[start:end], history[start:end], v, phistory[start:end])
        mode, lp = runtime.modes(raw, v)
        np.testing.assert_array_equal(mode, modes[start:end])
        probability_error = max(probability_error, float(np.abs(lp - (oldjoint[start:end] - oldtypes[start:end])).max()))
        np.testing.assert_allclose(lp, oldjoint[start:end] - oldtypes[start:end], atol=2e-4, rtol=0)
        m = y[start:end] == 9
        if m.any():
            nll = -runtime.log_mass(raw[m], targets[start:end][m], v[m])
            observed_error = max(observed_error, float(np.abs(nll - target_nll[start:end][m]).max()))
            np.testing.assert_allclose(nll, target_nll[start:end][m], atol=2e-4, rtol=0)
            correct += int((mode[m] == targets[start:end][m]).sum())
    dependencies = [pp, contextpath, BASE.parent / 'v13/validation-modes.npy',
                    BASE.parent / 'v13/validation-mode-logq.npy', BASE.parent / 'v14/validation-type-logp.npy',
                    BASE.parent / 'v9/runs/G00/validation-predictions.npz', directory / 'priority.json', path]
    immutable_json(REPORT / 'P05-portable-roundtrip.json', dict(
        original_DEV_rows=len(x), exact_priority_modes=True, true_priority_support=int((y == 9).sum()),
        conditional_integer_correct=correct, max_context_difference=raw_error,
        max_mode_logp_difference=probability_error, max_true_priority_nll_difference=observed_error,
        bindings={str(p.relative_to(ROOT)):digest(p) for p in dependencies},
        source_sha256=digest(__file__), portable_priority_sha256=digest(Path(__file__).with_name('portable_priority.py')),
        portable_operators_sha256=digest(Path(__file__).with_name('portable.py')),
        meaning='All original DEV integer modes and modeled probabilities for a new numerical port of the retained P05, not new model quality or a new replay/engine audit. Exact integer anchors/vocabularies retained. Host NumPy, not WASI execution.',
        new_fits=0, reserved_opened=0))
    print('Portable P05', len(x), correct, raw_error, probability_error, observed_error, flush=True)


if __name__ == '__main__': run()
