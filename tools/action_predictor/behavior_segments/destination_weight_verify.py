"""Read-only weight, label, schedule, cached-score and full-inference verification."""
import time
from pathlib import Path
import numpy as np
import torch
from . import destination_weight_fit as fit,code_path_fit as movement,code_movement_fit as prior
from . import expanded_code_data as expanded,data as original,model
from .destination_weights import DestinationHead
from .destination_predictor import DestinationWeightPredictor
from .study import endpoint_labels,evaluate
from ..audit import immutable_json
from ..data import digest


def audit(directory,rows,shared,indices,plan,architecture,path,lr,epochs,held=None):
    net=fit.new_head(path,architecture);trace=fit.read(directory/'trace.json');initial=torch.load(directory/'epoch-000.pt',weights_only=False)
    assert all(torch.equal(v,initial['model'][k]) for k,v in net.state_dict().items())
    assert not initial['optimizer']['state'];assert len(trace['epochs'])==epochs
    assert trace['initial']==(fit.score(net,rows,shared,held) if held is not None else None)
    values={0:trace['initial']};rng=np.random.default_rng(plan['seed']);updates=0;presentations=0
    for entry in trace['epochs']:
        order=rng.permutation(indices);assert order.tolist()==entry['order']
        counts=[len(order[i:i+plan['batch_rows']]) for i in range(0,len(order),plan['batch_rows'])]
        assert counts==entry['denominators'];assert len(counts)==len(entry['gradient_norms']) and np.isfinite(entry['gradient_norms']).all()
        updates+=len(counts);presentations+=sum(counts);assert updates==entry['updates'];epoch=entry['epoch']
        if epoch%plan['evaluate_every']==0 or epoch==epochs:
            saved=torch.load(directory/f'epoch-{epoch:03d}.pt',weights_only=False)
            assert saved['epoch']==epoch and saved['updates']==updates and saved['rng']==rng.bit_generator.state
            assert torch.equal(saved['model']['goal.2.bias'],initial['model']['goal.2.bias'])
            assert all(torch.isfinite(v).all() for v in saved['model'].values())
            assert len(saved['optimizer']['state'])==5
            group=saved['optimizer']['param_groups'][0];assert group['lr']==lr and group['weight_decay']==plan['weight_decay']
            for state in saved['optimizer']['state'].values():
                assert int(state['step'])==updates and all(torch.isfinite(v).all() for v in state.values() if torch.is_tensor(v))
            net.load_state_dict(saved['model'])
            if held is not None:values[epoch]=fit.score(net,rows,shared,held);assert values[epoch]==entry['validation']
    return dict(updates=updates,presentations=presentations),values


