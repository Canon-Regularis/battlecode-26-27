"""Controlled complete forecasts; every action is predicted, never oracle routed."""
import json,sys
from pathlib import Path
import numpy as np
import torch
from .protocol import ROOT,BASE,JOBS,WORK,REPORT
from .fit import load
from .integration import type_distribution,commands
from ..algorithmic_fit import evaluate
from ..observation_metrics import correctness,group_samples,interval
from ..command_mixture import canonical
from ..audit import immutable_json
from ..data import digest

def read(path):
    with np.load(path) as z:return {k:z[k] for k in z.files}

def binary(y,probability):
    positive=y==14;guess=probability>=.5;tp=int((guess&positive).sum());fp=int((guess&~positive).sum());fn=int((~guess&positive).sum());clip=np.clip(probability,1e-15,1-1e-15);bins=[]
    for lo,hi in zip(np.linspace(0,1,11)[:-1],np.linspace(0,1,11)[1:]):
        m=(probability>=lo)&(probability<hi if hi<1 else probability<=hi);bins.append(dict(low=float(lo),high=float(hi),rows=int(m.sum()),mean_probability=float(probability[m].mean()) if m.any() else None,ward_rate=float(positive[m].mean()) if m.any() else None))
    return dict(threshold=.5,tp=tp,fp=fp,fn=fn,precision=tp/max(1,tp+fp),recall=tp/max(1,tp+fn),f1=2*tp/max(1,2*tp+fp+fn),brier=float(np.mean((probability-positive)**2)),bernoulli_nll=float(np.mean(-positive.astype(float)*np.log(clip)-(~positive)*np.log1p(-clip))),bins=bins,meaning='Binaryfixed.5diagnostic; complete15waypredictedwardtypes scoredseparately')

def forecasts(split,placement=None,typing=None):
    d=load(split);old=np.array(d['type-logp']);types=type_distribution(torch.from_numpy(old),torch.from_numpy(typing['logit']) if typing is not None else None).numpy();nll=d['base_nll'].copy()
    if placement is not None:nll+=placement['nll']-d['base_nll']
    if typing is not None:nll+=typing['nll']-d['base_nll']
    a,b=commands(types,old,d['modes'],d['mode_joint'],placement['coordinate'] if placement is not None else None,placement['parameter_lp'] if placement is not None else None)
    for p in (a,b):p['nll']=nll;p['ward_probability']=np.exp(types[:,14])
    return d,a,b

def summarize(raw,p,mask,direction):
    selected={k:v[mask] for k,v in p.items()};r={k:v[mask] for k,v in raw.items()};out=evaluate(r,selected,direction[mask]);y=r['y'];ward=y==14;guess=selected['prediction']==14;typed=ward&guess;_,joint=correctness(r,selected);coordinate=selected['family_commands'][:,14,1]
    out['ward']=dict(support=int(ward.sum()),predicted=int(guess.sum()),type_TP=int(typed.sum()),type_FP=int((guess&~ward).sum()),joint_FP=int((guess&~joint).sum()),recall_to_ward=int((guess&(y==10)).sum()),conditional_all_true_exact=int((coordinate[ward]==r['py'][ward]).sum()),conditional_all_true_accuracy=float((coordinate[ward]==r['py'][ward]).mean()) if ward.any() else None,correctly_typed_parameter_accuracy=float(joint[typed].mean()) if typed.any() else None,joint_correct=int(joint[ward].sum()))
    out['binary_ward_diagnostic']=binary(y,selected['ward_probability']);return out

