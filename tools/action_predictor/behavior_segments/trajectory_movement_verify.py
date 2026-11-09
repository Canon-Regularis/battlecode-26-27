"""Parent verification of the joint causal-trajectory weight experiment."""
import time
import numpy as np
import torch
from . import trajectory_movement_fit as fit
from .trajectory_movement_predictor import TrajectoryMovementPredictor
from .model import move_support
from ..audit import immutable_json
from ..data import digest


def audit(directory,data,indices,held,name,epochs,plan,parent,architecture):
    net=fit.warm(name,parent,architecture);base={k:v.clone() for k,v in net.state_dict().items()};active={k for k,p in net.named_parameters() if p.requires_grad}
    initial=torch.load(directory/'epoch-000.pt',weights_only=False)
    assert all(torch.equal(v,initial['model'][k]) for k,v in base.items()) and not initial['optimizer']['state']
    trace=fit.read(directory/'trace.json');assert len(trace['epochs'])==epochs
    values={0:fit.joint.score(net,data,held)} if held is not None else {};assert trace['initial']==values.get(0)
    rng=np.random.default_rng(plan['seed']);updates=0;presentations=0
    for e in trace['epochs']:
        order=rng.permutation(indices);assert order.tolist()==e['order'];counts=[]
        for start in range(0,len(order),plan['batch_windows']):
            batch=order[start:start+plan['batch_windows']];counts.append([int((data['movement_labels'][batch]>=0).sum()),int(data['observed'][batch].sum())])
        assert counts==e['denominators'] and len(counts)==len(e['gradient_norms']) and np.isfinite(e['gradient_norms']).all()
        updates+=len(counts);presentations+=sum(c[0] for c in counts);assert e['updates']==updates and e['movement_presentations']==sum(c[0] for c in counts)
        if e['epoch']%plan['evaluate_every']==0 or e['epoch']==epochs:
            saved=torch.load(directory/f"epoch-{e['epoch']:03d}.pt",weights_only=False)
            assert saved['updates']==updates and saved['rng']==rng.bit_generator.state and saved['epoch']==e['epoch']
            for k,v in saved['model'].items():
                assert torch.isfinite(v).all()
                if k not in active:assert torch.equal(v,base[k])
            opt=saved['optimizer'];assert len(opt['state'])==len(active)
            assert opt['param_groups'][0]['lr']==plan['learning_rate'] and opt['param_groups'][0]['weight_decay']==plan['weight_decay']
            for v in opt['state'].values():assert int(v['step'])==updates and all(torch.isfinite(x).all() for x in v.values() if torch.is_tensor(x))
            net.load_state_dict(saved['model'])
            if held is not None:values[e['epoch']]=fit.joint.score(net,data,held);assert values[e['epoch']]==e['validation']
    return dict(updates=updates,movement_presentations=presentations),values


def run():
    start=time.perf_counter();plan,parent,architecture,cache,ids=fit.inputs();torch.set_num_threads(1)
    selection=fit.read(fit.REPORT/'selection.json');refit=fit.read(fit.REPORT/'refit.json');result=fit.read(fit.REPORT/'result.json')
    for r in (selection,refit,result):fit.check(r)
    assert selection['plan_sha256']==digest(fit.REPORT/'plan.json') and refit['selection_sha256']==digest(fit.REPORT/'selection.json') and result['refit_sha256']==digest(fit.REPORT/'refit.json')
    values={};accounting={}
    for fold in range(4):
        name='fold'+str(fold);data=fit.dataset(name,cache);training,held=fit.heading.folds.partition_indices(ids,fold)
        accounting[name],v=audit(fit.WORK/'tuning'/name,data,training,held,name,plan['epochs'],plan,parent,architecture)
        for epoch,value in v.items():values.setdefault(epoch,[]).append(value)
        print('Verified joint trajectory',name,flush=True)
    for c in selection['candidates']:assert {k:c[k] for k in ('rows','correct','nll','code_rows','code_correct')}==fit.joint.combine(values[c['epoch']])
    chosen=selection['selected'];assert chosen==fit.choose(selection['candidates'],plan['code_accuracy_allowance'])
    data=fit.dataset('full',cache);accounting['refit'],_=audit(fit.WORK/'refit',data,np.arange(len(ids)),None,'full',chosen['epoch'],plan,parent,architecture)
    saved=torch.load(fit.WORK/'selected.pt',weights_only=False);trained=torch.load(fit.WORK/'refit'/f"epoch-{chosen['epoch']:03d}.pt",weights_only=False)
    assert all(torch.equal(v,trained['model'][k]) for k,v in saved['model'].items())
    net=fit.warm('full',parent,architecture);net.load_state_dict(saved['model']);assert fit.joint.score(net,data,np.arange(len(ids)))==refit['fit']
    torch.set_num_threads(4);windows,maps=fit.heading.original.load();encoded,history,source_bindings=fit.prior.encoded(windows,maps,architecture)
    assert source_bindings==result['source_bindings'];discovery=fit.read(fit.heading.original.REPORT/'discovery.json');policy=fit.policy(plan,parent,architecture);exact={};groups={}
    for split in ('fit','evaluation'):
        actual=fit.heading.evaluate(policy,windows,maps,encoded,discovery,split,time.perf_counter()+300);baseline=fit.read(fit.prior.WORK/(split+'-predictions.json'))
        assert actual==fit.read(fit.WORK/(split+'-predictions.json')) and actual['summary']==result['results'][split]
        assert fit.joint.prior.paired(actual['records'],baseline['records'])==result['comparisons'][split]
        exact[split]=len(actual['records']);groups[split]=dict(edited=actual['groups'],baseline=baseline['groups'])
    x=result['results']['evaluation'];b=fit.read(fit.prior.REPORT/'result.json')['results']['evaluation']
    assert result['target_met']==(x['movement_accuracy']>=.8) and result['guards']==dict(code=x['code_accuracy']>=b['code_accuracy']-.01,nll=x['movement_nll']<=b['movement_nll']+.01)
    predictor=TrajectoryMovementPredictor();w=next(w for w in windows if w['partition']=='evaluation');state=None;support,_=move_support(w)
    with torch.no_grad():expected=policy(**encoded[w['key']])
    for i,s in enumerate(w['steps']):
        value=predictor.predict(s['input'] if s['observed'] else None,maps[w['payload']],s['round'],s['previous'],s['previous_mask'],state,previous_moves=history[w['key']][i]);state=value['state']
        assert value['code']==int(expected['code'][i].argmax())
        if value['movement_probabilities'] is not None:torch.testing.assert_close(torch.tensor(value['movement_probabilities']),expected['move'][i].masked_fill(~support[i],-1e9).softmax(-1),atol=2e-6,rtol=2e-5)
    immutable_json(fit.REPORT/'comparison.json',dict(groups=groups))
    immutable_json(fit.REPORT/'verification.json',dict(result_sha256=digest(fit.REPORT/'result.json'),accounting=accounting,
        exact_validation_measurements=len(values)*4,exact_forecasts=exact,streaming_turns=32,frozen_tensors_preserved=True,seconds=time.perf_counter()-start))
    print('VERIFIED trajectory movement',exact,flush=True)


if __name__=='__main__':run()
