"""A01: fixed signed-anchor priority baselines, trained on recorded TRAIN labels."""
import argparse,gzip,json,math,sys
from collections import defaultdict
from pathlib import Path
import numpy as np
import torch
from .category_study import ROOT,WORK,REPORTS
from .more_replays import frozen,sha
from . import reliable_train as rt
from .priority_modes import logistic_log_mass
from .priority_inputs import PriorityMemory
from .priority_fit_v3 import BASE,VAL,read,log,gate
from . import priority_modes_control as parent
from .rich_data import read_turns
from .audit import cursor
from .observation_metrics import correctness

PLAN=REPORTS/'priority-anchor-plan.json';SOURCES=REPORTS/'priority-anchor-sources.json'
PRIORS=REPORTS/'priority-anchor-priors.json';PREFIT=REPORTS/'priority-anchor-prefit.json'
ANCHORS=(('current',0,1),('scheduled',2,3),('latest',4,5))
FAMILIES=[dict(name='global_frequency',mode='global')]+[dict(name=name+('_plus_' if sign==1 else '_minus_')+mode,mode=mode,anchor=name,column=column,mask=mask,sign=sign) for name,column,mask in ANCHORS for sign in (1,-1) for mode in ('copy','residual')]

def sources():return {str(Path(__file__).with_name(n)):sha(Path(__file__).with_name(n)) for n in ('priority_anchor_baselines.py','test_priority_anchor_baselines.py')}

def integers(a):
    a=np.asarray(a);assert a.ndim==1 and a.dtype.kind in 'iuf' and np.isfinite(a).all()
    result=np.asarray([int(x) for x in a],dtype=np.int64)
    assert np.array_equal(a,result),'Recorded integer required; never round labels'
    return result

def differences(target,anchor):
    target=integers(target);anchor=integers(anchor);assert target.shape==anchor.shape,'Residual row alignment mismatch'
    return np.asarray([int(t)-int(a) for t,a in zip(target,anchor)],dtype=np.int64)

def prior_fit(target,copy=False):
    target=integers(target);assert len(target)
    if copy:values,counts=np.asarray([0],np.int64),np.asarray([1],np.int64)
    else:values,counts=np.unique(target,return_counts=True)
    count=torch.from_numpy(counts).double()
    logits=torch.cat((.95*count/count.sum(),torch.tensor([.05],dtype=torch.float64))).log().float()
    location=np.float32(np.median(target)/100)
    scale=max(float(target.astype(np.float64).std())*math.sqrt(3)/math.pi/100,math.exp(-6))
    log_scale=np.float32(np.log(scale))
    return dict(values=values.tolist(),counts=counts.tolist(),logits_fp32=logits.tolist(),location_fp32=float(location),log_scale_fp32=float(log_scale),fit_support=len(target))

def prior_log_mass(prior,target):
    target=torch.from_numpy(integers(target));values=torch.tensor(prior['values'],dtype=torch.int64)
    mix=torch.tensor(prior['logits_fp32'],dtype=torch.float64).log_softmax(-1)
    index=torch.searchsorted(values,target);safe=index.clamp(max=len(values)-1)
    point=mix[safe].masked_fill((index>=len(values))|(values[safe]!=target),-torch.inf)
    raw=torch.tensor([[prior['location_fp32'],prior['log_scale_fp32']]],dtype=torch.float64).expand(len(target),-1)
    fallback=mix[-1]+logistic_log_mass(raw,target)
    return torch.logaddexp(point,fallback).numpy()

def prior_mode(prior):
    center=prior['location_fp32']*100
    candidates=np.unique(np.asarray(prior['values']+[math.floor(center),math.ceil(center)],dtype=np.int64))
    return int(candidates[np.argmax(prior_log_mass(prior,candidates))]) # Smallest-integer ties.

def validate_values(values):
    assert values.dtype==np.int64 and values.ndim==2 and values.shape[1]==7
    assert np.isin(values[:,[1,3,5]],[0,1]).all() and (values[:,6]>=0).all()
    for column,mask in ((0,1),(2,3),(4,5)):assert (values[values[:,mask]==0,column]==0).all()

