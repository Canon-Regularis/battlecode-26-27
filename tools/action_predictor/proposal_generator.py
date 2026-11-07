"""Current repaired proposals. Frozen V4–V11 predictors remain historical.

No labels, model fitting, game actions or hypothetical simulations. All movement
destinations receive ONE forecast outcome; blocked attempts retain destinations.
"""
from dataclasses import dataclass,asdict
import numpy as np
from .algorithmic.library import emit as legacy_emit,NAMES as LEGACY,xy,dist
from .algorithmic_c01 import project
from .algorithmic_c02 import proposals as attempts
from .observation_data import compact_supplement
from .targets import OFFSETS

SPATIAL=('move','blocked','attack','cast_0','cast_1','ward','submit','altar','teleport')
NAMES=tuple(LEGACY[:-1])+('priority/P05',)+tuple('head/'+a for a in SPATIAL)+tuple('attempt/'+a for a in ('continue1','continue2','prior_blocked','camp2','bank2'))+tuple('ward2/'+g for g in ('camp','enemy','bank','continue'))+tuple(f'ground{slot}/{g}' for slot in (0,1) for g in ('camp','enemy','continue'))+('attack/nearest_lock','attack/weakest_lock')

@dataclass(frozen=True)
class Proposal:
    source:str
    action:str
    position:tuple|None=None
    priority:int|None=None
    entity:tuple|None=None
    entity_resolution:str='not_required'

    @property
    def api_action(self):return 'move' if self.action=='blocked' else self.action
    def as_dict(self):return dict(asdict(self),api_action=self.api_action)

def personal_locks(observation,pre,targets):
    if targets is None:return None
    expected=observation['perspective']
    if targets.get('pre')!=pre or targets.get('perspective')!=expected or targets.get('availability')!='personal_api':raise ValueError('Altar-lock input needs matching personal PRE provenance')
    result=[]
    for lock in targets['altar_locks']:
        if lock['entity']['kind']!=6:raise ValueError('Unexpected personal target kind')
        result.append(lock)
    return result

