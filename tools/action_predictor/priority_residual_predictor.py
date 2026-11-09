"""Offline P05 inference; exact causal anchors never reconstructed from floats."""
import torch
from .priority_predictor import PriorityPredictor
from .priority_modes_predictor import PriorityModesPredictor
from .priority_residual_modes import AnchoredPriorityModes
from .more_replays import sha
from .rich_data import SPATIAL
from .targets import OFFSETS


class PriorityResidualPredictor(PriorityModesPredictor):
    def __init__(self,baseline,normalization,vocabulary,head_checkpoint=None,actor=None):
        PriorityPredictor.__init__(self,baseline,normalization,actor=actor)
        v=vocabulary
        self.head=AnchoredPriorityModes(self.model.priority,v['absolute'],v['absolute_counts'],v['residual'],v['residual_counts'])
        if head_checkpoint is not None:
            saved=torch.load(head_checkpoint,weights_only=True,map_location='cpu')
            assert saved['architecture']=='frozen-M01-priority-anchored-modes-v1'
            assert saved['baseline_sha256']==sha(baseline)
            assert torch.equal(saved['extra_mean'],self.extra_mean) and torch.equal(saved['extra_std'],self.extra_std)
            for key in ('absolute','residual'):assert torch.equal(saved['head_state'][key],getattr(self.head,key))
            self.head.load_state_dict(saved['head_state'])
        self.head.eval()

    def inputs(self,observation,supplement,route,round_number,pre_cursor,priority_state):
        result=super().inputs(observation,supplement,route,round_number,pre_cursor,priority_state)
        values,_=self.memory.inputs(priority_state,pre_cursor,round_number)
        result['priority_values']=torch.from_numpy(values[None])
        return result

    def predict(self,observation,supplement,route,round_number,pre_cursor,priority_state):
        inputs=self.inputs(observation,supplement,route,round_number,pre_cursor,priority_state)
        output=self.distributions(inputs)
        name=self.labels[int(output['action'][0].argmax())]
        result=dict(action=name,action_probabilities=dict(zip(self.labels,output['action'][0].tolist())),parameter=None,full_engine_legality='unassessed')
        if name in SPATIAL:
            index=int(output['coordinate'][0].argmax());pos=observation['own'].get('position')
            if index<289 and pos is not None:
                result['parameter']=dict(position=dict(x=pos['x']+int(OFFSETS[index,0]),y=pos['y']+int(OFFSETS[index,1])),conditional_probability=float(output['coordinate'][0,index]))
            else:result['parameter']=dict(unassessed=True,reason='Outside coordinate window or missing own position')
        elif name=='priority':result['parameter']=dict(priority=int(self.head.integer(output['priority_raw'],inputs['priority_values'])[0]))
        elif name=='shop':result['parameter']=dict(unassessed=True,reason='Original purchase arguments not verified')
        return result