def anchor_values(family,values):
    validate_values(values)
    anchor=np.asarray([family['sign']*int(x) for x in values[:,family['column']]],dtype=np.int64)
    return anchor,values[:,family['mask']]==1

def fit_priors(values,target):
    validate_values(values);target=integers(target);assert len(values)==len(target)
    global_prior=prior_fit(target);result={'global_frequency':dict(prior=global_prior,available_support=len(target),missing_support=0)}
    for family in FAMILIES[1:]:
        anchor,available=anchor_values(family,values)
        residual=differences(target[available],anchor[available])
        result[family['name']]=dict(prior=prior_fit(residual,family['mode']=='copy') if len(residual) else None,
            available_support=int(available.sum()),missing_support=int((~available).sum()),
            recorded_residuals_over1000=int((np.abs(residual)>1000).sum()),recorded_plus1400=int((residual==1400).sum()),recorded_minus1400=int((residual==-1400).sum()))
    return result

def forecast(family,priors,values):
    validate_values(values);global_prior=priors['global_frequency']['prior']
    result=np.full(len(values),prior_mode(global_prior),np.int64)
    if family['mode']=='global':return result
    anchor,available=anchor_values(family,values);prior=priors[family['name']]['prior']
    if prior is not None:
        residual_mode=prior_mode(prior)
        result[available]=np.asarray([int(a)+residual_mode for a in anchor[available]],np.int64)
    return result

def log_mass(family,priors,values,target):
    validate_values(values);target=integers(target);assert len(values)==len(target)
    result=prior_log_mass(priors['global_frequency']['prior'],target)
    if family['mode']=='global':return result
    anchor,available=anchor_values(family,values);prior=priors[family['name']]['prior']
    if prior is not None:result[available]=prior_log_mass(prior,differences(target[available],anchor[available]))
    return result

def verify_parent():
    parent.verify_protocol();review=read(REPORTS/'P04-review.json');assert review['verdict']=='APPROVE'
    for file,key in (('P04.json','fit_report_sha256'),('P04-analysis.json','analysis_sha256'),('P04-input-gate-amendment.json','gate_amendment_sha256')):assert sha(REPORTS/file)==review[key]
    info=read(REPORTS/'P04.json')
    for file,key in (('model.pt','checkpoint_sha256'),('validation-predictions.npz','predictions_sha256'),('priority-outputs.npy','priority_outputs_sha256')):assert sha(WORK/'runs/P04'/file)==info[key]

def training():
    with np.load(BASE/'combined-train.npz') as z:mask=z['y']==rt.LABELS.index('priority');target=z['priority'][mask]
    with np.load(WORK/'priority-train.npz') as z:values=z['values'][mask]
    return values,integers(target)

def verify_protocol():
    verify_parent();source=read(SOURCES);plan=read(PLAN)
    assert source['sources']==sources() and source['parent_sources_sha256']==sha(parent.SOURCES)
    assert plan['sources_sha256']==sha(SOURCES) and plan['P04_review_sha256']==sha(REPORTS/'P04-review.json')
    assert plan['families']==FAMILIES and plan['training_sha256']==sha(BASE/'combined-train.npz')
    assert plan['priority_training_sha256']==sha(WORK/'priority-train.npz')
    priors=read(PRIORS);assert priors['plan_sha256']==sha(PLAN)
    values,target=training();assert priors['priors']==fit_priors(values,target),'Training prior reconstruction mismatch'
    global_prior=priors['priors']['global_frequency']['prior'];original=read(REPORTS/'priority-frequency-baseline-plan.json')
    assert global_prior['values']==original['values'] and global_prior['counts']==original['counts']
    assert global_prior['location_fp32']==float(np.float32(original['fallback_location']))
    assert global_prior['log_scale_fp32']==float(np.float32(original['fallback_log_scale']))
    return plan,priors['priors']

