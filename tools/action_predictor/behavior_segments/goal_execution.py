"""A movement residual explicitly conditioned on an externally supplied goal."""
import torch
from torch import nn
from .model import OFFSETS
from .objective_policy import field


def goal_geometry(current,route,goal,radius=0):
    """Only current observable state, public terrain and supplied goal enter here."""
    if current is None or goal is None:return None
    p=current['observation']['own'].get('position')
    if p is None:return None
    x,y=p['x'],p['y'];gx,gy=map(int,goal);w,h=route['width'],route['height']
    if not(0<=gx<w and 0<=gy<h):return None
    d=field(w,h,tuple(route['blocked']),(gx,gy),int(radius));old=d[y*w+x]
    if old>=10000:return None
    rows=[]
    for dx,dy in OFFSETS:
        nx,ny=x+dx,y+dy;new=d[ny*w+nx] if 0<=nx<w and 0<=ny<h else 10000
        rows.append([(gx-x)/32,(gy-y)/32,max(abs(gx-nx),abs(gy-ny))/32,min(old,64)/32,min(new,64)/32,max(-1.,min(1.,old-new)),radius/10,1.])
    return torch.tensor(rows,dtype=torch.float32)


def local_features(context):
    """V59 causal state/code and its existing per-move geometric/history features."""
    shape=context.shape[:-1]
    return torch.cat((context[...,:56].unsqueeze(-2).expand(*shape,9,56),context[...,56:596].reshape(*shape,9,60),context[...,596:632].reshape(*shape,9,4),context[...,632:704].reshape(*shape,9,8)),-1)


class GoalExecutor(nn.Module):
    def __init__(self,conditioned=True):
        super().__init__();self.conditioned=conditioned;self.layers=nn.Sequential(nn.Linear(136,64),nn.Tanh(),nn.Linear(64,1))
        nn.init.zeros_(self.layers[-1].weight);nn.init.zeros_(self.layers[-1].bias)

    def forward(self,context,goal,baseline):
        g=goal if self.conditioned else torch.zeros_like(goal)
        return baseline+self.layers(torch.cat((local_features(context),g),-1)).squeeze(-1)
