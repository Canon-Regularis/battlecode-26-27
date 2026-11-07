"""Paired evidence for every completed V13 arm; no refit/checkpoint selection."""
import json,sys
from pathlib import Path
import numpy as np
from .consistent_study import load
from .consistent_data import ROOT,BASE,WORK,REPORT
from .algorithmic.study import matches
from .observation_metrics import correctness,group_samples,interval
from .audit import immutable_json
from .data import digest
from . import reliable_train as rt

def archive(path):
    with np.load(path) as z:return {k:z[k] for k in z.files}

def compare(raw,new,old,mask,draws,groups):
    _,nj=correctness(raw,new);_,oj=correctness(raw,old);a=group_samples(raw,new,mask,draws,groups);b=group_samples(raw,old,mask,draws,groups)
    return dict(rows=int(mask.sum()),new_correct=int(nj[mask].sum()),reference_correct=int(oj[mask].sum()),rescues=int((nj&~oj&mask).sum()),regressions=int((~nj&oj&mask).sum()),new_nll=float(new['nll'][mask].mean()) if mask.any() else None,reference_nll=float(old['nll'][mask].mean()) if mask.any() else None,paired95={key:interval(a[key]-b[key]) for key in ('joint_accuracy','macro_f1','joint_nll')},loss_reduction95=interval(1-a['joint_nll']/b['joint_nll']),group_net={str(int(g)):int((nj&mask&(raw['group']==g)).sum()-(oj&mask&(raw['group']==g)).sum()) for g in groups})

