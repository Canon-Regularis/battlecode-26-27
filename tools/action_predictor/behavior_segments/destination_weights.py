"""Existing goal-query/readout weights trained on frozen causal representations."""
import copy
import torch
from torch import nn
from torch.nn import functional as F

PREFIXES=('query.','goal.')


class DestinationHead(nn.Module):
    def __init__(self,backbone):
        super().__init__();self.query=copy.deepcopy(backbone.query);self.goal=copy.deepcopy(backbone.goal)
        self.requires_grad_(True)
        # A common scalar added to every tile is unidentifiable under softmax.
        self.goal[2].bias.requires_grad_(False)

    def forward(self,spatial,whole,shared,valid):
        query=torch.tanh(self.query(shared))
        weight=self.goal[0].weight[:,:,0,0]
        offset=F.linear(query,weight[:,16:32])+F.linear(whole,weight[:,32:],self.goal[0].bias)
        activation=torch.tanh(F.linear(spatial,weight[:,:16])+offset[:,None,:])
        logits=F.linear(activation,self.goal[2].weight[:,:,0,0],self.goal[2].bias).squeeze(-1)
        return logits.masked_fill(~valid,-1e9)


def install(backbone,head):
    backbone.query.load_state_dict(head.query.state_dict());backbone.goal.load_state_dict(head.goal.state_dict())


def pack(rows,shared,indices):
    n=len(indices);length=max(len(rows[i]['spatial']) for i in indices)
    spatial=torch.zeros(n,length,16);valid=torch.zeros(n,length,dtype=torch.bool)
    whole=[];target=[]
    for j,i in enumerate(indices):
        r=rows[i];size=len(r['spatial']);spatial[j,:size]=r['spatial'];valid[j,:size]=True
        whole.append(r['whole']);target.append(r['target'])
    return dict(spatial=spatial,whole=torch.stack(whole),shared=shared[indices],valid=valid),torch.tensor(target)
