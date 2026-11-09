"""Causal map/history policy; offline segment labels are never forward inputs."""
import numpy as np
import torch
from torch import nn
from ..goal_position import model as gm
from .data import FEATURES

OFFSETS=[(x,y) for y in (-1,0,1) for x in (-1,0,1)]


def encode_observation(row,route,keys):
    if row['observation']['own'].get('position') is not None:return gm.encode(row,route,keys)
    # Dead/shop PREs are real observations without a location. Preserve their state
    # and public map, but never fabricate an origin or valid goal distribution.
    own,entities,raw=gm.feature_dicts(row);w,h=route['width'],route['height']
    grid=np.zeros((11,h,w),np.float32);grid[0]=1;grid[1].reshape(-1)[route['blocked']]=1
    yy,xx=np.mgrid[:h,:w];grid[2]=xx/100;grid[3]=yy/100;grid[10]=-1
    for p in route['altars']:grid[6,p['y'],p['x']]=1
    team=row['observation']['own']['team']
    for i,s in enumerate(route['spawns']):grid[7 if i==team else 8,s['minY']:s['maxY'],s['minX']:s['maxX']]=1
    positions=[]
    for e in raw:
        p=gm.xy(e.get('position'));positions.append(p if p and 0<=p[0]<w and 0<=p[1]<h else (-1,-1))
    return dict(grid=torch.from_numpy(grid),valid=torch.zeros(h,w,dtype=torch.bool),
        own=torch.from_numpy(gm.vector(own,keys['own'])),entities=torch.from_numpy(np.stack([gm.vector(e,keys['entity']) for e in entities])),
        positions=torch.tensor(positions),unencoded_fields=len(set(own)-set(keys['own']))+sum(len(set(e)-set(keys['entity'])) for e in entities))


class SegmentPolicy(nn.Module):
    def __init__(self,keys,codes=8):
        super().__init__();self.maps=gm.GoalMap(keys);del self.maps.output
        self.context=nn.Linear(48,32)
        self.memory=nn.GRUCell(32+2*len(FEATURES)+2,48)
        self.code=nn.Linear(48,codes);self.embeddings=nn.Parameter(torch.randn(codes,16)*.05)
        self.query=nn.Linear(64,16);self.goal=nn.Sequential(nn.Conv2d(48,16,1),nn.Tanh(),nn.Conv2d(16,1,1))
        self.movement=nn.Linear(64,9)

    def forward(self,batch,previous,previous_mask,rounds,observed,state=None):
        grid=batch['grid'];entity_mask=batch['entity_mask'];pos=batch['positions'];n,_,h,w=grid.shape
        em=self.maps.entity(batch['entities'])*entity_mask.unsqueeze(-1)
        pooled=em.sum(1)/entity_mask.sum(1,keepdim=True).clamp_min(1);own=self.maps.own(batch['own'])
        spatial=torch.zeros(n,16,h*w,device=grid.device);located=(pos[:,:,0]>=0)&entity_mask
        indices=(pos[:,:,1]*w+pos[:,:,0]).clamp_min(0)
        spatial.scatter_add_(2,indices[:,None,:].expand(-1,16,-1),em.transpose(1,2)*located[:,None,:])
        context=torch.cat((own,pooled),1)[:,:,None,None].expand(-1,-1,h,w);mask=grid[:,:1]
        z=torch.tanh(self.maps.input(torch.cat((grid,spatial.reshape(n,16,h,w),context),1)))*mask
        for layer in self.maps.layers:z=(z+torch.tanh(layer(z)))*mask
        whole=z.sum((2,3))/mask.sum((2,3)).clamp_min(1)
        feature=torch.tanh(self.context(torch.cat((whole,own,pooled),1)))*observed[:,None]
        recurrent=torch.cat((feature,previous/5,previous_mask,torch.log1p(rounds)[:,None]/10,observed[:,None]),1)
        if state is None:state=torch.zeros(1,48,device=grid.device)
        states=[]
        for x in recurrent:state=self.memory(x[None,:],state);states.append(state[0])
        states=torch.stack(states);codes=self.code(states);embedding=codes.softmax(-1)@self.embeddings
        shared=torch.cat((states,embedding),1);query=torch.tanh(self.query(shared))[:,:,None,None].expand(-1,-1,h,w)
        logits=self.goal(torch.cat((z,query,whole[:,:,None,None].expand(-1,-1,h,w)),1)).squeeze(1)
        # Missing-observation rows have no valid goal distribution and no goal loss.
        logits=logits.masked_fill(~batch['valid'],-1e9)
        return dict(goal=logits,move=self.movement(shared),code=codes,state=state)


def encode_window(window,route,keys):
    encoded=[]
    for step in window['steps']:
        if step['observed']:encoded.append(encode_observation(step['input'],route,keys))
        else:
            h,w=route['height'],route['width']
            encoded.append(dict(grid=torch.zeros(11,h,w),valid=torch.zeros(h,w,dtype=torch.bool),
                own=torch.zeros(2*len(keys['own'])),entities=torch.zeros(1,2*len(keys['entity'])),
                positions=torch.full((1,2),-1),unencoded_fields=0))
    args=dict(batch=gm.batch(encoded),previous=torch.tensor([s['previous'] for s in window['steps']],dtype=torch.float32),
        previous_mask=torch.tensor([s['previous_mask'] for s in window['steps']],dtype=torch.float32),
        rounds=torch.tensor([s['round'] for s in window['steps']],dtype=torch.float32),
        observed=torch.tensor([s['observed'] for s in window['steps']],dtype=torch.float32))
    return args,sum(x['unencoded_fields'] for x in encoded)


def move_support(window):
    support=torch.zeros(len(window['steps']),9,dtype=torch.bool);labels=torch.full((len(window['steps']),),-1,dtype=torch.long)
    for i,s in enumerate(window['steps']):
        if not s['observed']:continue
        own=s['input']['observation']['own'].get('position')
        if own is None:
            if s['movement'] is not None:raise ValueError('Movement without PRE origin')
            continue
        support[i,4]=True
        for p in s['input']['supplement']['movement']:
            delta=(p['x']-own['x'],p['y']-own['y'])
            if delta in OFFSETS:support[i,OFFSETS.index(delta)]=True
        if s['movement'] is not None:
            delta=tuple(s['movement'])
            if delta not in OFFSETS or not support[i,OFFSETS.index(delta)]:raise ValueError('Movement label outside personal support')
            labels[i]=OFFSETS.index(delta)
    return support,labels
