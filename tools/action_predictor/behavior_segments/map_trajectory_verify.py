"""Reproduce model selection, weight boundaries, accounting and streaming outputs."""
import time
import numpy as np
import torch
from . import map_trajectory_fit as fit
from .planner_weight_verify import equal
from .map_trajectory_predictor import MapTrajectoryPlanner
from ..audit import immutable_json
from ..data import digest


def audit_run(directory,net,env,indices,p,epochs):
    initial=torch.load(directory/'epoch-000.pt',weights_only=False)
    assert equal(initial['model'],net.state_dict()) and not initial['optimizer']['state']
    frozen={k:v.clone() for k,v in net.named_parameters() if not v.requires_grad};active={k for k,v in net.named_parameters() if v.requires_grad}
    rng=np.random.default_rng(p['seed']);trace=fit.read(directory/'trace.json');updates=0
    assert len(trace['epochs'])==epochs
    for e in trace['epochs']:
        order=rng.permutation(indices);assert e['order']==order.tolist();expected=[]
        for start in range(0,len(order),p['batch_windows']):
            batch=order[start:start+p['batch_windows']]
            expected.append([sum(int((env['data']['movement_labels'][i]>=0).sum()) for i in batch),sum(sum(s['observed'] for s in env['windows'][i]['steps']) for i in batch)])
        assert e['denominators']==expected and e['movement_presentations']==sum(x[0] for x in expected)
        updates+=len(expected);assert e['updates']==updates and len(e['norms'])==len(expected) and np.isfinite(e['norms']).all()
        checkpoint=torch.load(directory/f"epoch-{e['epoch']:03d}.pt",weights_only=False)
        assert checkpoint['updates']==updates and checkpoint['rng']==rng.bit_generator.state
        assert all(torch.equal(checkpoint['model'][k],v) for k,v in frozen.items())
        assert all(torch.isfinite(v).all() for v in checkpoint['model'].values())
        states=checkpoint['optimizer']['state'];assert len(states)==len(active)
        for state in states.values():
            assert int(state['step'])==updates
            assert all(not torch.is_tensor(v) or torch.isfinite(v).all() for v in state.values())
        group=checkpoint['optimizer']['param_groups'][0]
        assert group['lr']==p['learning_rate'] and group['weight_decay']==p['weight_decay']
    return trace,updates


