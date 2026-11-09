import torch
from .planner_weight_predictor import EditedPlannerPredictor
from . import map_trajectory_fit as fit


class MapTrajectoryPlanner(EditedPlannerPredictor):
    def __init__(self):
        super().__init__();_,parent,architecture,_,_=fit.inputs();fit.check(fit.read(fit.REPORT/'result.json'))
        net=fit.warm('full',parent,architecture);net.load_state_dict(torch.load(fit.WORK/'selected.pt',weights_only=False)['model']);self.net=fit.base.inference(net)
