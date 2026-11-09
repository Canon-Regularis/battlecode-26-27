"""Opt-in executor; only the causal V62 selector supplies runtime goals."""
import torch
from .planner_weight_predictor import EditedPlannerPredictor
from . import goal_execution_fit as fit
from .goal_execution import goal_geometry
from .model import OFFSETS


class GoalExecutionPlanner(EditedPlannerPredictor):
    def __init__(self,arm='goal'):
        if arm not in fit.ARMS:raise ValueError('Unknown execution arm')
        super().__init__();p,_,_,_,_=fit.inputs();fit.check(fit.read(fit.REPORT/'result.json'));self.executor=fit.new(arm,p)
        self.executor.load_state_dict(torch.load(fit.WORK/(arm+'-selected.pt'),weights_only=True));self.executor.eval();self.execution_arm=arm

    @torch.no_grad()
    def predict(self,*args,**kwargs):
        states=[];calls=[];h=self.net.parent.parent.backbone.code.register_forward_pre_hook(lambda module,a:states.append(a[0]))
        post=self.net.register_forward_hook(lambda module,a,k,out:calls.append((k,out)),with_kwargs=True)
        try:value=super().predict(*args,**kwargs)
        finally:h.remove();post.remove()
        value['routed_objective_movement']=value['objective_movement'];value['goal_conditioned_movement']=value['conditional_movement'];value['goal_conditioned_probabilities']=value['movement_probabilities']
        current=args[0] if args else kwargs['current'];route=args[1] if len(args)>1 else kwargs['route'];goal=value['objective']
        if goal is not None:
            encoded,out=calls[0];x=fit.waypoint.features(states[0][0],out['code'][0].softmax(-1),encoded['geometry'][0],encoded['heading'][0],encoded['command_heading'][0]);g=goal_geometry(current,route,goal['goal'],goal['radius'])
            if g is None:raise ValueError('Selected goal lacks current geometry')
            own=current['observation']['own']['position'];support=torch.zeros(9,dtype=torch.bool);support[4]=True
            for q in current['supplement']['movement']:
                delta=(q['x']-own['x'],q['y']-own['y'])
                if delta in OFFSETS:support[OFFSETS.index(delta)]=True
            probabilities=self.executor(x,g,out['move'][0]).masked_fill(~support,-1e9).softmax(-1);dx,dy=OFFSETS[int(probabilities.argmax())]
            value['goal_conditioned_movement']=(own['x']+dx,own['y']+dy);value['goal_conditioned_probabilities']=probabilities.tolist()
        value['objective_movement']=value['goal_conditioned_movement'];value['execution_scope']='Predicted goals only; replay future goals are never runtime inputs. Experimental, not promoted.'
        return value
