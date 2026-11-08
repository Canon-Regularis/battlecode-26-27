"""Readout predictions before target access; baseline causal state stays common."""
import numpy as np
import torch
from .data import inputs, geometry, targets
from ..learned_policy.model import SPATIAL


@torch.no_grad()
def infer(model, d, decode=True, batch_size=256):
    model.eval()
    n = len(d['raw']['y'])
    out = {key: np.full(n, -1, np.int64) for key in ('prediction', 'coordinate', 'proposed_coordinate')}
    out.update(priority=d['priority_mode'].copy(), top5=np.full((n, 5), -1, np.int64),
               nll=np.full(n, np.nan, np.float64), type_nll=np.full(n, np.nan, np.float64),
               param_nll=np.full(n, np.nan, np.float64))
    diagnostics = dict(rank=np.full(n, -1, np.int16), component_modes=np.full((n, 4), -1, np.int16))
    for start in range(0, n, batch_size):
        ix = np.arange(start, min(start + batch_size, n))
        step = model.begin(**inputs(d, ix))
        geo = geometry(d, ix)
        # Complete MAP depends only on frozen PRE inputs and trained readout.
        if decode:
            pred = model.decode(step, **geo, priority_mode=torch.from_numpy(d['priority_mode'][ix]),
                                priority_mode_logp=torch.from_numpy(d['priority_mode_logp'][ix]))
            out['prediction'][ix] = pred['prediction'].numpy()
            out['proposed_coordinate'][ix] = pred['coordinate'].numpy()
        target = targets(d, ix)
        loss = model.command_loss(step, **geo, **target)
        out['nll'][ix] = loss.numpy()
        if not decode:
            continue
        y = target['y'].numpy()
        type_nll = -pred['type_logp'][torch.arange(len(ix)), target['y']]
        out['type_nll'][ix] = type_nll.numpy()
        out['param_nll'][ix] = loss.numpy() - type_nll.numpy()
        for family in SPATIAL:
            mask = y == family
            if not mask.any():
                continue
            lp = pred['parameter_logp'][family][mask]
            py = target['py'][mask]
            out['coordinate'][ix[mask]] = lp.argmax(-1).numpy()
            out['top5'][ix[mask]] = lp.topk(5, -1).indices.numpy()
            correct_lp = lp[torch.arange(len(py)), py, None]
            order = torch.arange(lp.shape[-1])[None]
            rank = 1 + (lp > correct_lp).sum(-1) + ((lp == correct_lp) & (order < py[:, None])).sum(-1)
            diagnostics['rank'][ix[mask]] = rank.numpy()
            if family in (3, 8):
                sub = {key: value[mask] for key, value in step.items()}
                heads = model.spatial_log_probs(sub, **{key: value[mask] for key, value in geo.items()},
                                               family=target['y'][mask])
                diagnostics['component_modes'][ix[mask]] = heads.argmax(-1).numpy()
    if decode:
        typed = (out['prediction'] == d['raw']['y']) & np.isin(d['raw']['y'], SPATIAL)
        np.testing.assert_array_equal(out['coordinate'][typed], out['proposed_coordinate'][typed])
        assert np.isfinite(out['nll']).all()
        np.testing.assert_allclose(out['type_nll'] + out['param_nll'], out['nll'], atol=2e-5, rtol=0)
    return out, diagnostics
