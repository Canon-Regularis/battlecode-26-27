"""Raw PRE serving for V13: shared Q, repaired proposals and causal goal memory."""
import numpy as np
import torch
from .proposal_predictor import load_proposal_predictor
from .proposal_generator import generate,encode,NAMES,SPATIAL
from .consistent_data import base_features,static_descriptors
from .consistent_study import ConsistentSelector
from .goal_memory import GoalMemory,current_descriptors
from .command_mixture import FallbackDistribution,decode
from .observation_data import encode as encode_observation,compact_supplement
from .data import digest

class ConsistentPredictor:
    def __init__(self,actor,checkpoint=None,expected_sha256=None):
        self.frozen=load_proposal_predictor(actor).frozen;self.memory=GoalMemory();self.model=None
        if checkpoint is not None:
            assert digest(checkpoint)==expected_sha256;saved=torch.load(checkpoint,weights_only=False,map_location='cpu');self.variant=saved['variant'];self.mean=saved['mean'];self.std=saved['std'];self.model=ConsistentSelector();self.model.load_state_dict(saved['state']);self.model.eval()
    def observe(self,event,step,round_number,observation,route):
        self.frozen.observe(event,step,round_number);self.memory.observe(event,step,round_number,observation,route)
    @torch.no_grad()
    def predict(self,observation,supplement,route,round_number,pre,priority_state,personal_targets=None):
        s=compact_supplement(supplement);inputs=self.frozen.inputs(observation,s,route,round_number,pre,priority_state);q=FallbackDistribution(self.frozen,inputs);modes,mode_logq=q.modes()
        conditional=dict(coordinates={a:int(modes[0,self.frozen.labels.index(a),1]) for a in SPATIAL},priority=int(modes[0,9,2]),prefer_blocked=bool(q.types[0,3]>q.types[0,8]))
        bundle=generate(observation,s,route,inputs['history'][0].numpy(),conditional,personal_targets);commands=np.full((len(NAMES),3),-1,np.int64)
        for c in bundle['proposals']:
            value=encode(c,observation['own'].get('position'),self.frozen.labels)
            if value is not None:commands[NAMES.index(c.source)]=value
        current,point,gs=current_descriptors(observation,route,commands);past,belief,best=self.memory.descriptors(gs,round_number,pre,observation['own'].get('position'),commands);features=np.r_[base_features(encode_observation(observation,s,route,round_number),inputs['history'][0].numpy()),current,past]
        desc=np.column_stack((static_descriptors(commands,inputs['grid'][0].numpy()),point,point[:,:5]*belief[None],best)).astype(np.float16)
        if self.model is None:
            # Fixed U00 control also validates the raw serving path before fits.
            available=commands[:,0]>=0;weights=np.r_[.9,.1*available/max(1,available.sum())]
            if not available.any():weights[0]=1
            with np.errstate(divide='ignore'):scores=np.log(weights)[None]
        else:
            x=np.clip((features-self.mean)/self.std,-10,10)[None];d=desc.astype(np.float32)[None]
            if self.variant=='B00':x[:,445:]=0;d[:,:,44:]=0
            elif self.variant=='B01':x[:,485:]=0;d[:,:,54:]=0
            scores=self.model(torch.from_numpy(x),torch.from_numpy(d),torch.from_numpy(np.r_[True,commands[:,0]>=0])[None]).numpy()
        point_logq=q.log_prob(commands[None]);command,confidence,fraction=decode(scores,commands[None],point_logq,modes,mode_logq)
        return dict(command=command[0],command_log_probability=float(confidence[0]),point_probability_fraction=float(fraction[0]),features=features,descriptors=desc,commands=commands,log_weights=scores[0],point_logq=point_logq[0],modes=modes[0],mode_logq=mode_logq[0],Q=q)
