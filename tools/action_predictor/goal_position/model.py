"""A separate full-map goal distribution and a goal-conditioned walking adapter."""
import math
import numpy as np
import torch
from torch import nn
from .evaluator import astar,field,xy


def numeric(value,prefix=''):
    out={}
    if isinstance(value,dict):
        for k,v in sorted(value.items()):out.update(numeric(v,prefix+'/'+k))
    elif isinstance(value,list):
        for i,v in enumerate(value):out.update(numeric(v,prefix+'/'+str(i)))
    elif isinstance(value,(int,float,bool)):
        if not math.isfinite(float(value)):raise ValueError('Nonfinite observation')
        out[prefix]=math.copysign(math.log1p(abs(value)),value)/10
    return out


def entities(observation):
    own=observation['own'];result=[]
    for i,e in enumerate([own,*observation['entities']]):
        # Unknown entities contribute static public metadata only, never hidden dynamics.
        e=dict(e) if e.get('known',0)&1 else {k:e[k] for k in ('entity','team','type','known') if k in e}
        kind=e.pop('entity')['kind'];team=e.pop('team',None)
        e.update(kind=kind,is_self=i==0,is_ally=team==own['team'],is_enemy=team is not None and team!=own['team'])
        result.append(e)
    return result


def feature_dicts(row):
    obs=row['observation'];supp=row['supplement']
    es=entities(obs)
    own=numeric(dict(self=es[0],supplement={k:v for k,v in supp.items() if k not in ('pre','movement')}))
    return own,[numeric(e) for e in es],es


def schema(rows):
    own=set();entity=set()
    for r in rows:
        a,b,_=feature_dicts(r);own.update(a)
        for e in b:entity.update(e)
    return dict(own=sorted(own),entity=sorted(entity))


def vector(values,keys):
    return np.asarray([values.get(k,0) for k in keys]+[float(k in values) for k in keys],np.float32)


def encode(row,route,keys):
    w,h=route['width'],route['height'];own,es,raw=feature_dicts(row)
    origin=xy(row['observation']['own']['position']);team=row['observation']['own']['team']
    grid=np.zeros((11,h,w),np.float32);grid[0]=1
    grid[1].reshape(-1)[route['blocked']]=1
    yy,xx=np.mgrid[:h,:w];grid[2]=xx/100;grid[3]=yy/100
    grid[4]=(xx-origin[0])/100;grid[5]=(yy-origin[1])/100
    for p in route['altars']:grid[6,p['y'],p['x']]=1
    for i,s in enumerate(route['spawns']):grid[7 if i==team else 8,s['minY']:s['maxY'],s['minX']:s['maxX']]=1
    for p in row['supplement']['movement']:grid[9,p['y'],p['x']]=1
    distances=np.asarray(field(w,h,tuple(route['blocked']),origin,0)).reshape(h,w)
    grid[10]=np.where(distances<10000,distances/100,-1)
    positions=[]
    for e in raw:
        p=xy(e.get('position'))
        positions.append(p if p and 0<=p[0]<w and 0<=p[1]<h else (-1,-1))
    return dict(grid=torch.from_numpy(grid),valid=torch.from_numpy(distances<10000),
        own=torch.from_numpy(vector(own,keys['own'])),entities=torch.from_numpy(np.stack([vector(e,keys['entity']) for e in es])),
        positions=torch.tensor(positions),unencoded_fields=len(set(own)-set(keys['own']))+sum(len(set(e)-set(keys['entity'])) for e in es))


def batch(items):
    h=max(x['grid'].shape[1] for x in items);w=max(x['grid'].shape[2] for x in items)
    n=len(items);m=max(len(x['entities']) for x in items);d=items[0]['entities'].shape[1]
    grid=torch.zeros(n,11,h,w);valid=torch.zeros(n,h,w,dtype=torch.bool)
    entity=torch.zeros(n,m,d);mask=torch.zeros(n,m,dtype=torch.bool);pos=torch.full((n,m,2),-1,dtype=torch.long)
    for i,x in enumerate(items):
        a,b=x['valid'].shape;k=len(x['entities']);grid[i,:,:a,:b]=x['grid'];valid[i,:a,:b]=x['valid']
        entity[i,:k]=x['entities'];mask[i,:k]=True;pos[i,:k]=x['positions']
    return dict(grid=grid,valid=valid,own=torch.stack([x['own'] for x in items]),entities=entity,entity_mask=mask,positions=pos)


class GoalMap(nn.Module):
    def __init__(self,keys):
        super().__init__()
        self.entity=nn.Sequential(nn.Linear(2*len(keys['entity']),16),nn.Tanh())
        self.own=nn.Sequential(nn.Linear(2*len(keys['own']),16),nn.Tanh())
        self.input=nn.Conv2d(59,16,1)
        self.layers=nn.ModuleList([nn.Conv2d(16,16,3,padding=d,dilation=d) for d in (1,2,4,8)])
        self.output=nn.Sequential(nn.Conv2d(32,16,1),nn.Tanh(),nn.Conv2d(16,1,1))

    def forward(self,grid,valid,own,entities,entity_mask,positions):
        n,_,h,w=grid.shape;em=self.entity(entities)*entity_mask.unsqueeze(-1)
        pool=em.sum(1)/entity_mask.sum(1,keepdim=True).clamp_min(1)
        spatial=torch.zeros(n,16,h*w,device=grid.device)
        located=(positions[:,:,0]>=0)&entity_mask
        indices=(positions[:,:,1]*w+positions[:,:,0]).clamp_min(0)
        spatial.scatter_add_(2,indices[:,None,:].expand(-1,16,-1),em.transpose(1,2)*located[:,None,:])
        context=torch.cat((self.own(own),pool),1)[:,:,None,None].expand(-1,-1,h,w)
        mask=grid[:,:1]
        z=torch.tanh(self.input(torch.cat((grid,spatial.reshape(n,16,h,w),context),1)))*mask
        for layer in self.layers:z=(z+torch.tanh(layer(z)))*mask
        whole=z.sum((2,3),keepdim=True)/mask.sum((2,3),keepdim=True).clamp_min(1)
        logits=self.output(torch.cat((z,whole.expand(-1,-1,h,w)),1)).squeeze(1)
        return logits.masked_fill(~valid,-torch.inf)


def goal_guided_move(route,row,goal):
    origin=xy(row['observation']['own']['position'])
    allowed={xy(p) for p in row['supplement']['movement']};allowed.discard(origin)
    path=astar(route,origin,tuple(goal),allowed)
    return path[1] if path and len(path)>1 else None


def adapt_movement(family,destination,route,row,predicted_goal):
    """Experimental drop-in adapter: retain the command on unavailable paths."""
    if family!='move':return destination
    step=goal_guided_move(route,row,predicted_goal)
    return step if step is not None else destination
