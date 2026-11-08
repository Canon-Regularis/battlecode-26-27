"""Saved-prediction measures; no checkpoint or hyperparameter decisions."""
import numpy as np
from ..reliable_train import LABELS
from ..observation_metrics import correctness
from .engine import selectors


def masks(raw):
    y=raw['y'];move=y==8
    result={'all':np.ones(len(y),bool),'change':move&(raw['direction']==3),
            'continue':move&(raw['direction']==2),'startup':move&(raw['direction']==1),
            'zero_displacement':move&(raw['direction']==4)}
    result.update({name:y==i for i,name in enumerate(LABELS)})
    return result


def windows(data,size):
    """Nonoverlapping windows anchored at each true contiguous-run start."""
    raw=data['arrays'];result=[]
    for sequence in data['sequences']:
        boundaries=np.flatnonzero(raw['actor_start'][sequence]|(raw['root_gap'][sequence]!=1))
        boundaries=np.unique(np.r_[0,boundaries,len(sequence)])
        for a,b in zip(boundaries[:-1],boundaries[1:]):
            for start in range(a,b-size+1,size):result.append(sequence[start:start+size])
    return np.asarray(result,dtype=np.int64).reshape(-1,size)


def summarize(data,p):
    raw=data['arrays'];parameter,joint=correctness(raw,p);category={}
    for name,mask in masks(raw).items():
        support=int(mask.sum())
        category[name]=dict(support=support,complete=int(joint[mask].sum()),
            conditional=int(parameter[mask].sum()),
            nll=float(p['nll'][mask].mean()) if support else None)
    matrix=np.bincount(raw['y']*15+p['prediction'],minlength=225).reshape(15,15)
    f1=2*matrix.diagonal()/np.maximum(matrix.sum(0)+matrix.sum(1),1)
    sequences={}
    for size in (16,32):
        ids=windows(data,size)
        sequences[str(size)]=dict(windows=len(ids),
            across_rounds=int((raw['round'][ids[:,0]]!=raw['round'][ids[:,-1]]).sum()),
            complete_windows=int(joint[ids].all(1).sum()),
            mean_complete_fraction=float(joint[ids].mean()) if len(ids) else None,
            mean_joint_nll_per_root=float(p['nll'][ids].mean()) if len(ids) else None,
            groups=len(np.unique(data['group'][ids[:,0]])))
    return dict(categories=category,selectors=selectors(data,p),macro_F1=float(f1[1:].mean()),
        confusion=matrix.tolist(),false_positives={name:int(matrix[:,i].sum()-matrix[i,i]) for i,name in enumerate(LABELS)},
        windows=sequences,strict_unassessed_shops=int((raw['y']==11).sum()))


def paired(data,treatment,control):
    """Paired whole-group bootstrap and leave-one-group-out; descriptive only."""
    raw=data['arrays'];groups=np.unique(data['group']);n=len(groups)
    rng=np.random.default_rng(20261109);draws=rng.integers(0,n,(2000,n))
    tp,tj=correctness(raw,treatment);cp,cj=correctness(raw,control)
    report={}
    for name,mask in masks(raw).items():
        count=np.array([int((mask&(data['group']==g)).sum()) for g in groups])
        for label,delta in [('complete',tj.astype(float)-cj),('conditional',tp.astype(float)-cp),
                            ('nll',treatment['nll']-control['nll'])]:
            sums=np.array([delta[mask&(data['group']==g)].sum() for g in groups])
            denom=count[draws].sum(1);valid=denom>0
            boot=sums[draws].sum(1)[valid]/denom[valid]
            loo_den=count.sum()-count;loo=loo_den>0
            loo_values=(sums.sum()-sums)[loo]/loo_den[loo]
            report[name+'_'+label]=dict(delta=float(sums.sum()/count.sum()) if count.sum() else None,
                interval95=np.quantile(boot,[.025,.975]).tolist() if len(boot) else None,
                valid_draws=len(boot),leave_one_group_out=loo_values.tolist())
        report[name+'_rescues']=int((mask&tj&~cj).sum())
        report[name+'_regressions']=int((mask&~tj&cj).sum())
    t=selectors(data,treatment);c=selectors(data,control)
    checks=dict(move=report['move_complete']['delta']>=.01,
        change=report['change_complete']['delta']>=.01,
        continuation=report['continue_complete']['delta']>=-.005,
        balanced_movement_nll=t['movement']<c['movement'],
        full_nll=report['all_nll']['delta']<=.005,
        complete_commands=report['all_complete']['delta']>-.002,
        macro_F1=summarize(data,treatment)['macro_F1']>=summarize(data,control)['macro_F1'])
    for name in ('attack','cast_0','cast_1'):
        delta=report[name+'_conditional']['delta'];checks[name]=delta is not None and delta>-.02
    # Never conceal regressions in sparse categories, even though their uncertainty is large.
    for name in ('blocked','ward','submit','altar','teleport','priority','recall','cancel','end'):
        delta=report[name+'_complete']['delta'];checks[name]=delta is None or delta>=-.02
    sequence_report={}
    for size in (16,32):
        ids=windows(data,size);window_groups=data['group'][ids[:,0]]
        count=np.array([int((window_groups==g).sum()) for g in groups])
        sequence_report[str(size)]={}
        for name,delta in [('complete_windows',tj[ids].all(1).astype(float)-cj[ids].all(1)),
                           ('complete_fraction',tj[ids].mean(1)-cj[ids].mean(1)),
                           ('nll_per_root',(treatment['nll'][ids]-control['nll'][ids]).mean(1))]:
            sums=np.array([delta[window_groups==g].sum() for g in groups])
            denom=count[draws].sum(1);valid=denom>0
            boot=sums[draws].sum(1)[valid]/denom[valid]
            sequence_report[str(size)][name]=dict(windows=len(ids),
                delta=float(sums.sum()/count.sum()) if count.sum() else None,
                interval95=np.quantile(boot,[.025,.975]).tolist() if len(boot) else None,
                valid_draws=len(boot))
    return dict(groups=n,draws=2000,seed=20261109,metrics=report,allocation_checks=checks,
        all_checks_pass=all(checks.values()),windows=sequence_report,
        limits='Exploratory, pre-exposed groups; intervals are not selection-adjusted. No strategic or runtime promotion.')
