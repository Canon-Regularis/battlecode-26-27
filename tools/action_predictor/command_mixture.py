"""One probability contract for observed-command likelihood and MAP decoding.

P(c|x) = w0 Q(c|x) + sum_j wj 1[c == point_j]. The fallback is a
distribution, never an opaque routing option. Shops remain a marginalized
observed bucket, not complete original purchase commands; entity coordinates
retain the benchmark's identity limitation.
"""
import numpy as np
import torch
from .proposal_generator import SPATIAL
from . import reliable_train as rt

SPATIAL_CODES=tuple(rt.LABELS.index(a) for a in SPATIAL)

def canonical(commands):
    c=np.array(commands,dtype=np.int64,copy=True)
    c[...,1]=np.where(np.isin(c[...,0],SPATIAL_CODES),c[...,1],-1)
    c[...,2]=np.where(c[...,0]==9,c[...,2],0)
    return c

def target_commands(y,coordinate,priority):
    return canonical(np.stack((y,coordinate,priority),-1))

def agreement(points,target):
    return ((canonical(points)==canonical(target)[:,None]).all(-1)) & (points[:,:,0]>=0)

def log_mass(log_weights,point_matches,fallback_logq):
    """Differentiable observed likelihood; equivalent explanations marginalized."""
    mass=torch.cat((fallback_logq.double()[:,None],torch.where(point_matches,0.,-torch.inf).double()),-1)
    return torch.logsumexp(log_weights.double()+mass,-1)

class FallbackDistribution:
    """Batch joint Q; shared by training-cache generation and raw PRE serving."""
    def __init__(self,predictor,inputs):
        self.predictor=predictor;self.inputs=inputs
        model=predictor.model;logits,self.context=model(inputs['x'],inputs['history'])
        self.types=logits.double().log_softmax(-1)
        self.encoded=predictor.movement.encode(inputs['x'],inputs['history'],self.context)
        self.spatial={}
        for family in SPATIAL_CODES:
            codes=torch.full((len(logits),),family,dtype=torch.int64)
            self.spatial[family]=predictor.movement.parameter_log_probs(self.encoded,inputs['grid'],inputs['valid'],codes,inputs['rules'])[0].double() if family in (3,8) else model.parameter_logits(self.context,inputs['grid'],inputs['valid'],codes,inputs['rules']).double().log_softmax(-1)
        self.priority_raw=predictor.head(self.context,inputs['extra'])

    def log_prob(self,commands):
        c=canonical(commands);out=np.full(c.shape[:2],-np.inf,np.float64)
        for family in range(len(rt.LABELS)):
            rows,cols=np.where(c[:,:,0]==family)
            if not len(rows):continue
            lp=self.types[rows,family].clone()
            if family in SPATIAL_CODES:
                coordinates=c[rows,cols,1];ok=(coordinates>=0)&(coordinates<self.spatial[family].shape[1])
                lp[~ok]=-torch.inf
                lp[ok]+=self.spatial[family][rows[ok],coordinates[ok]]
            elif family==9:
                lp+=self.predictor.head.log_mass(self.priority_raw[rows],torch.from_numpy(c[rows,cols,2]),self.inputs['priority_values'][rows])
            out[rows,cols]=lp.numpy()
        return out

    def modes(self):
        """One global conditional mode per family, computed without any answer.

        Spatial support is the model's complete 291-bucket distribution. P05's
        candidate_log_masses includes every atomic mode plus both nearest
        logistic-center integers; outside these the logistic mass is no larger.
        """
        n=len(self.types);c=np.zeros((n,len(rt.LABELS),3),np.int64);c[:,:,0]=np.arange(len(rt.LABELS));c[:,:,1]=-1
        for family in SPATIAL_CODES:c[:,family,1]=self.spatial[family].argmax(-1).numpy()
        c[:,9,2]=self.predictor.head.integer(self.priority_raw,self.inputs['priority_values']).numpy()
        return c,self.log_prob(c)

def decode(log_weights,points,point_logq,modes,mode_logq,return_families=False):
    """Exact MAP in the modeled observed representation, deterministic ties.

    Every command outside the finite point set has probability w0 Q(c); its
    maximum occurs at a family mode (or is dominated by a point at that mode).
    Thus points union all family modes suffices; no destination enumeration.
    """
    points=canonical(points);modes=canonical(modes);out=[];confidence=[];fraction=[];families=[]
    for i in range(len(points)):
        group={}
        for j,c in enumerate(points[i]):
            if c[0]>=0:
                key=tuple(c);group[key]=np.logaddexp(group.get(key,-np.inf),float(log_weights[i,j+1]))
        options={}
        for c,q in zip(np.concatenate((points[i],modes[i])),np.r_[point_logq[i],mode_logq[i]]):
            if c[0]>=0:
                key=tuple(c);options[key]=np.logaddexp(float(log_weights[i,0])+q,group.get(key,-np.inf))
        winner=min(options,key=lambda c:(-options[c],c));out.append(winner);confidence.append(options[winner]);fraction.append(float(np.exp(group.get(winner,-np.inf)-options[winner])))
        if return_families:
            families.append([min((c for c in options if c[0]==k),key=lambda c:(-options[c],c)) for k in range(len(rt.LABELS))])
    result=(np.asarray(out,np.int64),np.asarray(confidence),np.asarray(fraction))
    return (*result,np.asarray(families,np.int64)) if return_families else result
