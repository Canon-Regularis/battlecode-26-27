"""Unnormalized causal input construction; no targets, fitting or model weights."""
import numpy as np
from ..audit import cursor
from ..observation_data import encode, safe_observation
from ..rich_data import history_vector, candidate_grid
from ..priority_inputs import PriorityMemory


def encode_frame(frame, route):
    obs, supp = frame['observation'], frame['supplement']
    if supp['pre'] != frame['pre']: raise ValueError('Supplement belongs to another PRE')
    for key in ('position', 'health', 'maxHealth', 'items', 'gems', 'channelType', 'channelTimer', 'roundFlags'):
        if key in supp['own'] and supp['own'][key] != obs['own'].get(key):
            raise ValueError('Supplement/observation disagreement')
    safe_observation(obs, frame['actor'], obs['own']['team'], supp)
    value = encode(obs, supp, route, frame['round'])
    if not np.isfinite(value).all(): raise ValueError('Nonfinite current features')
    return value


def inputs(frame, earlier, frames, route, labels):
    """Earlier roots include unsampled actions, strictly before the current PRE.

    Missing personal observations remain zero with a separate availability bit.
    Current/scheduled priority PRE fields are deliberately unavailable on EVERY
    row in this proposed interface. Earlier actual integer arguments remain
    causal inputs. This missing-input treatment needs review before fitting.
    """
    obs = frame['observation']; pos = obs['own'].get('position')
    history = np.zeros((16, len(labels)+9), np.float32)
    observations = np.zeros((16, 253), np.float32)
    gaps = np.zeros((16, 5), np.float32)
    previous = None; last_move = None
    memory = PriorityMemory(frame['actor'])
    for event in earlier:
        at = cursor(event['event']); step = event['step']
        if at > cursor(frame['pre']) or (previous is not None and at <= previous):
            raise ValueError('Earlier command order/future leak')
        if event['round'] > frame['round']: raise ValueError('Future command round')
        memory.observe(step, event['event'], event['round'])
        previous = at
        if step['kind'] == 4:
            last_move = np.array([step['to'][k]-step['from'][k] for k in ('x', 'y')])
    tail = earlier[-16:]
    for slot, prior in enumerate(tail, 16-len(tail)):
        name = prior['family']; kind = labels.index(name) if name in labels else 0
        history[slot] = history_vector((cursor(prior['event']), kind, prior['step'], prior['round']),
                                      frame['round'], pos, labels)
        cached = frames.get(prior['event'])
        if cached is not None:
            if (cached['actor'] != frame['actor'] or cached['event'] != prior['event'] or
                    cursor(cached['pre']) >= cursor(prior['event']) or cached['round'] != prior['round']):
                raise ValueError('Earlier observation identity mismatch')
            observations[slot] = encode_frame(cached, route)
        following = tail[slot-(16-len(tail))+1] if slot < 15 else frame
        elapsed = following['round']-prior['round']; age = frame['round']-prior['round']
        if elapsed < 0 or age < 0: raise ValueError('History rounds went backwards')
        gaps[slot] = [1, cached is not None, min(elapsed,100)/100,
                      following['turn'] != prior['turn'], min(age,100)/100]
    grid, valid, move = candidate_grid(obs, frame['supplement'], route, last_move)
    priority, priority_history = memory.inputs({}, frame['pre'], frame['round'])
    return dict(x=encode_frame(frame, route), history=history, observations=observations,
        history_gaps=gaps, grid=grid, valid=valid, move_mask=move,
        priority_inputs=priority, priority_history=priority_history)
