"""Change movement emissions using causal entities, without assigning objectives."""
import math
import torch
from torch import nn
from ..segment_policy.history_model import HistorySegmentPolicy, encode_command
from ..segment_policy.model import SPATIAL


class EntityMovementPolicy(HistorySegmentPolicy):
    def __init__(self, teacher, candidate_attention):
        super().__init__(teacher)
        if not all(teacher.config.get(k) for k in ('spatial', 'history', 'constrain')):
            raise ValueError('Requires the retained spatial, historical, constrained executor')
        self.candidate_attention = bool(candidate_attention)
        self.entity_query = nn.Linear(128, 32)
        self.destination_query = nn.Linear(32, 32, bias=False)
        self.entity_key = nn.Linear(32, 32, bias=False)
        self.entity_value = nn.Linear(32, 32, bias=False)
        self.movement_readout = nn.Sequential(nn.Linear(96, 32), nn.Tanh(), nn.Linear(32, 1))
        # Both arms initially reproduce the same unmodified movement distribution.
        nn.init.zeros_(self.movement_readout[-1].weight)
        nn.init.zeros_(self.movement_readout[-1].bias)

    def begin(self, x, history, observations, history_gaps, transition_gap,
              position, position_known, entities, entity_mask, public_tokens, public_mask, state):
        step = super().begin(x, history, observations, history_gaps, transition_gap,
            position, position_known, entities, entity_mask, public_tokens, public_mask, state)
        # No identity numbers, future targets or current command enter this path.
        step['entities'] = self.entity(entities)
        step['entity_mask'] = entity_mask
        return step

    def movement_residual(self, step, grid, valid):
        context = step['context']
        candidate = self.execution.candidate(grid)
        query = self.entity_query(context)[:, :, None, :]
        if self.candidate_attention:
            destination = candidate
        else:
            # Same active parameters and input set, but one query for all tiles.
            destination = (candidate * valid[:, :, None]).sum(1, keepdim=True)
            destination = destination / valid.sum(1).clamp_min(1)[:, None, None]
        query = query + self.destination_query(destination)[:, None]
        mask = step['entity_mask']
        # A zero null token makes empty entity sets well-defined. Masked entities
        # contribute neither attention mass nor values, including all-empty rows.
        tokens = step['entities'].masked_fill(~mask[:, :, None], 0)
        tokens = torch.cat((tokens, tokens.new_zeros(len(tokens), 1, 32)), 1)
        mask = torch.cat((mask, torch.ones(len(mask), 1, dtype=torch.bool, device=mask.device)), 1)
        score = torch.einsum('nkcd,ned->nkce', query, self.entity_key(tokens)) / math.sqrt(32)
        attention = score.masked_fill(~mask[:, None, None], -torch.inf).softmax(-1)
        value = torch.einsum('nkce,ned->nkcd', attention, self.entity_value(tokens))
        n, k = context.shape[:2]
        value = value.expand(n, k, 289, 32)
        features = torch.cat((candidate[:, None].expand(n, k, 289, 32), value,
            self.entity_query(context)[:, :, None].expand(n, k, 289, 32)), -1)
        return self.movement_readout(features).squeeze(-1)

    def spatial_log_probs(self, step, grid, valid, rules, family):
        result = super().spatial_log_probs(step, grid, valid, rules, family)
        move = family == 8
        if not move.any():
            return result
        sub = {key: step[key][move] for key in ('context', 'entities', 'entity_mask')}
        context = sub['context']
        grid, valid = grid[move], valid[move]
        # Preserve JointModel's exact support construction, adding the residual
        # BEFORE its restricted/full mixture, not after probability normalization.
        query = self.execution.query(context) + self.execution.family(family[move])[:, None]
        logits = (self.execution.candidate(grid)[:, None] * query[:, :, None]).sum(-1) / 5.657
        bias = self.execution.offset_bias(family[move])
        logits = logits + bias[:, None, :289] + self.movement_residual(sub, grid, valid)
        logits = logits.masked_fill(~valid[:, None], -1e4)
        logits = torch.cat((logits, self.execution.special(context) + bias[:, None, 289:]), -1)
        allowed = valid & (grid[:, :, 5] > 0)
        complete = torch.cat((allowed, torch.zeros(len(allowed), 2, dtype=torch.bool, device=allowed.device)), 1)
        complete[~allowed.any(-1)] = True
        full = logits.log_softmax(-1)
        restricted = logits.masked_fill(~complete[:, None], -1e4).log_softmax(-1)
        mixture = torch.logaddexp(restricted + torch.log(logits.new_tensor(.9999)),
                                 full + torch.log(logits.new_tensor(.0001)))
        result = result.clone()
        result[move] = mixture.double().log_softmax(-1)
        return result

    def observed(self, step, grid, valid, rules, y, py, priority_parameter_nll, priority_value):
        # Same likelihood as HistorySegmentPolicy, retaining entity inputs when
        # selecting spatial rows. Gold family is used only to score the outcome.
        component = self.types(step)[torch.arange(len(y)), :, y].clone()
        spatial = torch.isin(y, torch.tensor(SPATIAL, device=y.device))
        if spatial.any():
            sub = {key: step[key][spatial] for key in ('context', 'entities', 'entity_mask')}
            lp = self.spatial_log_probs(sub, grid[spatial], valid[spatial], rules[spatial], y[spatial])
            component[spatial] += lp[torch.arange(int(spatial.sum())), :, py[spatial]]
        component[y == 9] -= priority_parameter_nll[y == 9, None]
        loss, posterior = self.filter.observe(step['filter_prior'], component)
        return loss, dict(posterior=posterior, command=encode_command(y, py, priority_value))
