"""Offline causal inference for the isolated priority branch; no bot actions."""
import copy
import numpy as np
import torch
from .reliable_predictor import ReliablePredictor
from .priority_inputs import PriorityMemory
from .priority_head import PriorityHead,flatten,quantized_grid
from .observation_data import safe_observation,encode
from .rich_data import history_vector,candidate_grid,SPATIAL
from .targets import OFFSETS
from .more_replays import sha

class PriorityPredictor(ReliablePredictor):
    def __init__(self,baseline,normalization,head_checkpoint=None,use_inputs=False,actor=None):
        super().__init__(baseline,actor=actor);self.team=None
        self.memory=PriorityMemory(actor) if actor is not None else None
        with np.load(normalization) as z:self.extra_mean=torch.from_numpy(z['mean']);self.extra_std=torch.from_numpy(z['std'])
        self.head=PriorityHead(self.model.priority,use_inputs)
        if head_checkpoint is not None:
            saved=torch.load(head_checkpoint,weights_only=True,map_location='cpu')
            assert saved['architecture']=='frozen-M01-priority-logistic-v1' and saved['baseline_sha256']==sha(baseline)
            assert torch.equal(saved['extra_mean'],self.extra_mean) and torch.equal(saved['extra_std'],self.extra_std)
            self.head.use_inputs=saved['config']['use_inputs'];self.head.load_state_dict(saved['head_state'])
        self.head.eval()

    def observe(self,event_cursor,step,round_number):
        if self.actor is None:self.actor=step['actor']['index'];self.memory=PriorityMemory(self.actor)
        frozen_step=copy.deepcopy(step)
        # Both routines validate before altering their streams for ordinary valid replay input.
        self.memory.observe(frozen_step,event_cursor,round_number)
        super().observe(event_cursor,frozen_step,round_number)

    def inputs(self,observation,supplement,route,round_number,pre_cursor,priority_state):
        actor=observation['own']['entity']['index'];team=observation['own']['team']
        if self.actor is None:self.actor=actor;self.memory=PriorityMemory(actor)
        if self.actor!=actor or (self.team is not None and self.team!=team):raise ValueError('Actor/perspective mismatch')
        self.team=team;safe_observation(observation,actor,team,supplement)
        if supplement['pre']!=pre_cursor or priority_state['pre']!=pre_cursor:raise ValueError('PRE mismatch')
        if priority_state['actor']!=actor or priority_state['team']!=team or priority_state['round']!=round_number:raise ValueError('Priority state identity mismatch')
        v,h=self.memory.inputs(priority_state,pre_cursor,round_number)
        extra=(torch.from_numpy(flatten(v[None],h[None]).astype(np.float32))-self.extra_mean)/self.extra_std
        current=torch.from_numpy(encode(observation,supplement,route,round_number))
        history=np.zeros((32,24),np.float32)
        for i,event in enumerate(self.events,32-len(self.events)):
            history[i]=history_vector(event,round_number,observation['own'].get('position'),self.labels)
            if self.labels[event[1]] not in SPATIAL+['end']:history[i,len(self.labels)+1:len(self.labels)+3]=0
        last=None
        if self.last_move:last=np.array([self.last_move['to'][axis]-self.last_move['from'][axis] for axis in ('x','y')])
        grid,valid,_=candidate_grid(observation,supplement,route,last)
        own=observation['own'];props=own.get('abilityProps') or [{},{}]
        rules=torch.tensor([[own.get('attackRange',0),props[0].get('range',0),props[1].get('range',0),props[0].get('target',0),props[1].get('target',0)]],dtype=torch.float32)
        return dict(x=((current-self.mean)/self.std)[None],history=torch.from_numpy(history)[None],extra=extra,
            grid=torch.from_numpy(quantized_grid(grid))[None],valid=torch.from_numpy(valid)[None],rules=rules)

    @torch.no_grad()
    def distributions(self,inputs):
        logits,context=self.model(inputs['x'],inputs['history']);family=logits.argmax(-1)
        parameters=self.model.parameter_logits(context,inputs['grid'],inputs['valid'],family,inputs['rules']).softmax(-1)
        return dict(action=logits.softmax(-1),coordinate=parameters,priority_raw=self.head(context,inputs['extra']),context=context)

    def predict(self,observation,supplement,route,round_number,pre_cursor,priority_state):
        inputs=self.inputs(observation,supplement,route,round_number,pre_cursor,priority_state);output=self.distributions(inputs)
        family=int(output['action'][0].argmax());name=self.labels[family]
        result=dict(action=name,action_probabilities=dict(zip(self.labels,output['action'][0].tolist())),parameter=None,full_engine_legality='unassessed')
        if name in SPATIAL:
            index=int(output['coordinate'][0].argmax());pos=observation['own'].get('position')
            if index<289 and pos is not None:result['parameter']=dict(position=dict(x=pos['x']+int(OFFSETS[index,0]),y=pos['y']+int(OFFSETS[index,1])),conditional_probability=float(output['coordinate'][0,index]))
            else:result['parameter']=dict(unassessed=True,reason='Outside coordinate window or missing own position')
        elif name=='priority':result['parameter']=dict(priority=int((output['priority_raw'][0,0]*100).round()))
        elif name=='shop':result['parameter']=dict(unassessed=True,reason='Original purchase arguments not verified')
        return result
