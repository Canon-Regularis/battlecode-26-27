import torch
from .goal_execution_predictor import GoalExecutionPlanner
from . import goal_execution_edit as fit


class CalibratedGoalExecutor(GoalExecutionPlanner):
    def __init__(self):
        super().__init__('goal');fit.inputs();fit.check(fit.read(fit.REPORT/'result.json'));self.executor.load_state_dict(torch.load(fit.WORK/'selected.pt',weights_only=True))
