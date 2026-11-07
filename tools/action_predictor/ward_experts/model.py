"""Separate small ward heads; matched richer-input controls, no encoder updates."""
import numpy as np
import torch
from torch import nn
from .features import GLOBAL,INDICES

class Placement(nn.Module):
    def __init__(self,counts):
        super().__init__();self.query=nn.Linear(GLOBAL,32);self.tile=nn.Linear(36,32);self.dropout=nn.Dropout(.1);self.score=nn.Linear(32,1);self.bias=nn.Parameter(torch.from_numpy(np.log((counts+1)/(counts.sum()+25)).astype(np.float32)))
        nn.init.zeros_(self.score.weight);nn.init.zeros_(self.score.bias)
    def forward(self,x,tile,mask):
        h=self.dropout(torch.tanh(self.query(x)));score=self.score(torch.tanh(h[:,None]+self.tile(tile))).squeeze(-1)+self.bias
        return score.masked_fill(~mask,-1e9).log_softmax(-1)

class Typing(nn.Module):
    def __init__(self,prior):
        super().__init__();self.net=nn.Sequential(nn.Linear(GLOBAL,64),nn.Tanh(),nn.Dropout(.1),nn.Linear(64,1));nn.init.zeros_(self.net[-1].weight);nn.init.constant_(self.net[-1].bias,float(np.log(prior/(1-prior))))
    def forward(self,x):return self.net(x).squeeze(-1)

def target_local(coordinate):
    c=np.asarray(coordinate);dx=c%17-8;dy=c//17-8;valid=(c>=0)&(c<289)&(np.abs(dx)<=2)&(np.abs(dy)<=2)
    return (dy+2)*5+dx+2,valid

def placement_target(logp,mask,coordinate,old_logp):
    local,valid=target_local(coordinate);idx=torch.from_numpy(np.clip(local,0,24)).long();learned=logp.double()[torch.arange(len(logp)),idx].masked_fill(~torch.from_numpy(valid),-torch.inf)
    mixed=torch.logaddexp(np.log(.9999)+learned,np.log(.0001)+old_logp.double());return torch.where(mask.any(-1),mixed,old_logp.double())

def placement_modes(logp,mask,old_local,old_mode,old_mode_lp):
    mixed=torch.logaddexp(np.log(.9999)+logp.double(),np.log(.0001)+old_local.double());mixed=torch.where(mask.any(-1)[:,None],mixed,old_local.double())
    local,valid=target_local(old_mode.numpy());at=torch.from_numpy(np.clip(local,0,24)).long();mode_nn=logp.double()[torch.arange(len(logp)),at].masked_fill(~torch.from_numpy(valid),-torch.inf);mode_lp=torch.logaddexp(np.log(.9999)+mode_nn,np.log(.0001)+old_mode_lp.double());mode_lp=torch.where(mask.any(-1),mode_lp,old_mode_lp.double())
    coordinates=torch.cat((torch.from_numpy(INDICES)[None].expand(len(logp),-1),old_mode[:,None]),-1);probability=torch.cat((mixed,mode_lp[:,None]),-1);coordinates,order=coordinates.sort(-1);probability=probability.gather(1,order);winner=probability.argmax(-1);return coordinates[torch.arange(len(logp)),winner],probability[torch.arange(len(logp)),winner]
