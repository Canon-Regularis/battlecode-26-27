"""Matched V66 follow-up: only goal representation changes during fitting."""
import argparse,time
from pathlib import Path
import numpy as np
import torch
from . import goal_execution_fit as prior,goal_execution_edit as calibration
from .bounded_goal_execution import bounded_goal
from ..audit import immutable_json
from ..data import digest

ROOT=prior.ROOT;REPORT=ROOT/'tools/action_predictor/experiments/v68';WORK=ROOT/'.cambc/action-predictor/v68'
read,check,bindings=prior.read,prior.check,prior.bindings


def freeze():
    REPORT.mkdir(parents=True,exist_ok=True);prior.inputs();check(read(prior.REPORT/'verification.json'));calibration.inputs();check(read(calibration.REPORT/'verification.json'));p=read(prior.REPORT/'plan.json')
    config={k:p[k] for k in ('seed','horizons','epochs','every','lr','batch','clip')}
    immutable_json(REPORT/'plan.json',dict(**config,sources=bindings([Path(__file__).with_name(n) for n in ('bounded_goal_execution.py','bounded_goal_execution_fit.py','bounded_goal_execution_predictor.py','test_bounded_goal_execution.py')]),
        inputs=bindings([prior.REPORT/n for n in ('plan.json','cache.json','fit.json','selection.json','result.json','verification.json')]+[calibration.REPORT/n for n in ('plan.json','inspection.json','result.json','verification.json')]),fit_seconds_cap=600,
        intervention='Same8833parameter executor architecture and frozen V59/V62 models. Replace only8 supplied-goal features with bounded unit direction(x,y),clipped Chebyshev progress,clipped route progress,next/current goal-region membership,move-direction cosine,and availability. Each is in[-1,1]. Absolute goal distance and scalar radius are omitted; region shape still enters route progress/membership. Retrain the executor from matched fresh initialization,not by reinterpreting already-trained input weights.',
        matched_control='Reuse completed V66 goal-conditioned arm as original-feature control. Same seed66001,initial tensors,training rows,horizon weighting,permutations,optimizer settings,16passes,and0/4/8/12/16selection opportunities. Verify exact schedules and initialization against original archives. No additional control repeat.',
        selection='Same as V66: four fitting-game folds; select most supplied-goal diagnostic correct movements,then lowest NLL,then earlier epoch. One full refit selected duration. No evaluation-guided choices.',
        success='Primary transfer test on unchanged513 queries with frozen predicted V62 goals: exceed original V66,calibrated V67,and V59 direct correct counts; NLL<=direct+0.01. Supplied-future-goal diagnostic accuracy must lose<=2points vsV66. All required;80percent still411/513. Diagnostic goals remain privileged information. No promotion automatically.',
        limits='This changes representation plus learned weights,not a manual existing-weight-only edit. Removes potentially useful distance/urgency information from goal-specific channels; original map/context features remain. Bounded ranges do not prove equivalent task semantics or resolve high-level goal choice. Point-goal demonstrations versus region goals,teacher-forced history,preexposed games,one paired seed,no autonomous outcomes/strategy proof. No subagents.'))


def inputs():
    p=read(REPORT/'plan.json');check(p);prior.inputs();check(read(prior.REPORT/'cache.json'));check(read(prior.REPORT/'fit.json'));return p


def bank(name):
    value=torch.load(prior.WORK/(name+'.pt'),weights_only=True);return dict(value,goal=bounded_goal(value['goal']))


def fit():
    start=time.perf_counter();p=inputs();torch.set_num_threads(1);rows=read(prior.WORK/'rows.json');values={}
    for fold in range(4):
        data=bank(f'fold{fold}');training=np.array([i for i,r in enumerate(rows) if r['fold']!=fold]);held=np.array([i for i,r in enumerate(rows) if r['fold']==fold and r['canonical']])
        _,v=prior.train('goal',data,rows,training,held,p,p['epochs'],WORK/f'fold{fold}',start+p['fit_seconds_cap'])
        for e,s in v.items():values.setdefault(e,[]).append(s)
    cs=[dict(epoch=e,**{k:sum(v[k] for v in vs) for k in ('rows','correct','nll_sum')}) for e,vs in values.items()];selected=prior.select(cs);immutable_json(REPORT/'selection.json',dict(selected=selected,candidates=cs,evaluation_used=False))
    data=bank('full');net,_=prior.train('goal',data,rows,np.arange(len(rows)),None,p,selected['epoch'],WORK/'refit',start+p['fit_seconds_cap']);torch.save(net.state_dict(),WORK/'selected.pt');bound=bindings([q for q in WORK.rglob('*') if q.is_file()]);elapsed=time.perf_counter()-start
    if elapsed>=p['fit_seconds_cap']:raise TimeoutError('Bounded executor publication exceeded')
    immutable_json(REPORT/'fit.json',dict(bindings=bound,seconds=elapsed));print('SELECTED',selected,flush=True)


def causal_bank(split):
    check(read(calibration.REPORT/'result.json'));data=torch.load(calibration.WORK/(split+'.pt'),weights_only=False);return dict(data,goal=bounded_goal(data['goal']))


def assessment():
    p=inputs();check(read(REPORT/'fit.json'));torch.set_num_threads(4);selected=torch.load(WORK/'selected.pt',weights_only=True);net=prior.new('goal',p);net.load_state_dict(selected)
    data=bank('assessment-bank');rows=read(prior.WORK/'assessment-rows.json');diagnostic={};causal={}
    for split in ('fit','evaluation'):
        ix=np.array([i for i,r in enumerate(rows) if r['split']==split]);diagnostic[split]=prior.score(net,data,rows,ix);causal[split]=calibration.score(causal_bank(split),selected)
    old=read(prior.REPORT/'result.json');edited=read(calibration.REPORT/'result.json');x=causal['evaluation'];reference=old['causal']['evaluation'];d=diagnostic['evaluation'];od=old['diagnostic']['evaluation']['goal']
    gates=dict(original=x['correct']>reference['goal']['correct'],calibrated=x['correct']>edited['results']['evaluation']['edited']['correct'],direct=x['correct']>reference['direct'],nll=x['nll_sum']/x['rows']<=reference['direct_nll']+.01,diagnostic=d['correct']>=od['correct']-.02*od['rows'])
    return dict(diagnostic=diagnostic,causal=causal,checks=gates,all_checks_pass=all(gates.values()),target_met=x['rows']==513 and x['correct']>=411,promoted=False)


def assess():
    result=assessment();immutable_json(REPORT/'result.json',dict(**result,bindings=bindings([WORK/'selected.pt',prior.WORK/'assessment-bank.pt',prior.WORK/'assessment-rows.json',calibration.WORK/'fit.pt',calibration.WORK/'evaluation.pt'])));print('RESULT',result['checks'],{k:v for k,v in result['causal']['evaluation'].items() if k not in ('predictions','losses')},flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('command',choices=('freeze','fit','assess'));globals()[p.parse_args().command]()
