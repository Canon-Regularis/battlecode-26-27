"""Expose every family's existing MAP command before any recorded answer."""
import torch
from ..learned_policy.model import SPATIAL


@torch.no_grad()
def family_forecast(model,step,grid,valid,rules,priority_mode,priority_mode_logp):
    """Same GoalPolicy mixture arithmetic; no new scorer or selection rule.

    Shop remains the observed marginalized bucket, with purchase arguments
    unavailable. Coordinates retain the benchmark's entity-identity ambiguity.
    All rules/masks are supplied by the existing personal-PRE pipeline.
    """
    typ=model.types(step)
    n=len(typ)
    if typ.shape[2]!=15 or step['logprior'].shape!=typ.shape[:2]:
        raise ValueError('Existing goal/family interface changed')
    if priority_mode.shape!=(n,) or priority_mode.dtype!=torch.int64 or priority_mode_logp.shape!=(n,):
        raise ValueError('Predicted priority-mode interface changed')
    type_logp=torch.logsumexp(step['logprior'][:,:,None]+typ,1)
    mode_joint_logp=type_logp.clone()
    coordinates=torch.full((n,15),-1,dtype=torch.int64,device=typ.device)
    for family in SPATIAL:
        codes=torch.full((n,),family,dtype=torch.int64,device=typ.device)
        conditional=model.spatial_log_probs(step,grid,valid,rules,codes)
        joint=torch.logsumexp(step['logprior'][:,:,None]+typ[:,:,family,None]+conditional,1)
        mode_joint_logp[:,family],coordinates[:,family]=joint.max(-1)
    mode_joint_logp[:,9]+=priority_mode_logp
    prediction=mode_joint_logp.argmax(-1)
    return dict(type_logp=type_logp,mode_joint_logp=mode_joint_logp,
        family_coordinate=coordinates,priority=priority_mode,
        prediction=prediction,proposed_coordinate=coordinates[torch.arange(n),prediction])
