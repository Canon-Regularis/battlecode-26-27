"""Bounded objectives, planners and target rankings. Inputs contain no labels."""
from collections import deque
from functools import lru_cache
import math

GOALS=('camp_near','camp_hp','enemy_near','bank','home')
NAMES=[f'{g}/{p}' for g in GOALS for p in ('greedy_yx','field_yx','field_xy')]
NAMES += [f'{a}/{r}' for a in ('attack','cast_0','cast_1') for r in ('near','hp','fraction')]
NAMES += ['ward/self','ward/toward_bank','submit/bank','end','cancel','recall','priority/zero']

def xy(p):return (p['x'],p['y'])
def dist(a,b):return max(abs(a[0]-b[0]),abs(a[1]-b[1]))

@lru_cache(maxsize=4096)
def field(w,h,blocked,goal,radius):
    """Uniform eight-neighbour terrain planner, a hypothesis, not engine legality.

    Historical movement mask alone admits emitted steps. No hypothetical actions.
    """
    walls=set(blocked);d=[10000]*(w*h);q=deque()
    for y in range(max(0,goal[1]-radius),min(h,goal[1]+radius+1)):
        for x in range(max(0,goal[0]-radius),min(w,goal[0]+radius+1)):
            k=y*w+x
            if k not in walls:d[k]=0;q.append((x,y))
    while q:
        x,y=q.popleft();v=d[y*w+x]+1
        for dy in (-1,0,1):
            for dx in (-1,0,1):
                a,b=x+dx,y+dy;k=b*w+a
                if 0<=a<w and 0<=b<h and k not in walls and d[k]>v:
                    d[k]=v;q.append((a,b))
    return d

def emit(obs,supp,route,simple=False):
    """Return fixed slots of (family, absolute destination or None, integer or 0).

    None is abstention, never an invented unavailable parameter. No IDs are scores.
    No persistent state in C00: explicit reset on every PRE. Causal history is a
    selector input later, never inferred from consecutive sampled rows.
    """
    own=obs['own'];pos=own.get('position');out=[]
    if not pos:return [None]*len(NAMES)
    p=xy(pos);w,h=route['width'],route['height']
    visible=[e for e in obs['entities'] if e.get('known',0)&1 and e.get('position') and e.get('health',0)>0]
    camps=[e for e in visible if e['entity']['kind']==2]
    foes=[e for e in visible if e['entity']['kind']==1 and e['team']!=own['team']]
    def rank(es,mode):
        return min(es,key=lambda e:((dist(p,xy(e['position'])) if mode=='near' else e['health'] if mode=='hp' else e['health']/max(1,e.get('maxHealth',1))),e['position']['y'],e['position']['x']),default=None)
    def ep(e):return xy(e['position']) if e else None
    bank=min(map(xy,route['altars']),key=lambda g:(dist(p,g),g[1],g[0]),default=None)
    s=route['spawns'][own['team']]
    home=min(((x,y) for y in range(s['minY'],s['maxY']) for x in range(s['minX'],s['maxX'])),key=lambda g:(dist(p,g),g[1],g[0]))
    goals=[ep(rank(camps,'near')),ep(rank(camps,'hp')),ep(rank(foes,'near')),bank,home]
    steps=[xy(v) for v in supp['movement'] if xy(v)!=p]
    for gi,g in enumerate(goals):
        radius=route['submit_range'] if gi==3 else int(own.get('attackRange',1)) if gi<3 else 0
        for mode in range(3):
            if g is None or not steps or dist(p,g)<=radius:out.append(None);continue
            d=None if simple or mode==0 else field(w,h,tuple(route['blocked']),g,radius)
            def score(v):
                cost=dist(v,g) if d is None else d[v[1]*w+v[0]]
                # Simple control uses three geometric tie rules, same slot budget.
                tie=(v[0],v[1]) if mode==2 else (v[1],v[0])
                if simple and mode==1:tie=((v[0]-g[0])**2+(v[1]-g[1])**2,v[1],v[0])
                return (cost,*tie)
            v=min(steps,key=score);origin=dist(p,g) if d is None else d[p[1]*w+p[0]]
            out.append(('move',v,0) if score(v)[0]<origin else None)
    for a in ('attack','cast_0','cast_1'):
        props={} if a=='attack' else (own.get('abilityProps') or [{},{}])[int(a[-1])]
        mask=3 if a=='attack' else props.get('target',0)
        rr=own.get('attackRange',0) if a=='attack' else props.get('range',0)
        es=[]
        for e in [own,*visible]:
            bit=1 if e['entity']['kind']==2 else 8 if e['entity']==own['entity'] else 4 if e['team']==own['team'] else 2
            if bit&mask and e.get('position') and dist(p,xy(e['position']))<=rr:es.append(e)
        for r in ('near','hp','fraction'):
            e=rank(es,r);out.append((a,ep(e),0) if e else None)
    out += [('ward',p,0) if supp['own'].get('ward',{}).get('charges',0)>0 else None]
    toward=(p[0]+(bank[0]>p[0])-(bank[0]<p[0]),p[1]+(bank[1]>p[1])-(bank[1]<p[1])) if bank else p
    out += [('ward',toward,0) if supp['own'].get('ward',{}).get('charges',0)>0 else None]
    out += [('submit',bank,0) if bank and dist(p,bank)<=route['submit_range'] else None]
    out += [(a,None,0) for a in ('end','cancel','recall','priority')]
    assert len(out)==len(NAMES)
    return out
