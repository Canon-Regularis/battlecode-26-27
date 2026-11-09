"""C00 frozen-library coverage, eligible jobs only. Never opens replay archives."""
import argparse,json,sys,time
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor
from collections import Counter
import numpy as np
from ..audit import immutable_json,validate_decision
from ..data import digest,action_name
from ..rich_data import read_turns
from .. import reliable_train as rt
from .library import emit,NAMES

ROOT=Path(__file__).resolve().parents[3]
WORK=ROOT/'.cambc/action-predictor/v10';REPORT=ROOT/'tools/action_predictor/experiments/v10'
JOBS=ROOT/'.cambc/action-predictor/v7/jobs.json'

def freeze():
    WORK.mkdir(parents=True,exist_ok=True);REPORT.mkdir(parents=True,exist_ok=True)
    plan=dict(id='C00',ranked=['Measure TRAIN library coverage and same-size geometric control','Freeze source before DEV; measure every original DEV row','Fit one regularized causal command selector only if TRAIN coverage is informative','After fit fresh requested Sol xhigh review, then distinct diagnosed followup'],
        slots=NAMES,count=len(NAMES),complexity='5 objectives x3 planners;3 target ranks x3 families;2 ward,1submit,4utility. No destination enumeration, IDs or map routes. Eight-neighbour uniform terrain fields are planner hypotheses; emitted moves must belong to historical personal PRE engine movement mask. No claim hypothetical paths were engine-simulated.',
        memory='C00 has no carried latent state. Selector may consume frozen causal own-action history, with original gaps; no sampled-row adjacency.',
        useful_TRAIN_criterion='Movement union coverage >=0.60 OR at least0.03 of all TRAIN rows rescued beyond G00 strict commands. Exploratory allocation only, not original success.',
        coverage='Any strict family+required-parameter match. Shops always fail. Move attempts vsblocked remain different; separately report destination-only collapsed diagnostic. Coordinates cannot certify ambiguous entity identity.',
        fit_budget=dict(pilot_fits=2,seeds=[20261107],promising_repeat_seeds=[20261108,20261109],max_rounds=35,patience=6,minimum_dev_nll_improvement=.0001),
        frozen_targets='Original V8 success definition binding; sparse categories uncertified. No sealed or old exposed-test tuning. No downloads,matches,bot edits,deployment. DRAFT PR11 only.',
        jobs_sha256=digest(JOBS),sources={str(p.relative_to(ROOT)):digest(p) for p in Path(__file__).parent.glob('*.py')})
    immutable_json(REPORT/'C00-plan-r1.json',plan)
    return plan

def job_run(job):
    assert job['split'] in ('train','validation')
    record=job['record'];turns=read_turns(job['manifest'],record);supps={};route=None;bindings={}
    for suffix in ('supplement','augmentation'):
        path=Path(job['work'])/suffix/record['raw_sha256']/'pre.jsonl'
        if not path.exists():continue
        bindings[str(path)]=digest(path)
        for line in path.open(encoding='utf-8'):
            r=json.loads(line)
            if r['record']=='map':
                if route is not None:assert route==r['route']
                route=r['route']
            elif r['record']=='pre':
                if r['id'] in supps:assert supps[r['id']]==r
                supps[r['id']]=r
    assert route is not None and digest(job['shard'])==job['shard_sha256']
    with np.load(job['shard']) as z:y=z['y']
    result=np.full((len(y),2,len(NAMES),3),-1,np.int64);i=0;ambiguities=0
    for turn in turns:
        for d in turn['decisions']:
            validate_decision(d,turn);obs=d['observation'];s=supps[d['id']];assert s['pre']==d['pre_cursor']
            assert rt.LABELS[y[i]]==action_name(d['label'])
            for simple in (False,True):
                for k,c in enumerate(emit(obs,s,route,simple)):
                    if c is None:continue
                    family,pos,value=c;coord=-1
                    if pos is not None:
                        p=obs['own']['position'];dx,dy=pos[0]-p['x'],pos[1]-p['y']
                        if max(abs(dx),abs(dy))>8:continue
                        coord=(dy+8)*17+dx+8
                    result[i,int(simple),k]=[rt.LABELS.index(family),coord,value]
            i+=1
    assert i==job['rows']==len(y)
    return job['offset'],result,dict(raw=record['raw_sha256'],source=record.get('augmented_sha256',record['turns_sha256']),supplements=bindings,engine=record['engine_version'],rows=i)

