"""Loss-specific parameter gradients; no model/forward/inference changes."""
import torch


def backward(model, primary, auxiliary, weight=.05):
    """Keep only command gradients on retention parameters across the whole graph.

    Do not detach the retain activation: that would also remove auxiliary
    learning from upstream context and historical state. Other parameters get
    the original combined loss derivative. The caller retains original global
    clipping and AdamW (including weight decay).
    """
    parameters = tuple(model.retention.parameters())
    command = torch.autograd.grad(primary, parameters, retain_graph=True, allow_unused=True)
    (primary + weight * auxiliary).backward()
    for parameter, gradient in zip(parameters, command):
        parameter.grad = None if gradient is None else gradient.detach()
