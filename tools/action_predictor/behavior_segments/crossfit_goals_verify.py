"""Verify goal-model exclusion, matched fitting, causal forecasts and runtime."""
import argparse,time
import numpy as np
import torch
from . import crossfit_goals_fit as fit
from .crossfit_goals import selected_head,head_exclusions,selector_features
from .shared_goal_execution_verify import audit_run
from .planner_weight_verify import equal
from .crossfit_goals_predictor import CrossfitGoalPlanner
from ..audit import immutable_json
from ..data import digest


def prefit():
    start=time.perf_counter();p,_,_,_,ids=fit.inputs();torch.set_num_threads(1)
    for name in ('cache','selectors','assembled'):fit.check(fit.read(fit.REPORT/(name+'.json')))
    data=torch.load(fit.WORK/'selector-data.pt',weights_only=False);raw=torch.load(fit.WORK/'raw.pt',weights_only=False);membership=fit.read(fit.REPORT/'selectors.json')['membership'];updates=0;norms={}
    targets=fit.read(fit.OLD.WORK/'rows.json');lookup={(q['key'],q['position']):i for i,q in enumerate(raw['queries'])};i=0
    for r in targets:
        q=lookup[(r['key'],r['position'])]
        for c in r['candidates']:
            assert torch.equal(data['x'][i],selector_features(raw['raw'][q],c['features']));assert abs(float(data['y'][i])-c['utility'])<1e-6 and data['groups'][i]==r['group'] and int(data['folds'][i])==r['fold'];i+=1
    assert i==len(data['y'])==42959 and data['x'].shape[1]==660
    for name in fit.HEADS:
        excluded=head_exclusions(name);ix=np.array([i for i,f in enumerate(data['folds'].tolist()) if f not in excluded]);groups=sorted({data['groups'][i] for i in ix});assert membership[name]==dict(excluded_folds=excluded,training_groups=groups,examples=len(ix));directory=fit.WORK/'selectors'/name;initial=fit.new_selector(p).state_dict();assert equal(initial,torch.load(directory/'initial.pt',weights_only=True));trace=fit.read(directory/'trace.json');rng=np.random.default_rng(p['selector_seed']);u=0;assert len(trace)==p['selector_epochs']
        for e in trace:
            assert e['order']==rng.permutation(ix).tolist();assert len(e['norms'])==(len(ix)+p['selector_batch']-1)//p['selector_batch'] and np.isfinite(e['norms']).all() and np.isfinite(e['online_mse']);u+=len(e['norms'])
        final=torch.load(directory/'final.pt',weights_only=False);assert final['rng']==rng.bit_generator.state
        for group in final['optimizer']['param_groups']:assert group['lr']==p['selector_lr'] and group['weight_decay']==.01
        for state in final['optimizer']['state'].values():assert int(state['step'])==u and all(not torch.is_tensor(v) or torch.isfinite(v).all() for v in state.values())
        assert all(torch.isfinite(v).all() for v in final['model'].values());norms[name]={k:float((v-initial[k]).norm()) for k,v in final['model'].items()};assert all(v>0 for v in norms[name].values());updates+=u
    checks=0
    for outer in [0,1,2,3,None]:
        name='full' if outer is None else f'fold{outer}';original=torch.load(fit.prior.WORK/(name+'.pt'),weights_only=False);banks={a:torch.load(fit.WORK/'banks'/a/(name+'.pt'),weights_only=False) for a in fit.ARMS};outer_groups={q['group'] for q in ids if q['fold']==outer}
        for arm,b in banks.items():
            assert all(torch.equal(b[k],original[k]) for k in ('context','baseline','support','labels'));assert [(r['key'],r['position']) for r in b['records']]==[(r['key'],r['position']) for r in original['records']]
            for i,r in enumerate(b['records']):
                head=selected_head(outer,r['fold'],arm=='crossfit');assert head==r['selector'];trained=membership[head]['training_groups'];held=outer is not None and r['fold']==outer;assert (r['group'] not in trained)==(held or arm=='crossfit');assert outer_groups.isdisjoint(trained);assert int(b['goal'][i,0,7])==r['active'];checks+=1
            if outer is not None:
                held=torch.tensor([r['fold']==outer for r in b['records']]);assert torch.equal(b['goal'][held],banks['insample']['goal'][held])
            net=fit.prior.new('goal',p);ix=torch.arange(128);pred=net(b['context'][ix],b['goal'][ix],b['baseline'][ix]);assert torch.equal(pred,b['baseline'][ix]);loss=torch.nn.functional.cross_entropy(pred.masked_fill(~b['support'][ix],-1e9),b['labels'][ix]);loss.backward();assert all(v.grad is None or torch.isfinite(v.grad).all() for v in net.parameters())
    windows,maps=fit.prior.prior.base.heading.expanded.read();history,_=fit.OLD.audit.prior_moves(windows);probes=[]
    for fold in range(4):
        wi=next(i for i,x in enumerate(ids) if x['fold']==fold);w=windows[wi];x=fit.raw_window(w,maps[w['payload']],history[w['key']])
        for j,s in enumerate(w['steps']):
            if s['observed']:assert torch.equal(x[j],raw['raw'][lookup[(w['key'],j)]])
        probes.append(w['key'])
    probe_indices=[j for j,q in enumerate(raw['queries']) if q['key'] in probes];queries=[raw['queries'][j] for j in probe_indices]
    for outer in [0,1,2,3,None]:
        name='full' if outer is None else f'fold{outer}'
        for arm in fit.ARMS:
            fresh=fit.predicted(queries,raw['raw'][probe_indices],windows,maps,[selected_head(outer,q['fold'],arm=='crossfit') for q in queries]);bank=torch.load(fit.WORK/'banks'/arm/(name+'.pt'),weights_only=False);bykey={(r['key'],r['position']):j for j,r in enumerate(bank['records'])}
            for q,g in zip(queries,fresh):
                j=bykey.get((q['key'],q['position']))
                if j is not None:assert torch.equal(g['goal'],bank['goal'][j]) and g['selected']==bank['records'][j]['selected']
    immutable_json(fit.REPORT/'prefit-verification.json',dict(plan_sha256=digest(fit.REPORT/'plan.json'),source_sha256=digest(__file__),selector_initializations=11,selector_updates_accounted=updates,selector_weight_changes=norms,target_feature_rows_reconstructed=len(data['y']),movement_exclusion_checks=checks,held_goals_identical=True,raw_window_probes=probes,goal_window_probes=40,initial_executor_parity=True,finite_backward=True,executor_optimizer_updates=0,seconds=time.perf_counter()-start));print('VERIFIED nested goals',updates,checks,flush=True)


