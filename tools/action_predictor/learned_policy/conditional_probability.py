"""Stable conditional mixture arithmetic; not wired into retained predictors."""
import torch


def conditional_log_probs(log_prior, family_log_prob, head_log_prob):
    """Return P(parameter | family) and log P(family) for a latent mixture.

    Shapes are [batch, components], [batch, components], and
    [batch, components, parameters]. Inputs are component log probabilities;
    each row must have positive total family mass. No probabilities are
    detached, clipped, or silently re-normalized within component heads.

    Normalize the component weights BEFORE adding parameter probabilities.
    This avoids subtracting two large negative marginalized log masses for
    a rare family. It is algebraically equivalent in exact arithmetic. The
    returned family mass preserves the supplied prior/type representation.
    """
    joint_weight = log_prior + family_log_prob
    family_mass = torch.logsumexp(joint_weight, dim=-1)
    conditional_weight = joint_weight.log_softmax(dim=-1)
    conditional = torch.logsumexp(
        conditional_weight.unsqueeze(-1) + head_log_prob, dim=-2)
    return conditional, family_mass