def run(identifier):
    data=load('validation');raw=data['raw'];n=len(raw['y']);trained=identifier.startswith('B');path=WORK/f'runs/{identifier}/validation-predictions.npz' if trained else WORK/f'controls/{identifier}-validation.npz';pred=archive(path);_,joint=correctness(raw,pred)
    refs={};g=archive(BASE.parent/'v9/runs/G00/validation-predictions.npz');g['coordinate']=g['proposed_coordinate'];refs['G00']=g
    refs['A00']=archive(BASE.parent/'v10/runs/A00/validation-predictions.npz')
    for name in ('Q00','U00','D01'):
        if name!=identifier:refs[name]=archive(WORK/f'controls/{name}-validation.npz')
    for name in ('B00','B01'):
        p=WORK/f'runs/{name}/validation-predictions.npz'
        if p.exists() and name!=identifier:refs[name]=archive(p)
    groups=np.unique(raw['group']);rng=np.random.default_rng(20261106);draws=np.stack([np.bincount(rng.integers(len(groups),size=len(groups)),minlength=len(groups)) for _ in range(2000)]);direction=np.load(BASE.parent/'v7/validation-direction.npy');contexts={'overall':np.ones(n,bool),'except_recall':raw['y']!=10,'move_continuing':(raw['y']==8)&(direction==2),'move_changing':(raw['y']==8)&(direction==3)}
    contexts.update({name:raw['y']==k for k,name in enumerate(rt.LABELS) if (raw['y']==k).any()});comparisons={name:{context:compare(raw,pred,old,mask,draws,groups) for context,mask in contexts.items()} for name,old in refs.items()}
    _,basejoint=correctness(raw,g);covered=matches(data['c'],raw['y'],raw['py'],raw['priority']).any(1);opportunities=covered&~basejoint
    parameters={}
    if 'family_commands' in pred:
        all_commands=pred['family_commands'][np.arange(n),raw['y']];parameter=(all_commands[:,1]==raw['py'])&(raw['py']<289);parameter[raw['y']==9]=all_commands[raw['y']==9,2]==raw['priority'][raw['y']==9]
        for k,name in enumerate(rt.LABELS):
            if name not in ('move','blocked','attack','cast_0','cast_1','ward','submit','altar','teleport','priority'):continue
            mask=raw['y']==k;typed=mask&(pred['prediction']==k);count=int(mask.sum());tp=int(typed.sum());parameters[name]=dict(rows=count,all_true_family_exact=int(parameter[mask].sum()),all_true_family_accuracy=float(parameter[mask].mean()) if count else None,correctly_typed=tp,correctly_typed_parameter_accuracy=float(joint[typed].mean()) if tp else None)
    with np.load(BASE/'combined-train.npz') as z:ty=z['y'];tp=z['priority']
    values,counts=np.unique(tp[ty==9],return_counts=True);freq=dict(zip(values,counts));support=np.array([freq.get(v,0) for v in raw['priority']]);priority={}
    for name,mask in [('all',raw['y']==9),('rare',(raw['y']==9)&(support>0)&(support<20)),('unseen',(raw['y']==9)&(support==0))]:
        typed=mask&(pred['prediction']==9);err=pred['priority'][typed].astype(np.int64)-raw['priority'][typed].astype(np.int64);priority[name]=dict(rows=int(mask.sum()),joint=int(joint[mask].sum()),correctly_typed=int(typed.sum()),correctly_typed_MAE=float(np.abs(err).mean()) if len(err) else None,correctly_typed_max_abs_error=int(np.abs(err).max()) if len(err) else None,all_true_family_MAE=float(np.abs(pred['family_commands'][mask,9,2]-raw['priority'][mask]).mean()) if mask.any() and 'family_commands' in pred else None)
    movement={}
    for code,name in ((8,'successful_move_forecast'),(3,'blocked_attempt_forecast')):
        ids=np.flatnonzero(pred['prediction']==code);coordinate=pred['coordinate'][ids];ok=(coordinate>=0)&(coordinate<289);movement[name]=dict(rows=len(ids),mask_rejections=int((~ok).sum()+(~raw['move_mask'][ids[ok],coordinate[ok]]).sum()))
    partial=rt.invalid_rate(raw,dict(prediction=pred['prediction'],proposed_coordinate=pred['coordinate']));movement.update(other_readiness_flags=partial['invalid']-sum(v['mask_rejections'] for v in movement.values()),full_engine_illegality=None,meaning='Blocked mask rejection may be a correct attempted-move outcome; never aggregate this into illegal successful moves.')
    confidence=np.exp(pred['command_log_probability']);bins=[]
    for lo,hi in zip(np.linspace(0,1,11)[:-1],np.linspace(0,1,11)[1:]):
        mask=(confidence>=lo)&(confidence<hi if hi<1 else confidence<=hi);bins.append(dict(lo=float(lo),hi=float(hi),rows=int(mask.sum()),mean_modeled_confidence=float(confidence[mask].mean()) if mask.any() else None,strict_command_rate=float(joint[mask].mean()) if mask.any() else None))
    details=dict(identifier=identifier,prediction_sha256=digest(path),comparisons=comparisons,opportunity=dict(library_covered_G00_errors=int(opportunities.sum()),rescued=int((opportunities&joint).sum()),missed=int((opportunities&~joint).sum()),missing_point_support_errors=int((~covered&~joint).sum()),coverage_is_not_achieved_accuracy=True),parameter_metrics=parameters,priority=priority,partial_checks=movement,
        command_confidence_bins=bins,calibration_qualification='Modeled observed-representation probability, including marginalized shop and unavailable-coordinate buckets. Strict empirical accuracy below it is diagnostic, not certification of complete API-command calibration.',
        mixture_usage=dict(mean_fallback_weight=float(np.exp(pred['log_weights'][:,0]).mean()) if 'log_weights' in pred else None,selected_command_mean_point_fraction=float(pred['point_probability_fraction'].mean()),fallback_only_commands=int((pred['point_probability_fraction']==0).sum()),not_a_hard_route=True),
        uncertainty='2000paired whole-original-group draws,seed20261106;5reusedDEVgroups;conditional on checkpoint selection, not untouched/selection-adjusted/3seed.',source_sha256=digest(__file__),new_fits=0,reserved_opened=0)
    immutable_json(REPORT/f'{identifier}-analysis.json',details)
    print(identifier,{k:v['overall']['rescues']-v['overall']['regressions'] for k,v in comparisons.items()},flush=True)

if __name__=='__main__':run(sys.argv[1])
