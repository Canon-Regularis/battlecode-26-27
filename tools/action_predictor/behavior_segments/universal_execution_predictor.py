"""Opt-in goal planner with a learned correction when its selector abstains."""
import torch
from .goal_execution_edit_predictor import CalibratedGoalExecutor
from . import universal_execution_fit as fit
from .model import OFFSETS


class UniversalExecutionPlanner(CalibratedGoalExecutor):
    def __init__(self):
        super().__init__();p,_,_,_,_=fit.inputs();fit.check(fit.read(fit.REPORT/'result.json'));self.fallback=fit.prior.new('control',p);self.fallback.load_state_dict(torch.load(fit.WORK/'selected.pt',weights_only=True));self.fallback.eval()

    @torch.no_grad()
    def predict(self,*args,**kwargs):
        states=[];calls=[];h=self.net.parent.parent.backbone.code.register_forward_pre_hook(lambda module,a:states.append(a[0]));post=self.net.register_forward_hook(lambda module,a,k,out:calls.append((k,out)),with_kwargs=True)
        try:value=super().predict(*args,**kwargs)
        finally:h.remove();post.remove()
        current=args[0] if args else kwargs['current'];value['fallback_execution_used']=False
        if value['objective'] is None and value['conditional_movement'] is not None:
            encoded,out=calls[0];x=fit.prior.waypoint.features(states[0][0],out['code'][0].softmax(-1),encoded['geometry'][0],encoded['heading'][0],encoded['command_heading'][0]);own=current['observation']['own']['position'];support=torch.zeros(9,dtype=torch.bool);support[4]=True
            for q in current['supplement']['movement']:
                delta=(q['x']-own['x'],q['y']-own['y'])
                if delta in OFFSETS:support[OFFSETS.index(delta)]=True
            probability=self.fallback(x,torch.zeros(9,8),out['move'][0]).masked_fill(~support,-1e9).softmax(-1);dx,dy=OFFSETS[int(probability.argmax())]
            value['goal_conditioned_movement']=(own['x']+dx,own['y']+dy);value['goal_conditioned_probabilities']=probability.tolist();value['objective_movement']=value['goal_conditioned_movement'];value['fallback_execution_used']=True
        value['execution_scope']='Predicted-goal executor when active; learned causal fallback otherwise. Experimental, not promoted.'
        return value
