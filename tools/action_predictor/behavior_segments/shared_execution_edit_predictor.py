import torch
from .shared_goal_execution_predictor import SharedExecutionPlanner
from . import shared_execution_edit as fit


class CalibratedSharedPlanner(SharedExecutionPlanner):
    def __init__(self):
        super().__init__('goal');fit.inputs();fit.check(fit.read(fit.REPORT/'result.json'));self.executor.load_state_dict(torch.load(fit.WORK/'selected.pt',weights_only=True))
