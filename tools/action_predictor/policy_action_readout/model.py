"""Learn action beliefs while retaining frozen conditional command distributions.

This is an interface for a controlled readout experiment, not a trained policy.
The supplied causal feature schema and experimental controls must be separately
frozen before fitting. Nothing here chooses a feature or learns a latent intent.
"""
import torch
from torch import nn


class ActionBeliefCorrection(nn.Module):
    def __init__(self,features,classes=15):
        super().__init__()
        if not isinstance(features,int) or features<1 or classes!=15:
            raise ValueError('Positive fixed feature count and original15families required')
        self.correction=nn.Linear(features,classes,bias=False,dtype=torch.float64)
        nn.init.zeros_(self.correction.weight)

    def logits(self,baseline_family_logp,features):
        if baseline_family_logp.ndim!=2 or baseline_family_logp.shape[1]!=15:
            raise ValueError('Original family distribution required')
        if features.shape!=(len(baseline_family_logp),self.correction.in_features):
            raise ValueError('Causal feature interface changed')
        if not bool(torch.isfinite(baseline_family_logp).all()) or not bool(torch.isfinite(features).all()):
            raise ValueError('Nonfinite causal input')
        # Normalizing in float64 retains a complete family distribution. Baseline
        # rounding may make zero-initialization differ from archived logp by a
        # tiny common offset; no zero-weight branch may remove its gradients.
        return baseline_family_logp.double()+self.correction(features.double())

    def forward(self,baseline_family_logp,features):
        return self.logits(baseline_family_logp,features).log_softmax(-1)


def command_mode_scores(family_logp,conditional_mode_logp):
    if family_logp.shape!=conditional_mode_logp.shape or family_logp.ndim!=2 or family_logp.shape[1]!=15:
        raise ValueError('Every-family conditional modes required')
    if not bool(torch.isfinite(conditional_mode_logp).all()):raise ValueError('Nonfinite conditional mode')
    # Mode probabilities do not sum to one and must never be softmaxed.
    return family_logp.double()+conditional_mode_logp.double()


def decode(family_logp,conditional_mode_logp,family_coordinates,priority_mode):
    n=len(family_logp)
    if family_coordinates.dtype!=torch.int64 or family_coordinates.shape!=(n,15):
        raise ValueError('Causal all-family coordinate interface changed')
    if priority_mode.dtype!=torch.int64 or priority_mode.shape!=(n,):
        raise ValueError('Causal predicted priority mode required')
    score=command_mode_scores(family_logp,conditional_mode_logp);choice=score.argmax(-1)
    rows=torch.arange(n,device=choice.device)
    return dict(prediction=choice,proposed_coordinate=family_coordinates[rows,choice],
        priority=priority_mode,mode_logp=score[rows,choice])


def observed_nll(family_logp,recorded_family,recorded_conditional_logp):
    """Supervision only: the current recorded family is never a decoder input."""
    n=len(family_logp)
    if recorded_family.dtype!=torch.int64 or recorded_family.shape!=(n,):
        raise ValueError('Recorded family supervision schema changed')
    if recorded_conditional_logp.shape!=(n,) or not bool(torch.isfinite(recorded_conditional_logp).all()):
        raise ValueError('Recorded-family conditional likelihood required')
    rows=torch.arange(n,device=recorded_family.device)
    return -(family_logp[rows,recorded_family]+recorded_conditional_logp.double())
