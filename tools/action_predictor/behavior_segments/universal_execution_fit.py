"""Fit a causal movement fallback on every available fitting movement root."""
import argparse,time
from pathlib import Path
import numpy as np
import torch
from . import goal_execution_fit as prior,goal_execution_edit as calibration
from ..audit import immutable_json

ROOT=prior.ROOT;REPORT=ROOT/'tools/action_predictor/experiments/v69';WORK=ROOT/'.cambc/action-predictor/v69'
read,check,bindings=prior.read,prior.check,prior.bindings


def freeze():
    REPORT.mkdir(parents=True,exist_ok=True);calibration.inputs();check(read(calibration.REPORT/'verification.json'))
    immutable_json(REPORT/'plan.json',dict(sources=bindings([Path(__file__),Path(__file__).with_name('universal_execution_predictor.py'),Path(__file__).with_name('test_universal_execution.py')]),
        inputs=bindings([calibration.REPORT/n for n in ('plan.json','cache.json','selection.json','result.json','verification.json')]+[prior.REPORT/n for n in ('plan.json','cache.json','fit.json','verification.json')]),
        seed=66001,epochs=16,every=4,lr=.001,batch=128,clip=5.,fit_seconds_cap=600,
        intervention='Freeze V59 and calibrated V67 goal executor/selector. Fresh 8833-parameter goal-blind residual learns all 12318 expanded fitting movement roots once per epoch, with no future-goal eligibility or horizon duplication. At inference use this fallback only when no current goal is selected. Keep active-goal outputs unchanged.',
        selection='Four existing fitting-game folds. Train on expanded other24games; score hybrid predicted-goal execution on all1997 canonical held fitting moves. Select highest count among epochs0,4,8,12,16 with NLL<=initial+0.01; then lowest NLL,then earliest epoch. Epoch0 eligible. One full refit. No evaluation selection.',
        success='On unchanged513 evaluation moves require improvement over calibrated317 and direct318, movement NLL<=direct+0.01, and exact preservation of active-goal predictions.80percent requires411/513. No automatic promotion.',
        interpretation='This changes training coverage/weighting and inference coverage together; it is not a clean architecture-only contrast. Fallback learning is execution,not evidence of long-term strategy. Reused research groups,one seed,observed past actions,inferred goals and inherited fold exposure remain limitations. No subagents.'))


def inputs():
    p=read(REPORT/'plan.json');check(p);_,parent,architecture,cache,ids=calibration.inputs();return p,parent,architecture,cache,ids


def records(data,ids):
    return [dict(window=int(w),position=int(i),key=ids[w]['key'],group=ids[w]['group'],fold=ids[w]['fold'],canonical=ids[w]['canonical'],label=int(data['movement_labels'][w,i])) for w,i in (data['movement_labels']>=0).nonzero().tolist()]


@torch.no_grad()
def feature_bank(name,parent,architecture,cache,rows):
    context=prior.waypoint.cached_features(name,parent,architecture,cache);data=prior.base.dataset(name,cache);net=prior.waypoint.selected(name,parent,architecture)
    raw=torch.cat([net(prior.recurrent.take(data,slice(i,i+16)))['move'] for i in range(0,len(data['observed']),16)])
    w=torch.tensor([r['window'] for r in rows]);i=torch.tensor([r['position'] for r in rows]);labels=data['movement_labels'][w,i]
    assert labels.tolist()==[r['label'] for r in rows]
    bank=dict(context=context[w,i],baseline=raw[w,i],goal=torch.zeros(len(rows),9,8),support=data['support'][w,i],labels=labels)
    assert bank['support'].gather(1,labels[:,None]).all() and all(not v.requires_grad for v in bank.values())
    return bank


def prepare():
    p,parent,architecture,cache,ids=inputs();torch.set_num_threads(4);WORK.mkdir(parents=True,exist_ok=False)
    rows=records(prior.base.dataset('full',cache),ids);assert len(rows)==12318 and len({r['group'] for r in rows})==32 and len({(r['key'],r['position']) for r in rows})==len(rows)
    immutable_json(WORK/'rows.json',rows)
    for name in ['fold0','fold1','fold2','fold3','full']:
        bank=feature_bank(name,parent,architecture,cache,rows);torch.save(bank,WORK/(name+'.pt'));net=prior.new('control',p)
        pred=net(bank['context'][:128],bank['goal'][:128],bank['baseline'][:128]);assert torch.equal(pred,bank['baseline'][:128]);loss=torch.nn.functional.cross_entropy(pred.masked_fill(~bank['support'][:128],-1e9),bank['labels'][:128]);loss.backward();assert all(v.grad is None or torch.isfinite(v.grad).all() for v in net.parameters())
        print('Prepared universal fallback',name,len(rows),flush=True)
    old=read(prior.WORK/'rows.json');oldkeys={(r['key'],r['position']) for r in old}
    immutable_json(REPORT/'cache.json',dict(bindings=bindings(list(WORK.iterdir())),rows=len(rows),groups=32,previous_goal_training_unique=len(oldkeys),additional_roots=sum((r['key'],r['position']) not in oldkeys for r in rows),evaluation_used=False,initial_baseline_exact=True,finite_backward=True))


def goal_weights(name):
    return calibration.edit(calibration.weights(name),**read(calibration.REPORT/'selection.json')['selected']['setting'])


