"""Independent numerical forward-filter check; never an extra model fit."""
import json
import sys
from collections import Counter
from pathlib import Path
import numpy as np
import torch
from .sequence_data import BASE, WORK, REPORT, JOBS
from .model import GoalPolicy
from .portable import PortablePolicy
from .data import load, causal_inputs, geometry, targets
from ..priority_fit_v3 import load_base
from ..audit import immutable_json
from ..data import digest


def compare(model, d):
    """Fixed first 32 decisions of two actor streams per historical engine.

    For L00 also exercise the SAME weights with persistence enabled solely as
    an arithmetic test, with no performance interpretation or model selection.
    """
    eligible = [j for j in json.loads(JOBS.read_text()) if j['split'] == 'validation']
    streams = []
    for version in ('2.0.0', '3.0.0'):
        j = next(j for j in eligible if j['record']['engine_version'] == version)
        choices = [s for s in d['sequences'] if j['offset'] <= s[0] < j['offset'] + j['rows']]
        streams.extend((version, s[:32]) for s in choices[:2])
    maxima, counts = Counter(), Counter()
    weights = {k: v.detach().numpy() for k, v in model.state_dict().items()}
    persistent_values = (False, True) if not model.persistent else (True,)
    original = model.persistent
    for persistent in persistent_values:
        model.persistent = persistent
        portable = PortablePolicy(weights, model.execution.config, persistent)
        for version, stream in streams:
            ts = model.empty(1); ns = portable.empty(1)
            for row in stream:
                ix = np.array([row]); inputs = causal_inputs(d, ix); geo = geometry(d, ix)
                ni = {k: v.numpy() for k, v in inputs.items()}
                ng = {k: v.numpy() for k, v in geo.items()}
                with torch.no_grad():
                    t = model.begin(**inputs, state=ts)
                    n = portable.begin(**ni, state=ns)
                    for key in t:
                        diff = float(np.abs(t[key].float().numpy() - n[key].astype(np.float32)).max())
                        maxima['state/' + key] = max(maxima['state/' + key], diff)
                        np.testing.assert_allclose(t[key].numpy(), n[key], atol=1e-4, rtol=0)
                    pm = d['priority_mode'][ix]; pl = d['priority_mode_logp'][ix]
                    tp = model.decode(t, **geo, priority_mode=torch.from_numpy(pm), priority_mode_logp=torch.from_numpy(pl))
                    npred = portable.decode(n, **ng, priority_mode=pm, priority_mode_logp=pl)
                    for key in ('prediction', 'coordinate', 'priority'):
                        np.testing.assert_array_equal(tp[key].numpy(), npred[key])
                    for family, lp in tp['parameter_logp'].items():
                        diff = float(np.abs(lp.numpy() - npred['parameter_logp'][family]).max())
                        maxima['parameter_logp'] = max(maxima['parameter_logp'], diff)
                        actual, reference = npred['parameter_logp'][family], lp.numpy()
                        # Preserve the original failed absolute-log test in the
                        # preflight receipt. A -1e4 mask sentinel has float32
                        # spacing ~1e-3, while its probability underflows to 0.
                        meaningful = (actual > -80) | (reference > -80)
                        np.testing.assert_allclose(reference[meaningful], actual[meaningful], atol=2e-4, rtol=0)
                        np.testing.assert_allclose(np.exp(reference), np.exp(actual), atol=2e-5, rtol=0)
                        counts['underflow_log_slots_over_original_tolerance'] += int((np.abs(reference - actual) > 2e-4).sum())
                    target = targets(d, ix)
                    # Actual recorded action enters ONLY after both predictions.
                    tt = {k: target[k] for k in ('y', 'py', 'priority_parameter_nll')}
                    tl, ts = model.observed(t, **geo, **tt)
                    nl, ns = portable.observed(n, **ng, **{k: v.numpy() for k, v in tt.items()})
                    maxima['observed_nll'] = max(maxima['observed_nll'], float(np.abs(tl.numpy() - nl).max()))
                    np.testing.assert_allclose(tl.numpy(), nl, atol=2e-4, rtol=0)
                counts[f'persistent_{persistent}/engine_{version}'] += 1
    model.persistent = original
    return dict(cases=dict(counts), max_absolute_difference=dict(maxima),
                tolerance=dict(state=1e-4, logp_above_minus80=2e-4, all_probabilities=2e-5, observed_nll=2e-4, command='exact'),
                qualification='Bounded cached-input independent arithmetic and forward-filter check, not full raw-PRE or WASI/engine proof. Original absolute-log test failed on underflow sentinel slots and remains failed; revised probability/meaningful-log contract is explicit. Counterfactual persistence on control weights tests arithmetic only.')


def run(identifier):
    torch.set_num_threads(4)
    info = json.loads((REPORT / f'{identifier}.json').read_text())
    path = WORK / f"runs/{identifier}/round-{info['selected_round']:02d}.pt"
    assert digest(path) == info['checkpoint_sha256']
    teacher, saved = load_base(); checkpoint = torch.load(path, weights_only=False)
    model = GoalPolicy(teacher, checkpoint['persistent']); model.load_state_dict(checkpoint['state']); model.eval()
    result = compare(model, load('validation', saved))
    immutable_json(REPORT / f'{identifier}-portable-roundtrip.json', dict(
        **result, checkpoint_sha256=digest(path), source_sha256=digest(__file__),
        portable_sha256=digest(Path(__file__).with_name('portable.py')), new_fits=0, reserved_opened=0))
    print(result, flush=True)


if __name__ == '__main__':
    run(sys.argv[1])
