"""Reproduce previous-command features, fits, selection and streaming forecasts."""
import time
import numpy as np
import torch
from . import command_movement_fit as fit
from .command_movement import command_window
from .command_movement_predictor import CommandMovementPredictor
from .model import move_support
from ..audit import immutable_json
from ..data import digest


def audit(directory,data,indices,held,hidden,epochs,plan):
    net=fit.new_head(hidden,plan);saved=torch.load(directory/'epoch-000.pt',weights_only=False)
    assert all(torch.equal(v,saved['model'][k]) for k,v in net.state_dict().items()) and not saved['optimizer']['state']
    trace=fit.read(directory/'trace.json');assert len(trace['epochs'])==epochs
    values={0:fit.prior.score(net,data,held)} if held is not None else {};assert values.get(0)==trace['initial']
    rng=np.random.default_rng(plan['seed']);updates=0;presentations=0
    for e in trace['epochs']:
        order=rng.permutation(indices);assert order.tolist()==e['order']
        denominators=[int((data['labels'][order[i:i+plan['batch_windows']]]>=0).sum()) for i in range(0,len(order),plan['batch_windows'])]
        assert denominators==e['denominators'] and len(denominators)==len(e['gradient_norms']) and np.isfinite(e['gradient_norms']).all()
        updates+=len(denominators);presentations+=sum(denominators);assert updates==e['updates']
        if e['epoch']%plan['evaluate_every']==0 or e['epoch']==epochs:
            saved=torch.load(directory/f"epoch-{e['epoch']:03d}.pt",weights_only=False)
            assert saved['updates']==updates and saved['rng']==rng.bit_generator.state
            assert saved['optimizer']['param_groups'][0]['lr']==plan['learning_rate'] and saved['optimizer']['param_groups'][0]['weight_decay']==plan['weight_decay']
            assert len(saved['optimizer']['state'])==len(list(net.parameters()))
            for v in saved['optimizer']['state'].values():assert int(v['step'])==updates and all(torch.isfinite(x).all() for x in v.values() if torch.is_tensor(x))
            assert all(torch.isfinite(v).all() for v in saved['model'].values());net.load_state_dict(saved['model'])
            if held is not None:values[e['epoch']]=fit.prior.score(net,data,held);assert values[e['epoch']]==e['validation']
    return dict(updates=updates,movement_presentations=presentations),values


def run():
    start=time.perf_counter();plan,parent,architecture,_,ids=fit.inputs();torch.set_num_threads(1)
    selection=fit.read(fit.REPORT/'selection.json');refit=fit.read(fit.REPORT/'refit.json');result=fit.read(fit.REPORT/'result.json')
    for r in (selection,refit,result):fit.check(r)
    assert selection['plan_sha256']==digest(fit.REPORT/'plan.json') and refit['selection_sha256']==digest(fit.REPORT/'selection.json') and result['refit_sha256']==digest(fit.REPORT/'refit.json')
    windows,_=fit.prior.expanded.read();assert all(w['partition']=='fit' and w['key']==ids[i]['key'] for i,w in enumerate(windows))
    history,source_bindings=fit.audit.prior_moves(windows);assert source_bindings==fit.read(fit.REPORT/'cache.json')['source_bindings']
    heading=torch.stack([command_window(history[w['key']]) for w in windows]);values={};accounting={}
    for name in ['fold0','fold1','fold2','fold3','full']:
        actual=fit.features(name,heading);data=fit.cached(name);assert all(torch.equal(v,data[k]) for k,v in actual.items())
        if name=='full':continue
        fold=int(name[-1]);training,held=fit.prior.folds.partition_indices(ids,fold)
        for hidden in plan['hidden']:
            label=f'h{hidden}-fold{fold}';accounting[label],v=audit(fit.WORK/'tuning'/label,data,training,held,hidden,plan['epochs'],plan)
            for epoch,value in v.items():values.setdefault((hidden,epoch),[]).append(value)
        print('Verified command history',name,flush=True)
    for c in selection['candidates']:assert {k:c[k] for k in ('rows','correct','nll')}==fit.prior.combine(values[(c['hidden'],c['epoch'])])
    chosen=selection['selected'];assert chosen==fit.prior.choose(selection['candidates'])
    data=fit.cached('full');accounting['refit'],_=audit(fit.WORK/'refit',data,np.arange(len(ids)),None,chosen['hidden'],chosen['epoch'],plan)
    saved=torch.load(fit.WORK/'selected.pt',weights_only=False);trained=torch.load(fit.WORK/'refit'/f"epoch-{chosen['epoch']:03d}.pt",weights_only=False)
    assert all(torch.equal(v,trained['model'][k]) for k,v in saved['model'].items())
    head=fit.new_head(chosen['hidden'],plan);head.load_state_dict(saved['model']);assert fit.prior.score(head,data,np.arange(len(ids)))==refit['fit']
    torch.set_num_threads(4);windows,maps=fit.prior.original.load();encoded,history,source_bindings=fit.encoded(windows,maps,architecture)
    assert source_bindings==result['source_bindings'];discovery=fit.read(fit.prior.original.REPORT/'discovery.json');policy=fit.policy(plan,parent,architecture);exact={};groups={}
    for split in ('fit','evaluation'):
        actual=fit.prior.evaluate(policy,windows,maps,encoded,discovery,split,time.perf_counter()+300);baseline=fit.read(fit.prior.WORK/(split+'-predictions.json'))
        assert actual==fit.read(fit.WORK/(split+'-predictions.json')) and actual['summary']==result['results'][split]
        fit.prior.unchanged(actual,baseline);assert fit.prior.joint.prior.paired(actual['records'],baseline['records'])==result['comparisons'][split]
        exact[split]=len(actual['records']);groups[split]=dict(edited=actual['groups'],baseline=baseline['groups'])
    assert result['target_met']==(result['results']['evaluation']['movement_accuracy']>=.8)
    predictor=CommandMovementPredictor();w=next(w for w in windows if w['partition']=='evaluation');state=None;support,_=move_support(w)
    with torch.no_grad():expected=policy(**encoded[w['key']])
    for i,s in enumerate(w['steps']):
        value=predictor.predict(s['input'] if s['observed'] else None,maps[w['payload']],s['round'],s['previous'],s['previous_mask'],state,previous_moves=history[w['key']][i]);state=value['state']
        assert value['code']==int(expected['code'][i].argmax())
        if value['movement_probabilities'] is not None:torch.testing.assert_close(torch.tensor(value['movement_probabilities']),expected['move'][i].masked_fill(~support[i],-1e9).softmax(-1),atol=2e-6,rtol=2e-5)
    immutable_json(fit.REPORT/'comparison.json',dict(groups=groups))
    immutable_json(fit.REPORT/'verification.json',dict(result_sha256=digest(fit.REPORT/'result.json'),accounting=accounting,
        cache_exact=True,previous_turn_descriptors_match=True,exact_validation_measurements=len(values)*4,
        exact_forecasts=exact,streaming_turns=32,code_and_goal_unchanged=True,seconds=time.perf_counter()-start))
    print('VERIFIED command movement',exact,flush=True)


if __name__=='__main__':run()
