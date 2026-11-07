"""Frequency, persistence and visible-geometry baselines; no test fitting."""
import json
import numpy as np
import torch

from .audit import immutable_json
from .benchmark import REPORTS, WORK
from .reliable_model import priority_log_mass
from .reliable_train import LABELS, load_data, summarize


def fitted(train):
    classes=len(LABELS)
    action=np.bincount(train['y'],minlength=classes).astype(float)+1
    action/=action.sum()
    previous=train['history'][:,-1,:classes].argmax(-1)
    previous[train['history'][:,-1,-1]==0]=classes
    table=np.ones((classes+1,classes))
    np.add.at(table,(previous,train['y']),1)
    table/=table.sum(-1,keepdims=True)
    offsets=np.ones((classes,291))*.1
    chosen=train['py']>=0
    np.add.at(offsets,(train['y'][chosen],train['py'][chosen]),1)
    priority=train['priority'][train['y']==LABELS.index('priority')]
    location=float(np.median(priority)/100)
    scale=max(float(np.std(priority)/180),.01)
    return dict(action=action,transition=table,offsets=offsets,priority_mean=location,priority_scale=scale)


def candidate_choices(raw,family,method):
    grid=raw['grid'].astype(np.float32);valid=raw['valid'].copy()
    n=len(grid);scores=np.zeros((n,289),dtype=np.float32)
    if family=='move':
        valid&=raw['move_mask']
        if method=='persistence':
            scores=grid[:,:,18]*100-grid[:,:,19]
        elif method=='nearest':
            distance=np.where((raw['gems']>0)[:,None],grid[:,:,16],grid[:,:,9])
            scores=-distance*1000+grid[:,:,2]-grid[:,:,19]*.01
        else:
            return None,valid
    elif family=='blocked':
        return None,valid
    elif family in ('attack','cast_0','cast_1'):
        if family=='attack':
            masks=np.full(n,3);radius=raw['attack_range']
        else:
            slot=int(family[-1]);masks=raw['ability_mask'][:,slot];radius=raw['ability_range'][:,slot]
        allowed=np.zeros_like(valid)
        for bit,col in ((1,12),(2,10),(4,11),(8,17)):
            allowed|=((masks&bit)!=0)[:,None]&(grid[:,:,col]>0)
        ground=(masks&16)!=0
        # Ground aim baseline uses current visible enemy/camp cells, or self if absent.
        allowed[ground]=(grid[ground,:,10]+grid[ground,:,12])>0
        empty=~allowed.any(-1)
        allowed[ground&empty]=grid[ground&empty,:,17]>0
        valid&=allowed&(grid[:,:,2]*8<=radius[:,None]+1e-5)
        scores=-grid[:,:,2]
        if method=='lowest-health':
            hp=grid[:,:,13:16].sum(-1)
            scores=-hp*100-grid[:,:,2]
        elif method=='persistence':
            # A simple ground-aim persistence rule; unit casts stay nearest.
            scores[ground]=-grid[ground,:,19]
    elif family in ('submit','altar','teleport'):
        valid&=grid[:,:,16]==0;scores=-grid[:,:,2]
    elif family=='ward':
        scores=-grid[:,:,2]
    else:
        return None,valid
    scores=np.where(valid,scores,-1e9)
    return scores.argmax(-1),valid


def coordinate_probs(raw,families,fit,method,blend):
    probs=fit['offsets'][families].copy()
    probs[:,:289]*=raw['valid']
    probs/=probs.sum(-1,keepdims=True)
    if method!='frequency':
        for family in set(families):
            name=LABELS[int(family)];selected=np.flatnonzero(families==family)
            if name not in ('move','blocked','attack','cast_0','cast_1','ward','submit','altar','teleport'):
                continue
            subset={k:v[selected] for k,v in raw.items() if len(v)==len(families)}
            choice,valid=candidate_choices(subset,name,method)
            if method=='legal-frequency':
                choice=np.where(valid,probs[selected,:289],-1.).argmax(-1)
            if choice is not None:
                has=valid.any(-1);ids=selected[has]
                probs[ids]*=1-blend
                probs[ids,choice[has]]+=blend
    return probs


def predict(raw,fit,action_method,parameter_method,blend=.9):
    n=len(raw['y']);classes=len(LABELS)
    if action_method=='frequency':
        a=np.broadcast_to(fit['action'],(n,classes))
    else:
        previous=raw['history'][:,-1,:classes].argmax(-1)
        previous[raw['history'][:,-1,-1]==0]=classes
        a=fit['transition'][previous]
    prediction=a.argmax(-1)
    conditional=coordinate_probs(raw,raw['y'],fit,parameter_method,blend)
    proposed=coordinate_probs(raw,prediction,fit,parameter_method,blend)
    type_nll=-np.log(a[np.arange(n),raw['y']])
    param_nll=np.zeros(n);spatial=raw['py']>=0
    param_nll[spatial]=-np.log(conditional[np.arange(n)[spatial],raw['py'][spatial]])
    priority=raw['y']==LABELS.index('priority')
    logistic=torch.tensor([[fit['priority_mean'],np.log(fit['priority_scale'])]],dtype=torch.float64).expand(int(priority.sum()),2)
    param_nll[priority]=-priority_log_mass(logistic,torch.from_numpy(raw['priority'][priority])).numpy()
    return dict(prediction=prediction,nll=type_nll+param_nll,type_nll=type_nll,param_nll=param_nll,
                coordinate=conditional.argmax(-1),proposed_coordinate=proposed.argmax(-1),
                top5=np.argsort(-conditional,axis=-1,kind='stable')[:,:5],
                priority=np.full(n,round(fit['priority_mean']*100)))


def run():
    train=load_data('train');val=load_data('validation');fit=fitted(train)
    table={}
    directory=WORK/'baselines';directory.mkdir(parents=True,exist_ok=True)
    for action_method in ('frequency','transition'):
        for parameter_method in ('frequency','persistence','nearest','lowest-health'):
            name=f'{action_method}-{parameter_method}'
            pred=predict(val,fit,action_method,parameter_method)
            table[name]=summarize(val,pred)
            np.savez_compressed(directory/f'{name}-validation.npz',**pred)
    immutable_json(REPORTS/'simple-baselines.json',dict(validation=table,
                   fitted={k:v.tolist() if isinstance(v,np.ndarray) else v for k,v in fit.items()},
                   calibrated_on='Train counts/priority distribution; fixed .9 heuristic probability mass, .1 train-frequency mixture.',
                   observed_untouched_test=False))
    print({k:(v['joint_nll'],v['parameters']['move']['exact_accuracy']) for k,v in table.items()})


def additional():
    train=load_data('train');val=load_data('validation');fit=fitted(train);table={}
    for method in ('frequency','transition'):
        name=method+'-legal-frequency'
        pred=predict(val,fit,method,'legal-frequency')
        table[name]=summarize(val,pred)
        np.savez_compressed(WORK/'baselines'/f'{name}-validation.npz',**pred)
    immutable_json(REPORTS/'additional-simple-baselines.json',dict(validation=table,
        rationale='Add an explicit most-common PRE-valid coordinate baseline, beyond the existing map-valid frequency baseline. No benchmark or target changes; this can only strengthen references.'))


if __name__=='__main__':
    import sys
    torch.set_num_threads(4)
    additional() if '--additional' in sys.argv else run()
