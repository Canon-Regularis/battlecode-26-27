"""Paired uncertainty by resampling complete game groups, never individual turns."""
import numpy as np

from .reliable_train import LABELS


def bootstrap(raw,pred,draws=None):
    groups=np.unique(raw['group']);classes=len(LABELS);g=len(groups)
    if draws is None:
        rng=np.random.default_rng(20261106)
        draws=np.stack([np.bincount(rng.integers(0,g,size=g),minlength=g) for _ in range(2000)])
    matrices=[];sums={k:[] for k in ('n','nll','joint','move_n','move_correct','move_top3','attack_n','attack_correct','cast_0_n','cast_0_correct','cast_1_n','cast_1_correct')}
    for group in groups:
        selected=raw['group']==group;y=raw['y'][selected];p=pred['prediction'][selected];py=raw['py'][selected]
        matrices.append(np.bincount(y*classes+p,minlength=classes**2))
        good=y==p;parameter=np.ones(len(y),bool);sp=py>=0
        parameter[sp]=(pred['coordinate'][selected][sp]==py[sp])&(py[sp]<289)
        priority=y==LABELS.index('priority')
        parameter[priority]=pred['priority'][selected][priority]==raw['priority'][selected][priority]
        joint=good&parameter&(y!=LABELS.index('shop'))
        sums['n'].append(len(y));sums['nll'].append(pred['nll'][selected].sum());sums['joint'].append(joint.sum())
        for family in ('move','attack','cast_0','cast_1'):
            m=y==LABELS.index(family)
            sums[family+'_n'].append(m.sum());sums[family+'_correct'].append(parameter[m].sum())
        m=y==LABELS.index('move')
        sums['move_top3'].append(((pred['top5'][selected][m,:3]==py[m,None])&(py[m,None]<289)).any(-1).sum())
    total={k:draws@np.array(v) for k,v in sums.items()}
    matrix=(draws@np.stack(matrices)).reshape(-1,classes,classes)
    diagonal=np.diagonal(matrix,axis1=1,axis2=2)
    precision=diagonal/np.maximum(matrix.sum(1),1);recall=diagonal/np.maximum(matrix.sum(2),1)
    f1=2*precision*recall/np.maximum(precision+recall,1e-12)
    samples=dict(macro_f1=f1[:,1:].mean(-1),joint_nll=total['nll']/total['n'],joint_accuracy=total['joint']/total['n'])
    for i,name in enumerate(LABELS):samples['action_f1_'+name]=f1[:,i]
    for family in ('move','attack','cast_0','cast_1'):
        samples[family+'_exact']=np.divide(total[family+'_correct'],total[family+'_n'],out=np.full(len(draws),np.nan),where=total[family+'_n']>0)
    samples['move_top3']=total['move_top3']/np.maximum(total['move_n'],1)
    intervals={k:(dict(low=float(np.nanquantile(v,.025)),high=float(np.nanquantile(v,.975))) if np.isfinite(v).any()
                  else dict(low=None,high=None)) for k,v in samples.items()}
    return intervals,samples,draws


def paired(raw,model,baseline):
    _,m,draws=bootstrap(raw,model);_,b,_=bootstrap(raw,baseline,draws)
    differences=dict(movement_gain=m['move_exact']-b['move_exact'],
                     joint_loss_reduction=1-m['joint_nll']/b['joint_nll'],
                     macro_f1_gain=m['macro_f1']-b['macro_f1'],joint_accuracy_gain=m['joint_accuracy']-b['joint_accuracy'])
    for family in ('attack','cast_0','cast_1'):
        differences[family+'_exact_gain']=m[family+'_exact']-b[family+'_exact']
    return {k:(dict(low=float(np.nanquantile(v,.025)),high=float(np.nanquantile(v,.975))) if np.isfinite(v).any()
               else dict(low=None,high=None)) for k,v in differences.items()}
