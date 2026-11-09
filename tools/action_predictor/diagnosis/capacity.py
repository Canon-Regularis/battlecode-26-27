"""R02 bounded existing-architecture capacity test, not a new large-model phase."""
import json,time
import numpy as np
import torch
import torch.nn.functional as F
from .saved import ROOT,OLD,WORK,REPORT,read,arrays
from ..audit import immutable_json
from ..data import digest
from .. import reliable_train as rt
from ..reliable_model import JointModel,priority_log_mass

def run():
    rt.setup(20261117);source=digest(__file__);path=OLD/'v5/combined-train.npz';assert digest(path)=='39386010575ad30add064fdae750680f34cfcc732c4fd00fb657875ff4c61ffb';maskpath=OLD/'v9/frequency/natural-mask.npy';mask=np.load(maskpath);assert digest(maskpath)==read(ROOT/'tools/action_predictor/experiments/v9/frequency-data-ready.json')['mask_sha256']
    with np.load(path) as z:y=z['y'];group=z['group']
    direction=np.load(OLD/'v7/train-direction.npy');rng=np.random.default_rng(20261117);groups=np.unique(group);shuffled=rng.permutation(groups);held=set(map(int,shuffled[:20]));trainpool=mask&~np.isin(group,list(held));heldpool=mask&np.isin(group,list(held));used=np.zeros(len(y),bool)
    def choose(pool):
        chosen=[]
        for code in range(1,len(rt.LABELS)):
            contexts=[2,3] if code==8 else [0]
            for context in contexts:
                m=pool&~used&(y==code)
                if context:m&=direction==context
                indices=np.flatnonzero(m);count=min(256 if code==8 else 128,len(indices));selected=rng.choice(indices,count,replace=False);chosen.extend(selected);used[selected]=True
        return np.array(sorted(chosen),dtype=np.int64)
    indices={'fit':choose(trainpool),'seen_group':choose(trainpool),'held_group':choose(heldpool)}
    config=read(ROOT/'tools/action_predictor/experiments/v5/M01.json').get('config')
    # Only architecture/config metadata is read; no trained weights or normalization.
    saved=torch.load(OLD/'v5/runs/M01/model.pt',weights_only=True,map_location='cpu');config=dict(saved['config']);del saved
    directory=WORK/'R02-capacity';assert not directory.exists(),'Preserve attempted diagnostic';directory.mkdir(parents=True)
    plan=dict(source_sha256=source,kind='ONE bounded capacity/generalization diagnostic explicitly requested,not a productionarchitectureexperiment. ExistingM01JointModelfromscratch;noG00teacher/fallback/pretrainedweights. NoDEVlookup/checkpointselection. All originalbenchmarksunchanged.',data_sha256=digest(path),natural_mask_sha256=digest(maskpath),seed=20261117,split='Fresh deterministic20/94wholeTRAINgroupsheldout,74fitgroups. Seen-group controls are disjoint sampledrows,not groupheldout and mayhave nearby samegamestate. Everycandidate row is identity-certified natural sampling; quotas deliberately balance action/diverse move contexts,not natural frequency. Never call oldtrainedmodels independentfoldpredictors.',groups=dict(held=sorted(held),fit=sorted(set(map(int,groups))-held)),indices_sha256={k:__import__('hashlib').sha256(v.tobytes()).hexdigest() for k,v in indices.items()},supports={s:dict(rows=len(idx),per_family={name:int((y[idx]==code).sum()) for code,name in enumerate(rt.LABELS)}) for s,idx in indices.items()},architecture=config,normalization='Fit rows only;causal historical encodings as originalruntime;no row/groupIDs in model input.',optimization=dict(updates=2000,batch=128,optimizer='AdamW',lr_first1000=.003,lr_last1000=.001,weight_decay=0,gradient_clip=5,loss='unweightedactionCE +spatialCE +priorityintegerNLL,sum/fullbatch;shoppurchaseargsremainunobserved',presentations=256000),assessment_steps=[0,100,500,1000,2000],checkpoint='Fixed finalstep2000;intermediateevaluationsdescriptive,noearlystopping,thresholdtuning orfoldselection. This capacitydiagnostic does not use the original DEVcheckpoint rule and cannot promote a model.',questions=['Can existingarchitecturefit a smalldiverse set with this boundedoptimization?','How much degrades on disjointrows inseen groups and freshgroupheldout rows?'],limits='Onefold,oneseed,finitebudget. Fitfailure does not prove data insufficiency or a hardcapacity limit;fit success does not provepolicyrecoverability. Rarefamilysupportexplicit,not certified. FrozenP05priorityhead not used;originalM01singlelogisticcanbe a parameter bottleneck.',reserved_opened=0,new_large_models=0)
    immutable_json(REPORT/'R02-plan.json',plan);np.savez(directory/'row-indices.npz',**indices)
    combined=np.concatenate(list(indices.values()));raw={}
    with np.load(path) as z:
        for key in z.files:raw[key]=z[key][combined]
    rawsets={};data={};a=0;normalizer=None
    for s,idx in indices.items():
        b=a+len(idx);rawsets[s]={k:v[a:b] for k,v in raw.items()};data[s],norm=rt.model_data(rawsets[s],config,normalizer)
        if s=='fit':normalizer=norm
        a=b
    del raw
    model=JointModel(data['fit']['x'].shape[1],24,len(rt.LABELS),config);opt=torch.optim.AdamW(model.parameters(),lr=.003,weight_decay=0);trace=[];start=time.perf_counter()
    def assess(step):
        model.eval();row=dict(step=step,seconds=time.perf_counter()-start,sets={})
        for s,d in data.items():
            pred=rt.infer(model,d);row['sets'][s]=rt.summarize(rawsets[s],pred)
            if step==2000:np.savez_compressed(directory/f'{s}-predictions.npz',**pred)
        trace.append(row);print('R02',step,{s:(r['strict_full_command_accuracy'],r['accuracy'],r['parameters']['move']['exact_accuracy']) for s,r in row['sets'].items()},flush=True)
    assess(0)
    for step in range(1,2001):
        model.train()
        if step==1001:
            for g in opt.param_groups:g['lr']=.001
        idx=torch.from_numpy(rng.integers(len(indices['fit']),size=128));d=data['fit'];logits,c=model(d['x'][idx],d['history'][idx]);labels=d['y'][idx];py=d['py'][idx];loss=F.cross_entropy(logits,labels);sp=py>=0
        if sp.any():loss+=F.cross_entropy(model.parameter_logits(c[sp],d['grid'][idx[sp]].float(),d['valid'][idx[sp]],labels[sp],d['rules'][idx[sp]]),py[sp],reduction='sum')/len(idx)
        priority=labels==9
        if priority.any():loss-=priority_log_mass(model.priority(c[priority]),d['priority'][idx[priority]]).sum()/len(idx)
        opt.zero_grad();loss.backward();torch.nn.utils.clip_grad_norm_(model.parameters(),5);opt.step()
        if step in (100,500,1000,2000):assess(step)
    checkpoint=directory/'final.pt';torch.save(dict(state_dict=model.state_dict(),config=config,mean=normalizer[0],std=normalizer[1],labels=rt.LABELS,plan_sha256=digest(REPORT/'R02-plan.json'),step=2000),checkpoint)
    immutable_json(REPORT/'R02-capacity.json',dict(plan_sha256=digest(REPORT/'R02-plan.json'),trace=trace,checkpoint_sha256=digest(checkpoint),indices_sha256=digest(directory/'row-indices.npz'),predictions_sha256={s:digest(directory/f'{s}-predictions.npz') for s in indices},parameters=sum(p.numel() for p in model.parameters()),seconds=time.perf_counter()-start,optimizer_updates=2000,new_large_models=0,reserved_opened=0,production_model=False))
    print('R02 complete;fresh mandated Solxhighreview before any further fitting',flush=True)

if __name__=='__main__':run()