def run():
    start=time.perf_counter();p,parent,architecture,cache,ids=fit.inputs();torch.set_num_threads(4)
    for name in ('selection','refit','result'):fit.check(fit.read(fit.REPORT/(name+'.json')))
    selection=fit.read(fit.REPORT/'selection.json');values={};updates=0;trial_deltas={}
    for fold in range(4):
        name=f'fold{fold}';env=fit.environment(name,parent,architecture,cache,ids);net=fit.warm(name,parent,architecture);training,held=fit.base.heading.folds.partition_indices(ids,fold)
        trace,u=audit_run(fit.WORK/'tuning'/name,net,env,training,p,p['epochs']);updates+=u
        values[(fold,0)]=fit.score(net,env,held);assert equal(values[(fold,0)],trace['initial'])
        old=torch.load(fit.planner.WORK/f'fold{fold}.pt',weights_only=False);edit=fit.read(fit.planner.REPORT/'selection.json')['selected'];reference=fit.planner.simulate(old,edit['scale'],edit['shift'])
        assert [r['prediction'] for r in values[(fold,0)]['predictions']]==reference['predictions']
        for e in trace['epochs']:
            net.load_state_dict(torch.load(fit.WORK/'tuning'/name/f"epoch-{e['epoch']:03d}.pt",weights_only=False)['model'])
            values[(fold,e['epoch'])]=fit.score(net,env,held);assert equal(values[(fold,e['epoch'])],e['validation'])
        initial=torch.load(fit.WORK/'tuning'/name/'epoch-000.pt',weights_only=False)['model'];groups={}
        for k,v in net.state_dict().items():
            group='.'.join(k.split('.')[:2]);g=groups.setdefault(group,dict(squared_delta=0.,changed=0,total=0));g['squared_delta']+=float((v-initial[k]).square().sum());g['changed']+=int((v!=initial[k]).sum());g['total']+=v.numel()
        trial_deltas[name]=dict(final_epoch=p['epochs'],groups=groups,clipped_updates=sum(n>p['clip'] for e in trace['epochs'] for n in e['norms']))
        print('Verified map trajectory fold',fold,flush=True)
    cs=[dict(epoch=e,**fit.combine([values[(k,e)] for k in range(4)])) for e in range(p['epochs']+1)]
    assert cs==selection['candidates'] and fit.choose(cs,p)==selection['selected']
    env=fit.environment('full',parent,architecture,cache,ids);net=fit.warm('full',parent,architecture);warm={k:v.clone() for k,v in net.state_dict().items()}
    _,u=audit_run(fit.WORK/'refit',net,env,np.arange(len(ids)),p,selection['selected']['epoch']);updates+=u
    selected=torch.load(fit.WORK/'selected.pt',weights_only=False)['model'];expected=torch.load(fit.WORK/'refit'/f"epoch-{selection['selected']['epoch']:03d}.pt",weights_only=False)['model'];assert equal(selected,expected)
    deltas={k:dict(norm_before=float(warm[k].norm()),norm_after=float(v.norm()),delta_norm=float((v-warm[k]).norm()),changed=int((v!=warm[k]).sum())) for k,v in selected.items()}
    net.load_state_dict(selected);env,_=fit.assessment_environment(parent,architecture,cache,ids);result=fit.read(fit.REPORT/'result.json')
    for split in ('fit','evaluation'):
        actual=fit.score(net,env,[i for i,w in enumerate(env['windows']) if w['partition']==split]);assert equal(actual,result['results'][split])
    x=result['results']['evaluation'];b=fit.read(fit.base.REPORT/'result.json')['results']['evaluation'];previous=fit.read(fit.planner.REPORT/'result.json')['results']['evaluation']['edited']
    gates=dict(combined=x['combined']>previous['correct'],direct_reference=x['combined']>318,utility=x['utility_sum']>0,active=x['active']>=.1*x['available'],code=x['code_correct']/x['code_rows']>=b['code_accuracy']-.01,nll=x['nll']<=b['movement_nll']+.01)
    assert gates==result['checks'] and all(gates.values())==result['all_checks_pass'] and (x['combined']>=411 and x['rows']==513)==result['target_met']
    windows=env['windows'];maps=env['maps'];_,history,_=fit.base.prior.encoded(windows,maps,architecture);expected={(r['key'],r['position']):r for r in x['predictions']};predictor=MapTrajectoryPlanner();turns=0
    for w in [w for w in windows if w['partition']=='evaluation'][:2]:
        state=None
        for i,s in enumerate(w['steps']):
            value=predictor.predict(s['input'] if s['observed'] else None,maps[w['payload']],s['round'],s['previous'],s['previous_mask'],state,previous_moves=history[w['key']][i]);state=value['state'];turns+=1
            if not s['observed']:continue
            r=expected[(w['key'],i)];assert state['objective_identity']==r['selected'];own=s['input']['observation']['own'].get('position')
            if own is not None:
                for key,index in (('objective_movement',r['prediction']),('conditional_movement',r['direct'])):
                    dx,dy=fit.model.OFFSETS[index];assert value[key]==(own['x']+dx,own['y']+dy)
    immutable_json(fit.REPORT/'weight-inspection.json',dict(tensors=deltas,trial_deltas=trial_deltas,selected_epoch=selection['selected']['epoch'],meaning='Weight magnitudes and changes are descriptive; they do not identify semantic strategy or a unique causal bottleneck.'))
    immutable_json(fit.REPORT/'verification.json',dict(result_sha256=digest(fit.REPORT/'result.json'),source_sha256=digest(__file__),fold_measurements=12,initial_predictions_exact=True,optimizer_updates_accounted=updates,optimizer_replays=0,streaming_turns=turns,all_forecasts_reproduced=True,seconds=time.perf_counter()-start))
    print('VERIFIED full map trajectory weights',flush=True)


if __name__=='__main__':run()
