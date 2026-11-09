"""Causal joint categorical action/coordinate and discrete priority model."""
import torch
from torch import nn
import torch.nn.functional as F


def priority_log_mass(raw, target):
    # Normalized priorities have integer-bin width .01. Stable logistic CDF difference.
    mean=raw[:,0]
    scale=raw[:,1].clamp(-6,5).exp()
    hi=(target/100+.005-mean)/scale
    lo=(target/100-.005-mean)/scale
    return F.logsigmoid(hi)+F.logsigmoid(-lo)+torch.log(-torch.expm1(-.01/scale))


class JointModel(nn.Module):
    def __init__(self,inputs,history_features,classes,config):
        super().__init__()
        self.config=config
        self.current=nn.Sequential(nn.Linear(inputs,128),nn.ReLU(),nn.Linear(128,128),nn.ReLU())
        if config['history']:
            self.history=nn.GRU(history_features,64,batch_first=True)
            self.combine=nn.Sequential(nn.Linear(192,128),nn.ReLU())
        else:
            self.combine=nn.Sequential(nn.Linear(128,192),nn.ReLU(),nn.Linear(192,128),nn.ReLU())
        self.action=nn.Linear(128,classes)
        self.family=nn.Embedding(classes,32)
        self.query=nn.Linear(128,32)
        self.candidate=nn.Sequential(nn.Linear(20 if config['spatial'] else 5,32),nn.Tanh(),nn.Linear(32,32))
        self.offset_bias=nn.Embedding(classes,291)
        self.special=nn.Linear(128,2)
        self.priority=nn.Linear(128,2)

    def forward(self,x,history):
        current=self.current(x)
        if self.config['history']:
            _,h=self.history(history[:,-self.config['history']:])
            context=self.combine(torch.cat((current,h[-1]),-1))
        else:
            context=self.combine(current)
        return self.action(context),context

    def parameter_logits(self,context,grid,valid,family,rules=None):
        original_grid=grid
        if not self.config['spatial']:
            grid=grid[:,:,[0,1,2,3,17]]
        elif not self.config['history']:
            # Last movement is historical and must not enter the stateless baseline.
            grid=grid.clone();grid[:,:,18:20]=0
        query=self.query(context)+self.family(family)
        logits=(self.candidate(grid)*query[:,None]).sum(-1)/5.657
        logits=logits+self.offset_bias(family)[:,:289]
        logits=logits.masked_fill(~valid,-1e4)
        logits=torch.cat((logits,self.special(context)+self.offset_bias(family)[:,289:]),-1)
        if self.config.get('constrain'):
            if rules is None:raise ValueError('Constrained model requires PRE geometry rules')
            allowed=valid.clone()
            # Existing vocabulary: move=8, attack=2, cast_0=5, cast_1=6.
            move=family==8
            allowed[move]&=original_grid[move,:,5]>0
            for code,slot in ((2,-1),(5,0),(6,1)):
                selected=family==code
                if not selected.any():continue
                bits=torch.full_like(family[selected],3) if slot<0 else rules[selected,3+slot].long()
                radius=rules[selected,0] if slot<0 else rules[selected,1+slot]
                units=torch.zeros_like(allowed[selected])
                for bit,col in ((1,12),(2,10),(4,11),(8,17)):
                    units|=((bits&bit)!=0)[:,None]&(original_grid[selected,:,col]>0)
                units|=((bits&16)!=0)[:,None]
                allowed[selected]&=units&(original_grid[selected,:,2]*8<=radius[:,None]+1e-5)
            has=allowed.any(-1)
            complete=torch.cat((allowed,torch.zeros(len(allowed),2,dtype=torch.bool)),1)
            complete[~has]=True
            full=logits.log_softmax(-1)
            restricted=logits.masked_fill(~complete,-1e4).log_softmax(-1)
            # Keep a fixed 1e-4 full-support mixture: unsupported recorded labels
            # stay in both likelihood and exact metrics, never filtered away.
            logits=torch.logaddexp(restricted+torch.log(torch.tensor(.9999)),full+torch.log(torch.tensor(.0001)))
        return logits