def matches(commands,y,py,priority):
    return ((commands[:,:,0]==y[:,None]) & ((py[:,None]<0)|(commands[:,:,1]==py[:,None])) & ((y[:,None]!=rt.LABELS.index('priority'))|(commands[:,:,2]==priority[:,None])) & (y[:,None]!=rt.LABELS.index('shop')) & ((py[:,None]<289)))

def run(split):
    plan=freeze();assert digest(JOBS)==plan['jobs_sha256']
    # DEV may run only after an immutable TRAIN result and frozen source library.
    if split=='validation':assert (REPORT/'C00-train.json').exists()
    jobs=[j for j in json.loads(JOBS.read_text()) if j['split']==split]
    assert len(jobs)==(470 if split=='train' else 25)
    path=ROOT/('.cambc/action-predictor/v5/combined-train.npz' if split=='train' else '.cambc/action-predictor/v4/validation.npz')
    expected='39386010575ad30add064fdae750680f34cfcc732c4fd00fb657875ff4c61ffb' if split=='train' else '01a15e1e10f68922334a5367bb825c8ef9bbe228ae7a9e86e92aae9609b204ed'
    assert digest(path)==expected
    with np.load(path) as z:y=z['y'];py=z['py'];priority=z['priority'];group=z['group']
    out=np.full((len(y),2,len(NAMES),3),-1,np.int64);bindings=[]
    target=WORK/(split+'-candidates.npy');assert not target.exists(),'Preserve existing output; do not overwrite'
    with ProcessPoolExecutor(max_workers=4) as pool:
        for n,(offset,rows,binding) in enumerate(pool.map(job_run,jobs),1):
            out[offset:offset+len(rows)]=rows;bindings.append(binding)
            if n%25==0 or n==len(jobs):print(split,n,'/',len(jobs),flush=True)
    np.save(target,out)
    predpath=ROOT/'.cambc/action-predictor/v9/runs/G00'/f'{split}-predictions.npz'
    with np.load(predpath) as z:
        baseline=np.stack((z['prediction'],z['proposed_coordinate'],z['priority']),axis=-1)[:,None,:]
    base=matches(baseline,y,py,priority).any(1);reports={}
    for mode,name in enumerate(('algorithmic','simple')):
        c=out[:,mode];m=matches(c,y,py,priority);covered=m.any(1)
        distinct=Counter(len({tuple(v) for v in row if v[0]>=0}) for row in c)
        families={}
        for k,label in enumerate(rt.LABELS):
            mask=y==k;n=int(mask.sum());families[label]=dict(support=n,covered=int(covered[mask].sum()),coverage=float(covered[mask].mean()) if n else None,unexplained=int((~covered[mask]).sum()))
        blocked=y==rt.LABELS.index('blocked');collapsed=((c[:,:,0]==rt.LABELS.index('move'))&(c[:,:,1]==py[:,None])).any(1)
        reports[name]=dict(covered=int(covered.sum()),coverage=float(covered.mean()),per_family=families,distinct_outputs=dict(sorted(distinct.items())),per_slot_matches=dict(zip(NAMES,map(int,m.sum(0)))),rescues_beyond_G00=int((covered&~base).sum()),blocked_destination_only_diagnostic=int((blocked&collapsed).sum()),per_group={str(int(g)):dict(rows=int((group==g).sum()),coverage=float(covered[group==g].mean())) for g in np.unique(group)})
    immutable_json(REPORT/f'C00-{split}.json',dict(plan_sha256=digest(REPORT/'C00-plan-r1.json'),data_sha256=expected,candidates_sha256=digest(target),G00_predictions_sha256=digest(predpath),rows=len(y),groups=len(np.unique(group)),libraries=reports,bindings=bindings,reserved_opened=0,shop_assessed=0,strict_entity_identity_certified=False))
    print(json.dumps(reports,indent=2),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('split',choices=['train','validation']);a=p.parse_args();run(a.split)
