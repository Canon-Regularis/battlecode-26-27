"""Learned decision router between frozen JP02 and V59 movement destinations."""
import numpy as np
import torch
from torch import nn

FEATURE_COUNT = 273


def features(current, probabilities, old_coordinate, old_mode_logp, move_type_logp, history_turns):
    """Only causal PRE features, frozen forecasts and incoming history age."""
    current = np.asarray(current, dtype=np.float32)
    probabilities = np.asarray(probabilities, dtype=np.float32)
    if current.shape != (253,) or probabilities.shape != (9,):
        raise ValueError('Router feature interface changed')
    if not np.isfinite(current).all() or not np.isfinite(probabilities).all():
        raise ValueError('Nonfinite router input')
    if (probabilities < 0).any() or abs(float(probabilities.sum()) - 1) > 2e-6:
        raise ValueError('Invalid movement distribution')
    if not np.isfinite([old_mode_logp, move_type_logp]).all():
        raise ValueError('Invalid baseline confidence')
    valid = 0 <= old_coordinate < 289
    dx, dy = (old_coordinate % 17 - 8, old_coordinate // 17 - 8) if valid else (0, 0)
    mode = int(probabilities.argmax()); nx, ny = mode % 3 - 1, mode // 3 - 1
    mass = probabilities[(dy + 1) * 3 + dx + 1] if valid and max(abs(dx), abs(dy)) <= 1 else 0.
    entropy = -float((probabilities * np.log(probabilities.clip(1e-12))).sum()) / np.log(9)
    ordered = np.sort(probabilities)
    extra = [np.clip(old_mode_logp, -30, 0), np.clip(move_type_logp, -30, 0),
             min(history_turns, 32) / 32, dx / 8, dy / 8, float(valid), nx, ny,
             mass, entropy, ordered[-1] - ordered[-2]]
    return np.concatenate((current, probabilities, np.asarray(extra, np.float32)))


class MovementRouter(nn.Module):
    """Fit expected change in correctness; a zero score keeps the baseline."""
    def __init__(self, mean, scale):
        super().__init__()
        self.register_buffer('mean', torch.as_tensor(mean, dtype=torch.float32).clone())
        self.register_buffer('scale', torch.as_tensor(scale, dtype=torch.float32).clone())
        if self.mean.shape != (FEATURE_COUNT,) or self.scale.shape != (FEATURE_COUNT,) or not (self.scale > 0).all():
            raise ValueError('Invalid normalization')
        self.output = nn.Linear(FEATURE_COUNT, 1)
        nn.init.zeros_(self.output.weight); nn.init.zeros_(self.output.bias)

    def forward(self, x):
        return self.output(((x - self.mean) / self.scale).clamp(-8, 8)).squeeze(-1).tanh()


def normalized_router(x):
    if len(x) == 0: raise ValueError('Empty fitting router population')
    return MovementRouter(x.mean(0), x.std(0, ddof=0).clip(.01))


def route(record, prediction, coordinate, score):
    from .full_action_movement import dispatch
    if not np.isfinite(score): raise ValueError('Nonfinite routing score')
    return dispatch(prediction, coordinate, record['movement'],
                    record['eligible'] and score > 0)


class TrainedMovementRouter:
    """Runtime companion to TurnMovementAdapter; does not assimilate labels."""
    def __init__(self, checkpoint=None):
        from pathlib import Path
        from . import full_action_evaluate as e
        report = e.ROOT / 'tools/action_predictor/experiments/v75'
        work = e.ROOT / '.cambc/action-predictor/v75'
        receipt = e.read(report / 'refit.json'); e.check(receipt['bindings'])
        checkpoint = work / 'selected.pt' if checkpoint is None else Path(checkpoint)
        if str(checkpoint.resolve()) not in receipt['bindings']:
            raise ValueError('Unbound router checkpoint')
        saved = torch.load(checkpoint, map_location='cpu', weights_only=False)
        state = saved['model']
        self.net = MovementRouter(state['mean'], state['scale']).eval()
        self.net.load_state_dict(state)

    @torch.no_grad()
    def predict(self, current, movement_record, action, coordinate, old_mode_logp, move_type_logp):
        if action != 8 or not movement_record['eligible'] or movement_record['movement'] is None:
            return dict(coordinate=coordinate, routed=False, score=0.)
        x = features(current, movement_record['probabilities'], coordinate, old_mode_logp,
                     move_type_logp, movement_record['history_turns'])
        score = float(self.net(torch.from_numpy(x)))
        output = route(movement_record, action, coordinate, score)
        return dict(coordinate=output, routed=output != coordinate, score=score)
