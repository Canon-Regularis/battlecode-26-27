"""Experimental eight-turn waypoint candidate; original direct movement preserved."""
import torch
from .trajectory_movement_predictor import TrajectoryMovementPredictor
from . import strategic_waypoint_fit as fit
from .strategic_waypoint import features,reachable_goal,route_move,commitment


class StrategicWaypointPredictor(TrajectoryMovementPredictor):
    def __init__(self):
        super().__init__();self.waypoint_head,self.net=fit.loaded()

    @torch.no_grad()
    def predict(self,*args,**kwargs):
        previous_state=args[5] if len(args)>5 else kwargs.get('state')
        states=[];capture=[]
        hook=self.net.parent.parent.backbone.code.register_forward_pre_hook(lambda module,args:states.append(args[0]))
        post=self.net.register_forward_hook(lambda module,args,kw,out:capture.append((kw,out)),with_kwargs=True)
        try:value=super().predict(*args,**kwargs)
        finally:hook.remove();post.remove()
        current=args[0] if args else kwargs['current'];route=args[1] if len(args)>1 else kwargs['route'];value['strategic_waypoint']=None;value['goal_guided_movement']=None
        prior=None if previous_state is None or value['state']['turns']==1 else previous_state.get('waypoint_commitment')
        value['committed_waypoint']=None;value['committed_movement']=None
        if current is not None and current['observation']['own'].get('position') is not None:
            kw,out=capture[0];x=features(states[0],out['code'].softmax(-1),kw['geometry'],kw['heading'],kw['command_heading'])
            p=current['observation']['own']['position'];goal=reachable_goal((p['x'],p['y']),self.waypoint_head(x)[0],route)
            value['strategic_waypoint']=goal;value['goal_guided_movement']=route_move(current,route,goal,value['conditional_movement'])
            committed,prior=commitment((p['x'],p['y']),goal,prior)
            value['committed_waypoint']=committed;value['committed_movement']=route_move(current,route,committed,value['conditional_movement'])
        elif current is not None:prior=None
        elif prior is not None:prior=dict(prior,remaining=prior['remaining']-1)
        value['state']['waypoint_commitment']=prior
        value['strategy_scope']='Experimental eight-own-turn waypoint and A* candidate; not verified internal intent or autonomous strategy. Direct movement is preserved.'
        return value
