"""A01 personal PRE serving with candidate descriptors; frozen A00 unchanged."""
import numpy as np
import torch
from .algorithmic_conditioned import CandidateSelector,descriptors
from .algorithmic_predictor import command_table
from .algorithmic_fit import decode
from .observation_data import compact_supplement,encode
from .audit import cursor
from .data import digest

class AlgorithmicPredictor:
    def __init__(self,fallback,checkpoint,expected_sha256):
        assert digest(checkpoint)==expected_sha256;self.fallback=fallback;saved=torch.load(checkpoint,weights_only=False,map_location='cpu');self.mean=saved['mean'];self.std=saved['std'];self.model=CandidateSelector(len(self.mean));self.model.load_state_dict(saved['state']);self.model.eval()
    def observe(self,event,step,round_number):self.fallback.observe(event,step,round_number)
    @torch.no_grad()
    def predict(self,observation,supplement,route,round_number,pre_cursor,priority_state):
        s=compact_supplement(supplement)
        if self.fallback.events and self.fallback.events[-1][0]>cursor(pre_cursor):raise ValueError('Future own action history')
        inputs=self.fallback.inputs(observation,s,route,round_number,pre_cursor,priority_state);current=encode(observation,s,route,round_number);x=np.concatenate((current,inputs['history'][0,-8:].numpy().reshape(-1)));commands=command_table(observation,s,route);desc=descriptors(commands[None],inputs['grid'].numpy());available=torch.from_numpy(np.r_[True,commands[:,0]>=0])[None]
        weights=self.model(torch.from_numpy(np.clip((x-self.mean)/self.std,-10,10))[None],available,torch.from_numpy(desc)).exp().numpy();out=self.fallback.distributions(inputs);baseline=dict(prediction=np.array([int(out['action'].argmax())]),proposed_coordinate=np.array([int(out['coordinate'].argmax())]),priority=np.array([int(self.fallback.head.integer(out['priority_raw'],inputs['priority_values'])[0])]))
        prediction,routed=decode(weights,dict(baseline=baseline,c=commands[None]))
        return dict(prediction=prediction,used_fallback=bool(routed[0]),weights=weights[0],selector_features=x,commands=commands,candidate_descriptors=desc[0],baseline=baseline,full_engine_legality='unassessed')
