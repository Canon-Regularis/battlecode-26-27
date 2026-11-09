"""Conditional movement with explicitly supplied completed-turn moves."""
import torch
from .heading_movement_predictor import HeadingMovementPredictor
from .expanded_code_predictor import ExpandedCodePredictor
from .command_movement import command_step
from . import command_movement_fit as fit


class CommandMovementPredictor(HeadingMovementPredictor):
    def __init__(self):
        ExpandedCodePredictor.__init__(self)
        plan,parent,architecture,_,_=fit.inputs();fit.check(fit.read(fit.REPORT/'result.json'))
        self.net=fit.policy(plan,parent,architecture);self.movement_target_met=fit.read(fit.REPORT/'result.json')['target_met']

    @torch.no_grad()
    def predict(self,current,route,round_number,previous=None,previous_mask=None,state=None,*,previous_moves=None):
        actor=None if current is None else current['observation']['own']['entity']
        if state is not None and (state['turns']>=32 or actor is not None and state.get('actor') is not None and actor!=state['actor']):state=None
        features,history=command_step([] if state is None else previous_moves,None if state is None else state.get('command_history'))
        hook=self.net.register_forward_pre_hook(lambda module,args,kwargs:(args,dict(kwargs,command_heading=features[None])),with_kwargs=True)
        try:value=super().predict(current,route,round_number,previous,previous_mask,state)
        finally:hook.remove()
        value['state']['command_history']=history;return value
