"""Offline mode-head inference using the unchanged causal V3 input builder."""
import torch
from .priority_predictor import PriorityPredictor
from .priority_modes import AbsolutePriorityModes
from .rich_data import SPATIAL
from .targets import OFFSETS
from .more_replays import sha


class PriorityModesPredictor(PriorityPredictor):
    def __init__(self,baseline,normalization,values,counts,head_checkpoint=None,actor=None):
        super().__init__(baseline,normalization,actor=actor)
        self.head=AbsolutePriorityModes(self.model.priority,values,counts,True)
        if head_checkpoint is not None:
            saved=torch.load(head_checkpoint,weights_only=True,map_location='cpu')
            assert saved['architecture']=='frozen-M01-priority-absolute-modes-v1'
            assert saved['baseline_sha256']==sha(baseline)
            assert torch.equal(saved['extra_mean'],self.extra_mean) and torch.equal(saved['extra_std'],self.extra_std)
            assert torch.equal(saved['head_state']['values'],self.head.values)
            self.head.load_state_dict(saved['head_state'])
        self.head.eval()

    def predict(self,observation,supplement,route,round_number,pre_cursor,priority_state):
        inputs=self.inputs(observation,supplement,route,round_number,pre_cursor,priority_state)
        output=self.distributions(inputs)
        family=int(output['action'][0].argmax());name=self.labels[family]
        result=dict(action=name,action_probabilities=dict(zip(self.labels,output['action'][0].tolist())),parameter=None,full_engine_legality='unassessed')
        if name in SPATIAL:
            index=int(output['coordinate'][0].argmax());pos=observation['own'].get('position')
            if index<289 and pos is not None:
                result['parameter']=dict(position=dict(x=pos['x']+int(OFFSETS[index,0]),y=pos['y']+int(OFFSETS[index,1])),conditional_probability=float(output['coordinate'][0,index]))
            else:result['parameter']=dict(unassessed=True,reason='Outside coordinate window or missing own position')
        elif name=='priority':result['parameter']=dict(priority=int(self.head.integer(output['priority_raw'])[0]))
        elif name=='shop':result['parameter']=dict(unassessed=True,reason='Original purchase arguments not verified')
        return result
