"""Causal predict-then-assimilate ordering; all original rows retained."""
import numpy as np
import torch
from .data import causal_inputs, geometry, targets, chunks


def take(state, indices):
    return {k: v[indices] for k, v in state.items()}


def put(state, indices, updated):
    return {k: v.index_copy(0, indices, updated[k]) for k, v in state.items()}


@torch.no_grad()
def infer(model, d, directory, decode=True):
    """Raw per-row arrays survive a later scoring exception.

    Decoded commands and every-family coordinates are written BEFORE reading the
    current answer. The current answer then updates the forward filter only for
    subsequent decisions. Padding rows never enter the model.
    """
    model.eval()
    directory.mkdir(parents=True, exist_ok=False)
    n = len(d['raw']['y'])
    shapes = {'nll': (n,), 'reset': (n,), 'prior': (n, model.states)}
    if model.hierarchy:
        shapes.update(expected_age=(n, model.states), previous_state_hazard=(n, model.states), state_exit_mass=(n, model.states), previous_state_probability=(n, model.states), transition_exit_probability=(n,))
    if decode:
        shapes.update(prediction=(n,), coordinate=(n,), proposed_coordinate=(n,),
            priority=(n,), top5=(n, 5), type_nll=(n,), param_nll=(n,),
            family_coordinate=(n, 15), type_logp=(n, 15),
            component_move_modes=(n, model.states), conditional_move_target_logp=(n,),
            move_target_rank=(n,))
    integer = {'prediction', 'coordinate', 'proposed_coordinate', 'priority',
        'top5', 'family_coordinate', 'component_move_modes', 'move_target_rank'}
    arrays = {k: np.lib.format.open_memmap(directory/(k+'.npy'), mode='w+',
        dtype=np.int64 if k in integer else np.float64, shape=shape) for k, shape in shapes.items()}
    for k, a in arrays.items(): a[:] = -1 if k in integer else np.nan
    seen = np.zeros(n, np.uint8)
    state = model.empty(32)
    for rows in chunks(d['sequences']):
        for row in rows:
            active = torch.from_numpy(np.flatnonzero(row >= 0))
            ids = row[row >= 0]
            if not len(ids): continue
            step = model.begin(**causal_inputs(d, ids), state=take(state, active))
            geo = geometry(d, ids)
            arrays['reset'][ids] = step['reset'].numpy()
            arrays['prior'][ids] = step['logprior'].exp().numpy()
            if model.hierarchy:
                age = (step['filter_prior']['logp']-step['logprior'][:, :, None]).exp()
                arrays['expected_age'][ids] = (age*torch.arange(model.max_age)).sum(-1).numpy()
                for key in ('previous_state_hazard', 'state_exit_mass', 'previous_state_probability', 'transition_exit_probability'):
                    arrays[key][ids] = step['filter_prior'][key].numpy()
            if decode:
                p = model.decode(step, **geo, priority_mode=torch.from_numpy(d['priority_mode'][ids]),
                    priority_mode_logp=torch.from_numpy(d['priority_mode_logp'][ids]))
                for k, value in [('prediction', p['prediction']), ('proposed_coordinate', p['coordinate']),
                    ('priority', p['priority']), ('family_coordinate', p['family_coordinates']),
                    ('type_logp', p['type_logp']), ('component_move_modes', p['component_move_modes'])]:
                    arrays[k][ids] = value.numpy()
            target = targets(d, ids)
            loss, post = model.observed(step, **geo, **target)
            arrays['nll'][ids] = loss.numpy()
            if decode:
                y = target['y'].numpy()
                type_nll = -p['type_logp'][torch.arange(len(ids)), target['y']].numpy()
                arrays['type_nll'][ids] = type_nll
                arrays['param_nll'][ids] = loss.numpy() - type_nll
                # Gold family is consulted only AFTER final command selection.
                arrays['coordinate'][ids] = p['family_coordinates'][torch.arange(len(ids)), target['y']].numpy()
                arrays['top5'][ids] = -1
                for family, lp in p['parameter_logp'].items():
                    selected = y == family
                    arrays['top5'][ids[selected]] = lp.topk(5, -1).indices.numpy()[selected]
                lp = p['parameter_logp'][8]
                move = y == 8
                arrays['conditional_move_target_logp'][ids] = np.nan
                arrays['move_target_rank'][ids] = -1
                if move.any():
                    local = torch.from_numpy(np.flatnonzero(move))
                    label = target['py'][local]
                    actual = lp[local, label]
                    arrays['conditional_move_target_logp'][ids[move]] = actual.numpy()
                    # First-argmax tie convention, rank one is actual decoding.
                    rank = 1 + ((lp[local] > actual[:, None]) |
                        ((lp[local] == actual[:, None]) & (torch.arange(291)[None] < label[:, None]))).sum(-1)
                    arrays['move_target_rank'][ids[move]] = rank.numpy()
            state = put(state, active, post)
            seen[ids] += 1
        for a in arrays.values(): a.flush()
    if not np.all(seen == 1): raise RuntimeError('Every original decision must be scored exactly once')
    if not np.isfinite(arrays['nll']).all(): raise RuntimeError('Nonfinite likelihood; raw arrays preserved')
    if decode:
        typed = (arrays['prediction'] == d['raw']['y']) & (d['raw']['py'] >= 0)
        np.testing.assert_array_equal(arrays['coordinate'][typed], arrays['proposed_coordinate'][typed])
    return arrays
