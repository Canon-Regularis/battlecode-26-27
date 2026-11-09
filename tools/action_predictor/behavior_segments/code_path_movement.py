"""Current-PRE candidate geometry and soft-code-conditioned movement scoring."""
import math
import torch
from torch import nn
from .model import OFFSETS
from ..algorithmic.library import field

TARGETS=('near_camp','weak_camp','near_enemy','weak_enemy','near_ally','altar','home','enemy_home')
CHANNELS=('chebyshev_progress','euclidean_progress','inverse_distance','within_range',
          'health_weighted_progress','terrain_progress','terrain_reachable')
FEATURE_NAMES=['dx','dy','stay','terrain_degree']+[t+'/'+c for t in TARGETS for c in CHANNELS]


def candidate_features(current,route):
    """No command arguments, inferred labels, future frames, or unknown dynamics."""
    out=torch.zeros(9,len(FEATURE_NAMES))
    if current is None:return out
    own=current['observation']['own'];p=own.get('position')
    if p is None:return out
    x,y=p['x'],p['y'];w,h=route['width'],route['height'];blocked=set(route['blocked'])
    def distance(e):return max(abs(e['position']['x']-x),abs(e['position']['y']-y))
    visible=[e for e in current['observation']['entities'] if e.get('known',0)&1 and e.get('position') is not None and e.get('health',0)>0]
    camps=[e for e in visible if e['entity']['kind']==2]
    enemies=[e for e in visible if e['entity']['kind']==1 and e.get('team')!=own['team']]
    allies=[e for e in visible if e['entity']['kind']==1 and e.get('team')==own['team'] and e['entity']!=own['entity']]
    def select(es,weak=False):
        return min(es,key=lambda e:((e['health'] if weak else distance(e)),distance(e),e['position']['y'],e['position']['x']),default=None)
    entities=[select(camps),select(camps,True),select(enemies),select(enemies,True),select(allies)]
    targets=[None if e is None else (e['position']['x'],e['position']['y']) for e in entities]
    altars=[(p['x'],p['y']) for p in route['altars']]
    targets.append(min(altars,key=lambda q:(max(abs(q[0]-x),abs(q[1]-y)),q[1],q[0]),default=None))
    for team in (own['team'],1-own['team']):
        spawn=route['spawns'][team]
        cells=[(a,b) for b in range(spawn['minY'],spawn['maxY']) for a in range(spawn['minX'],spawn['maxX']) if b*w+a not in blocked]
        cx=(spawn['minX']+spawn['maxX']-1)/2;cy=(spawn['minY']+spawn['maxY']-1)/2
        targets.append(min(cells,key=lambda q:((q[0]-cx)**2+(q[1]-cy)**2,q[1],q[0]),default=None))
    fields=[None]*5+[None if q is None else field(w,h,tuple(route['blocked']),q,0) for q in targets[5:]]
    for i,(dx,dy) in enumerate(OFFSETS):
        a,b=x+dx,y+dy
        if not (0<=a<w and 0<=b<h):continue
        degree=sum(0<=a+u<w and 0<=b+v<h and (b+v)*w+a+u not in blocked for u,v in OFFSETS if u or v)/8
        out[i,:4]=torch.tensor([dx,dy,float(dx==dy==0),degree])
        for j,q in enumerate(targets):
            if q is None:continue
            d0=max(abs(q[0]-x),abs(q[1]-y));d1=max(abs(q[0]-a),abs(q[1]-b));progress=d0-d1
            euclid=(math.hypot(q[0]-x,q[1]-y)-math.hypot(q[0]-a,q[1]-b))/math.sqrt(2)
            rr=own.get('attackRange',0) if j<5 else route['submit_range'] if j==5 else 0
            hp=entities[j].get('health',0)/max(1,entities[j].get('maxHealth',entities[j].get('health',1))) if j<5 else 1.
            terrain=fields[j];reachable=terrain is not None and terrain[y*w+x]<10000 and terrain[b*w+a]<10000
            path_progress=terrain[y*w+x]-terrain[b*w+a] if reachable else 0
            out[i,4+j*7:4+(j+1)*7]=torch.tensor([progress,euclid,1/(1+d1),float(d1<=rr),min(hp,1.)*progress,path_progress,float(reachable)])
    return out


class PathCorrection(nn.Module):
    def __init__(self,mean_probabilities,conditioned=True):
        super().__init__();self.conditioned=conditioned
        self.register_buffer('mean_probabilities',mean_probabilities.detach().clone())
        self.coefficients=nn.Linear(56,len(FEATURE_NAMES))
        nn.init.zeros_(self.coefficients.weight);nn.init.zeros_(self.coefficients.bias)

    def forward(self,states,probabilities,baseline):
        hidden=states[...,:48];geometry=states[...,48:].reshape(*states.shape[:-1],9,len(FEATURE_NAMES))
        gate=probabilities if self.conditioned else self.mean_probabilities.expand_as(probabilities)
        weights=self.coefficients(torch.cat((hidden,gate),-1))
        return baseline+(geometry*weights[...,None,:]).sum(-1)


class PathMovementPolicy(nn.Module):
    def __init__(self,backbone,correction):
        super().__init__();self.backbone=backbone.eval().requires_grad_(False);self.correction=correction

    def forward(self,*args,geometry,**kwargs):
        states=[];handle=self.backbone.code.register_forward_pre_hook(lambda module,values:states.append(values[0]))
        try:
            with torch.no_grad():result=self.backbone(*args,**kwargs)
        finally:handle.remove()
        combined=torch.cat((states[0],geometry.flatten(-2)),-1)
        result['move']=self.correction(combined,result['code'].softmax(-1),result['move'])
        return result