def generate(observation,supplement,route,history,conditional,targets=None):
    """Generate bounded complete benchmark commands from PRE and frozen heads.

    conditional contains every family's predicted coordinate and P05 integer,
    never a recorded family/argument. The action classifier does not gate heads.
    Unknown shop args stay unassessed. Entity identity ambiguity is explicit.
    """
    s=compact_supplement(supplement);own=observation['own'];pos=own.get('position');p=xy(pos) if pos else None
    value=conditional['priority']
    if not isinstance(value,(int,np.integer)) or isinstance(value,(bool,np.bool_)):raise ValueError('P05 priority must be an exact integer, not a float or zero placeholder')
    locks=personal_locks(observation,s['pre'],targets);visible=[e for e in observation['entities'] if e.get('known',0)&1 and e.get('position') and e.get('health',0)>0];enemies=[e for e in visible if e['entity']['kind']==1 and e['team']!=own['team']];camps=[e for e in visible if e['entity']['kind']==2];enemylocks=[e for e in (locks or []) if e['team']!=own['team'] and e.get('hitsRemaining',0)>0]
    legal=set(map(xy,s['movement']));old=legacy_emit(observation,s,route,simple=True);result=[];unavailable={}
    def resolve_outcome(q):
        # A causal forecast, not a successful-move legality assertion. Same API
        # move destination cannot be duplicated under both benchmark outcomes.
        return 'blocked' if q not in legal or conditional['prefer_blocked'] else 'move'
    def add(name,action,q=None,v=None,entity=None,resolution='not_required'):
        free=own.get('alive',False) and own.get('channelType',0)==0
        flags=own.get('roundFlags',0);restr=s['restrictions'];ready=True
        if action=='attack':ready=free and bool(flags&2) and not restr&2
        elif action.startswith('cast_'):
            slot=int(action[-1]);props=(own.get('abilityProps') or [{},{}])[slot]
            ready=free and bool(flags&1024) and not restr&4 and bool(props.get('type')) and own.get('cooldowns',[1,1])[slot]==0 and (not props.get('maxCharges') or own.get('charges',[0,0])[slot]>0)
        elif action=='ward':ready=free and s['own'].get('ward',{}).get('charges',0)>0
        elif action=='submit':ready=free and own.get('gems',0)>0
        if not ready:unavailable[name]='observable_readiness_or_resource';return
        if q is not None:
            q=tuple(map(int,q))
            if p is None or not (0<=q[0]<route['width'] and 0<=q[1]<route['height']):unavailable[name]='missing_position_or_outside_public_map';return
            if action in ('move','blocked'):action=resolve_outcome(q)
        result.append(Proposal(name,action,q,int(v) if v is not None else None,entity,resolution))
    def target_at(action,q):
        if action not in ('attack','cast_0','cast_1'):return None,'not_required'
        props={} if action=='attack' else (own.get('abilityProps') or [{},{}])[int(action[-1])];mask=3 if action=='attack' else props.get('target',0)
        if action!='attack' and mask&16:return None,'ground_position'
        matches=[]
        for e in [own,*visible,*enemylocks]:
            bit=1 if e['entity']['kind']==2 else 2 if e['entity']['kind']==6 else 8 if e['entity']==own['entity'] else 4 if e['team']==own['team'] else 2
            if e.get('position') and xy(e['position'])==q and bit&mask:matches.append(e)
        if not matches:return None,'unavailable_entity'
        # A hypothesis using an observed identity; no original-ID certification
        # follows from coordinate-only replay labels when several targets overlap.
        e=matches[0];return (e['entity']['kind'],e['entity']['index']),'unique_visible' if len(matches)==1 else 'ambiguous_visible'
    for name,c in zip(LEGACY[:-1],old[:-1]):
        if name in ('end','cancel','recall'):continue
        if c is None:continue
        a,q,_=c;entity,resolution=target_at(a,q) if q else (None,'not_required')
        if resolution=='unavailable_entity':unavailable[name]=resolution;continue
        add(name,a,q,entity=entity,resolution=resolution)
    # Position-independent actions and priority are outside every spatial gate.
    add('end','end')
    if own.get('channelType',0)!=0:add('cancel','cancel')
    if own.get('alive',False) and own.get('channelType',0)==0:add('recall','recall')
    add('priority/P05','priority',v=value)
    for action in SPATIAL:
        index=int(conditional['coordinates'][action]);name='head/'+action
        if p is None or not 0<=index<289:unavailable[name]='unavailable_model_coordinate';continue
        q=(p[0]+int(OFFSETS[index,0]),p[1]+int(OFFSETS[index,1]));entity,resolution=target_at(action,q)
        if resolution=='unavailable_entity':unavailable[name]=resolution;continue
        add(name,action,q,entity=entity,resolution=resolution)
    if p is not None:
        def nearest(es):return min((xy(e['position']) for e in es),key=lambda q:(dist(p,q),q[1],q[0]),default=None)
        camp,enemy=nearest(camps),nearest(enemies);bank=min(map(xy,route['altars']),key=lambda q:(dist(p,q),q[1],q[0]),default=None);previous=np.flatnonzero(history[:,8]>0);heading=None
        if len(previous):
            delta=np.rint(history[previous[-1],18:20]*8).astype(int)
            if delta.any():heading=(p[0]+int(delta[0])*8,p[1]+int(delta[1])*8)
        for name,c in zip(('continue1','continue2','prior_blocked','camp2','bank2'),attempts(observation,s,route,history)):
            if c is not None:add('attempt/'+name,c[0],c[1])
        if own.get('alive',False) and own.get('channelType',0)==0 and s['own'].get('ward',{}).get('charges',0)>0:
            for name,g in zip(('camp','enemy','bank','continue'),(camp,enemy,bank,heading)):
                q=project(p,g,2)
                if q:add('ward2/'+name,'ward',q)
        for slot in (0,1):
            props=(own.get('abilityProps') or [{},{}])[slot]
            if props.get('target',0)&16:
                for name,g in zip(('camp','enemy','continue'),(camp,enemy,heading)):
                    q=project(p,g,int(props.get('range',0)))
                    if q:add(f'ground{slot}/'+name,f'cast_{slot}',q,resolution='ground_position')
        eligible=[e for e in enemylocks if dist(p,xy(e['position']))<=own.get('attackRange',0)]
        for name,key in [('nearest',lambda e:(dist(p,xy(e['position'])),e['position']['y'],e['position']['x'])),('weakest',lambda e:(e['hitsRemaining'],dist(p,xy(e['position'])),e['position']['y'],e['position']['x']))]:
            if eligible:
                e=min(eligible,key=key);add('attack/'+name+'_lock','attack',xy(e['position']),entity=(6,e['entity']['index']),resolution='personal_api_target_hypothesis')
    assert len({c.source for c in result})==len(result)
    assert all(c.source in NAMES for c in result)
    return dict(schema='repaired-proposals-v1',proposals=result,unavailable=unavailable,altar_lock_state_available=locks is not None,shop_arguments='unavailable_unassessed',full_engine_legality='unassessed')

def encode(proposal,position,labels):
    index=-1
    if proposal.position is not None:
        if position is None:return None
        dx=proposal.position[0]-position['x'];dy=proposal.position[1]-position['y']
        if max(abs(dx),abs(dy))>8:return None
        index=(dy+8)*17+dx+8
    return (labels.index(proposal.action),index,proposal.priority if proposal.priority is not None else 0)
