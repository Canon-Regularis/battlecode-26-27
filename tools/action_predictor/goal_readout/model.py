"""Existing GoalPolicy readout with one controlled geometry-input contrast."""
import copy
import torch
from torch import nn
from ..learned_policy.model import GoalPolicy, SPATIAL


class FrozenGoalReadout(nn.Module):
    def __init__(self, upstream, geometry_mean, dynamic):
        super().__init__()
        self.execution = copy.deepcopy(upstream.execution).requires_grad_(False)
        for name in ('action', 'query', 'candidate', 'family', 'offset_bias', 'special'):
            getattr(self.execution, name).requires_grad_(True)
        self.goal_condition = copy.deepcopy(upstream.goal_condition).requires_grad_(True)
        self.register_buffer('geometry_mean', torch.as_tensor(geometry_mean).clone().float())
        self.dynamic = bool(dynamic)

    def begin(self, latent, features, logprior, position_known):
        if not self.dynamic:
            features = features.clone()
            features[:, :, :2] = torch.where(position_known[:, None, None],
                self.geometry_mean[None], torch.zeros_like(features[:, :, :2]))
        return dict(context=latent + self.goal_condition(features), logprior=logprior)

    types = GoalPolicy.types
    spatial_log_probs = GoalPolicy.spatial_log_probs
    decode = GoalPolicy.decode

    def command_loss(self, step, grid, valid, rules, y, py, priority_parameter_nll):
        n = len(y)
        typ = self.types(step)
        component = typ[torch.arange(n), :, y].clone()
        spatial = torch.zeros(n, dtype=torch.bool)
        for family in SPATIAL:
            spatial |= y == family
        if spatial.any():
            sub = {key: value[spatial] for key, value in step.items()}
            lp = self.spatial_log_probs(sub, grid[spatial], valid[spatial], rules[spatial], y[spatial])
            component[spatial] += lp[torch.arange(int(spatial.sum())), :, py[spatial]]
        component[y == 9] -= priority_parameter_nll[y == 9, None]
        return -torch.logsumexp(step['logprior'] + component, 1)
