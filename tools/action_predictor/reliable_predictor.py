"""Replay-oriented inference for a locked V4 model; no SDK actions are executed."""
import numpy as np
import torch

from .audit import cursor
from .data import features
from .reliable_model import JointModel
from .rich_data import extra_features,history_vector,candidate_grid,SPATIAL
from .targets import OFFSETS


class ReliablePredictor:
    def __init__(self,checkpoint,actor=None):
        saved=torch.load(checkpoint,map_location='cpu',weights_only=True)
        self.labels=saved['labels'];self.config=saved['config'];self.mean=saved['mean'];self.std=saved['std']
        self.model=JointModel(len(self.mean),len(self.labels)+9,len(self.labels),self.config)
        self.model.load_state_dict(saved['state_dict']);self.model.eval()
        self.actor=actor;self.events=[];self.last_move=None

    def observe(self,event_cursor,step,round_number):
        """Append an action after it was actually observed; never append a forecast."""
        if self.actor is None or step['actor']!={'kind':1,'index':self.actor}:
            raise ValueError('History must belong to this predictor actor')
        at=cursor(event_cursor)
        if self.events and at<=self.events[-1][0]:
            raise ValueError('Observed history must be strictly chronological')
        roots={4:'move',5:'attack',6:'cast',8:'end',9:'priority',11:'recall',12:'submit',13:'shop',14:'ward',16:'cancel',20:'altar',21:'teleport',23:'blocked'}
        name=roots.get(step['kind'],'<unknown>')
        if name=='cast':name=f'cast_{step["abilitySlot"]}'
        self.events.append((at,self.labels.index(name),step,round_number))
        if step['kind']==4:self.last_move=step
        self.events=self.events[-32:]

    @torch.no_grad()
    def predict(self,observation,supplement,route,round_number,pre_cursor):
        if supplement['pre']!=pre_cursor:
            raise ValueError('Supplement is not at the same PRE cursor')
        actor=observation['own']['entity']['index']
        if self.actor is None:self.actor=actor
        if self.actor!=actor:raise ValueError('Do not mix actors in one predictor')
        if self.events and self.events[-1][0]>cursor(pre_cursor):
            raise ValueError('Future observed action cannot enter a prediction')
        basic,_=features(observation);extra,_=extra_features(observation,supplement,route,round_number)
        x=np.concatenate((basic,extra))[:len(self.mean)]
        history=np.zeros((32,len(self.labels)+9),dtype=np.float32)
        for i,e in enumerate(self.events):history[32-len(self.events)+i]=history_vector(e,round_number,observation['own'].get('position'),self.labels)
        for i,e in enumerate(self.events):
            if self.labels[e[1]] not in SPATIAL+['end']:
                history[32-len(self.events)+i,len(self.labels)+1:len(self.labels)+3]=0
        last=None
        if self.last_move:
            step=self.last_move;last=np.array([step['to']['x']-step['from']['x'],step['to']['y']-step['from']['y']])
        grid,valid,_=candidate_grid(observation,supplement,route,last)
        logits,context=self.model(((torch.from_numpy(x)-self.mean)/self.std)[None],torch.from_numpy(history)[None])
        probability=logits[0].softmax(-1);family=int(probability.argmax());name=self.labels[family]
        result=dict(action=name,action_probabilities=dict(zip(self.labels,probability.tolist())),parameter=None)
        if name in SPATIAL:
            own=observation['own'];props=own.get('abilityProps',[{},{}])
            rules=torch.tensor([[own.get('attackRange',0),props[0].get('range',0),props[1].get('range',0),props[0].get('target',0),props[1].get('target',0)]],dtype=torch.float32)
            lp=self.model.parameter_logits(context,torch.from_numpy(grid)[None],torch.from_numpy(valid)[None],torch.tensor([family]),rules)[0].softmax(-1)
            index=int(lp.argmax());pos=observation['own'].get('position')
            if index<289 and pos:
                result['parameter']=dict(position={'x':pos['x']+int(OFFSETS[index,0]),'y':pos['y']+int(OFFSETS[index,1])},conditional_probability=float(lp[index]))
            else:result['parameter']=dict(unassessed=True,reason='outside coordinate window or missing actor position')
        elif name=='priority':result['parameter']=dict(priority=int((self.model.priority(context)[0,0]*100).round()))
        elif name=='shop':result['parameter']=dict(unassessed=True,reason='Original item/count unidentifiable in root events')
        result['full_engine_legality']='unassessed'
        return result
