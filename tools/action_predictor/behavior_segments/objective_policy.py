"""Identity-bound causal objectives and learned utility-based termination."""
import math
import torch
from torch import nn
from ..algorithmic.library import field
from .model import OFFSETS


def candidates(current,route):
    if current is None:return []
    own=current['observation']['own'];p=own.get('position')
    if p is None:return []
    origin=(p['x'],p['y']);rows=[]
    for e in current['observation']['entities']:
        if not e.get('known',0)&1 or e.get('position') is None or e.get('health',0)<=0:continue
        kind=e['entity']['kind']
        if kind==2:category=0
        elif kind==1 and e.get('team')!=own['team']:category=1
        else:continue
        q=e['position'];rows.append(dict(key=f"entity:{kind}:{e['entity']['index']}",goal=(q['x'],q['y']),radius=int(own.get('attackRange',1)),category=category,health=e['health']/max(1,e.get('maxHealth',e['health']))))
    for i,p in enumerate(route['altars']):rows.append(dict(key=f'altar:{i}',goal=(p['x'],p['y']),radius=route['submit_range'],category=2,health=0.))
    for team in (own['team'],1-own['team']):
        s=route['spawns'][team];cells=[(x,y) for y in range(s['minY'],s['maxY']) for x in range(s['minX'],s['maxX']) if y*route['width']+x not in route['blocked']]
        if cells:rows.append(dict(key=f'home:{team}',goal=min(cells,key=lambda q:(max(abs(q[0]-origin[0]),abs(q[1]-origin[1])),q[1],q[0])),radius=0,category=3 if team==own['team'] else 4,health=0.))
    result=[]
    for r in rows:
        distances=field(route['width'],route['height'],tuple(route['blocked']),r['goal'],r['radius']);d=distances[origin[1]*route['width']+origin[0]]
        if not 0<d<10000:continue
        dx=r['goal'][0]-origin[0];dy=r['goal'][1]-origin[1]
        x=[float(r['category']==k) for k in range(5)]+[dx/32,dy/32,max(abs(dx),abs(dy))/32,d/32,r['radius']/10,r['health'],float(own.get('health',0))/max(1,own.get('maxHealth',1))]
        result.append(dict(r,features=x))
    return sorted(result,key=lambda r:r['key'])


def utility(candidate,path,route):
    """Supervision only: mean progress per recorded future grid step."""
    if len(path)<2:return None
    d=field(route['width'],route['height'],tuple(route['blocked']),tuple(candidate['goal']),candidate['radius']);w=route['width']
    costs=[d[y*w+x] for x,y in path]
    if any(v>=10000 for v in costs):return None
    return (costs[0]-costs[-1])/(len(path)-1)


def choose(rows,scores,state=None,margin=.15):
    if not rows:return None,None,'unavailable'
    best=max(range(len(rows)),key=lambda i:(scores[i],-i));old=None if state is None else next((i for i,r in enumerate(rows) if r['key']==state),None)
    if scores[best]<=0:return None,None,'abstain'
    if old is not None and scores[old]>0 and scores[old]>=scores[best]-margin:return rows[old],state,'retain'
    return rows[best],rows[best]['key'],'select' if state is None else 'switch'


def movement(candidate,current,route,base_probabilities):
    p=current['observation']['own']['position'];origin=(p['x'],p['y']);fallback=int(torch.tensor(base_probabilities).argmax())
    if candidate is None:return fallback
    d=field(route['width'],route['height'],tuple(route['blocked']),tuple(candidate['goal']),candidate['radius']);w=route['width'];old=d[origin[1]*w+origin[0]]
    allowed=[]
    for q in current['supplement']['movement']:
        delta=(q['x']-origin[0],q['y']-origin[1])
        if delta in OFFSETS and d[q['y']*w+q['x']]<old:allowed.append(OFFSETS.index(delta))
    return max(allowed,key=lambda i:(base_probabilities[i],-i)) if allowed else fallback


class ObjectiveHead(nn.Module):
    def __init__(self):
        super().__init__();self.net=nn.Sequential(nn.Linear(68,64),nn.Tanh(),nn.Linear(64,1),nn.Tanh())

    def forward(self,x):return self.net(x).squeeze(-1)