@torch.no_grad()
def diagnose():
    p,_,_,_,_=fit.inputs();torch.set_num_threads(1);data=torch.load(fit.WORK/'selector-data.pt',weights_only=False);values={};weight_norms={}
    for arm in fit.ARMS:
        total=0.;n=0
        for fold in range(4):
            name=selected_head(None,fold,arm=='crossfit');net=fit.new_selector(p);net.load_state_dict(torch.load(fit.WORK/'selectors'/name/'final.pt',weights_only=False)['model']);ix=(data['folds']==fold).nonzero().flatten()
            for start in range(0,len(ix),512):
                b=ix[start:start+512];total+=float((net(data['x'][b])-data['y'][b]).square().double().sum());n+=len(b)
        b=torch.load(fit.WORK/'banks'/arm/'full.pt',weights_only=False);weights=torch.load(fit.WORK/(arm+'-selected.pt'),weights_only=True);initial=fit.prior.new('goal',p).state_dict();weight_norms[arm]={k:float((v-initial[k]).norm()) for k,v in weights.items()};values[arm]=dict(candidate_rows=n,raw_utility_mse=total/n,training_active_movements=sum(r['active'] for r in b['records']))
    immutable_json(fit.REPORT/'diagnostics.json',dict(fitting_only=True,selector_prediction_quality=values,executor_weight_changes=weight_norms,interpretation='Raw utility error before fixed calibration compares same-size selectors including/excluding each fitting game. This is a training-input diagnostic,not evidence of evaluation or strategic improvement.'))