def training_roundtrip(priors):
    jobs=read(ROOT/'.cambc/action-predictor/v7/jobs.json')
    selected=[next(j for j in jobs if j['split']=='train' and j['record']['engine_version']==version) for version in ('2.0.0','3.0.0')]
    with np.load(WORK/'priority-train.npz') as z:stored=z['values']
    cases=0
    for job in selected:
        digest=job['record']['raw_sha256'];index=Path(job['manifest']['source'])/'extracted'/digest/'index.jsonl';events=defaultdict(list)
        for line in index.open():
            turn=json.loads(line)
            if turn.get('record')=='turn':
                for root in turn['roots']:events[turn['actor']].append((root,turn['round']))
        for rows in events.values():rows.sort(key=lambda p:cursor(p[0]['event']))
        states={}
        with gzip.open(WORK/'priority'/digest/'pre.jsonl.gz','rt') as stream:
            for line in stream:
                row=json.loads(line)
                if row['record']=='priority_pre':states[row['event']]=row
        targets=[(turn,d) for turn in read_turns(job['manifest'],job['record']) for d in turn['decisions']]
        for local in sorted({0,len(targets)//2,len(targets)-1}):
            turn,d=targets[local];memory=PriorityMemory(turn['actor'])
            assert cursor(d['pre_cursor'])<cursor(d['event_cursor'])
            for root,round_number in events[turn['actor']]:
                if cursor(root['event'])>cursor(d['pre_cursor']):break
                memory.observe(root['header']['step'],root['event'],round_number)
            state=states[d['event_cursor']]
            assert state['actor']==turn['actor'] and state['round']==turn['round'] and state['pre']==d['pre_cursor']
            actual,_=memory.inputs(state,d['pre_cursor'],turn['round'])
            expected=stored[job['offset']+local];np.testing.assert_array_equal(actual,expected)
            for family in FAMILIES:np.testing.assert_array_equal(forecast(family,priors,actual[None]),forecast(family,priors,expected[None]))
            cases+=1
    return dict(cases=cases,games=len(selected),engines=['2.0.0','3.0.0'],split='training_only',selection='First/middle/last target of first eligible training game per engine',inputs_exact=True,forecasts_exact=True)

def prepare():
    verify_parent();gate()
    directory=WORK/'anchor-baseline-sources';directory.mkdir(exist_ok=True)
    for path,digest in sources().items():
        dest=directory/(digest+'_'+Path(path).name)
        if not dest.exists():dest.write_bytes(Path(path).read_bytes())
        assert sha(dest)==digest
    frozen(SOURCES,dict(sources=sources(),parent_sources_sha256=sha(parent.SOURCES)))
    # Static family/formulas locked before fitting counts, with no new dev evaluation.
    frozen(PLAN,dict(id='A01',families=FAMILIES,sources_sha256=sha(SOURCES),P04_review_sha256=sha(REPORTS/'P04-review.json'),training_sha256=sha(BASE/'combined-train.npz'),priority_training_sha256=sha(WORK/'priority-train.npz'),
        hypothesis='Signed causal priorities and recorded residual frequencies may outperform absolute value modes; no benefit assumed.',
        anchors='Only own personal-PRE current/scheduled priority and latest actual earlier own priority argument, each with its availability bit. Fixed sign+1/-1; no target-dependent sign choice.',
        copy='Predict signed anchor exactly; probabilistic score .95pointmass at residual0 plus .05trained-residual logistic fallback.',
        residual='Predict anchor plus global mode of .95training-recorded residual frequencies plus .05normalized full-support integer logistic. Residual=recorded target minus causal signed anchor only in training/loss; never feature input.',
        fallback='Unavailable anchor or no eligible training anchor support: unconditional training-frequency prior. Missing is explicit and all rows retained. Logistic median/std-derived from TRAIN only, old[-6,5]scale bounds; logits and parameters quantizedfloat32 then stablefloat64 log masses as retained baseline.',
        ties='Smallest integer among equal-probability global maxima; compare point vocabulary union floor and ceiling of logistic location. Checked int64 arithmetic raises overflow; no clipping or label rounding.',
        budget='Thirteen predeclared fixed baseline families; no neural optimizer, no seed repeats. Fresh reviewed bound approval before evaluating development behavior; fresh review after results before any learned residual design.',
        reporting='All families reported, without selecting signs/formulas from validation. Report strongest baselines separately by exact/joint/loss/error, with paired whole-group uncertainty and rare/unseen/missing strata. Any stronger loss baseline only tightens comparison; all original goals unchanged.',
        membership='Same433071training rows470games94groups, same14439development targets25games5groups. All43shops unassessed failures. FixedM01action/spatialpaths preserved in hybrid parameter comparisons.',
        guards='All original90%percategory,3seeds,macroF1,movement10pp,loss10%,targetingguards and frozen studies unchanged; no strategy labels. Both75-game reserved partitions sealed; old exposed test unused; no downloads/matches/botchanges/deployments/PR from this runner.'))
    values,target=training();priors=fit_priors(values,target)
    frozen(PRIORS,dict(plan_sha256=sha(PLAN),training_support=len(target),priors=priors))
    verify_protocol();roundtrip=training_roundtrip(priors)
    train_metrics={}
    for family in FAMILIES:
        prediction=forecast(family,priors,values);loss=-log_mass(family,priors,values,target)
        train_metrics[family['name']]=dict(exact=int((prediction==target).sum()),support=len(target),mean_nll=float(loss.mean()),mean_absolute_error=float(np.abs(prediction-target).mean()),available_support=priors[family['name']]['available_support'],missing_support=priors[family['name']]['missing_support'])
    frozen(PREFIT,dict(plan_sha256=sha(PLAN),sources_sha256=sha(SOURCES),priors_sha256=sha(PRIORS),training_only_metrics=train_metrics,training_roundtrip=roundtrip,new_development_evaluations=0,new_optimizer_steps=0))
    print('A01 training-only priors/protocol and causal proof frozen. STOP for fresh Sol xhigh review before evaluation.',flush=True)

def evaluate():
    plan,priors=verify_protocol();approval=read(REPORTS/'priority-anchor-code-approval.json')
    assert approval['verdict']=='APPROVE' and approval['plan_sha256']==sha(PLAN) and approval['sources_sha256']==sha(SOURCES)
    assert approval['prefit_sha256']==sha(PREFIT) and approval['priors_sha256']==sha(PRIORS)
    gate();verify_protocol();rt.setup(26)
    assert not (REPORTS/'A01.json').exists(),'Completed evaluation immutable'
    with np.load(VAL) as z:raw={k:z[k] for k in z.files}
    with np.load(WORK/'priority-validation.npz') as z:values=z['values'];outside=z['last_outside_window']
    with np.load(BASE/'runs/M01/validation-predictions.npz') as z:base={k:z[k] for k in z.files}
    mask=raw['y']==rt.LABELS.index('priority');groups=np.unique(raw['group']);rng=np.random.default_rng(20261106)
    draws=np.stack([np.bincount(rng.integers(0,len(groups),len(groups)),minlength=len(groups)) for _ in range(2000)])
    def sums(a,selected):return np.array([a[selected&(raw['group']==g)].sum() for g in groups])
    def interval(num,den):
        d=draws@den;ok=d>0;v=(draws@num)[ok]/d[ok]
        return dict(valid_draws=int(ok.sum()),interval=list(map(float,np.quantile(v,[.025,.975]))))
    models={};metrics={};comparisons={};directory=WORK/'anchor-baselines';directory.mkdir(exist_ok=True)
    original_frequency=dict(zip(priors['global_frequency']['prior']['values'],priors['global_frequency']['prior']['counts']))
    frequency=np.array([original_frequency.get(int(t),0) for t in raw['priority']])
    strata={'unseen_value':mask&(frequency==0),'training_count_1_19':mask&(frequency>0)&(frequency<20),'training_count_20_99':mask&(frequency>=20)&(frequency<100),'training_count_100_plus':mask&(frequency>=100),'no_previous':mask&(values[:,5]==0),'latest_outside16':mask&outside}
    for family in FAMILIES:
        name=family['name'];pred={k:v.copy() for k,v in base.items()}
        pred['priority']=forecast(family,priors,values);loss=-log_mass(family,priors,values[mask],raw['priority'][mask])
        pred['param_nll'][mask]=loss;pred['nll'][mask]=pred['type_nll'][mask]+loss
        _,joint=correctness(raw,pred);error=np.abs(pred['priority'][mask]-raw['priority'][mask]);available=np.ones(len(mask),bool) if family['mode']=='global' else values[:,family['mask']]==1
        path=directory/(name+'.npz');assert not path.exists();np.savez_compressed(path,**pred)
        summary=rt.summarize(raw,pred);summary['parameters']['priority']['exact_accuracy']=float((error==0).mean())
        summary['joint_per_action']={label:dict(support=int((raw['y']==i).sum()),joint_correct=int(joint[raw['y']==i].sum()),type_false_positives=int(((pred['prediction']==i)&(raw['y']!=i)).sum()),joint_false_positives=int((pred['prediction']==i).sum()-joint[raw['y']==i].sum()),observed_joint_nll=float(pred['nll'][raw['y']==i].mean()) if (raw['y']==i).any() else None) for i,label in enumerate(rt.LABELS)}
        metrics[name]=dict(priority_support=int(mask.sum()),priority_exact=int((error==0).sum()),priority_joint=int(joint[mask].sum()),priority_nll=float(loss.mean()),full_observed_joint_nll=float(pred['nll'].mean()),strict_correct=int(joint.sum()),
            mean_absolute_error=float(error.mean()),median_absolute_error=float(np.median(error)),maximum_absolute_error=int(error.max()),errors_over1000=int((error>1000).sum()),
            available_support=int((mask&available).sum()),available_exact=int(((pred['priority']==raw['priority'])&mask&available).sum()),missing_support=int((mask&~available).sum()),missing_exact=int(((pred['priority']==raw['priority'])&mask&~available).sum()),
            priority_strata={label:dict(support=int(selected.sum()),exact=int(((pred['priority']==raw['priority'])&selected).sum()),joint=int(joint[selected].sum()),nll=float(pred['param_nll'][selected].mean()) if selected.any() else None) for label,selected in strata.items()},
            per_group=[dict(group=int(g),support=int((mask&(raw['group']==g)).sum()),exact=int(((pred['priority']==raw['priority'])&mask&(raw['group']==g)).sum()),joint=int((joint&mask&(raw['group']==g)).sum())) for g in groups],predictions_sha256=sha(path),validation=summary)
        models[name]=pred
    p03_info=read(REPORTS/'P03.json');assert sha(WORK/'runs/P03/validation-predictions.npz')==p03_info['predictions_sha256']
    with np.load(WORK/'runs/P03/validation-predictions.npz') as z:p03={k:z[k] for k in z.files}
    _,p03_joint=correctness(raw,p03);counts=sums(np.ones(len(mask)),mask)
    for name,pred in models.items():
        _,joint=correctness(raw,pred)
        comparisons[name]=dict(exact_delta_vs_P03=interval(sums((pred['priority']==raw['priority']).astype(float)-(p03['priority']==raw['priority']),mask),counts),joint_delta_vs_P03=interval(sums(joint.astype(float)-p03_joint,mask),counts),
            priority_loss_reduction_vs_P03=interval(sums(p03['param_nll']-pred['param_nll'],mask),sums(p03['param_nll'],mask)))
    frozen(REPORTS/'A01.json',dict(plan_sha256=sha(PLAN),sources_sha256=sha(SOURCES),priors_sha256=sha(PRIORS),approval_sha256=sha(REPORTS/'priority-anchor-code-approval.json'),metrics=metrics,paired_comparisons=comparisons,
        interpretation='All13 predeclared baselines reported; validation-best by each metric is descriptive, not a tuned sign/formula or selected neural model. Full command support unchanged; all43shops unassessed.',
        uncertainty='2000whole-group paired resamples of five reused development groups; no independent generalization/seed confirmation.',groups=len(groups),new_optimizer_steps=0,reserved_games_opened=0,three_seed_confirmed=False,all_category_goal_met=False))
    print('A01 baseline evaluation complete. STOP for fresh Sol xhigh review before further work.',flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--prepare',action='store_true');p.add_argument('--evaluate',action='store_true');args=p.parse_args();assert args.prepare!=args.evaluate
    log([sys.executable,'-m','tools.action_predictor.priority_anchor_baselines',*sys.argv[1:]])
    prepare() if args.prepare else evaluate()
