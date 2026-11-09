"""Read-only reproduction of full-map weight adaptation and inference."""
import time
from pathlib import Path
import numpy as np
import torch
from . import full_movement_fit as fit,joint_movement_fit as joint,movement_bias_edit as bias,code_path_fit as old
from . import expanded_code_fit as expanded, data as original
from .full_movement_predictor import FullMovementPredictor
from .study import evaluate
from ..audit import immutable_json
from ..data import digest


def audit(directory,env,indices,held,name,plan,parent,architecture,epochs):
    net=fit.warm(name,parent,architecture);base={k:v.clone() for k,v in net.state_dict().items()};active={k for k,p in net.named_parameters() if p.requires_grad}
    initial=torch.load(directory/'epoch-000.pt',weights_only=False);assert all(torch.equal(v,initial['model'][k]) for k,v in base.items())
    assert not initial['optimizer']['state'];trace=fit.read(directory/'trace.json');assert len(trace['epochs'])==epochs
    zero=fit.score(net,env,held) if held is not None else None;assert trace['initial']==zero
    values={0:zero};rng=np.random.default_rng(plan['seed']);updates=0;presentations=0
    for entry in trace['epochs']:
        order=rng.permutation(indices);assert order.tolist()==entry['order'];counts=[]
        for start in range(0,len(order),plan['batch_windows']):
            batch=order[start:start+plan['batch_windows']]
            counts.append([sum(int((env['labels'][i]>=0).sum()) for i in batch),sum(sum(s['observed'] for s in env['windows'][i]['steps']) for i in batch)])
        assert counts==entry['denominators'] and len(counts)==len(entry['gradient_norms']) and np.isfinite(entry['gradient_norms']).all()
        updates+=len(counts);presentations+=sum(x[0] for x in counts);assert entry['updates']==updates and entry['movement_presentations']==sum(x[0] for x in counts)
        epoch=entry['epoch'];saved=torch.load(directory/f'epoch-{epoch:03d}.pt',weights_only=False)
        assert saved['epoch']==epoch and saved['updates']==updates and saved['rng']==rng.bit_generator.state
        for k,v in saved['model'].items():
            assert torch.isfinite(v).all()
            if k not in active:assert torch.equal(v,base[k]),k
        optimizer=saved['optimizer'];assert len(optimizer['state'])==len(active)
        assert optimizer['param_groups'][0]['lr']==plan['learning_rate'] and optimizer['param_groups'][0]['weight_decay']==plan['weight_decay']
        for value in optimizer['state'].values():
            assert int(value['step'])==updates and all(torch.isfinite(v).all() for v in value.values() if torch.is_tensor(v))
        net.load_state_dict(saved['model'])
        if held is not None:values[epoch]=fit.score(net,env,held);assert values[epoch]==entry['validation']
    return dict(updates=updates,movement_presentations=presentations),values


def run():
    start=time.perf_counter();plan,parent,architecture,cache,ids=fit.inputs();torch.set_num_threads(4)
    selection=fit.read(fit.REPORT/'selection.json');refit=fit.read(fit.REPORT/'refit.json');result=fit.read(fit.REPORT/'result.json')
    for r in (selection,refit,result):fit.check(r)
    assert selection['plan_sha256']==digest(fit.REPORT/'plan.json') and refit['selection_sha256']==digest(fit.REPORT/'selection.json') and result['refit_sha256']==digest(fit.REPORT/'refit.json')
    values={};accounting={};teacher_probes=0
    for fold in range(4):
        name='fold'+str(fold);env=fit.environment(parent,architecture,cache,ids,name);training,held=expanded.partition_indices(ids,fold)
        net=fit.warm(name,parent,architecture);groups=set()
        for i in held:
            if ids[i]['group'] in groups:continue
            groups.add(ids[i]['group'])
            with torch.no_grad():actual=net(fit.encoded(env,i))['code'].softmax(-1)
            torch.testing.assert_close(actual,env['teacher'][i],atol=2e-6,rtol=2e-5);teacher_probes+=1
        accounting[name],v=audit(fit.WORK/'tuning'/name,env,training,held,name,plan,parent,architecture,plan['epochs'])
        for epoch,value in v.items():values.setdefault(epoch,[]).append(value)
        print('Verified full-map',name,flush=True)
    for c in selection['candidates']:
        assert {k:c[k] for k in ('rows','correct','nll','code_rows','code_correct')}==joint.combine(values[c['epoch']])
    chosen=selection['selected'];assert chosen==fit.choose(selection['candidates'],plan['code_accuracy_allowance'])
    env=fit.environment(parent,architecture,cache,ids,'full');accounting['refit'],_=audit(fit.WORK/'refit',env,np.arange(len(ids)),None,'full',plan,parent,architecture,chosen['epoch'])
    saved=torch.load(fit.WORK/'selected.pt',weights_only=False);selected=torch.load(fit.WORK/'refit'/f"epoch-{chosen['epoch']:03d}.pt",weights_only=False)
    assert all(torch.equal(v,selected['model'][k]) for k,v in saved['model'].items())
    net=fit.warm('full',parent,architecture);net.load_state_dict(saved['model']);assert fit.score(net,env,[i for i,r in enumerate(ids) if r['canonical']])==refit['original_fit']
    windows,maps=original.load();encoded=old.encoded_windows(windows,maps,architecture);discovery=fit.read(original.REPORT/'discovery.json');net=fit.policy(plan,parent,architecture);exact={};groups={}
    for split in ('fit','evaluation'):
        actual=evaluate(net,windows,maps,encoded,discovery,split,time.perf_counter()+300)
        assert actual==fit.read(fit.WORK/(split+'-predictions.json')) and actual['summary']==result['results'][split]
        baseline=fit.read(bias.WORK/(split+'-predictions.json'));assert joint.prior.paired(actual['records'],baseline['records'])==result['comparisons'][split]
        exact[split]=len(actual['records']);groups[split]=dict(edited=actual['groups'],baseline=baseline['groups'])
    b=fit.read(bias.REPORT/'result.json')['results']['evaluation'];x=result['results']['evaluation']
    assert result['target_met']==(x['movement_accuracy']>=.8) and result['guards']==dict(code=x['code_accuracy']>=b['code_accuracy']-.01,nll=x['movement_nll']<=b['movement_nll']+.01)
    predictor=FullMovementPredictor();w=next(w for w in windows if w['partition']=='evaluation');state=None
    from .model import move_support
    support,_=move_support(w)
    with torch.no_grad():expected=net(**encoded[w['key']])
    for i,s in enumerate(w['steps']):
        value=predictor.predict(s['input'] if s['observed'] else None,maps[w['payload']],s['round'],s['previous'],s['previous_mask'],state);state=value['state']
        assert value['code']==int(expected['code'][i].argmax())
        if value['movement_probabilities'] is not None:torch.testing.assert_close(torch.tensor(value['movement_probabilities']),expected['move'][i].masked_fill(~support[i],-1e9).softmax(-1),atol=2e-6,rtol=2e-5)
    immutable_json(fit.REPORT/'comparison.json',dict(groups=groups))
    immutable_json(fit.REPORT/'verification.json',dict(result_sha256=digest(fit.REPORT/'result.json'),sources=fit.bindings([Path(__file__)]),
        accounting=accounting,exact_validation_measurements=len(values)*4,teacher_full_network_probes=teacher_probes,
        exact_forecasts=exact,streaming_turns=32,frozen_tensors_preserved=True,seconds=time.perf_counter()-start))
    print('VERIFIED full-map weights',exact,flush=True)


if __name__=='__main__':run()
