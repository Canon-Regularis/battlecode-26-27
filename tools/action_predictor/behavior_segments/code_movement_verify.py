"""Read-only reproduction of frozen movement correction evidence."""
import time
from pathlib import Path
import numpy as np
import torch
from . import code_movement_fit as fit, expanded_code_data, expanded_code_fit as expanded
from . import data as original, model
from .code_movement import supported_log_probabilities
from .code_movement_predictor import CodeMovementPredictor
from .study import evaluate, aggregate
from ..audit import immutable_json
from ..data import digest


def audit_run(directory, data, indices, plan, epochs, arm, held=None):
    trace=fit.read(directory/'trace.json');net=fit.head(data,indices,arm)
    initial=torch.load(directory/'epoch-000.pt',weights_only=False)
    assert all(torch.equal(v,initial['model'][k]) for k,v in net.state_dict().items())
    assert not initial['optimizer']['state']
    assert trace['initial']==(fit.score(net,data,held) if held is not None else None)
    assert len(trace['epochs'])==epochs
    rng=np.random.default_rng(plan['seed']);updates=0;presentations=0;measurements={0:trace['initial']}
    for entry in trace['epochs']:
        order=rng.permutation(indices);assert order.tolist()==entry['order']
        counts=[int((data['labels'][order[i:i+plan['batch_windows']]]>=0).sum()) for i in range(0,len(order),plan['batch_windows'])]
        assert counts==entry['denominators'] and sum(counts)==entry['presentations']
        assert len(entry['gradient_norms'])==sum(n>0 for n in counts)
        assert np.isfinite(entry['gradient_norms']).all()
        updates+=sum(n>0 for n in counts);presentations+=sum(counts);assert entry['updates']==updates
        epoch=entry['epoch']
        if epoch%plan['evaluate_every']==0 or epoch==epochs:
            saved=torch.load(directory/f'epoch-{epoch:03d}.pt',weights_only=False)
            assert saved['epoch']==epoch and saved['updates']==updates and saved['rng']==rng.bit_generator.state
            assert torch.equal(saved['model']['mean_probabilities'],initial['model']['mean_probabilities'])
            assert all(torch.isfinite(v).all() for v in saved['model'].values())
            optimizer=saved['optimizer'];assert len(optimizer['state'])==2
            assert optimizer['param_groups'][0]['lr']==plan['learning_rate']
            assert optimizer['param_groups'][0]['weight_decay']==plan['weight_decay']
            for value in optimizer['state'].values():
                assert int(value['step'])==updates
                assert all(torch.isfinite(v).all() for v in value.values() if torch.is_tensor(v))
            net.load_state_dict(saved['model'])
            if held is not None:
                actual=fit.score(net,data,held);assert actual==entry['validation'];measurements[epoch]=actual
    return dict(updates=updates,presentations=presentations),measurements


