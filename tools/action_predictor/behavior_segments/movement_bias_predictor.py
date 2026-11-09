from .code_path_predictor import CodePathPredictor
from . import movement_bias_edit as fit


class MovementBiasPredictor(CodePathPredictor):
    def __init__(self):
        super().__init__('predicted');result=fit.read(fit.REPORT/'result.json');fit.check(result)
        plan,parent,architecture,cache,ids=fit.inputs();self.net=fit.policy(parent,architecture)
        self.movement_target_met=result['target_met']