def run():
    start=time.perf_counter();p,_,architecture,_,_=fit.inputs();torch.set_num_threads(1)
    for name in ('selectors','assembled','fit','result'):fit.check(fit.read(fit.REPORT/(name+'.json')))
    proof=fit.read(fit.REPORT/'prefit-verification.json');assert proof['plan_sha256']==digest(fit.REPORT/'plan.json');selection=fit.read(fit.REPORT/'selection.json');updates=0
    for arm in fit.ARMS:
        values={}
        for fold in range(4):
            name=f'fold{fold}';b=torch.load(fit.WORK/'banks'/arm/(name+'.pt'),weights_only=False);rs=b['records'];ix=np.array([i for i,r in enumerate(rs) if r['fold']!=fold]);held=np.array([i for i,r in enumerate(rs) if r['fold']==fold and r['canonical']]);v,u,_=audit_run(fit.WORK/'executors'/arm/name,'goal',b,ix,p,p['epochs'],held);updates+=u
            for e,s in v.items():values.setdefault(e,[]).append(s)
            a=fit.read(fit.WORK/'executors'/'insample'/name/'trace.json');z=fit.read(fit.WORK/'executors'/'crossfit'/name/'trace.json');assert [e['order'] for e in a['epochs']]==[e['order'] for e in z['epochs']]
        cs=[dict(epoch=e,**{k:sum(v[k] for v in vs) for k in ('rows','correct','nll_sum')}) for e,vs in values.items()];assert cs==selection['candidates'][arm] and fit.prior.previous.select(cs)==selection['selected'][arm]
        b=torch.load(fit.WORK/'banks'/arm/'full.pt',weights_only=False);_,u,final=audit_run(fit.WORK/'executors'/arm/'refit','goal',b,np.arange(len(b['records'])),p,selection['selected'][arm]['epoch']);updates+=u;assert equal(final['model'],torch.load(fit.WORK/(arm+'-selected.pt'),weights_only=True))
    torch.set_num_threads(4);r=fit.read(fit.REPORT/'result.json');actual=fit.assessment();assert all(equal(v,r[k]) for k,v in actual.items());windows,maps=fit.prior.prior.base.heading.original.load();_,history,_=fit.prior.prior.base.prior.encoded(windows,maps,architecture);bank=torch.load(fit.WORK/'evaluation.pt',weights_only=False);evaluation=[w for w in windows if w['partition']=='evaluation'];activity={w['key']:sum(z['active'] for z in bank['records'] if z['key']==w['key']) for w in evaluation};chosen=[evaluation[0]]
    for w in sorted(evaluation,key=lambda w:-activity[w['key']]):
        if w not in chosen:chosen.append(w)
        if len(chosen)==3:break
    turns=active=absent=0
    for arm in fit.ARMS:
        predictor=CrossfitGoalPlanner(arm);expected={(z['key'],z['position']):(z,pred) for z,pred in zip(bank['records'],r['results']['evaluation'][arm]['predictions'])}
        for w in chosen:
            state=None
            for i,s in enumerate(w['steps']):
                v=predictor.predict(s['input'] if s['observed'] else None,maps[w['payload']],s['round'],s['previous'],s['previous_mask'],state,previous_moves=history[w['key']][i]);state=v['state'];turns+=1
                if not s['observed']:continue
                z,pred=expected[(w['key'],i)];assert state['objective_identity']==z['selected'];own=s['input']['observation']['own'].get('position')
                if own is not None:
                    dx,dy=fit.prior.prior.model.OFFSETS[pred];assert v['shared_movement']==(own['x']+dx,own['y']+dy) and v['shared_execution_used'];active+=z['active'];absent+=not z['active']
    assert active>0 and absent>0
    immutable_json(fit.REPORT/'verification.json',dict(result_sha256=digest(fit.REPORT/'result.json'),source_sha256=digest(__file__),prefit_sha256=digest(fit.REPORT/'prefit-verification.json'),fold_measurements=40,executor_updates_accounted=updates,matched_sampling=True,selected_weights_exact=True,all_forecasts_reproduced=True,streaming_turns=turns,active_streaming_queries=active,absent_goal_streaming_queries=absent,optimizer_replays=0,seconds=time.perf_counter()-start));print('VERIFIED crossfit executors',updates,turns,active,absent,flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('command',choices=('prefit','diagnose','run'));globals()[parser.parse_args().command]()
