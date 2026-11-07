"""Immutable additional comparisons; no optimizer or revised checkpoint choice."""
import json,sys
from pathlib import Path
import numpy as np
import torch
from .algorithmic.study import ROOT,WORK,REPORT,matches
from .algorithmic_fit import load,Selector
from .observation_metrics import correctness,group_samples,interval
from .entity_experiment import legality
from .audit import immutable_json
from .data import digest
from . import reliable_train as rt

def run(identifier='A00'):
    d=load('validation');raw=d['raw'];n=len(raw['y']);path=WORK/f'runs/{identifier}/validation-predictions.npz'
    with np.load(path) as z:p={k:z[k] for k in z.files}
    base=d['baseline'];_,j=correctness(raw,p);_,b=correctness(raw,base);cm=matches(d['c'],raw['y'],raw['py'],raw['priority']);covered=cm.any(1);groups=np.unique(raw['group']);rng=np.random.default_rng(20261106);draws=np.stack([np.bincount(rng.integers(len(groups),size=len(groups)),minlength=len(groups)) for _ in range(2000)])
    direction=np.load(ROOT/'.cambc/action-predictor/v7/validation-direction.npy');contexts={'overall':np.ones(n,bool),'except_recall':raw['y']!=rt.LABELS.index('recall'),'point_routed':~p['fallback'],'fallback_routed':p['fallback'],'move_continuing':(raw['y']==8)&(direction==2),'move_changing':(raw['y']==8)&(direction==3)}
    contexts.update({name:raw['y']==code for code,name in enumerate(rt.LABELS) if (raw['y']==code).any()});comparison={}
    for name,mask in contexts.items():
        a=group_samples(raw,p,mask,draws,groups);old=group_samples(raw,base,mask,draws,groups)
        comparison[name]=dict(rows=int(mask.sum()),new_correct=int(j[mask].sum()),G00_correct=int(b[mask].sum()),rescues=int((j&~b&mask).sum()),regressions=int((~j&b&mask).sum()),mean_nll=float(p['nll'][mask].mean()) if mask.any() else None,G00_nll=float(base['nll'][mask].mean()) if mask.any() else None,paired95={key:interval(a[key]-old[key]) for key in ('joint_accuracy','macro_f1','joint_nll')},loss_reduction95=interval(1-a['joint_nll']/old['joint_nll']))
    with np.load(ROOT/'.cambc/action-predictor/v4/validation.npz') as z:full={k:z[k] for k in z.files if k not in ('x','history','grid','valid')}
    leg=legality(full,dict(prediction=p['prediction'],proposed_coordinate=p['coordinate']))
    with np.load(ROOT/'.cambc/action-predictor/v5/combined-train.npz') as z:ty=z['y'];tp=z['priority']
    values,counts=np.unique(tp[ty==9],return_counts=True);freq=dict(zip(values,counts));support=np.array([freq.get(v,0) for v in raw['priority']]);priority={}
    for name,mask in [('all',raw['y']==9),('rare',(raw['y']==9)&(support>0)&(support<20)),('unseen',(raw['y']==9)&(support==0))]:
        err=p['priority'][mask].astype(np.int64)-raw['priority'][mask].astype(np.int64);priority[name]=dict(rows=int(mask.sum()),joint=int(j[mask].sum()),correctly_typed=int(((p['prediction']==9)&mask).sum()),mean_abs_error_all_true_rows=float(np.abs(err).mean()) if len(err) else None,max_abs_error_all_true_rows=int(np.abs(err).max()) if len(err) else None,all_true_argument_accuracy=None,reason='Joint-only decoder; leftover priority scalar on another type is not its priority prediction')
    # Calibration of causal route confidence, not command confidence.
    route_conf=p['selector_weights'][:,0];bins=[]
    for lo,hi in zip(np.linspace(0,1,11)[:-1],np.linspace(0,1,11)[1:]):
        mask=(route_conf>=lo)&(route_conf<hi if hi<1 else route_conf<=hi)
        bins.append(dict(low=float(lo),high=float(hi),rows=int(mask.sum()),mean_fallback_weight=float(route_conf[mask].mean()) if mask.any() else None,G00_command_correct_rate=float(b[mask].mean()) if mask.any() else None,meaning='route weight, not calibrated probability of hard-command correctness'))
    details=dict(rows=n,comparisons=comparison,opportunity=dict(library_rescues=int((covered&~b).sum()),captured=int((covered&~b&j).sum()),missed=int((covered&~b&~j).sum())),support_ceiling={label:dict(rows=int((raw['y']==k).sum()),union_correct=int(((covered|b)&(raw['y']==k)).sum())) for k,label in enumerate(rt.LABELS)},unique_slot_rescue={name:int((cm[:,k]&(cm.sum(1)==1)&~b).sum()) for k,name in enumerate(__import__('tools.action_predictor.algorithmic.library',fromlist=['NAMES']).NAMES)},legality=leg,priority=priority,route_confidence_bins=bins,uncertainty='2000paired whole-group draws,seed20261106;5reusedDEVgroups,conditional on selectedcheckpoint;not untouched/selection-adjusted/3seed',warnings=['No parameter accuracy inferred by reading a leftover scalar from a differently typed command','No strategy similarity claim','Partial legality only;blocked movement-mask rejections are not illegal successful moves'],new_fits=0,reserved_opened=0)
    immutable_json(REPORT/f'{identifier}-analysis.json',details)
    info=json.loads((REPORT/f'{identifier}.json').read_text());directory=WORK/'runs'/identifier
    immutable_json(REPORT/f'{identifier}-completion-addendum.json',dict(report_sha256=digest(REPORT/f'{identifier}.json'),analysis_sha256=digest(REPORT/f'{identifier}-analysis.json'),files={str(f.relative_to(ROOT)):digest(f) for f in directory.glob('*') if f.is_file()},source_sha256=digest(__file__),optimizer_updates=len(info['trace'])*int(np.ceil(433071/512)),commands=[f'.venv-action-predictor/Scripts/python.exe -m tools.action_predictor.algorithmic.study {s}' for s in ('train','validation')]+['.venv-action-predictor/Scripts/python.exe -m tools.action_predictor.algorithmic_fit','.venv-action-predictor/Scripts/python.exe -m tools.action_predictor.algorithmic_roundtrip',f'.venv-action-predictor/Scripts/python.exe -m tools.action_predictor.algorithmic_analysis {identifier}'],all_category_success=False,three_seeds=False,serving_receipt=digest(REPORT/'A00-causal-roundtrip.json') if identifier=='A00' else None))
    print(identifier,'analysis',comparison['overall'],flush=True)

if __name__=='__main__':run(sys.argv[1] if len(sys.argv)>1 else 'A00')
