"""Explicit linear-projection contrasts; actual availability/state stay intact."""
import torch
import torch.nn.functional as F

CONTRASTS=('geometry_mean','uncertainty_mean','availability_mean','all_means','bias_off','projection_off')


def features(step,inputs):
    known=inputs['position_known']
    relative=(step['world']-inputs['position'][:,None])*known[:,None,None]
    usable=step['known']&known[:,None]
    return torch.cat((relative,step['logscale'],usable[:,:,None].float()),-1)


def contrast(model,step,inputs,reference,name):
    """Change projection contribution only, never flags/masks/world/prior in-place.

    Mean contrasts replace input-channel variability with TRAIN-derived means.
    Geometry remains exactly zero without current position. Uncertainty means
    are stratified by actual current-position availability. Availability mean
    is a projection coefficient, never asserted as an actual API availability.
    The constant learned bias remains in all mean contrasts.
    """
    if name=='identity':return dict(step)
    f=features(step,inputs);known=inputs['position_known']
    g=torch.as_tensor(reference['geometry_known'],dtype=f.dtype)[None].expand(len(f),-1,-1)
    g=torch.where(known[:,None,None],g,torch.zeros_like(g))
    u=torch.as_tensor(reference['uncertainty_by_position_known'],dtype=f.dtype)[known.long()]
    a=torch.as_tensor(reference['availability'],dtype=f.dtype)[None,:,None].expand(len(f),-1,-1)
    delta=torch.zeros_like(f)
    if name in ('geometry_mean','all_means'):delta[:,:,:2]=f[:,:,:2]-g
    if name in ('uncertainty_mean','all_means'):delta[:,:,2:4]=f[:,:,2:4]-u
    if name in ('availability_mean','all_means'):delta[:,:,4:]=f[:,:,4:]-a
    if name=='projection_off':delta=f
    if name=='bias_off':effect=model.goal_condition.bias[None,None].expand_as(step['context'])
    elif name in CONTRASTS:
        effect=F.linear(delta,model.goal_condition.weight)
        if name=='projection_off':effect=effect+model.goal_condition.bias[None,None]
    else:raise ValueError(name)
    return dict(step,context=step['context']-effect)
