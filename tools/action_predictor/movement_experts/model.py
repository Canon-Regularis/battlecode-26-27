"""Candidate-conditioned personal entity attention; unlabeled latent experts."""
import numpy as np
import torch
from torch import nn
import torch.nn.functional as F

class Head(nn.Module):
    def __init__(self,width,counts):
        super().__init__();self.query=nn.Linear(72,16);self.tile_query=nn.Linear(20,16);self.score=nn.Sequential(nn.Linear(112,width),nn.Tanh(),nn.Dropout(.1),nn.Linear(width,1));self.special=nn.Linear(72,2);self.distance=nn.Parameter(torch.zeros(()));self.bias=nn.Parameter(torch.from_numpy(np.log((counts+1)/(counts.sum(1,keepdims=True)+291)).astype(np.float32)))
        nn.init.zeros_(self.score[-1].weight);nn.init.zeros_(self.score[-1].bias);nn.init.zeros_(self.special.weight);nn.init.zeros_(self.special.bias)
    def forward(self,context,grid,entities,entity_mask,encoded,family):
        keys,values=encoded.split(16,-1);q=self.query(context)[:,None]+self.tile_query(grid);attention=torch.bmm(q,keys.transpose(1,2))/4
        # Entity positions are personally known relative offsets. Unknown position
        # flags remain explicit; distance is never inferred from hidden state.
        delta=entities[:,None,:,23:25]*32-grid[:,:,None,:2]*8;distance=delta.abs().amax(-1)/8;known=entities[:,:,22]>0
        attention=attention-F.softplus(self.distance)*distance*known[:,None];weights=attention.masked_fill(~entity_mask[:,None],-1e4).softmax(-1);pool=torch.bmm(weights,values)
        geometry=torch.stack(((weights*delta[:,:,:,0]*known[:,None]).sum(-1)/32,(weights*delta[:,:,:,1]*known[:,None]).sum(-1)/32,(weights*distance*known[:,None]).sum(-1),(weights*known[:,None]).sum(-1)),-1)
        joined=torch.cat((context[:,None].expand(-1,289,-1),grid,pool,geometry),-1);tile=self.score(joined).squeeze(-1);return torch.cat((tile,self.special(context)),-1)+self.bias[family]

class MovementExpert(nn.Module):
    def __init__(self,mixture,counts):
        super().__init__();self.mixture=bool(mixture);self.current=nn.Sequential(nn.Linear(613,64),nn.Tanh(),nn.Dropout(.1),nn.Linear(64,64),nn.Tanh());self.entity=nn.Sequential(nn.Linear(119,32),nn.Tanh(),nn.Linear(32,32));self.family=nn.Embedding(2,8);self.heads=nn.ModuleList([Head(32 if mixture else 64,counts) for _ in range(2 if mixture else 1)]);self.gate=nn.Linear(72,2) if mixture else None
        if self.gate is not None:nn.init.zeros_(self.gate.weight);nn.init.zeros_(self.gate.bias)
    def forward(self,x,grid,valid,entities,entity_mask,family):
        f=(family==3).long();context=torch.cat((self.current(x),self.family(f)),-1);encoded=self.entity(entities);allowed=valid&torch.where((family==8)[:,None],grid[:,:,5]>0,torch.ones_like(valid));complete=torch.cat((allowed,torch.zeros((len(x),2),dtype=torch.bool)),1);complete[~allowed.any(-1)]=True;parts=[]
        for head in self.heads:
            logits=head(context,grid,entities,entity_mask,encoded,f);logits[:,:289]=logits[:,:289].masked_fill(~valid,-1e4);full=logits.log_softmax(-1);restricted=logits.masked_fill(~complete,-1e4).log_softmax(-1);parts.append(torch.logaddexp(restricted+np.log(.9999),full+np.log(.0001)))
        lp=torch.stack(parts,1);gate=self.gate(context).log_softmax(-1) if self.mixture else torch.zeros((len(x),1));return torch.logsumexp(lp+gate[:,:,None],1),gate.exp()
