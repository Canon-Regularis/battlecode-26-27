"""Causal replay inference: remember personal PRE observations only after actions."""
import copy

import numpy as np
import torch

from .observation_model import ObservationHistoryModel
from .observation_data import encode,safe_observation
from .rich_data import history_vector,candidate_grid,SPATIAL
from .targets import OFFSETS,point
from .audit import cursor

ROOT_NAMES={4:'move',5:'attack',6:'cast',8:'end',9:'priority',11:'recall',12:'submit',13:'shop',14:'ward',
            15:'consumable',16:'cancel',20:'altar',21:'teleport',23:'blocked',25:'sell'}


def label_for(step,labels):
    name=ROOT_NAMES.get(step['kind'],'<unknown>')
    if name=='cast':name=f'cast_{step["abilitySlot"]}'
    return labels.index(name) if name in labels else 0


class ObservationPredictor:
    """One instance per actor/game. No actions, matches or bot integration.

    predict() does not append its forecast. observe() receives an actual earlier
    action plus its personal PRE snapshot. Pass observation=None explicitly when
    the old observation is unavailable; the frame/action is retained with a mask.
    Own-turn IDs need only identify this actor's real turn boundaries.
    """
    def __init__(self,checkpoint,actor=None):
        saved=torch.load(checkpoint,map_location='cpu',weights_only=True)
        if saved.get('architecture')!='personal-observation-history-gru-v1':raise ValueError('Wrong checkpoint architecture')
        self.labels=saved['labels'];self.config=saved['config'];self.mean=saved['mean'];self.std=saved['std']
        self.model=ObservationHistoryModel(len(self.mean),len(self.labels)+9,len(self.labels),self.config)
        self.model.load_state_dict(saved['state_dict']);self.model.eval()
        self.actor=actor;self.team=None;self.frames=[];self.last_move=None

    def observe(self,observation,supplement,route,round_number,own_turn,pre_cursor,event_cursor,actual_step):
        actor=actual_step['actor']
        if actor['kind']!=1:raise ValueError('An own champion action is required')
        if self.actor is None:self.actor=actor['index']
        if actor['index']!=self.actor:raise ValueError('Do not mix actors')
        if cursor(pre_cursor)>=cursor(event_cursor):raise ValueError('Observation must precede its actual action')
        if self.frames and cursor(event_cursor)<=self.frames[-1]['at']:raise ValueError('Observed actions must be strictly ordered')
        vector=None
        if observation is not None:
            if supplement is None or supplement['pre']!=pre_cursor:raise ValueError('Supplement cursor mismatch')
            team=observation['own']['team']
            if self.team is None:self.team=team
            if self.team!=team:raise ValueError('Do not mix perspectives')
            safe_observation(observation,self.actor,team,supplement)
            vector=encode(observation,supplement,route,round_number).copy()
        if self.frames and round_number<self.frames[-1]['round']:raise ValueError('Round went backwards')
        frame=dict(at=cursor(event_cursor),pre=cursor(pre_cursor),round=round_number,turn=own_turn,
                   step=copy.deepcopy(actual_step),kind=label_for(actual_step,self.labels),observation=vector)
        self.frames.append(frame);self.frames=self.frames[-32:]
        if actual_step['kind']==4:self.last_move=copy.deepcopy(actual_step)

    def inputs(self,observation,supplement,route,round_number,own_turn,pre_cursor):
        actor=observation['own']['entity']['index'];team=observation['own']['team']
        if self.actor is None:self.actor=actor
        if self.actor!=actor or (self.team is not None and self.team!=team):raise ValueError('Actor/perspective mismatch')
        self.team=team
        if supplement['pre']!=pre_cursor:raise ValueError('Current supplement cursor mismatch')
        safe_observation(observation,actor,team,supplement)
        if self.frames and self.frames[-1]['at']>cursor(pre_cursor):raise ValueError('Future action/observation cannot enter prediction')
        if self.frames and round_number<self.frames[-1]['round']:raise ValueError('Current round precedes history')
        pos=observation['own'].get('position');history=np.zeros((32,len(self.labels)+9),np.float32)
        for i,frame in enumerate(self.frames,32-len(self.frames)):
            history[i]=history_vector((frame['at'],frame['kind'],frame['step'],frame['round']),round_number,pos,self.labels)
            if self.labels[frame['kind']] not in SPATIAL+['end']:history[i,len(self.labels)+1:len(self.labels)+3]=0
        previous=self.frames[-16:];obs=np.zeros((16,len(self.mean)),np.float32);gaps=np.zeros((16,5),np.float32)
        for i,frame in enumerate(previous,16-len(previous)):
            available=frame['observation'] is not None
            if available:obs[i]=frame['observation']
            following=previous[i-(16-len(previous))+1] if i<15 else dict(round=round_number,turn=own_turn)
            gap=following['round']-frame['round'];age=round_number-frame['round']
            if gap<0 or age<0:raise ValueError('Negative elapsed time')
            gaps[i]=[1,float(available),min(gap,100)/100,float(following['turn']!=frame['turn']),min(age,100)/100]
        current=torch.from_numpy(encode(observation,supplement,route,round_number))
        return ((current-self.mean)/self.std)[None],torch.from_numpy(history)[None],((torch.from_numpy(obs)-self.mean)/self.std)[None],torch.from_numpy(gaps)[None]

    @torch.no_grad()
    def predict(self,observation,supplement,route,round_number,own_turn,pre_cursor):
        logits,context=self.model(*self.inputs(observation,supplement,route,round_number,own_turn,pre_cursor))
        probability=logits[0].softmax(-1);family=int(probability.argmax());name=self.labels[family]
        result=dict(action=name,action_probabilities=dict(zip(self.labels,probability.tolist())),parameter=None,
                    available_history=sum(f['observation'] is not None for f in self.frames[-16:]),
                    present_history=min(len(self.frames),16),full_engine_legality='unassessed')
        if name in SPATIAL:
            last=None
            if self.last_move:last=np.array([self.last_move['to'][a]-self.last_move['from'][a] for a in ('x','y')])
            grid,valid,_=candidate_grid(observation,supplement,route,last);own=observation['own'];props=own.get('abilityProps',[{},{}])
            rules=torch.tensor([[own.get('attackRange',0),props[0].get('range',0),props[1].get('range',0),props[0].get('target',0),props[1].get('target',0)]],dtype=torch.float32)
            p=self.model.parameter_logits(context,torch.from_numpy(grid.astype(np.float16)).float()[None],
                torch.from_numpy(valid)[None],torch.tensor([family]),rules)[0].softmax(-1)
            index=int(p.argmax());pos=own.get('position')
            if index<289 and point(pos):result['parameter']=dict(position=dict(x=pos['x']+int(OFFSETS[index,0]),y=pos['y']+int(OFFSETS[index,1])),conditional_probability=float(p[index]))
            else:result['parameter']=dict(unassessed=True,reason='Outside coordinate window or unknown actor position')
        elif name=='priority':result['parameter']=dict(priority=int((self.model.priority(context)[0,0]*100).round()))
        elif name=='shop':result['parameter']=dict(unassessed=True,reason='Original item/count unavailable')
        return result