def run():
    start=time.perf_counter();plan,architecture,cache,ids=fit.inputs();torch.set_num_threads(1)
    selection=fit.read(fit.REPORT/'selection.json');refit=fit.read(fit.REPORT/'refit.json');result=fit.read(fit.REPORT/'result.json')
    for receipt in (selection,refit,result):fit.check(receipt)
    assert refit['selection_sha256']==digest(fit.REPORT/'selection.json')
    assert result['refit_sha256']==digest(fit.REPORT/'refit.json')
    windows,maps=expanded_code_data.read();targets=torch.load(fit.WORK/'targets.pt',weights_only=True)
    for i,w in enumerate(windows):
        support,labels=model.move_support(w)
        assert torch.equal(targets['support'][i],support) and torch.equal(targets['labels'][i],labels)
    all_values={};accounting={}
    for name,path in [*(('fold'+str(k),fit.ROOT/p) for k,p in enumerate(plan['fold_backbones'])),('full',fit.ROOT/plan['full_backbone'])]:
        data=fit.cached(name);net=fit.backbone(path,architecture);actual=fit.frozen_features(net,cache)
        assert all(torch.equal(v,data[k]) for k,v in actual.items())
        if name!='full':
            fold=int(name[-1]);training,held=expanded.partition_indices(ids,fold)
            for arm in fit.ARMS:
                directory=fit.WORK/'tuning'/f'{arm}-fold{fold}'
                accounting[directory.name],values=audit_run(directory,data,training,plan,plan['epochs'],arm,held)
                for epoch,value in values.items():all_values.setdefault((arm,epoch),[]).append(value)
        else:
            for arm in fit.ARMS:
                directory=fit.WORK/('refit-'+arm);indices=np.arange(len(ids))
                accounting[directory.name],_=audit_run(directory,data,indices,plan,selection['selected']['epoch'],arm)
                saved=torch.load(fit.WORK/(arm+'.pt'),weights_only=False)
                chosen=torch.load(directory/f"epoch-{selection['selected']['epoch']:03d}.pt",weights_only=False)
                assert all(torch.equal(v,chosen['model'][k]) for k,v in saved['correction'].items())
                correction=fit.head(data,indices,arm);correction.load_state_dict(saved['correction'])
                assert fit.score(correction,data,indices)==refit['arms'][arm]['fit']
        print('Verified frozen features and training',name,flush=True)
    for candidate in selection['candidates']:
        assert candidate['arms']=={arm:fit.combine(all_values[(arm,candidate['epoch'])]) for arm in fit.ARMS}
    assert selection['selected']==fit.choose(selection['candidates'])
    # Exact shared schedules and denominators across arms.
    for suffix in ['fold'+str(k) for k in range(4)]+['refit']:
        paths=[fit.WORK/('refit-'+arm) if suffix=='refit' else fit.WORK/'tuning'/(arm+'-'+suffix) for arm in fit.ARMS]
        traces=[fit.read(p/'trace.json')['epochs'] for p in paths]
        assert [{k:r[k] for k in ('order','denominators','updates','presentations')} for r in traces[0]]==[{k:r[k] for k in ('order','denominators','updates','presentations')} for r in traces[1]]
    torch.set_num_threads(4);windows,maps=original.load();discovery=fit.read(original.REPORT/'discovery.json')
    encoded={w['key']:model.encode_window(w,maps[w['payload']],architecture['schema'])[0] for w in windows}
    exact={};results={}
    for arm in fit.ARMS:
        net=fit.policy(arm,plan,architecture)
        for split in ('fit','evaluation'):
            actual=evaluate(net,windows,maps,encoded,discovery,split,time.perf_counter()+300)
            saved=fit.read(fit.WORK/f'{arm}-{split}-predictions.json');assert actual==saved
            assert actual['summary']==result['results'][arm][split]
            old=fit.read(expanded.WORK/(split+'-predictions.json'))
            for a,b in zip(actual['records'],old['records']):
                assert {k:v for k,v in a.items() if k not in ('move_prediction','movement_nll')}=={k:v for k,v in b.items() if k not in ('move_prediction','movement_nll')}
            exact[arm+'/'+split]=len(actual['records']);results[(arm,split)]=actual
        predictor=CodeMovementPredictor(arm);w=next(w for w in windows if w['partition']=='evaluation');state=None
        with torch.no_grad():expected=net(**encoded[w['key']])
        support,_=model.move_support(w)
        for i,s in enumerate(w['steps']):
            value=predictor.predict(s['input'] if s['observed'] else None,maps[w['payload']],s['round'],s['previous'],s['previous_mask'],state);state=value['state']
            assert value['code']==int(expected['code'][i].argmax())
            if support[i].any():
                lp=supported_log_probabilities(expected['move'][i],support[i])
                torch.testing.assert_close(torch.tensor(value['movement_probabilities']),lp.exp(),atol=2e-6,rtol=2e-5)
            else:assert value['conditional_movement'] is None
        print('Verified full forecasts and streaming',arm,flush=True)
    p=results[('predicted','evaluation')];c=results[('constant','evaluation')]
    b=fit.read(expanded.WORK/'evaluation-predictions.json');o=fit.read(original.WORK/'S01-run/evaluation-predictions.json')
    assert result['comparisons']==dict(v49=fit.paired(p['records'],b['records']),constant=fit.paired(p['records'],c['records']),s01=fit.paired(p['records'],o['records']))
    for k,v in fit.gates(p['summary'],c['summary'],b['summary'],o['summary']).items():assert result[k]==v
    strata={}
    for key in ('group','move_label','code_label'):
        strata[key]={}
        for value in sorted({r[key] for r in p['records'] if r['move_label'] is not None}):
            strata[key][str(value)]={name:aggregate([r for r in package['records'] if r[key]==value and r['move_label'] is not None])
                for name,package in [('predicted',p),('constant',c),('v49',b),('s01',o)]}
    immutable_json(fit.REPORT/'comparison.json',dict(strata=strata,interpretation='Descriptive reused-game comparisons; code labels only stratify diagnostics.'))
    immutable_json(fit.REPORT/'verification.json',dict(result_sha256=digest(fit.REPORT/'result.json'),
        sources=fit.bindings([Path(__file__)]),accounting=accounting,exact_feature_windows=1607*5,
        exact_validation_measurements=len(all_values)*4,exact_forecasts=exact,streaming_turns=64,
        unchanged_code_and_goal_forecasts=True,shared_schedules=True,seconds=time.perf_counter()-start))
    print('VERIFIED',exact,flush=True)


if __name__=='__main__':run()
