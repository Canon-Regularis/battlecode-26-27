"""Matched current-map geometry correction using the frozen V49 code predictor."""
import argparse
import time
from pathlib import Path
import numpy as np
import torch
from . import code_movement_fit as prior, expanded_code_data, expanded_code_fit as expanded
from . import data as original,model
from .code_path_movement import PathCorrection,PathMovementPolicy,candidate_features,FEATURE_NAMES
from .study import evaluate
from ..audit import immutable_json
from ..data import digest

ROOT=original.ROOT;REPORT=ROOT/'tools/action_predictor/experiments/v52';WORK=ROOT/'.cambc/action-predictor/v52'
read=prior.read;check=prior.check;bindings=prior.bindings;ARMS=prior.ARMS


def freeze():
    REPORT.mkdir(parents=True,exist_ok=True);plan,_,_,_=prior.inputs()
    check(read(prior.REPORT/'result.json'))
    sources=[Path(__file__).with_name(n) for n in ('code_path_movement.py','code_path_fit.py','code_path_verify.py','code_path_predictor.py','test_code_path.py')]
    inputs=[prior.REPORT/n for n in ('plan.json','cache.json','selection.json','result.json','verification.json')]
    immutable_json(REPORT/'plan.json',dict(sources=bindings(sources),inputs=bindings(inputs),
        fold_backbones=plan['fold_backbones'],full_backbone=plan['full_backbone'],seed=52001,
        epochs=64,evaluate_every=8,batch_windows=32,learning_rate=.003,weight_decay=.01,clip=5.,
        tuning_seconds_cap=1200,refit_seconds_cap=600,feature_names=FEATURE_NAMES,trainable_parameters=57*len(FEATURE_NAMES),
        design='Freeze the original V49 backbone and logits, not failed V51 weights. '
        'Add a zero-initialized candidate-geometry residual. A linear layer of frozen recurrent state '
        'and predicted soft code outputs geometry coefficients; matched control substitutes the fitting '
        'training mean code. All causal PRE entity geometry, static-terrain distances and first-step masks '
        'are identical across arms. No hindsight code or endpoint labels enter inputs.',
        targets='Current known alive nearest/weakest camp and enemy, nearest ally, nearest public altar, '
        'fixed public home/enemy-home central tile. These are input features, not objective labels. '
        'Static eight-neighbor terrain progress is available for altar/home targets only; entity progress '
        'uses current geometric distance. Unknown entity dynamic fields are ignored. No future blocker or legality claim.',
        data=plan['data'],loss=plan['loss'],selection=plan['selection'],success=plan['success'],
        limitations=plan['limitations']+' Follow-up after exposed negative V51; not a fresh confirmatory study.'))


def inputs():
    plan=read(REPORT/'plan.json');check(plan)
    _,architecture,cache,ids=prior.inputs()
    return plan,architecture,cache,ids


def prepare():
    plan,architecture,cache,ids=inputs();WORK.mkdir(parents=True,exist_ok=False)
    windows,maps=expanded_code_data.read();geometry=[]
    for i,w in enumerate(windows):
        assert w['partition']=='fit' and w['key']==ids[i]['key']
        geometry.append(torch.stack([candidate_features(s['input'] if s['observed'] else None,maps[w['payload']]) for s in w['steps']]))
        if (i+1)%200==0:print('Geometry',i+1,'/',len(windows),flush=True)
    tensor=torch.stack(geometry);assert torch.isfinite(tensor).all()
    torch.save(tensor,WORK/'geometry.pt')
    immutable_json(REPORT/'cache.json',dict(plan_sha256=digest(REPORT/'plan.json'),bindings=bindings([WORK/'geometry.pt']),
        windows=len(windows),shape=list(tensor.shape),fitting_only=True))


def cached(name):
    receipt=read(REPORT/'cache.json');check(receipt);assert receipt['plan_sha256']==digest(REPORT/'plan.json')
    data=prior.cached(name);geometry=torch.load(WORK/'geometry.pt',weights_only=True)
    data['states']=torch.cat((data['states'],geometry.flatten(-2)),-1)
    return data


def head(data,indices,arm):
    mask=data['labels'][indices]>=0;mean=data['probabilities'][indices][mask].mean(0)
    return PathCorrection(mean,arm=='predicted')


def tune():
    start=time.perf_counter();plan,architecture,_,ids=inputs();torch.set_num_threads(1)
    directory=WORK/'tuning';directory.mkdir(exist_ok=False);values={}
    for fold in range(4):
        data=cached('fold'+str(fold));training,held=expanded.partition_indices(ids,fold)
        for arm in ARMS:
            net=head(data,training,arm);values[(arm,fold,0)]=prior.score(net,data,held)
            trace=prior.train(net,data,training,plan,directory/f'{arm}-fold{fold}',plan['epochs'],start+plan['tuning_seconds_cap'],held)
            for entry in trace:
                if 'validation' in entry:values[(arm,fold,entry['epoch'])]=entry['validation']
    candidates=[dict(epoch=e,arms={a:prior.combine([values[(a,k,e)] for k in range(4)]) for a in ARMS}) for e in range(0,plan['epochs']+1,plan['evaluate_every'])]
    chosen=prior.choose(candidates);paths=[p for p in directory.rglob('*') if p.is_file()];bound=bindings(paths)
    elapsed=time.perf_counter()-start
    if elapsed>=plan['tuning_seconds_cap']:raise TimeoutError('Geometry tuning publication budget exceeded')
    immutable_json(REPORT/'selection.json',dict(plan_sha256=digest(REPORT/'plan.json'),selected=chosen,candidates=candidates,
        seconds=elapsed,outer_evaluation_used=False,bindings=bound))
    print('SELECTED',chosen,flush=True)