def run():
    start=time.perf_counter();plan,architecture,cache,ids=fit.inputs();rows,identities=fit.cached();torch.set_num_threads(4)
    selection=fit.read(fit.REPORT/'selection.json');refit=fit.read(fit.REPORT/'refit.json');result=fit.read(fit.REPORT/'result.json')
    for receipt in (selection,refit,result):fit.check(receipt)
    assert selection['plan_sha256']==digest(fit.REPORT/'plan.json') and refit['selection_sha256']==digest(fit.REPORT/'selection.json')
    assert result['refit_sha256']==digest(fit.REPORT/'refit.json')
    windows,maps=expanded.read();codes=fit.read(expanded.WORK/'labels.json')['labels'];old=fit.read(original.REPORT/'discovery.json')
    net=prior.backbone(fit.ROOT/plan['full_backbone'],architecture);captured=[];hook=net.goal.register_forward_pre_hook(lambda module,args:captured.append(args[0]))
    ri=0;canonical=0
    with torch.no_grad():
        for wi,w in enumerate(windows):
            goals,_=endpoint_labels(w,codes[w['key']],maps[w['payload']]);selected=[i for i,g in enumerate(goals) if g is not None]
            if ids[wi]['canonical']:assert goals==old['endpoints'][w['key']];canonical+=len(selected)
            if not selected:continue
            args,_=model.encode_window(w,maps[w['payload']],architecture['schema']);net(**args);feature=captured.pop()
            for i in selected:
                r=rows[ri];identity=identities[ri];mask=args['batch']['valid'][i].flatten();cells=mask.nonzero().flatten()
                assert identity==dict(**ids[wi],window=wi,position=i,event=w['steps'][i]['event'])
                assert torch.equal(r['spatial'],feature[i,:16].flatten(1).T[mask]) and torch.equal(r['whole'],feature[i,32:,0,0])
                assert torch.equal(cells,r['cells']) and r['width']==maps[w['payload']]['width'] and r['goal']==goals[i]
                assert int(cells[r['target']])==goals[i][1]*r['width']+goals[i][0];ri+=1
    hook.remove();assert ri==2099 and canonical==369
    for name,path in [*(('fold'+str(k),fit.ROOT/p) for k,p in enumerate(plan['fold_backbones'])),('full',fit.ROOT/plan['full_backbone'])]:
        features=prior.cached(name);backbone=prior.backbone(path,architecture)
        shared=torch.cat((features['states'],features['probabilities']@backbone.embeddings),-1)
        expected=torch.stack([shared[r['window'],r['position']] for r in identities])
        assert torch.equal(expected,torch.load(fit.WORK/(name+'-shared.pt'),weights_only=True))
    print('Verified all goal labels, spatial caches and five shared-state banks',flush=True)
    torch.set_num_threads(1);values={};accounting={}
    for lr in plan['learning_rates']:
        for fold in range(4):
            training=np.array([i for i,r in enumerate(identities) if r['fold']!=fold]);held=np.array([i for i,r in enumerate(identities) if r['fold']==fold and r['canonical']])
            assert not {identities[i]['group'] for i in training}&{identities[i]['group'] for i in held}
            shared=torch.load(fit.WORK/f'fold{fold}-shared.pt',weights_only=True);directory=fit.WORK/'tuning'/f'lr{lr:g}-fold{fold}'
            accounting[directory.name],v=audit(directory,rows,shared,training,plan,architecture,fit.ROOT/plan['fold_backbones'][fold],lr,plan['epochs'],held)
            for epoch,value in v.items():values.setdefault((lr,epoch),[]).append(value)
    for c in selection['candidates']:
        assert {k:c[k] for k in ('rows','within2','exact','error_sum','nll')}==fit.combine(values[(c['learning_rate'],c['epoch'])])
    chosen=selection['selected'];assert chosen==fit.choose(selection['candidates'])
    shared=torch.load(fit.WORK/'full-shared.pt',weights_only=True)
    accounting['refit'],_=audit(fit.WORK/'refit',rows,shared,np.arange(len(rows)),plan,architecture,fit.ROOT/plan['full_backbone'],chosen['learning_rate'],chosen['epoch'])
    saved=torch.load(fit.WORK/'selected.pt',weights_only=False);base=torch.load(fit.ROOT/plan['full_backbone'],weights_only=False)['model']
    permitted=[]
    for k,v in saved['model'].items():
        if not k.startswith(('query.','goal.')) or k=='goal.2.bias':assert torch.equal(v,base[k]),k
        elif not torch.equal(v,base[k]):permitted.append(k)
    head=DestinationHead(fit.policy(architecture).backbone)
    assert fit.score(head,rows,shared,np.arange(len(rows)))==refit['fit']
    selected_head=torch.load(fit.WORK/'refit'/f"epoch-{chosen['epoch']:03d}.pt",weights_only=False)['model']
    assert all(torch.equal(v,selected_head[k]) for k,v in head.state_dict().items())
    torch.set_num_threads(4);windows,maps=original.load();cache=movement.encoded_windows(windows,maps,architecture)
    net=fit.policy(architecture);discovery=fit.read(original.REPORT/'discovery.json');exact={};groups={}
    for split in ('fit','evaluation'):
        actual=evaluate(net,windows,maps,cache,discovery,split,time.perf_counter()+300)
        assert actual==fit.read(fit.WORK/(split+'-predictions.json')) and actual['summary']==result['results'][split]
        baseline=fit.read(movement.WORK/f'predicted-{split}-predictions.json');goals=[]
        for a,b in zip(actual['records'],baseline['records']):
            assert {k:v for k,v in a.items() if k not in ('goal_prediction','goal_error','goal_nll','astar_correct')}=={k:v for k,v in b.items() if k not in ('goal_prediction','goal_error','goal_nll','astar_correct')}
            if a['goal_label'] is not None:goals.append((a,b))
        assert result['comparisons'][split]==dict(rows=len(goals),within2_rescues=sum(a['goal_error']<=2<b['goal_error'] for a,b in goals),within2_regressions=sum(b['goal_error']<=2<a['goal_error'] for a,b in goals))
        exact[split]=len(actual['records']);groups[split]=dict(edited=actual['groups'],baseline=baseline['groups'])
    x=result['results']['evaluation'];b=fit.read(movement.REPORT/'result.json')['results']['predicted']['evaluation']
    expected=dict(within2=x['goal_within2']>=b['goal_within2']+.05,exact=x['goal_exact']>=b['goal_exact'],mean_error=x['mean_goal_error']<b['mean_goal_error'],nll=x['goal_nll']<b['goal_nll'],astar=x['astar_movement_accuracy']>=b['astar_movement_accuracy'])
    assert result['checks']==expected and result['all_checks_pass']==all(expected.values())
    predictor=DestinationWeightPredictor();w=next(w for w in windows if w['partition']=='evaluation');state=None
    with torch.no_grad():expected=net(**cache[w['key']])
    width=maps[w['payload']]['width'];streaming=0
    for i,s in enumerate(w['steps']):
        value=predictor.predict(s['input'] if s['observed'] else None,maps[w['payload']],s['round'],s['previous'],s['previous_mask'],state);state=value['state']
        assert value['code']==int(expected['code'][i].argmax())
        if s['observed'] and s['input']['observation']['own'].get('position') is not None:
            cell=int(expected['goal'][i].flatten().argmax());assert value['goal']==(cell%width,cell//width)
        streaming+=1
    immutable_json(fit.REPORT/'comparison.json',dict(groups=groups))
    immutable_json(fit.REPORT/'verification.json',dict(result_sha256=digest(fit.REPORT/'result.json'),sources=fit.bindings([Path(__file__)]),
        reconstructed_goals=2099,original_labels_exact=369,exact_validation_measurements=len(values)*4,
        accounting=accounting,changed_tensors=permitted,code_and_direct_movement_unchanged=True,
        exact_forecasts=exact,streaming_turns=streaming,seconds=time.perf_counter()-start))
    print('VERIFIED destination weights',exact,flush=True)


if __name__=='__main__':run()
