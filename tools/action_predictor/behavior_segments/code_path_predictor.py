"""Experimental code-and-current-geometry conditional movement predictor."""
import torch
from .expanded_code_predictor import ExpandedCodePredictor
from . import code_path_fit as fit,model
from .code_path_movement import candidate_features


class CodePathPredictor(ExpandedCodePredictor):
    def __init__(self,arm='predicted'):
        if arm not in fit.ARMS:raise ValueError('Unknown movement arm')
        super().__init__();fit.check(fit.read(fit.REPORT/'result.json'))
        plan=fit.read(fit.REPORT/'plan.json');fit.check(plan);self.net=fit.policy(arm,plan,self.plan)

    @torch.no_grad()
    def predict(self,current,route,round_number,previous=None,previous_mask=None,state=None):
        geometry=candidate_features(current,route)[None];captured=[]
        def inject(module,args,kwargs):return args,dict(kwargs,geometry=geometry)
        pre=self.net.register_forward_pre_hook(inject,with_kwargs=True)
        post=self.net.register_forward_hook(lambda module,args,value:captured.append(value['move'][0]))
        try:value=super().predict(current,route,round_number,previous,previous_mask,state)
        finally:pre.remove();post.remove()
        support,_=model.move_support(dict(steps=[dict(observed=current is not None,input=current,movement=None)]))
        value['conditional_movement']=None;value['movement_probabilities']=None
        if support.any():
            probabilities=captured[0].masked_fill(~support[0],-1e9).softmax(-1);dx,dy=model.OFFSETS[int(probabilities.argmax())]
            p=current['observation']['own']['position'];value['conditional_movement']=(p['x']+dx,p['y']+dy)
            value['movement_probabilities']=probabilities.tolist()
        value['movement_scope']='Destination conditional on choosing move; this does not select a command family.'
        return value
