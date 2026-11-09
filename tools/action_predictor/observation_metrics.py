"""Fixed-support metrics and paired group intervals, including sparse contexts."""
import numpy as np

from . import reliable_train as rt


def context_masks(raw,aux):
    n=len(raw['y']);move=raw['y']==rt.LABELS.index('move')
    available=aux['available'];known=raw['pos_known'].astype(bool)
    masks={'overall':np.ones(n,bool)}
    for name,mask in [('0',available==0),('1-3',(available>=1)&(available<=3)),
                      ('4-7',(available>=4)&(available<=7)),('8-15',(available>=8)&(available<=15)),('16',available==16)]:
        masks['history_'+name]=mask
    masks.update(direction_change=move&(aux['direction']==3),same_direction=move&(aux['direction']==2),
                 no_previous_move=move&(aux['direction']==1),zero_displacement=move&(aux['direction']==4),
                 near_static_obstacle=known&aux['near_obstacle'],away_from_static_obstacle=known&~aux['near_obstacle'],
                 unknown_position=~known,visible_set_changed=aux['visible_change']==2,
                 visible_set_unchanged=aux['visible_change']==1,visible_history_unavailable=aux['visible_change']==0,
                 new_own_turn=aux['gaps'][:,-1,3]>0,
                 same_own_turn=(aux['gaps'][:,-1,0]>0)&(aux['gaps'][:,-1,3]==0))
    return masks


def correctness(raw,pred):
    y,py=raw['y'],raw['py'];parameter=np.ones(len(y),bool)
    spatial=py>=0
    parameter[spatial]=(pred['coordinate'][spatial]==py[spatial])&(py[spatial]<289)
    priority=y==rt.LABELS.index('priority')
    parameter[priority]=pred['priority'][priority]==raw['priority'][priority]
    joint=(pred['prediction']==y)&parameter&(y!=rt.LABELS.index('shop'))
    return parameter,joint


def ratio(a,b):
    return np.divide(a,b,out=np.full(np.asarray(a).shape,np.nan,dtype=float),where=np.asarray(b)>0)


def interval(values):
    valid=np.isfinite(values)
    if not valid.any():return dict(low=None,high=None,valid_draws=0)
    return dict(low=float(np.quantile(values[valid],.025)),high=float(np.quantile(values[valid],.975)),valid_draws=int(valid.sum()))


def group_samples(raw,pred,mask,draws,groups):
    classes=len(rt.LABELS);parameter,joint=correctness(raw,pred)
    counts=[];loss=[];joint_counts=[];matrices=[];family_counts={};family_correct={};family_joint={}
    families=['move','blocked','attack','cast_0','cast_1','ward','submit','altar','teleport']
    for family in families:family_counts[family]=[];family_correct[family]=[];family_joint[family]=[]
    for group in groups:
        selected=mask&(raw['group']==group);y=raw['y'][selected];p=pred['prediction'][selected]
        counts.append(selected.sum());loss.append(pred['nll'][selected].sum());joint_counts.append(joint[selected].sum())
        matrices.append(np.bincount(y*classes+p,minlength=classes**2))
        for family in families:
            chosen=selected&(raw['y']==rt.LABELS.index(family))
            family_counts[family].append(chosen.sum());family_correct[family].append(parameter[chosen].sum());family_joint[family].append(joint[chosen].sum())
    n=draws@np.asarray(counts);matrix=(draws@np.stack(matrices)).reshape(-1,classes,classes)
    diagonal=np.diagonal(matrix,axis1=1,axis2=2)
    f1=2*diagonal/np.maximum(matrix.sum(1)+matrix.sum(2),1)
    output=dict(joint_nll=ratio(draws@np.asarray(loss),n),joint_accuracy=ratio(draws@np.asarray(joint_counts),n),macro_f1=f1[:,1:].mean(-1))
    output['macro_f1'][n==0]=np.nan
    for family in families:
        denominator=draws@np.asarray(family_counts[family])
        output[family+'_exact']=ratio(draws@np.asarray(family_correct[family]),denominator)
        output[family+'_joint']=ratio(draws@np.asarray(family_joint[family]),denominator)
    return output


def point_metrics(raw,pred,mask):
    n=int(mask.sum());parameter,joint=correctness(raw,pred);y=raw['y']
    supports=np.bincount(y[mask],minlength=len(rt.LABELS))
    result=dict(rows=n,group_support={str(int(g)):int((mask&(raw['group']==g)).sum()) for g in np.unique(raw['group'])},
                per_action_support=dict(zip(rt.LABELS,map(int,supports))),
                joint_nll=float(pred['nll'][mask].mean()) if n else None,
                joint_accuracy=float(joint[mask].mean()) if n else None)
    if n:
        matrix=np.bincount(y[mask]*len(rt.LABELS)+pred['prediction'][mask],minlength=len(rt.LABELS)**2).reshape(len(rt.LABELS),-1)
        diagonal=matrix.diagonal();f1=2*diagonal/np.maximum(matrix.sum(0)+matrix.sum(1),1)
        result['macro_f1']=float(f1[1:].mean())
    else:result['macro_f1']=None
    result['parameters']={}
    for family in ('move','blocked','attack','cast_0','cast_1','ward','submit','altar','teleport'):
        selected=mask&(y==rt.LABELS.index(family));support=int(selected.sum())
        result['parameters'][family]=dict(support=support,
            exact_accuracy=float(parameter[selected].mean()) if support else None,
            joint_accuracy=float(joint[selected].mean()) if support else None)
    return result


def compare(raw,rich,control,aux):
    groups=np.unique(raw['group']);g=len(groups)
    rng=np.random.default_rng(20261106)
    draws=np.stack([np.bincount(rng.integers(0,g,size=g),minlength=g) for _ in range(2000)])
    output={}
    for name,mask in context_masks(raw,aux).items():
        a=group_samples(raw,rich,mask,draws,groups);b=group_samples(raw,control,mask,draws,groups)
        differences={key:a[key]-b[key] for key in a if key!='joint_nll'}
        differences['joint_loss_reduction']=1-ratio(a['joint_nll'],b['joint_nll'])
        output[name]=dict(observations=point_metrics(raw,rich,mask),control=point_metrics(raw,control,mask),
                          paired_intervals={key:interval(value) for key,value in differences.items()})
    return output


def targeting_regressions(a,b):
    return {family:{metric:a['parameters'][family].get(metric)-b['parameters'][family].get(metric)
                    for metric in ('exact_accuracy','joint_accuracy')
                    if a['parameters'][family].get(metric) is not None and b['parameters'][family].get(metric) is not None}
            for family in a['parameters']}
