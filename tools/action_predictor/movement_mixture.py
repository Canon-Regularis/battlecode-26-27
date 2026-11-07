"""Causal movement mixture; future direction is never a forward argument."""
import copy
import numpy as np
import torch
from torch import nn
import torch.nn.functional as F
from .targets import OFFSETS

def previous_direction(grid):
    marked=grid[:,:,18]>.5
    if not bool((marked.sum(-1)<=1).all()):raise ValueError('Multiple earlier-move offsets')
    available=marked.any(-1);index=marked.float().argmax(-1)
    offsets=torch.as_tensor(OFFSETS,device=grid.device)[index]
    offsets=torch.where(available[:,None],offsets,torch.zeros_like(offsets))
    matching=(torch.as_tensor(np.sign(OFFSETS),device=grid.device)[None]==offsets.sign()[:,None]).all(-1)
    matching=torch.cat((matching,torch.zeros((len(grid),2),dtype=torch.bool,device=grid.device)),1)
    return offsets,available,matching

def log_partition(logp,mask):
    return torch.logsumexp(logp.masked_fill(~mask,-torch.inf),-1)

class MovementMixture(nn.Module):
    def __init__(self,teacher,specialized):
        super().__init__();self.teacher=teacher.requires_grad_(False);self.specialized=bool(specialized)
        self.continuation=copy.deepcopy(teacher).requires_grad_(True)
        self.change=copy.deepcopy(teacher).requires_grad_(True)
        for expert in (self.continuation,self.change):
            expert.action.requires_grad_(False);expert.priority.requires_grad_(False)
        rng=torch.get_rng_state();self.gate=nn.Sequential(nn.Linear(131,64),nn.ReLU(),nn.Linear(64,1))
        nn.init.zeros_(self.gate[-1].weight);nn.init.zeros_(self.gate[-1].bias);torch.set_rng_state(rng)

    def train(self,mode=True):
        super().train(mode);self.teacher.eval();return self

    def forward(self,x,history,grid,valid,family,rules,teacher_context=None):
        contexts=self.encode(x,history,teacher_context)
        return self.parameter_log_probs(contexts,grid,valid,family,rules)

    def encode(self,x,history,teacher_context=None):
        if teacher_context is None:
            with torch.no_grad():_,teacher_context=self.teacher(x,history)
        _,first=self.continuation(x,history);_,second=self.change(x,history)
        return teacher_context,first,second

    def parameter_log_probs(self,contexts,grid,valid,family,rules):
        teacher_context,first,second=contexts
        with torch.no_grad():
            teacher=self.teacher.parameter_logits(teacher_context,grid,valid,family,rules).log_softmax(-1)
        offset,available,matching=previous_direction(grid)
        p=self.continuation.parameter_logits(first,grid,valid,family,rules).log_softmax(-1)
        q=self.change.parameter_logits(second,grid,valid,family,rules).log_softmax(-1)
        enabled=available&(family==8)
        prior=log_partition(teacher,matching)-log_partition(teacher,~matching)
        prior=torch.where(enabled,prior,torch.zeros_like(prior))
        gate=prior+self.gate(torch.cat((teacher_context,offset.float()/8,available.float()[:,None]),-1))[:,0]
        if self.specialized:
            # A partition of *all*291 outcomes, not a legality filter. Unknown
            # coordinates stay supported in the change component. Missing history
            # and blocked outcomes use the unrestricted mixture in both arms.
            a=p.masked_fill(~matching,-torch.inf)-log_partition(p,matching)[:,None]
            b=q.masked_fill(matching,-torch.inf)-log_partition(q,~matching)[:,None]
            p=torch.where(enabled[:,None],a,p);q=torch.where(enabled[:,None],b,q)
        combined=torch.logaddexp(F.logsigmoid(gate)[:,None]+p,F.logsigmoid(-gate)[:,None]+q)
        # Existing1e-4 full-support legality mixture is already inside expert
        # distributions; the directional partition preserves every integer code.
        return combined,gate,available
