"""Opt-in jointly adapted recurrent/movement weights with the existing interface."""
from .code_path_predictor import CodePathPredictor
from . import joint_movement_fit as fit


class JointMovementPredictor(CodePathPredictor):
    def __init__(self):
        super().__init__('predicted');result=fit.read(fit.REPORT/'result.json');fit.check(result)
        plan=fit.read(fit.REPORT/'plan.json');fit.check(plan);self.net=fit.policy(plan,self.plan)
        self.movement_target_met=result['target_met']
