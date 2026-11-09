import torch
from .goal_execution_predictor import GoalExecutionPlanner
from .bounded_goal_execution import BoundedGoalExecutor
from . import bounded_goal_execution_fit as fit


class BoundedGoalPlanner(GoalExecutionPlanner):
    def __init__(self):
        super().__init__('goal');fit.inputs();fit.check(fit.read(fit.REPORT/'result.json'));self.executor=BoundedGoalExecutor(True)
        self.executor.load_state_dict(torch.load(fit.WORK/'selected.pt',weights_only=True));self.executor.eval()
