"""Frozen causal code predictor with a small soft-code movement correction."""
import torch
from torch import nn


class MovementCorrection(nn.Module):
    def __init__(self, mean_probabilities, conditioned=True):
        super().__init__()
        self.conditioned = conditioned
        self.register_buffer('mean_probabilities', mean_probabilities.detach().clone())
        # Zero correction preserves the original policy exactly before fitting.
        self.weight = nn.Parameter(torch.zeros(8, 9, 48))
        self.bias = nn.Parameter(torch.zeros(8, 9))

    def forward(self, states, probabilities, baseline):
        gate = probabilities if self.conditioned else self.mean_probabilities.expand_as(probabilities)
        experts = torch.einsum('...h,cmh->...cm', states, self.weight) + self.bias
        return baseline + (gate[..., :, None] * experts).sum(-2)


class CodeMovementPolicy(nn.Module):
    def __init__(self, backbone, correction):
        super().__init__()
        self.backbone = backbone.eval().requires_grad_(False)
        self.correction = correction

    def forward(self, *args, **kwargs):
        states = []
        handle = self.backbone.code.register_forward_pre_hook(lambda module, values: states.append(values[0]))
        try:
            with torch.no_grad():
                result = self.backbone(*args, **kwargs)
        finally:
            handle.remove()
        result['move'] = self.correction(states[0], result['code'].softmax(-1), result['move'])
        return result


def supported_log_probabilities(logits, support):
    return logits.masked_fill(~support, -1e9).log_softmax(-1)
