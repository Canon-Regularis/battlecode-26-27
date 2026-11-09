"""Causal observed-position history, separate from command or goal labels."""
import math
import torch
from torch import nn
from .model import OFFSETS


def heading_step(current, round_number, state=None):
    """Compute from PRE positions, then assimilate current PRE. Missing retains state."""
    out = torch.zeros(9, 4)
    if current is None:
        return out, state
    own = current['observation']['own']; p = own.get('position'); actor = own['entity']
    if p is None:
        return out, None
    if state is not None and state['actor'] == actor and round_number > state['round']:
        dx, dy = p['x']-state['x'], p['y']-state['y']
        length = math.hypot(dx, dy)
        if length:
            sx, sy = (dx > 0)-(dx < 0), (dy > 0)-(dy < 0)
            recency = 1./max(1, round_number-state['round'])
            for i, (x, y) in enumerate(OFFSETS):
                cosine = (x*dx+y*dy)/(math.hypot(x, y)*length) if x or y else 0.
                match = float((x, y) == (sx, sy))
                out[i] = torch.tensor([cosine, match, cosine*recency, match*recency])
    return out, dict(actor=actor, x=p['x'], y=p['y'], round=round_number)


def heading_window(window):
    state = None; rows = []
    for step in window['steps']:
        features, state = heading_step(step['input'] if step['observed'] else None, step['round'], state)
        rows.append(features)
    return torch.stack(rows)


class HeadingCorrection(nn.Module):
    def __init__(self, hidden=0):
        super().__init__()
        self.weights = nn.Sequential(nn.Linear(56, hidden), nn.Tanh(), nn.Linear(hidden, 4)) if hidden else nn.Linear(56, 4)
        final = self.weights[-1] if hidden else self.weights
        nn.init.zeros_(final.weight); nn.init.zeros_(final.bias)

    def forward(self, context, features, baseline):
        return baseline + (features*self.weights(context)[..., None, :]).sum(-1)


class HeadingPolicy(nn.Module):
    def __init__(self, parent, correction):
        super().__init__(); self.parent = parent.eval().requires_grad_(False); self.correction = correction

    def forward(self, *args, heading, **kwargs):
        states = []
        hook = self.parent.backbone.code.register_forward_pre_hook(lambda module, args: states.append(args[0]))
        try:
            with torch.no_grad(): output = self.parent(*args, **kwargs)
        finally: hook.remove()
        context = torch.cat((states[0], output['code'].softmax(-1)), -1)
        output['move'] = self.correction(context, heading, output['move'])
        return output
