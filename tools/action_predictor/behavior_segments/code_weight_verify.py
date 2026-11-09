"""Read-only reproduction of weight-update selection, accounting and inference."""
import json
import time
from pathlib import Path
import numpy as np
import torch
from . import model
from . import code_weight_fit as first
from . import code_weight_full as second
from . import code_weight_regularized as third
from .data import ROOT,REPORT as BASE,load
from .study import evaluate
from .rare_code_edit import metrics
from .code_weight_predictor import CodeWeightPredictor
from ..audit import immutable_json
from ..data import digest


def bound(receipt):
    for p,h in receipt['bindings'].items():assert digest(ROOT/p)==h,p


def audit_trace(directory,plan,indices,observed,base,prefixes,epochs,lr,full=False):
    trace=json.loads((directory/'trace.json').read_text())
    rng=np.random.default_rng(plan['seed']);updates=0;presentations=0;clipped=0
    active=[k for k in base if k.startswith(prefixes)]
    for entry in trace:
        epoch=entry['epoch']
        if epoch==0:continue
        order=rng.permutation(indices);assert order.tolist()==entry['window_order']
        den=[int(observed[order[i:i+plan['batch_windows']]].sum()) for i in range(0,len(order),plan['batch_windows'])]
        assert den==entry['batch_denominators'] and sum(den)==entry['observed_presentations']
        assert np.isfinite(entry['gradient_norms']).all() and len(entry['gradient_norms'])==len(den)
        clipped+=sum(x>plan['clip'] for x in entry['gradient_norms'])
        updates+=len(den);presentations+=sum(den);assert updates==entry['updates']
        path=directory/f'epoch-{epoch:03d}.pt'
        if path.exists():
            saved=torch.load(path,map_location='cpu',weights_only=False)
            assert saved['epoch']==epoch and saved['updates']==updates and saved['rng']==rng.bit_generator.state
            assert all(torch.isfinite(v).all() for v in saved['model'].values())
            for k,v in base.items():
                if k not in active:assert torch.equal(v,saved['model'][k]),k
            optimizer=saved['optimizer'];assert len(optimizer['state'])==len(active)
            group=optimizer['param_groups'][0]
            assert group['lr']==lr and group['weight_decay']==plan['weight_decay']
            for state in optimizer['state'].values():
                assert int(state['step'])==updates
                assert all(torch.isfinite(v).all() for v in state.values() if torch.is_tensor(v))
    assert len([r for r in trace if r['epoch']])==epochs
    initial_path=directory/('epoch-000.pt' if full else 'initial.pt')
    initial=torch.load(initial_path,map_location='cpu',weights_only=False)
    assert not initial['optimizer']['state']
    assert all(torch.equal(v,initial['model'][k]) for k,v in base.items())
    return dict(updates=updates,observed_presentations=presentations,clipped_updates=clipped)


