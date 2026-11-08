"""H01 amendment: causal command history reaches transitions and hazards."""
import torch
import torch.nn.functional as F
from .model import SegmentPolicy, SPATIAL
from .history_filter import CommandHistorySemiMarkov


def encode_command(y, py, priority_value):
    # Byte-equivalent arithmetic to H00's direct command encoding.
    coordinate = (py >= 0) & torch.isin(y, torch.tensor(SPATIAL))
    tile = coordinate & (py < 289)
    xy = torch.stack(((py.clamp(0, 288) % 17-8)/8,
                      (py.clamp(0, 288)//17-8)/8), -1)*tile[:, None]
    return torch.cat((F.one_hot(y, 15).float(), xy,
        ((py == 289) & coordinate)[:, None], ((py == 290) & coordinate)[:, None],
        (torch.asinh(priority_value.double()/100)*(y == 9))[:, None], coordinate[:, None]), -1).float()


class HistorySegmentPolicy(SegmentPolicy):
    def __init__(self, teacher, hierarchy=True, states=4, max_age=16):
        if not hierarchy: raise ValueError('Preserve H00; amended class is H01 only')
        super().__init__(teacher, True, states, max_age)
        self.filter = CommandHistorySemiMarkov(self.filter)

    def empty(self, n):
        state = super().empty(n)
        state['command'] = torch.zeros(n, 21)
        return state

    def begin(self, x, history, observations, history_gaps, transition_gap,
              position, position_known, entities, entity_mask, public_tokens, public_mask, state):
        # Same shared causal context arithmetic as preserved H00/original H01.
        _, base = self.execution(x, history)
        encoded = self.observation(observations)*history_gaps[:, :, 1:2]
        _, h = self.observation_history(torch.cat((history[:, -16:], encoded, history_gaps), -1))
        tokens = torch.cat((self.entity(entities), self.public(public_tokens)), 1)
        mask = torch.cat((entity_mask, public_mask), 1)
        pooled = (tokens*mask[:, :, None]).sum(1)/mask.sum(1).clamp_min(1)[:, None]
        context = base+self.history_projection(h[-1])+self.global_entities(pooled)
        roots = torch.expm1(transition_gap[:, 0].double()*8).round().long()
        if bool((roots < 1).any()): raise ValueError('Positive actual own-root gaps required')
        reset = (transition_gap[:, 2] > .5) | (roots != 1)
        prior = self.filter.predict(context, state['posterior'], roots, reset, state['command'])
        prior['logp'] = prior['logp'].double().flatten(1).log_softmax(-1).reshape_as(prior['logp'])
        return dict(context=self.condition(context), logprior=torch.logsumexp(prior['logp'], -1),
                    filter_prior=prior, reset=reset, root_gap=roots, base=context)

    def observed(self, step, grid, valid, rules, y, py, priority_parameter_nll, priority_value):
        loss, post = super().observed(step, grid, valid, rules, y, py, priority_parameter_nll, priority_value)
        # Only after prediction/actual occurrence. No command enters its own prior.
        post['command'] = encode_command(y, py, priority_value)
        return loss, post
