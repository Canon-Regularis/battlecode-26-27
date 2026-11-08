"""Matched direct sequence and explicit-duration policies; no waypoint proxy."""
import copy
import torch
from torch import nn
import torch.nn.functional as F
from .filter import NeuralSemiMarkov, StateExecutionCondition

SPATIAL = (1, 2, 3, 5, 6, 8, 12, 13, 14)


class SegmentPolicy(nn.Module):
    def __init__(self, teacher, hierarchy, states=4, max_age=16):
        super().__init__()
        self.hierarchy = bool(hierarchy)
        self.states = states if hierarchy else 1
        self.max_age = max_age
        self.execution = copy.deepcopy(teacher).requires_grad_(True)
        self.execution.priority.requires_grad_(False)
        # Identical causal observation interface and common initialization.
        self.observation = nn.Sequential(nn.Linear(253, 16), nn.Tanh())
        self.observation_history = nn.GRU(45, 32, batch_first=True)
        self.history_projection = nn.Linear(32, 128)
        self.entity = nn.Sequential(nn.Linear(119, 32), nn.Tanh(), nn.Linear(32, 32))
        self.public = nn.Sequential(nn.Linear(8, 32), nn.Tanh(), nn.Linear(32, 32))
        self.global_entities = nn.Linear(32, 128)
        for layer in (self.history_projection, self.global_entities):
            nn.init.zeros_(layer.weight)
            nn.init.zeros_(layer.bias)
        if hierarchy:
            self.filter = NeuralSemiMarkov(128, states, max_age)
            self.condition = StateExecutionCondition(128, states, 32)
            # Tiny random symmetry breaking; no large arbitrary action offset.
            with torch.no_grad(): self.condition.condition.weight.mul_(.001)
            nn.init.zeros_(self.condition.condition.bias)
        else:
            # 21 command fields: family one-hot, relative xy, two special
            # coordinate buckets, signed-asinh priority, coordinate-known.
            self.memory = nn.GRUCell(128 + 21, 28)
            self.memory_projection = nn.Linear(28, 128)
            nn.init.zeros_(self.memory_projection.bias)

    def empty(self, n):
        if self.hierarchy:
            return dict(posterior=torch.full((n, self.states, self.max_age),
                -float(torch.log(torch.tensor(self.states * self.max_age))), dtype=torch.float64))
        return dict(hidden=torch.zeros(n, 28))

    def begin(self, x, history, observations, history_gaps, transition_gap,
              position, position_known, entities, entity_mask,
              public_tokens, public_mask, state):
        # No labels, future endpoints, IDs or retrospective segment assignments.
        _, base = self.execution(x, history)
        encoded = self.observation(observations) * history_gaps[:, :, 1:2]
        _, h = self.observation_history(torch.cat((history[:, -16:], encoded, history_gaps), -1))
        tokens = torch.cat((self.entity(entities), self.public(public_tokens)), 1)
        mask = torch.cat((entity_mask, public_mask), 1)
        pooled = (tokens * mask[:, :, None]).sum(1) / mask.sum(1).clamp_min(1)[:, None]
        context = base + self.history_projection(h[-1]) + self.global_entities(pooled)
        roots = torch.expm1(transition_gap[:, 0].double() * 8).round().long()
        if bool((roots < 1).any()):
            raise ValueError('Positive actual own-root gaps required')
        reset = (transition_gap[:, 2] > .5) | (roots != 1)
        if self.hierarchy:
            prior = self.filter.predict(context, state['posterior'], roots, reset)
            # Normalize probability arithmetic in float64, preserving gradients.
            prior['logp'] = prior['logp'].double().flatten(1).log_softmax(-1).reshape_as(prior['logp'])
            logprior = torch.logsumexp(prior['logp'], -1)
            conditioned = self.condition(context)
            return dict(context=conditioned, logprior=logprior, filter_prior=prior,
                        reset=reset, root_gap=roots, base=context)
        hidden = torch.where(reset[:, None], torch.zeros_like(state['hidden']), state['hidden'])
        conditioned = context + self.memory_projection(hidden)
        return dict(context=conditioned[:, None], logprior=torch.zeros(len(x), 1, dtype=torch.float64),
                    hidden=hidden, reset=reset, root_gap=roots, base=context)

    def types(self, step):
        return self.execution.action(step['context']).double().log_softmax(-1)

    def spatial_log_probs(self, step, grid, valid, rules, family):
        n, k, _ = step['context'].shape
        repeat = lambda t: t.repeat_interleave(k, 0)
        logits = self.execution.parameter_logits(step['context'].reshape(n*k, 128),
            repeat(grid), repeat(valid), repeat(family), repeat(rules))
        return logits.double().log_softmax(-1).reshape(n, k, 291)

    def observed(self, step, grid, valid, rules, y, py, priority_parameter_nll, priority_value):
        n = len(y)
        typ = self.types(step)
        component = typ[torch.arange(n), :, y].clone()
        spatial = torch.isin(y, torch.tensor(SPATIAL))
        if spatial.any():
            sub = dict(context=step['context'][spatial])
            lp = self.spatial_log_probs(sub, grid[spatial], valid[spatial], rules[spatial], y[spatial])
            component[spatial] += lp[torch.arange(int(spatial.sum())), :, py[spatial]]
        component[y == 9] -= priority_parameter_nll[y == 9, None]
        if self.hierarchy:
            loss, posterior = self.filter.observe(step['filter_prior'], component)
            return loss, dict(posterior=posterior)
        loss = -component[:, 0]
        # Current command enters recurrent state only AFTER prediction.
        coordinate = (py >= 0) & torch.isin(y, torch.tensor(SPATIAL))
        tile = coordinate & (py < 289)
        xy = torch.stack(((py.clamp(0, 288) % 17 - 8)/8,
                          (py.clamp(0, 288)//17 - 8)/8), -1) * tile[:, None]
        command = torch.cat((F.one_hot(y, 15).float(), xy,
            ((py == 289) & coordinate)[:, None], ((py == 290) & coordinate)[:, None],
            (torch.asinh(priority_value.double()/100) * (y == 9))[:, None], coordinate[:, None]), -1).float()
        hidden = self.memory(torch.cat((step['base'], command), -1), step['hidden'])
        return loss, dict(hidden=hidden)

    def decode(self, step, grid, valid, rules, priority_mode, priority_mode_logp):
        typ = self.types(step)
        n = len(typ)
        marginal = torch.logsumexp(step['logprior'][:, :, None] + typ, 1)
        coordinates = torch.full((n, 15), -1, dtype=torch.long)
        family_mode = marginal.clone()
        parameter_lp = {}
        component_modes = torch.full((n, self.states), -1, dtype=torch.long)
        for family in SPATIAL:
            lp = self.spatial_log_probs(step, grid, valid, rules, torch.full((n,), family, dtype=torch.long))
            joint = torch.logsumexp(step['logprior'][:, :, None] + typ[:, :, family, None] + lp, 1)
            conditional = joint - marginal[:, family, None]
            parameter_lp[family] = conditional
            family_mode[:, family], coordinates[:, family] = joint.max(-1)
            if family == 8:
                component_modes = lp.argmax(-1)
        family_mode[:, 9] += priority_mode_logp
        prediction = family_mode.argmax(-1)
        return dict(prediction=prediction, coordinate=coordinates[torch.arange(n), prediction],
                    family_coordinates=coordinates, priority=priority_mode,
                    type_logp=marginal, parameter_logp=parameter_lp,
                    component_move_modes=component_modes, family_mode_logp=family_mode)