def refit():
    start=time.perf_counter();plan,_,_,ids=inputs();selection=read(REPORT/'selection.json');check(selection)
    assert selection['selected']==prior.choose(selection['candidates'])
    torch.set_num_threads(1);data=cached('full');indices=np.arange(len(ids));result={}
    for arm in ARMS:
        net=head(data,indices,arm);trace=prior.train(net,data,indices,plan,WORK/('refit-'+arm),
            selection['selected']['epoch'],start+plan['refit_seconds_cap'])
        torch.save(dict(correction=net.state_dict(),conditioned=arm=='predicted',inference_only=True,
            plan_sha256=digest(REPORT/'plan.json'),selection_sha256=digest(REPORT/'selection.json'),
            backbone_sha256=digest(ROOT/plan['full_backbone'])),WORK/(arm+'.pt'))
        result[arm]=dict(fit=prior.score(net,data,indices),updates=trace[-1]['updates'] if trace else 0)
    paths=[WORK/(a+'.pt') for a in ARMS]+[p for a in ARMS for p in (WORK/('refit-'+a)).iterdir() if p.is_file()]
    bound=bindings(paths);elapsed=time.perf_counter()-start
    if elapsed>=plan['refit_seconds_cap']:raise TimeoutError('Geometry refit publication budget exceeded')
    immutable_json(REPORT/'refit.json',dict(selection_sha256=digest(REPORT/'selection.json'),arms=result,seconds=elapsed,bindings=bound))


def policy(arm,plan,architecture):
    saved=torch.load(WORK/(arm+'.pt'),map_location='cpu',weights_only=False)
    assert saved['plan_sha256']==digest(REPORT/'plan.json') and saved['selection_sha256']==digest(REPORT/'selection.json')
    assert saved['backbone_sha256']==digest(ROOT/plan['full_backbone'])
    assert saved['conditioned']==(arm=='predicted') and saved['inference_only']
    net=PathCorrection(saved['correction']['mean_probabilities'],saved['conditioned']);net.load_state_dict(saved['correction'])
    return PathMovementPolicy(prior.backbone(ROOT/plan['full_backbone'],architecture),net).eval()


def encoded_windows(windows,maps,architecture):
    cache={}
    for w in windows:
        args,_=model.encode_window(w,maps[w['payload']],architecture['schema'])
        args['geometry']=torch.stack([candidate_features(s['input'] if s['observed'] else None,maps[w['payload']]) for s in w['steps']])
        cache[w['key']]=args
    return cache


def assess():
    start=time.perf_counter();plan,architecture,_,_=inputs();check(read(REPORT/'refit.json'));torch.set_num_threads(4)
    windows,maps=original.load();discovery=read(original.REPORT/'discovery.json');cache=encoded_windows(windows,maps,architecture)
    results={};predictions={}
    for arm in ARMS:
        net=policy(arm,plan,architecture);results[arm]={}
        for split in ('fit','evaluation'):
            value=evaluate(net,windows,maps,cache,discovery,split,start+600);old=read(expanded.WORK/(split+'-predictions.json'))
            assert len(value['records'])==len(old['records'])
            for a,b in zip(value['records'],old['records']):
                assert {k:v for k,v in a.items() if k not in ('move_prediction','movement_nll')}=={k:v for k,v in b.items() if k not in ('move_prediction','movement_nll')}
            immutable_json(WORK/f'{arm}-{split}-predictions.json',value);results[arm][split]=value['summary'];predictions[(arm,split)]=value
            print(arm,split,value['summary'],flush=True)
    b=read(expanded.WORK/'evaluation-predictions.json');o=read(original.WORK/'S01-run/evaluation-predictions.json')
    p=predictions[('predicted','evaluation')];c=predictions[('constant','evaluation')]
    comparisons={name:prior.paired(p['records'],v['records']) for name,v in [('v49',b),('constant',c),('s01',o)]}
    checks=prior.gates(p['summary'],c['summary'],b['summary'],o['summary'])
    paths=[WORK/(a+'.pt') for a in ARMS]+[WORK/f'{a}-{s}-predictions.json' for a in ARMS for s in ('fit','evaluation')]
    bound=bindings(paths);elapsed=time.perf_counter()-start
    if elapsed>=600:raise TimeoutError('Geometry assessment publication budget exceeded')
    immutable_json(REPORT/'result.json',dict(refit_sha256=digest(REPORT/'refit.json'),results=results,comparisons=comparisons,
        **checks,bindings=bound,seconds=elapsed,promoted=False,qualification='Conditional first moves on repeatedly used research games; no verified intent or playing-strength claim.'))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('command',choices=('freeze','prepare','tune','refit','assess'));globals()[p.parse_args().command]()
