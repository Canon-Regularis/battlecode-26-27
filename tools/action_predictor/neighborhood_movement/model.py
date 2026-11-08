"""Frozen base policy plus a small movement-tile residual."""
import torch
from torch import nn
import torch.nn.functional as F
from ..history_horizon.model import Policy as BasePolicy


def terrain_patch(grid,use_neighborhood):
    """Channel-major 3x3 patches: in-map, blocked-in-map, crop availability.

    Crop padding is unavailable, not a world boundary. Both arms receive the
    same crop mask. The control repeats its center terrain at available slots.
    """
    valid=grid[:,:,3]
    center=torch.stack((valid,grid[:,:,4]*valid,torch.ones_like(valid)),-1)
    image=center.transpose(1,2).reshape(-1,3,17,17)
    patch=F.unfold(image,kernel_size=3,padding=1).transpose(1,2)
    if use_neighborhood:return patch
    available=patch[:,:,18:27]
    return torch.cat((center[:,:,0:1]*available,center[:,:,1:2]*available,available),-1)


class Policy(BasePolicy):
    def __init__(self,base_state,use_neighborhood):
        super().__init__();self.load_state_dict(base_state,strict=True)
        for p in self.parameters():p.requires_grad_(False)
        self.use_neighborhood=bool(use_neighborhood)
        self.tile_projection=nn.Linear(47,32)
        self.context_projection=nn.Linear(128,32)
        self.residual_readout=nn.Linear(32,1)
        nn.init.zeros_(self.residual_readout.weight);nn.init.zeros_(self.residual_readout.bias)

    def residual(self,context,grid):
        tile=torch.cat((grid,terrain_patch(grid,self.use_neighborhood)),-1)
        return self.residual_readout(torch.tanh(self.tile_projection(tile)+
            self.context_projection(context)[:,None])).squeeze(-1)

    def spatial(self,step,grid,valid,rules,family):
        result=super().spatial(step,grid,valid,rules,family)
        move=family==8
        if not move.any():return result
        # Preserve the original batch shape, even in mixed-family likelihoods.
        # This avoids changing floating-point kernels at zero residual.
        context=step['context'];execution=self.execution
        query=execution.query(context)+execution.family(family)
        logits=(execution.candidate(grid)*query[:,None]).sum(-1)/5.657
        bias=execution.offset_bias(family)
        logits=logits+bias[:,:289]+self.residual(context,grid)
        logits=logits.masked_fill(~valid,-1e4)
        logits=torch.cat((logits,execution.special(context)+bias[:,289:]),-1)
        allowed=valid&(grid[:,:,5]>0)
        complete=torch.cat((allowed,torch.zeros(len(allowed),2,dtype=torch.bool,device=allowed.device)),1)
        complete[~allowed.any(-1)]=True
        full=logits.log_softmax(-1)
        restricted=logits.masked_fill(~complete,-1e4).log_softmax(-1)
        mixture=torch.logaddexp(restricted+torch.log(logits.new_tensor(.9999)),
            full+torch.log(logits.new_tensor(.0001))).double().log_softmax(-1)
        # Only movement outputs use this correction. Other-family formulas and
        # all base weights remain exactly the reviewed reference.
        return result.index_copy(0,torch.where(move)[0],mixture[move])

    def trainable_parameters(self):
        return [p for p in self.parameters() if p.requires_grad]

    def base_state(self):
        return {k:v for k,v in self.state_dict().items() if not k.startswith(
            ('tile_projection.','context_projection.','residual_readout.'))}