@torch.no_grad()
def score(bank,fallback,goal):
    p=read(REPORT/'plan.json');f=prior.new('control',p);f.load_state_dict(fallback);g=prior.new('goal',p);g.load_state_dict(goal)
    active=torch.tensor([r['active'] for r in bank['records']]);labels=torch.tensor([r['label'] for r in bank['records']]);predictions=[];losses=[]
    for start in range(0,len(labels),256):
        sl=slice(start,start+256);args=(bank['context'][sl],bank['goal'][sl],bank['baseline'][sl]);raw=torch.where(active[sl,None],g(*args),f(*args));lp=raw.masked_fill(~bank['support'][sl],-1e9).log_softmax(-1)
        predictions.extend(lp.argmax(-1).tolist());losses.extend((-lp.gather(1,labels[sl].clamp_min(0)[:,None]).squeeze(1)).tolist())
    cohorts={}
    for name,wanted in [('all',None),('goal',True),('fallback',False)]:
        ix=[i for i,r in enumerate(bank['records']) if r['label']>=0 and (wanted is None or r['active']==wanted)]
        cohorts[name]=dict(rows=len(ix),correct=sum(predictions[i]==bank['records'][i]['label'] for i in ix),nll_sum=sum(losses[i] for i in ix))
    return dict(**cohorts['all'],cohorts=cohorts,predictions=predictions,losses=losses)


def select(cs):
    initial=next(c for c in cs if c['epoch']==0);eligible=[c for c in cs if c['nll_sum']/c['rows']<=initial['nll_sum']/initial['rows']+.01]
    return prior.select(eligible)


def fit():
    start=time.perf_counter();p,_,_,_,_=inputs();check(read(REPORT/'cache.json'));torch.set_num_threads(1);rows=read(WORK/'rows.json');values={}
    for fold in range(4):
        name=f'fold{fold}';bank=torch.load(WORK/(name+'.pt'),weights_only=True);training=np.array([i for i,r in enumerate(rows) if r['fold']!=fold]);held=torch.load(calibration.WORK/(name+'.pt'),weights_only=False);goal=goal_weights(name)
        prior.train('control',bank,rows,training,None,p,p['epochs'],WORK/name,start+p['fit_seconds_cap'])
        for epoch in range(0,p['epochs']+1,p['every']):
            s=score(held,torch.load(WORK/name/f'epoch-{epoch:03d}.pt',weights_only=True),goal);values.setdefault(epoch,[]).append(s)
    cs=[dict(epoch=e,**{k:sum(v[k] for v in vs) for k in ('rows','correct','nll_sum')}) for e,vs in values.items()];chosen=select(cs);assert all(c['rows']==1997 for c in cs)
    immutable_json(REPORT/'selection.json',dict(candidates=cs,selected=chosen,evaluation_used=False));immutable_json(WORK/'fold-validation.json',values)
    bank=torch.load(WORK/'full.pt',weights_only=True);net,_=prior.train('control',bank,rows,np.arange(len(rows)),None,p,chosen['epoch'],WORK/'refit',start+p['fit_seconds_cap']);torch.save(net.state_dict(),WORK/'selected.pt')
    bound=bindings([q for q in WORK.rglob('*') if q.is_file()]);elapsed=time.perf_counter()-start
    if elapsed>=p['fit_seconds_cap']:raise TimeoutError('Universal fallback publication cap')
    immutable_json(REPORT/'fit.json',dict(bindings=bound,seconds=elapsed));print('SELECTED',chosen,flush=True)


def assessment():
    selected=torch.load(WORK/'selected.pt',weights_only=True);goal=goal_weights('full');values={};old=read(calibration.REPORT/'result.json')['results']
    for split in ('fit','evaluation'):
        bank=torch.load(calibration.WORK/(split+'.pt'),weights_only=False);value=score(bank,selected,goal);comparisons={}
        for name in ('edited','direct'):
            previous=old[split][name]['predictions'];ix=[i for i,r in enumerate(bank['records']) if r['label']>=0];pred=value['predictions'];rs=bank['records']
            comparisons[name]=dict(rescues=sum(previous[i]!=rs[i]['label'] and pred[i]==rs[i]['label'] for i in ix),regressions=sum(previous[i]==rs[i]['label'] and pred[i]!=rs[i]['label'] for i in ix))
        assert all(value['predictions'][i]==old[split]['edited']['predictions'][i] for i,r in enumerate(bank['records']) if r['active'])
        values[split]=dict(**value,comparisons=comparisons)
    x=values['evaluation'];reference=old['evaluation'];checks=dict(calibrated=x['correct']>reference['edited']['correct'],direct=x['correct']>reference['direct']['correct'],nll=x['nll_sum']<=reference['direct']['nll_sum']+.01*x['rows'],active_goal_unchanged=True)
    return dict(results=values,checks=checks,all_checks_pass=all(checks.values()),target_met=x['rows']==513 and x['correct']>=411,promoted=False)


def assess():
    inputs();check(read(REPORT/'fit.json'));torch.set_num_threads(4);result=assessment();immutable_json(REPORT/'result.json',dict(**result,bindings=bindings([WORK/'selected.pt',calibration.WORK/'selected.pt',calibration.WORK/'fit.pt',calibration.WORK/'evaluation.pt'])))
    print('RESULT',result['checks'],{k:v for k,v in result['results']['evaluation'].items() if k not in ('predictions','losses')},flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('command',choices=('freeze','prepare','fit','assess'));globals()[parser.parse_args().command]()
