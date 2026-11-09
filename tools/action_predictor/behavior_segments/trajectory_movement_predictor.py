"""Opt-in joint trajectory weights with the same prior-command interface."""
from .command_movement_predictor import CommandMovementPredictor
from .expanded_code_predictor import ExpandedCodePredictor
from . import trajectory_movement_fit as fit


class TrajectoryMovementPredictor(CommandMovementPredictor):
    def __init__(self):
        ExpandedCodePredictor.__init__(self)
        plan,parent,architecture,_,_=fit.inputs();fit.check(fit.read(fit.REPORT/'result.json'))
        self.net=fit.policy(plan,parent,architecture);self.movement_target_met=fit.read(fit.REPORT/'result.json')['target_met']
