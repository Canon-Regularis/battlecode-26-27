"""Raw personal-PRE inference, using predicted families and causal own history."""
import numpy as np
import torch
from .model import MovementExpert
from ..proposal_predictor import load_proposal_predictor
from ..command_mixture import FallbackDistribution
from ..consistent_data import base_features
from ..observation_data import compact_supplement,encode
from ..goal_memory import current_descriptors
from ..entity_set import encode_entities
from ..data import digest

class Predictor:
    def __init__(self,actor,path,expected):
        assert digest(path)==expected;self.frozen=load_proposal_predictor(actor).frozen;self.saved=torch.load(path,weights_only=False);self.model=MovementExpert(self.saved['mixture'],self.saved['counts']);self.model.load_state_dict(self.saved['state']);self.model.eval()
    def observe(self,event,step,round_number):self.frozen.observe(event,step,round_number)
    @torch.no_grad()
    def predict(self,obs,supplement,route,round_number,pre,priority_state):
        s=compact_supplement(supplement);raw=self.frozen.inputs(obs,s,route,round_number,pre,priority_state);q=FallbackDistribution(self.frozen,raw);modes,logq=q.modes();family=q.types.argmax(-1);command=modes[0,int(family[0])].copy();current,_,_=current_descriptors(obs,route,np.empty((0,3),np.int64));global_=np.r_[q.context[0].numpy(),base_features(encode(obs,s,route,round_number),raw['history'][0].numpy()),current].astype(np.float32);entities=encode_entities(obs);x=torch.from_numpy(np.clip((global_-self.saved['mean'])/self.saved['std'],-10,10)[None]);entity=torch.from_numpy(entities.astype(np.float32)[None]);mask=torch.ones((1,len(entities)),dtype=torch.bool);lp,gate=self.model(x,raw['grid'],raw['valid'],entity,mask,torch.full((1,),8));blocked,bgate=self.model(x,raw['grid'],raw['valid'],entity,mask,torch.full((1,),3))
        if command[0] in (3,8):command[1]=int((lp if command[0]==8 else blocked)[0].argmax())
        return dict(command=command,move_logp=lp[0].numpy(),blocked_logp=blocked[0].numpy(),global_features=global_,entities=entities,grid=raw['grid'][0].numpy(),valid=raw['valid'][0].numpy(),gate_move=gate[0].numpy(),gate_blocked=bgate[0].numpy())
