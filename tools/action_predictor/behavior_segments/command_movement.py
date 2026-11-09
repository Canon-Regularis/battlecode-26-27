"""Candidate alignment with completed prior-turn movement, never current commands."""
import math
import torch
from torch import nn
from .model import OFFSETS


def alignment(vector):
    out=torch.zeros(9,2)
    if vector is None:return out
    dx,dy=vector;length=math.hypot(dx,dy)
    if not length:return out
    sign=((dx>0)-(dx<0),(dy>0)-(dy<0))
    for i,(x,y) in enumerate(OFFSETS):
        out[i,0]=(x*dx+y*dy)/(math.hypot(x,y)*length) if x or y else 0
        out[i,1]=float((x,y)==sign)
    return out


def command_step(previous_moves,state=None):
    """Caller provides executed moves from the completed previous own turn."""
    if previous_moves is None:raise ValueError('Supply prior-turn moves explicitly; empty means no moves')
    for v in previous_moves:
        if len(v)!=2 or tuple(v) not in OFFSETS or tuple(v)==(0,0):raise ValueError('Invalid executed move')
    last=None if state is None else state['last'];age=0 if state is None else state['age']+1
    if previous_moves:last=list(previous_moves[-1]);age=1
    dx=sum(v[0] for v in previous_moves);dy=sum(v[1] for v in previous_moves)
    net=alignment((dx,dy));recent=alignment(last)
    length=sum(math.hypot(*v) for v in previous_moves)
    straightness=math.hypot(dx,dy)/length if length else 0
    features=torch.cat((recent,recent/max(1,age),net,net*straightness),-1)
    return features,dict(last=last,age=age)


def command_window(history):
    rows=[];state=None
    for previous in history:
        features,state=command_step(previous,state);rows.append(features)
    return torch.stack(rows)


class CommandCorrection(nn.Module):
    def __init__(self,hidden=0):
        super().__init__();self.weights=nn.Sequential(nn.Linear(56,hidden),nn.Tanh(),nn.Linear(hidden,8)) if hidden else nn.Linear(56,8)
        final=self.weights[-1] if hidden else self.weights;nn.init.zeros_(final.weight);nn.init.zeros_(final.bias)

    def forward(self,context,features,baseline):return baseline+(features*self.weights(context)[...,None,:]).sum(-1)


class CommandPolicy(nn.Module):
    def __init__(self,parent,correction):
        super().__init__();self.parent=parent.eval().requires_grad_(False);self.correction=correction

    def forward(self,*args,command_heading,**kwargs):
        states=[];hook=self.parent.parent.backbone.code.register_forward_pre_hook(lambda module,args:states.append(args[0]))
        try:
            with torch.no_grad():out=self.parent(*args,**kwargs)
        finally:hook.remove()
        out['move']=self.correction(torch.cat((states[0],out['code'].softmax(-1)),-1),command_heading,out['move'])
        return out
