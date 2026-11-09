from .code_path_predictor import CodePathPredictor
from . import full_movement_fit as fit


class FullMovementPredictor(CodePathPredictor):
    def __init__(self):
        super().__init__('predicted');result=fit.read(fit.REPORT/'result.json');fit.check(result)
        plan,parent,architecture,cache,ids=fit.inputs();self.net=fit.policy(plan,parent,architecture)
        self.movement_target_met=result['target_met']