def run():
    start=time.perf_counter()
    p1,architecture,data,ids=first.load_cache();p2,_,_,items=second.inputs()
    s1=json.loads((first.REPORT/'selection.json').read_text());r1=json.loads((first.REPORT/'refit.json').read_text())
    s2=json.loads((second.REPORT/'selection.json').read_text())
    p3,_,_,_=third.inputs();s3=json.loads((third.REPORT/'selection.json').read_text())
    r3=json.loads((third.REPORT/'refit.json').read_text());winner=json.loads((third.REPORT/'winner.json').read_text())
    result=json.loads((third.REPORT/'result.json').read_text())
    for receipt in (s1,r1,s2,s3,r3,result):bound(receipt)
    assert s1['plan_sha256']==digest(first.REPORT/'plan.json') and s2['plan_sha256']==digest(second.REPORT/'plan.json')
    assert r1['selection_sha256']==digest(first.REPORT/'selection.json')
    assert r3['winner_sha256']==digest(third.REPORT/'winner.json')
    assert result['refit_sha256']==digest(third.REPORT/'refit.json')
    assert s1['selected']==min(s1['candidates'],key=lambda c:(-c['correct'],c['nll'],c['epoch'],c['learning_rate']))
    assert s2['selected']==min(s2['candidates'],key=lambda c:(-c['correct'],c['nll'],c['epoch']))
    assert s3['selected']==min(s3['candidates'],key=lambda c:(-c['correct'],c['nll'],c['epoch'],c['config']))
    assert winner['candidates']==dict(recurrent=s1['selected'],encoder=s2['selected'],regularized=s3['selected'])
    assert winner['stage']==min(winner['candidates'],key=lambda s:(-winner['candidates'][s]['correct'],winner['candidates'][s]['nll'],s))
    for p,h in winner['inputs'].items():assert digest(ROOT/p)==h,p
    folds=np.array([r['fold'] for r in ids]);observed=data['observed'];accounting={};candidate_values={}
    base=torch.load(first.INITIAL,map_location='cpu',weights_only=False)['model']
    torch.set_num_threads(1)
    for lr in p1['learning_rates']:
        for fold in range(4):
            directory=first.WORK/'tuning'/f'lr{lr:g}-fold{fold}'
            accounting[directory.name]=audit_trace(directory,p1,np.flatnonzero(folds!=fold),observed,base,first.PREFIXES,p1['epochs'],lr)
            trace=json.loads((directory/'trace.json').read_text());net=model.SegmentPolicy(architecture['schema'],8).eval()
            for entry in trace:
                if 'validation' not in entry:continue
                saved=torch.load(directory/f"epoch-{entry['epoch']:03d}.pt",map_location='cpu',weights_only=False)
                net.load_state_dict(saved['model']);value=first.score(net,data,np.flatnonzero(folds==fold))
                assert value==entry['validation'],(directory,entry['epoch'])
                candidate_values.setdefault((lr,entry['epoch']),[]).append(value)
            print('Verified',directory.name,flush=True)
    for c in s1['candidates']:
        values=candidate_values[(c['learning_rate'],c['epoch'])]
        assert c['correct']==sum(v['correct'] for v in values)
        assert c['nll']==sum(v['nll']*v['rows'] for v in values)/c['rows']
        assert c['codes']==metrics(sum([v['labels'] for v in values],[]),sum([v['predictions'] for v in values],[]))
    chosen=s1['selected']
    accounting['stage1-refit']=audit_trace(first.WORK/'refit',p1,np.arange(len(ids)),observed,base,first.PREFIXES,chosen['epoch'],chosen['learning_rate'])
    net=model.SegmentPolicy(architecture['schema'],8).eval()
    net.load_state_dict(torch.load(first.WORK/'selected.pt',map_location='cpu',weights_only=False)['model'])
    assert first.score(net,data,np.arange(len(ids)))==r1['fit']
    torch.set_num_threads(4)
    # Rebuild every frozen map feature, rather than trusting the cached feature file alone.
    capture={};handle=net.context.register_forward_pre_hook(lambda module,args:capture.update(context=args[0].detach()))
    with torch.no_grad():
        for i,(args,y) in enumerate(items):
            actual=net(**args)['code'];assert torch.equal(capture['context'],data['context'][i])
            torch.testing.assert_close(actual,first.code_forward(net,first.take(data,[i]))[0],atol=2e-5,rtol=2e-5)
    handle.remove();torch.set_num_threads(4);candidate_values={}
    for fold in range(4):
        initial=torch.load(ROOT/p2['fold_initial'][str(fold)],map_location='cpu',weights_only=False)['model']
        directory=second.WORK/'tuning'/f'fold{fold}'
        accounting['stage2-'+directory.name]=audit_trace(directory,p2,np.flatnonzero(folds!=fold),observed,initial,second.PREFIXES,p2['epochs'],p2['learning_rate'],True)
        trace=json.loads((directory/'trace.json').read_text())
        for entry in trace:
            if 'validation' not in entry:continue
            net.load_state_dict(torch.load(directory/f"epoch-{entry['epoch']:03d}.pt",map_location='cpu',weights_only=False)['model'])
            value=second.score(net,items,np.flatnonzero(folds==fold));assert value==entry['validation']
            candidate_values.setdefault(entry['epoch'],[]).append(value)
        print('Verified encoder',directory.name,flush=True)
    for c in s2['candidates']:
        values=candidate_values[c['epoch']]
        assert c['correct']==sum(v['correct'] for v in values)
        assert c['nll']==sum(v['nll']*v['rows'] for v in values)/c['rows']
        assert c['codes']==metrics(sum([v['labels'] for v in values],[]),sum([v['predictions'] for v in values],[]))
    torch.set_num_threads(1);candidate_values={}
    for name,config in p3['configs'].items():
        for fold in range(4):
            directory=third.WORK/'tuning'/f'{name}-fold{fold}'
            accounting['stage3-'+directory.name]=audit_trace(directory,p3|dict(weight_decay=config['weight_decay']),
                np.flatnonzero(folds!=fold),observed,base,first.PREFIXES,p3['epochs'],p3['learning_rate'])
            trace=json.loads((directory/'trace.json').read_text())
            for entry in trace:
                if 'validation' not in entry:continue
                net.load_state_dict(torch.load(directory/f"epoch-{entry['epoch']:03d}.pt",map_location='cpu',weights_only=False)['model'])
                value=first.score(net,data,np.flatnonzero(folds==fold));assert value==entry['validation']
                candidate_values.setdefault((name,entry['epoch']),[]).append(value)
            print('Verified regularized',directory.name,flush=True)
    for c in s3['candidates']:
        values=candidate_values[(c['config'],c['epoch'])]
        assert c['correct']==sum(v['correct'] for v in values)
        assert c['nll']==sum(v['nll']*v['rows'] for v in values)/c['rows']
        assert c['codes']==metrics(sum([v['labels'] for v in values],[]),sum([v['predictions'] for v in values],[]))
    predictor=CodeWeightPredictor();saved=torch.load(third.WORK/'selected.pt',map_location='cpu',weights_only=False)
    assert saved['winner_sha256']==digest(third.REPORT/'winner.json') and 'optimizer' not in saved
    if winner['stage']=='regularized':
        config=p3['configs'][s3['selected']['config']]
        accounting['stage3-refit']=audit_trace(third.WORK/'refit',p3|dict(weight_decay=config['weight_decay']),np.arange(len(ids)),
            observed,base,first.PREFIXES,s3['selected']['epoch'],p3['learning_rate'])
        assert first.score(predictor.net,data,np.arange(len(ids)))==r3['fit']
    else:
        source=ROOT/saved['source_checkpoint'];assert digest(source)==saved['source_sha256']
        state=torch.load(source,map_location='cpu',weights_only=False)['model']
        assert all(torch.equal(v,state[k]) for k,v in saved['model'].items())
        if winner['stage']=='encoder':
            r2=json.loads((second.REPORT/'refit.json').read_text());bound(r2)
            initial=torch.load(first.WORK/'selected.pt',map_location='cpu',weights_only=False)['model']
            accounting['stage2-refit']=audit_trace(second.WORK/'refit',p2,np.arange(len(ids)),observed,initial,second.PREFIXES,s2['selected']['epoch'],p2['learning_rate'],True)
            torch.set_num_threads(4)
            assert second.score(predictor.net,items,np.arange(len(ids)))==r2['fit']
        else:assert first.score(predictor.net,data,np.arange(len(ids)))==r3['fit']
    torch.set_num_threads(4)
    windows,maps=load();discovery=json.loads((BASE/'discovery.json').read_text())
    cache={w['key']:model.encode_window(w,maps[w['payload']],architecture['schema'])[0] for w in windows}
    reproduced={}
    for split in ('fit','evaluation'):
        value=evaluate(predictor.net,windows,maps,cache,discovery,split,time.perf_counter()+300)
        assert value==json.loads((third.WORK/f'{split}-predictions.json').read_text())
        codes=metrics([r['code_label'] for r in value['records']],[r['code_prediction'] for r in value['records']])
        assert codes==result['results'][split]['codes'] and value['summary']==result['results'][split]['summary']
        assert result['results'][split]['target_met']==(codes['accuracy']>=.85)
        reproduced[split]=len(value['records'])
    assert result['target_met']==result['results']['evaluation']['target_met']
    w=next(w for w in windows if w['partition']=='evaluation');state=None
    with torch.no_grad(): expected=predictor.net(**cache[w['key']])['code'].argmax(-1).tolist()
    for i,s in enumerate(w['steps']):
        out=predictor.predict(s['input'] if s['observed'] else None,maps[w['payload']],s['round'],s['previous'],s['previous_mask'],state)
        assert out['code']==expected[i];state=out['state']
    for p,h in p1['inputs'].items():assert digest(ROOT/p)==h,p
    for p,h in p2['inputs'].items():assert digest(ROOT/p)==h,p
    for p,h in p3['inputs'].items():assert digest(ROOT/p)==h,p
    immutable_json(third.REPORT/'verification.json',dict(result_sha256=digest(third.REPORT/'result.json'),
        sources={str(p.relative_to(ROOT)):digest(p) for p in (Path(__file__),Path(__file__).with_name('code_weight_predictor.py'))},
        accounting=accounting,exact_cached_map_windows=256,exact_stage1_validation_checkpoints=192,
        exact_stage2_validation_checkpoints=36,exact_stage3_validation_checkpoints=288,exact_final_forecasts=reproduced,streaming_predictions=32,
        target_checks_reproduced=True,original_inputs_preserved=True,seconds=time.perf_counter()-start))
    print('Verified all weight accounting and',reproduced,'final forecasts',flush=True)


if __name__=='__main__':run()
