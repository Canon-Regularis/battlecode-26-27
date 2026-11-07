"""Bounded causal goal descriptors and a forward, identity-preserving filter.

Internal entity IDs associate remembered observations only; no ID reaches the
learner. This filter is a hypothesis, not a label for Fish's hidden intent.
"""
import math
import numpy as np
from .algorithmic.library import xy,dist
from .audit import cursor

def goals(obs,route):
    own=obs['own'];pos=own.get('position')
    if not pos:return [None]*5
    p=xy(pos);visible=[e for e in obs['entities'] if e.get('known',0)&1 and e.get('position') and e.get('health',0)>0]
    camps=[e for e in visible if e['entity']['kind']==2];foes=[e for e in visible if e['entity']['kind']==1 and e['team']!=own['team']]
    def entity(es,hp=False):
        if not es:return None
        e=min(es,key=lambda e:(e['health'] if hp else dist(p,xy(e['position'])),e['position']['y'],e['position']['x']))
        return dict(key=('entity',e['entity']['kind'],e['entity']['index']),position=xy(e['position']),hp=e['health']/max(1,e.get('maxHealth',1)),radius=own.get('attackRange',1))
    bank=min(map(xy,route['altars']),key=lambda q:(dist(p,q),q[1],q[0]),default=None);s=route['spawns'][own['team']];home=min(((x,y) for y in range(s['minY'],s['maxY']) for x in range(s['minX'],s['maxX'])),key=lambda q:(dist(p,q),q[1],q[0]))
    return [entity(camps),entity(camps,True),entity(foes),dict(key=('bank',*bank),position=bank,hp=0,radius=route['submit_range']) if bank else None,dict(key=('home',own['team']),position=home,hp=0,radius=0)]

def current_descriptors(obs,route,commands):
    gs=goals(obs,route);p=xy(obs['own']['position']) if obs['own'].get('position') else None
    global_=np.zeros((5,8),np.float32);point=np.zeros((len(commands),10),np.float32)
    for k,g in enumerate(gs):
        if g is None:continue
        q=g['position'];before=max(0,dist(p,q)-g['radius']);global_[k]=[(q[0]-p[0])/32,(q[1]-p[1])/32,before/32,g['hp'],g['radius']/8,1,float(k<2),float(k==2)]
        for j,c in enumerate(commands):
            if c[0]<0 or not 0<=c[1]<289:continue
            at=(p[0]+int(c[1]%17)-8,p[1]+int(c[1]//17)-8);after=max(0,dist(at,q)-g['radius']);point[j,k]=(before-after)/8;point[j,5+k]=after/32
    return global_.reshape(-1),point,gs

class GoalMemory:
    def __init__(self):self.states={};self.last=None;self.roots=0;self.available=0;self.moves=0;self.missing=0
    def observe(self,event,step,round_number,observation,route):
        at=cursor(event)
        if self.last is not None and at<=self.last:raise ValueError('Nonconsecutive/repeated causal event order')
        # Every actual own root is accounted for, including unavailable PREs.
        self.last=at;self.roots+=1
        for v in self.states.values():v['score']*=.93
        if observation is None:self.missing+=1;return
        self.available+=1
        current_keys=set()
        for g in goals(observation,route):
            if g is not None:
                current_keys.add(g['key'])
                state=self.states.setdefault(g['key'],dict(score=0.,last_seen=round_number))
                state.update(position=g['position'],radius=g['radius'],last_seen=round_number)
        if step['kind']==4 and step.get('from') and step.get('to'):
            self.moves+=1;a,b=xy(step['from']),xy(step['to'])
            for key,state in self.states.items():
                # Score only goals actually seen at this action's PRE; no
                # retrospectively scoring old moves against current locations.
                if key in current_keys:
                    state['score']+=max(-2,min(2,dist(a,state['position'])-dist(b,state['position'])))
        # Bounded observed identity memory; no map/game IDs in learned features.
        if len(self.states)>64:
            keys=sorted(self.states,key=lambda k:(self.states[k]['last_seen'],repr(k)))
            for key in keys[:len(keys)-64]:del self.states[key]
    def descriptors(self,gs,round_number,pre,position=None,commands=None):
        if self.last is not None and self.last>cursor(pre):raise ValueError('Future goal memory')
        scores=np.array([self.states[g['key']]['score'] if g is not None and g['key'] in self.states else 0 for g in gs]);known=np.array([g is not None and g['key'] in self.states for g in gs]);belief=np.zeros(5,np.float32)
        if known.any():
            ex=np.exp(np.clip(scores[known]-scores[known].max(),-30,0));belief[known]=ex/ex.sum()
        age=np.array([min(100,max(0,round_number-self.states[g['key']]['last_seen']))/100 if k else 0 for g,k in zip(gs,known)],np.float32)
        best=np.zeros(7,np.float32);progress=np.zeros(len(commands) if commands is not None else 0,np.float32)
        if self.states and position is not None:
            key=min(self.states,key=lambda k:(-self.states[k]['score'],-self.states[k]['last_seen'],repr(k)));state=self.states[key]
            current=next((g for g in gs if g is not None and g['key']==key),None);q=current['position'] if current is not None else state['position'];p=xy(position);before=max(0,dist(p,q)-state['radius']);age_best=0 if current is not None else min(100,max(0,round_number-state['last_seen']))/100
            best[:]=[(q[0]-p[0])/32,(q[1]-p[1])/32,before/32,state['radius']/8,age_best,1,float(current is not None)]
            if commands is not None:
                for j,c in enumerate(commands):
                    if c[0]>=0 and 0<=c[1]<289:
                        at=(p[0]+int(c[1]%17)-8,p[1]+int(c[1]//17)-8);progress[j]=(before-max(0,dist(at,q)-state['radius']))/8
        return np.r_[belief,age,min(self.roots,100)/100,self.available/max(1,self.roots),self.missing/max(1,self.roots),min(self.moves,100)/100,best].astype(np.float32),belief,progress
