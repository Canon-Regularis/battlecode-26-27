"""Shared movement execution with a separately trained raw-feature goal selector."""
import torch
from .trajectory_movement_predictor import TrajectoryMovementPredictor
from . import crossfit_goals_fit as fit
from .crossfit_goals import selector_features
from .model import OFFSETS


class CrossfitGoalPlanner(TrajectoryMovementPredictor):
    def __init__(self,arm='crossfit'):
        if arm not in fit.ARMS:raise ValueError('Unknown crossfit arm')
        super().__init__();p,_,_,_,_=fit.inputs();fit.check(fit.read(fit.REPORT/'result.json'));self.objectives=fit.selector('full');self.executor=fit.prior.new('goal',p);self.executor.load_state_dict(torch.load(fit.WORK/(arm+'-selected.pt'),weights_only=True));self.executor.eval();self.execution_arm=arm

    @torch.no_grad()
    def predict(self,*args,**kwargs):
        old=args[5] if len(args)>5 else kwargs.get('state');states=[];calls=[];h=self.net.parent.parent.backbone.code.register_forward_pre_hook(lambda m,a:states.append(a[0]));post=self.net.register_forward_hook(lambda m,a,k,o:calls.append((k,o)),with_kwargs=True)
        try:v=super().predict(*args,**kwargs)
        finally:h.remove();post.remove()
        current=args[0] if args else kwargs['current'];route=args[1] if len(args)>1 else kwargs['route'];remembered=None if old is None or v['state']['turns']==1 else old.get('objective_identity');encoded,out=calls[0];x=fit.prior.prior.waypoint.features(states[0][0],out['code'][0].softmax(-1),encoded['geometry'][0],encoded['heading'][0],encoded['command_heading'][0]);cs=fit.prior.prior.candidates(current,route);scores=self.objectives(torch.stack([selector_features(x[56:],c['features']) for c in cs])).tolist() if cs else [];chosen,identity,reason=fit.prior.prior.choose(cs,scores,remembered,.15)
        if current is None:identity=remembered;reason='unobserved'
        v['state']['objective_identity']=identity;v['objective']=chosen;v['objective_decision']=reason;v['objective_scores']=scores;v['shared_movement']=v['conditional_movement'];v['shared_movement_probabilities']=v['movement_probabilities'];v['shared_execution_used']=False;v['routed_objective_movement']=v['conditional_movement'];v['goal_utility']=0.
        if v['conditional_movement'] is not None:
            utility=0. if chosen is None else scores[next(i for i,c in enumerate(cs) if c['key']==chosen['key'])];g=fit.prior.optional_goal(current,route,chosen,utility);own=current['observation']['own']['position'];support=torch.zeros(9,dtype=torch.bool);support[4]=True
            for q in current['supplement']['movement']:
                delta=(q['x']-own['x'],q['y']-own['y'])
                if delta in OFFSETS:support[OFFSETS.index(delta)]=True
            prob=self.executor(x,g,out['move'][0]).masked_fill(~support,-1e9).softmax(-1);dx,dy=OFFSETS[int(prob.argmax())];v['shared_movement']=(own['x']+dx,own['y']+dy);v['shared_movement_probabilities']=prob.tolist();v['shared_execution_used']=True;v['goal_utility']=utility
            if chosen is not None:
                index=fit.prior.prior.movement(chosen,current,route,v['movement_probabilities']);dx,dy=OFFSETS[index];v['routed_objective_movement']=(own['x']+dx,own['y']+dy)
        v['objective_movement']=v['shared_movement'];v['goal_conditioned_movement']=v['shared_movement'];v['goal_conditioned_probabilities']=v['shared_movement_probabilities'];v['execution_scope']='Raw-feature goal selector,shared executor. Crossfit training excludes each predicted game from goal-model updates. Experimental,not promoted.';return v
