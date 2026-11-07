"""Explicit control inference; the original P03 predictor stays unchanged."""
import torch
from .priority_modes_predictor import PriorityModesPredictor


class PriorityModesControlPredictor(PriorityModesPredictor):
    def __init__(self,baseline,normalization,values,counts,head_checkpoint=None,actor=None):
        if head_checkpoint is not None:
            saved=torch.load(head_checkpoint,weights_only=True,map_location='cpu')
            assert saved['config']['id']=='P04' and saved['config']['use_inputs'] is False,'Not a P04 control checkpoint'
        super().__init__(baseline,normalization,values,counts,head_checkpoint,actor)
        self.head.use_inputs=False
