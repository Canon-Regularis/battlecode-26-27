"""Read-only causal V10 inference. Never executes or simulates a game command."""
import numpy as np
import torch
from .algorithmic.library import emit,NAMES
from .algorithmic_fit import Selector,decode
from .observation_data import compact_supplement,encode
from .audit import cursor
from .data import digest

def command_table(observation,supplement,route):
    # Reject arbitrary supplement fields at the boundary, including transactions.
    s=compact_supplement(supplement)
    result=np.full((len(NAMES),3),-1,np.int64)
    for j,c in enumerate(emit(observation,s,route,simple=True)):
        if c is None:continue
        family,pos,value=c;coord=-1
        if pos is not None:
            p=observation['own']['position'];dx,dy=pos[0]-p['x'],pos[1]-p['y']
            if max(abs(dx),abs(dy))>8:continue
            coord=(dy+8)*17+dx+8
        from .reliable_train import LABELS
        result[j]=[LABELS.index(family),coord,value]
    return result

class AlgorithmicPredictor:
    def __init__(self,fallback,checkpoint,expected_sha256):
        assert digest(checkpoint)==expected_sha256
        self.fallback=fallback;saved=torch.load(checkpoint,weights_only=False,map_location='cpu')
        self.mean=saved['mean'];self.std=saved['std'];self.model=Selector(len(self.mean));self.model.load_state_dict(saved['state']);self.model.eval()

    def observe(self,event,step,round_number):self.fallback.observe(event,step,round_number)

    @torch.no_grad()
    def predict(self,observation,supplement,route,round_number,pre_cursor,priority_state):
        s=compact_supplement(supplement)
        if self.fallback.events and self.fallback.events[-1][0]>cursor(pre_cursor):raise ValueError('Future own-action history')
        inputs=self.fallback.inputs(observation,s,route,round_number,pre_cursor,priority_state)
        current=encode(observation,s,route,round_number)
        x=np.concatenate((current,inputs['history'][0,-8:].numpy().reshape(-1)))
        commands=command_table(observation,s,route);available=torch.from_numpy(np.r_[True,commands[:,0]>=0])[None]
        weights=self.model(torch.from_numpy(np.clip((x-self.mean)/self.std,-10,10))[None],available).exp().numpy()
        distributions=self.fallback.distributions(inputs);family=int(distributions['action'].argmax());coordinate=int(distributions['coordinate'].argmax());priority=int(self.fallback.head.integer(distributions['priority_raw'],inputs['priority_values'])[0])
        baseline=dict(prediction=np.array([family]),proposed_coordinate=np.array([coordinate]),priority=np.array([priority]))
        prediction,routed=decode(weights,dict(baseline=baseline,c=commands[None]))
        return dict(prediction=prediction,used_fallback=bool(routed[0]),weights=weights[0],selector_features=x,commands=commands,baseline=baseline,full_engine_legality='unassessed')