def run(name,placement_id=None,typing_id=None):
    reports={};outdir=WORK/'evaluations'/name;outdir.mkdir(parents=True,exist_ok=True);hashes={}
    for split in ('train','validation'):
        placement=read(WORK/f'runs/{placement_id}/{split}-outputs.npz') if placement_id else None;typing=read(WORK/f'runs/{typing_id}/{split}-outputs.npz') if typing_id else None;d,a,b=forecasts(split,placement,typing);direction=np.load(BASE.parent/f'v7/{split}-direction.npy');masks={'all':np.ones(len(a['prediction']),bool)}
        if split=='train':masks['natural']=np.load(BASE.parent/'v9/frequency/natural-mask.npy')
        for decoder,p in [('primary',a),('joint_MAP',b)]:
            path=outdir/f'{split}-{decoder}.npz'
            if path.exists():
                retained=read(path);assert set(retained)==set(p)
                for key in p:np.testing.assert_array_equal(retained[key],p[key])
            else:np.savez_compressed(path,**p)
            hashes[f'{split}-{decoder}']=digest(path);reports[f'{split}-{decoder}']={k:summarize(d['raw'],p,m,direction) for k,m in masks.items()}
        if typing_id is None:
            with np.load(BASE.parent/f'v9/runs/G00/{split}-predictions.npz') as z:oldpred=z['prediction'];oldcommand=np.stack((oldpred,z['proposed_coordinate'],z['priority']),-1)
            np.testing.assert_array_equal(a['prediction'],oldpred)
            if placement_id is None:np.testing.assert_array_equal(canonical(np.stack((a['prediction'],a['coordinate'],a['priority']),-1)),canonical(oldcommand))
        if split=='validation':
            raw=d['raw'];groups=np.unique(raw['group']);rng=np.random.default_rng(20261106);draws=np.stack([np.bincount(rng.integers(len(groups),size=len(groups)),minlength=len(groups)) for _ in range(2000)]);details={}
            for decoder,p in [('primary',a),('joint_MAP',b)]:
                control=read(WORK/f'evaluations/control/validation-{decoder}.npz') if name!='control' else p;_,j=correctness(raw,p);_,cj=correctness(raw,control);contexts={'all':np.ones(len(j),bool),'ward':raw['y']==14,'recall':raw['y']==10,'move':raw['y']==8,'attack':raw['y']==2,'cast_0':raw['y']==5,'cast_1':raw['y']==6};paired={}
                for context,m in contexts.items():
                    x=group_samples(raw,p,m,draws,groups);c=group_samples(raw,control,m,draws,groups);paired[context]=dict(rows=int(m.sum()),rescues=int((j&~cj&m).sum()),regressions=int((~j&cj&m).sum()),paired95={k:interval(x[k]-c[k]) for k in ('joint_accuracy','macro_f1','joint_nll')})
                details[decoder]=paired
            reports['paired_DEV_vs_matched_control']=details
            champion=np.array(d['champion']);engine=np.empty(len(champion),np.int8)
            for job in json.loads(JOBS.read_text()):
                if job['split']==split:engine[job['offset']:job['offset']+job['rows']]=int(job['record']['engine_version'][0])
            reports['DEV_contexts']={decoder:{kind:{str(int(k)):summarize(raw,p,values==k,direction) for k in np.unique(values)} for kind,values in [('champion',champion),('engine',engine)]} for decoder,p in [('primary',a),('joint_MAP',b)]}
    immutable_json(REPORT/f'{name}-evaluation.json',dict(placement=placement_id,typing=typing_id,reports=reports,prediction_hashes=hashes,source_sha256=digest(__file__),interpretation='Primarytypeargmax thenconditionalargmax;Atypesfixed. SecondaryjointMAP separatelypredeclared. NoDECODERselectedafterresults. Conditionalgivenrecordedwarddiagnostic notdeployableaccuracy. Bothdecoderssame normalizedjointNLL. Engine3DEVonegroup,notpolicyversioncausality.',new_fits=0,reserved_opened=0));print(name,{k:v['all']['ward'] for k,v in reports.items() if k.startswith('validation')},flush=True)

if __name__=='__main__':run(sys.argv[1],None if len(sys.argv)<3 or sys.argv[2]=='-' else sys.argv[2],None if len(sys.argv)<4 or sys.argv[3]=='-' else sys.argv[3])
