"""Explicit-duration filter with already-occurred command-conditioned factors."""
import torch
from torch import nn
import torch.nn.functional as F
from .filter import NeuralSemiMarkov


class CommandHistorySemiMarkov(NeuralSemiMarkov):
    def __init__(self, original, command_size=21):
        context_size = original.initial.in_features
        # Preserve the original initialization and global RNG exactly. Additional
        # columns start zero; transition/hazard likelihood gradients can train them.
        with torch.random.fork_rng():
            super().__init__(context_size, original.states, original.max_age)
            self.transition = nn.Linear(context_size+command_size, original.transition.out_features)
            self.termination = nn.Linear(context_size+command_size, original.termination.out_features)
        self.command_size = command_size
        self.context_size = context_size
        self.initial.load_state_dict(original.initial.state_dict())
        with torch.no_grad():
            self.age_logits.copy_(original.age_logits)
            for name in ('transition', 'termination'):
                old = getattr(original, name); new = getattr(self, name)
                new.weight.zero_()
                new.weight[:, :context_size].copy_(old.weight)
                new.bias.copy_(old.bias)

    def factors(self, context, previous_command):
        if previous_command.shape != (len(context), self.command_size):
            raise ValueError('Explicit previous-command buffer required')
        inputs = torch.cat((context, previous_command), -1)
        n = len(context)
        logits = self.transition(inputs).double().reshape(n, self.states, self.states-1).log_softmax(-1)
        transition = torch.full((n, self.states, self.states), -torch.inf, dtype=logits.dtype, device=context.device)
        transition = transition.scatter(2, self.destinations[None].expand(n, -1, -1), logits)
        hazard = self.termination(inputs).double()[:, :, None]+self.age_logits.double()[None]
        end = torch.cat((F.logsigmoid(hazard), torch.zeros_like(hazard[:, :, -1:])), -1)
        return transition, end, F.logsigmoid(-hazard)

    def predict(self, context, previous_logp, root_gap, prefix_unavailable, previous_command):
        n = len(context)
        if previous_logp.shape != (n, self.states, self.max_age): raise ValueError('State/age shape changed')
        if root_gap.shape != (n,) or root_gap.dtype != torch.int64 or bool((root_gap < 1).any()):
            raise ValueError('Positive own-root gaps required')
        if prefix_unavailable.shape != (n,) or prefix_unavailable.dtype != torch.bool:
            raise ValueError('Explicit unavailable prefix required')
        reset = prefix_unavailable | (root_gap != 1)
        previous_command = torch.where(reset[:, None], torch.zeros_like(previous_command), previous_command)
        transition, end, stay = self.factors(context, previous_command)
        ending = torch.logsumexp(previous_logp+end, -1)
        advanced = torch.cat((torch.logsumexp(ending[:, :, None]+transition, 1)[:, :, None],
                              previous_logp[:, :, :-1]+stay), -1)
        prior = torch.where(reset[:, None, None], self.initial_logp(context), advanced)
        # Hazards apply to the PREVIOUS posterior, not the resulting current prior.
        previous_mass = torch.logsumexp(previous_logp, -1)
        nan = torch.full_like(ending, torch.nan)
        return dict(logp=prior, unknown_prefix=reset, transition=transition, termination_logp=end,
            previous_state_probability=torch.where(reset[:, None], nan, previous_mass.exp()).detach(),
            previous_state_hazard=torch.where(reset[:, None], nan, (ending-previous_mass).exp()).detach(),
            state_exit_mass=torch.where(reset[:, None], nan, ending.exp()).detach(),
            transition_exit_probability=torch.where(reset, torch.full_like(ending[:, 0], torch.nan),
                torch.logsumexp(ending, -1).exp()).detach())
