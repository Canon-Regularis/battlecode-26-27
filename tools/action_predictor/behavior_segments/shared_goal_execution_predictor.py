"""Causal shared executor: goal availability is an input, not an execution gate."""
import torch
from .planner_weight_predictor import EditedPlannerPredictor
from . import shared_goal_execution_fit as fit
from .shared_goal_execution import optional_goal
from .model import OFFSETS


class SharedExecutionPlanner(EditedPlannerPredictor):
    def __init__(self,arm='goal'):
        if arm not in fit.ARMS:raise ValueError('Unknown shared-executor arm')
        super().__init__();p,_,_,_,_=fit.inputs();fit.check(fit.read(fit.REPORT/'result.json'));self.executor=fit.selected(arm,p);self.execution_arm=arm

    @torch.no_grad()
    def predict(self,*args,**kwargs):
        states=[];calls=[];h=self.net.parent.parent.backbone.code.register_forward_pre_hook(lambda module,a:states.append(a[0]));post=self.net.register_forward_hook(lambda module,a,k,out:calls.append((k,out)),with_kwargs=True)
        try:value=super().predict(*args,**kwargs)
        finally:h.remove();post.remove()
        value['routed_objective_movement']=value['objective_movement'];value['shared_movement']=value['conditional_movement'];value['shared_movement_probabilities']=value['movement_probabilities'];value['shared_execution_used']=False;value['goal_utility']=0.
        current=args[0] if args else kwargs['current'];route=args[1] if len(args)>1 else kwargs['route'];chosen=value['objective']
        if value['conditional_movement'] is not None:
            encoded,out=calls[0];x=fit.prior.waypoint.features(states[0][0],out['code'][0].softmax(-1),encoded['geometry'][0],encoded['heading'][0],encoded['command_heading'][0]);utility=0.
            if chosen is not None:
                cs=fit.prior.candidates(current,route);utility=value['objective_scores'][next(i for i,c in enumerate(cs) if c['key']==chosen['key'])]
            g=optional_goal(current,route,chosen,utility);own=current['observation']['own']['position'];support=torch.zeros(9,dtype=torch.bool);support[4]=True
            for q in current['supplement']['movement']:
                delta=(q['x']-own['x'],q['y']-own['y'])
                if delta in OFFSETS:support[OFFSETS.index(delta)]=True
            probability=self.executor(x,g,out['move'][0]).masked_fill(~support,-1e9).softmax(-1);dx,dy=OFFSETS[int(probability.argmax())]
            value['shared_movement']=(own['x']+dx,own['y']+dy);value['shared_movement_probabilities']=probability.tolist();value['shared_execution_used']=True;value['goal_utility']=utility
        value['objective_movement']=value['shared_movement'];value['goal_conditioned_movement']=value['shared_movement'];value['goal_conditioned_probabilities']=value['shared_movement_probabilities'];value['execution_scope']='One executor on every located movement query; current predicted goals are optional inputs. Experimental, not promoted.'
        return value
