"""Opt-in edited destination weights with the preserved V52 movement model."""
from .code_path_predictor import CodePathPredictor
from . import destination_weight_fit as fit


class DestinationWeightPredictor(CodePathPredictor):
    def __init__(self):
        super().__init__('predicted');fit.check(fit.read(fit.REPORT/'result.json'))
        fit.check(fit.read(fit.REPORT/'plan.json'));self.net=fit.policy(self.plan)
