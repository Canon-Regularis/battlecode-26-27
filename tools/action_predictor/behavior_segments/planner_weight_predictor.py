"""Opt-in calibrated final readout of the combined objective planner."""
import torch
from .objective_predictor import ObjectivePredictor
from . import planner_weight_edit as fit


class EditedPlannerPredictor(ObjectivePredictor):
    def __init__(self):
        super().__init__();fit.inputs();fit.check(fit.read(fit.REPORT/'result.json'))
        self.objectives.load_state_dict(torch.load(fit.WORK/'selected.pt',weights_only=True))
