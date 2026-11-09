import torch
from .shared_goal_execution_predictor import SharedExecutionPlanner
from . import shared_readout_fit as fit


class ReadoutSharedPlanner(SharedExecutionPlanner):
    def __init__(self,arm='ranking'):
        if arm not in fit.ARMS:raise ValueError('Unknown readout arm')
        super().__init__('goal');fit.inputs();fit.check(fit.read(fit.REPORT/'result.json'));self.executor.load_state_dict(torch.load(fit.WORK/(arm+'-selected.pt'),weights_only=True));self.execution_arm=arm
