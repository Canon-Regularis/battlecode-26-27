"""Direct weight calibration of the shared, always-active movement executor."""
import argparse
from pathlib import Path
import numpy as np
import torch
from . import shared_goal_execution_fit as prior
from ..audit import immutable_json

ROOT=prior.ROOT;REPORT=ROOT/'tools/action_predictor/experiments/v71';WORK=ROOT/'.cambc/action-predictor/v71'
read,check,bindings=prior.read,prior.check,prior.bindings


def edit(weights,goal_scale=1.,output_scale=1.):
    if goal_scale<=0 or output_scale<=0:raise ValueError('Shared goal correction must remain enabled')
    result={k:v.clone() for k,v in weights.items()};result['layers.0.weight'][:,128:137]*=goal_scale;result['layers.2.weight']*=output_scale;return result


def weights(name):
    e=read(prior.REPORT/'selection.json')['selected']['goal']['epoch'];path=prior.WORK/'goal-selected.pt' if name=='full' else prior.WORK/'goal'/name/f'epoch-{e:03d}.pt';return torch.load(path,weights_only=True)


def freeze():
    REPORT.mkdir(parents=True,exist_ok=True);prior.inputs();check(read(prior.REPORT/'verification.json'))
    immutable_json(REPORT/'plan.json',dict(sources=bindings([Path(__file__),Path(__file__).with_name('shared_execution_edit_predictor.py'),Path(__file__).with_name('test_shared_execution_edit.py')]),inputs=bindings([prior.REPORT/n for n in ('plan.json','cache.json','fit.json','selection.json','result.json','verification.json','weight-inspection.json','weight-debug.json')]),
        goal_scales=[.25,.5,.75,1.],output_scales=[.25,.5,.75,1.,1.25],nll_allowance=.01,cohort_allowance=.01,
        intervention='20 direct weight edits of V70 goal head. Scale first-layer goal/availability/utility columns128:137 and final output weight. Keep output bias unchanged:its shared scalar cancels in softmax. No zero-scale candidate; executor always runs and keeps goal inputs. All other weights,inputs,selector and support unchanged. No optimizer updates.',
        selection='Four matching held fitting-game folds,all1997 movement rows. Require NLL<=direct+0.01 and neither goal-present nor absent accuracy loses>1point vs original V70. Maximize correct,then minimize NLL,then minimize summed squared weight edit; deterministic grid tie. Unedited eligible. One selected edit applied to full checkpoint,then fixed513 evaluation.',
        success='Beat V70 original311 and direct318 on fixed513;NLL<=direct+0.01;neither cohort loses>2points vs direct. All required. No evaluation-dependent edits or automatic promotion.',
        motivation='Fitting validation has54rescues and45regressions vsdirect;median original logit gap0.219and0.182respectively. Goal masking changes fitting-validation correct1246to1245. This motivates testing correction/goal strength; it does not prove overcorrection is causal.',
        limits='Repeatedly exposed research groups,existing selector and in-sample training goals,one seed. Calibration does not establish strategy or solve objective quality. No subagents.'))


def inputs():
    p=read(REPORT/'plan.json');check(p);prior.inputs();return p


def settings(p):return [dict(goal_scale=g,output_scale=o) for g in p['goal_scales'] for o in p['output_scales']]


def new(changed):
    net=prior.new('goal',read(prior.REPORT/'plan.json'));net.load_state_dict(changed);return net.eval()


def combine(values):
    return dict(**{k:sum(v[k] for v in values) for k in ('rows','correct','nll_sum')},cohorts={c:{k:sum(v['cohorts'][c][k] for v in values) for k in ('rows','correct','nll_sum')} for c in ('goal','no_goal')})


def choose(cs,direct,p):
    original=next(c for c in cs if c['setting']==dict(goal_scale=1.,output_scale=1.));eligible=[c for c in cs if c['nll_sum']<=direct['nll_sum']+p['nll_allowance']*c['rows'] and all(c['cohorts'][k]['correct']>=original['cohorts'][k]['correct']-p['cohort_allowance']*c['cohorts'][k]['rows'] for k in ('goal','no_goal'))]
    if not eligible:raise ValueError('No eligible shared executor weight edit')
    return min(eligible,key=lambda c:(-c['correct'],c['nll_sum'],c['edit_squared_norm'],cs.index(c)))


def candidates(p):
    banks=[torch.load(prior.WORK/f'fold{k}.pt',weights_only=False) for k in range(4)];indices=[np.array([i for i,r in enumerate(b['records']) if r['fold']==k and r['canonical']]) for k,b in enumerate(banks)];original=[weights(f'fold{k}') for k in range(4)];cs=[]
    direct=combine([prior.score(prior.new('goal',read(prior.REPORT/'plan.json')),b,ix) for b,ix in zip(banks,indices)])
    for setting in settings(p):
        values=[];squared=0.
        for b,ix,w in zip(banks,indices,original):
            changed=edit(w,**setting);values.append(prior.score(new(changed),b,ix));squared+=sum(float((changed[k]-v).square().sum()) for k,v in w.items())
        cs.append(dict(setting=setting,**combine(values),edit_squared_norm=squared))
    return cs,direct


def select():
    p=inputs();torch.set_num_threads(1);WORK.mkdir(parents=True,exist_ok=False);cs,direct=candidates(p);selected=choose(cs,direct,p);changed=edit(weights('full'),**selected['setting']);torch.save(changed,WORK/'selected.pt')
    immutable_json(REPORT/'selection.json',dict(candidates=cs,direct=direct,selected=selected,evaluation_used=False,optimizer_updates=0,bindings=bindings([WORK/'selected.pt'])));print('SELECTED',selected,flush=True)


def assessment():
    selected=torch.load(WORK/'selected.pt',weights_only=True);values={};old=read(prior.REPORT/'result.json')['results']
    for split in ('fit','evaluation'):
        bank=torch.load(prior.WORK/(split+'.pt'),weights_only=False);value=prior.score(new(selected),bank);comp={}
        for name in ('goal','direct'):
            before=old[split][name]['predictions'];after=value['predictions'];rs=bank['records'];comp[name]=dict(rescues=sum(a!=r['label'] and b==r['label'] for a,b,r in zip(before,after,rs) if r['label']>=0),regressions=sum(a==r['label'] and b!=r['label'] for a,b,r in zip(before,after,rs) if r['label']>=0))
        values[split]=dict(**value,comparisons=comp)
    x=values['evaluation'];d=old['evaluation']['direct'];g=old['evaluation']['goal'];checks=dict(original=x['correct']>g['correct'],direct=x['correct']>d['correct'],nll=x['nll_sum']<=d['nll_sum']+.01*x['rows'])
    for c in ('goal','no_goal'):checks[c+'_guard']=x['cohorts'][c]['correct']>=d['cohorts'][c]['correct']-.02*d['cohorts'][c]['rows']
    return dict(results=values,checks=checks,all_checks_pass=all(checks.values()),target_met=x['rows']==513 and x['correct']>=411,promoted=False)


def assess():
    inputs();check(read(REPORT/'selection.json'));torch.set_num_threads(4);result=assessment();immutable_json(REPORT/'result.json',dict(**result,bindings=bindings([WORK/'selected.pt',prior.WORK/'fit.pt',prior.WORK/'evaluation.pt'])))
    print('RESULT',result['checks'],{k:v for k,v in result['results']['evaluation'].items() if k not in ('predictions','losses')},flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('command',choices=('freeze','select','assess'));globals()[parser.parse_args().command]()
