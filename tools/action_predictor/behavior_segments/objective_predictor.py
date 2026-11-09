"""Experimental learned objective selection and abandonment; V59 stays available."""
import torch
from .trajectory_movement_predictor import TrajectoryMovementPredictor
from . import objective_experiment as fit
from .objective_policy import candidates,choose,movement
from .model import OFFSETS


class ObjectivePredictor(TrajectoryMovementPredictor):
    def __init__(self):
        super().__init__();p,_,_,_,_=fit.inputs();fit.check(fit.read(fit.REPORT/'fit.json'))
        self.objectives=fit.new(p);self.objectives.load_state_dict(torch.load(fit.WORK/'selected.pt',weights_only=True));self.objectives.eval();self.margin=p['margin']

    @torch.no_grad()
    def predict(self,*args,**kwargs):
        old=args[5] if len(args)>5 else kwargs.get('state');states=[];outputs=[]
        h=self.net.parent.parent.backbone.code.register_forward_pre_hook(lambda module,args:states.append(args[0]))
        post=self.net.register_forward_hook(lambda module,args,out:outputs.append(out))
        try:value=super().predict(*args,**kwargs)
        finally:h.remove();post.remove()
        current=args[0] if args else kwargs['current'];route=args[1] if len(args)>1 else kwargs['route']
        remembered=None if old is None or value['state']['turns']==1 else old.get('objective_identity')
        cs=candidates(current,route);scores=[]
        if cs:
            context=torch.cat((states[0][0],outputs[0]['code'][0].softmax(-1)))
            scores=self.objectives(torch.stack([torch.cat((context,torch.tensor(c['features']))) for c in cs])).tolist()
        chosen,identity,reason=choose(cs,scores,remembered,self.margin)
        if current is None:identity=remembered;reason='unobserved'
        value['state']['objective_identity']=identity;value['objective']=chosen;value['objective_decision']=reason
        value['objective_movement']=value['conditional_movement'];value['objective_scores']=scores
        if chosen is not None:
            index=movement(chosen,current,route,value['movement_probabilities']);p=current['observation']['own']['position'];dx,dy=OFFSETS[index];value['objective_movement']=(p['x']+dx,p['y']+dy)
        value['objective_scope']='Learned replay progress utility, not verified Fish intent or autonomous strategy; direct movement preserved.'
        return value
