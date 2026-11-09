"""Parent verification of supplied-goal diagnostics and causal runtime behavior."""
import argparse,time
import numpy as np
import torch
from . import goal_execution_fit as fit
from .planner_weight_verify import equal
from .goal_execution_predictor import GoalExecutionPlanner
from ..audit import immutable_json
from ..data import digest


def prefit():
    start=time.perf_counter();p,parent,architecture,cache,ids=fit.inputs();fit.check(fit.read(fit.REPORT/'cache.json'));torch.set_num_threads(1)
    windows,maps=fit.base.heading.expanded.read();history,_=fit.waypoint.audit.prior_moves(windows);rows,goals=fit.records(windows,maps,history,ids,p['horizons']);assert rows==fit.read(fit.WORK/'rows.json')
    assert all(r['split']=='fit' and r['position']+r['horizon']<32 for r in rows)
    for name in ['fold0','fold1','fold2','fold3','full']:
        actual=fit.feature_bank(name,parent,architecture,cache,rows,goals,windows,maps);saved=torch.load(fit.WORK/(name+'.pt'),weights_only=True);assert equal(actual,saved)
        a=fit.new('control',p);b=fit.new('goal',p);assert equal(a.state_dict(),b.state_dict())
        out=b(saved['context'][:128],saved['goal'][:128],saved['baseline'][:128]);assert torch.equal(out,saved['baseline'][:128])
        value=torch.nn.functional.cross_entropy(out.masked_fill(~saved['support'][:128],-1e9),saved['labels'][:128]);value.backward()
        assert all(v.grad is None or torch.isfinite(v.grad).all() for v in b.parameters());assert b.layers[-1].weight.grad.abs().sum()>0
        assert all(not x.requires_grad for x in saved.values());print('Verified executor input bank',name,flush=True)
    immutable_json(fit.REPORT/'prefit-verification.json',dict(plan_sha256=digest(fit.REPORT/'plan.json'),cache_sha256=digest(fit.REPORT/'cache.json'),source_sha256=digest(__file__),exact_banks=5,labels_reconstructed=len(rows),groups=len({r['group'] for r in rows}),identical_initialization=True,initial_baseline_exact=True,finite_backward=True,optimizer_updates=0,seconds=time.perf_counter()-start))


def audit_run(directory,arm,bank,rows,indices,p,epochs,held=None):
    net=fit.new(arm,p);initial=torch.load(directory/'epoch-000.pt',weights_only=True);assert equal(initial,net.state_dict());trace=fit.read(directory/'trace.json');rng=np.random.default_rng(p['seed']);updates=0;values={}
    assert len(trace['epochs'])==epochs
    for e in trace['epochs']:
        assert e['order']==rng.permutation(indices).tolist();assert len(e['norms'])==(len(indices)+p['batch']-1)//p['batch'] and np.isfinite(e['norms']).all();updates+=len(e['norms'])
    final=torch.load(directory/'final.pt',weights_only=False);assert final['rng']==rng.bit_generator.state
    for state in final['optimizer']['state'].values():
        assert int(state['step'])==updates and all(not torch.is_tensor(v) or torch.isfinite(v).all() for v in state.values())
    assert all(torch.isfinite(v).all() for v in final['model'].values())
    if epochs:assert not equal(initial,final['model'])
    if held is not None:
        for epoch in range(0,epochs+1,p['every']):
            net.load_state_dict(torch.load(directory/f'epoch-{epoch:03d}.pt',weights_only=True));values[epoch]=fit.score(net,bank,rows,held);assert equal(values[epoch],trace['validation'][str(epoch)])
    return values,updates,final


def run():
    start=time.perf_counter();p,parent,architecture,_,_=fit.inputs();torch.set_num_threads(1)
    for name in ('cache','fit','result'):fit.check(fit.read(fit.REPORT/(name+'.json')))
    proof=fit.read(fit.REPORT/'prefit-verification.json');assert proof['plan_sha256']==digest(fit.REPORT/'plan.json') and proof['cache_sha256']==digest(fit.REPORT/'cache.json')
    rows=fit.read(fit.WORK/'rows.json');selection=fit.read(fit.REPORT/'selection.json');updates=0;nets={}
    for arm in fit.ARMS:
        values={}
        for fold in range(4):
            bank=torch.load(fit.WORK/f'fold{fold}.pt',weights_only=True);training=np.array([i for i,r in enumerate(rows) if r['fold']!=fold]);held=np.array([i for i,r in enumerate(rows) if r['fold']==fold and r['canonical']])
            v,u,_=audit_run(fit.WORK/arm/f'fold{fold}',arm,bank,rows,training,p,p['epochs'],held);updates+=u
            for epoch,s in v.items():values.setdefault(epoch,[]).append(s)
            other=fit.read(fit.WORK/'control'/f'fold{fold}'/'trace.json');this=fit.read(fit.WORK/arm/f'fold{fold}'/'trace.json');assert [e['order'] for e in other['epochs']]==[e['order'] for e in this['epochs']]
        cs=[dict(epoch=e,**{k:sum(v[k] for v in vs) for k in ('rows','correct','nll_sum')}) for e,vs in values.items()];assert cs==selection['candidates'][arm] and fit.select(cs)==selection['selected'][arm]
        bank=torch.load(fit.WORK/'full.pt',weights_only=True);_,u,final=audit_run(fit.WORK/arm/'refit',arm,bank,rows,np.arange(len(rows)),p,selection['selected'][arm]['epoch']);updates+=u
        selected=torch.load(fit.WORK/(arm+'-selected.pt'),weights_only=True);assert equal(selected,final['model']);nets[arm]=fit.new(arm,p);nets[arm].load_state_dict(selected);print('Verified executor training',arm,flush=True)
    torch.set_num_threads(4);bank=torch.load(fit.WORK/'assessment-bank.pt',weights_only=True);rows=fit.read(fit.WORK/'assessment-rows.json');causal=fit.read(fit.WORK/'causal.json');result=fit.read(fit.REPORT/'result.json');summary=fit.summaries(nets,bank,rows,causal)
    assert all(equal(v,result[k]) for k,v in summary.items())
    for split in ('fit','evaluation'):
        old_bank=torch.load(fit.planner.WORK/(split+'.pt'),weights_only=False);old=fit.read(fit.planner.REPORT/'result.json')['results'][split]['edited'];actual=[r for r in causal if r['split']==split]
        assert [(r['key'],r['position']) for r in actual]==[(r['key'],r['position']) for r in old_bank['records']]
        assert [r['selected'] for r in actual]==old['selected'] and [r['routed'] for r in actual]==old['predictions']
        assert [r['direct'] for r in actual]==[r['baseline'] for r in old_bank['records']]
    windows,maps=fit.base.heading.original.load();encoded,history,_=fit.base.prior.encoded(windows,maps,architecture)
    reconstructed,goals=fit.records(windows,maps,history,[dict(fold=-1,canonical=True) for w in windows],p['horizons']);mapping={(r['key'],r['position'],r['horizon']):(r,g) for r,g in zip(reconstructed,goals)}
    for i,r in enumerate(rows):
        original,g=mapping[(r['key'],r['position'],r['horizon'])];assert r==original and torch.equal(g,bank['goal'][i])
    # Rebuild every assessment feature and logit from the frozen policy, not from saved predictions.
    policy=fit.base.policy(fit.read(fit.base.REPORT/'plan.json'),parent,architecture);bykey={}
    with torch.no_grad():
        for w in windows:
            states=[];hook=policy.parent.parent.backbone.code.register_forward_pre_hook(lambda module,args:states.append(args[0]))
            try:out=policy(**encoded[w['key']])
            finally:hook.remove()
            args=encoded[w['key']];x=fit.waypoint.features(states[0],out['code'].softmax(-1),args['geometry'],args['heading'],args['command_heading']);support,_=fit.model.move_support(w);bykey[w['key']]=(x,out['move'],support)
        for i,r in enumerate(rows):
            x,raw,support=bykey[r['key']];j=r['position'];assert torch.equal(x[j],bank['context'][i]) and torch.equal(raw[j],bank['baseline'][i]) and torch.equal(support[j],bank['support'][i])
    # Verify every causal execution forecast independently from saved feature-free records.
    from .objective_policy import candidates,choose
    objective=fit.planner.old.new(fit.read(fit.planner.old.REPORT/'plan.json'));objective.load_state_dict(torch.load(fit.planner.WORK/'selected.pt',weights_only=True));expected={(r['key'],r['position']):r for r in causal}
    with torch.no_grad():
        for w in windows:
            x,raw,support=bykey[w['key']];remembered=None
            for i,s in enumerate(w['steps']):
                if not s['observed']:continue
                r=expected[(w['key'],i)];cs=candidates(s['input'],maps[w['payload']]);scores=objective(torch.stack([torch.cat((x[i,:56],torch.tensor(c['features']))) for c in cs])).tolist() if cs else []
                selected,remembered,_=choose(cs,scores,remembered,.15);assert remembered==r['selected']
                for arm in fit.ARMS:
                    logits=raw[i] if selected is None else nets[arm](x[i],fit.goal_geometry(s['input'],maps[w['payload']],selected['goal'],selected['radius']),raw[i]);lp=logits.masked_fill(~support[i],-1e9).log_softmax(-1)
                    assert int(lp.argmax())==r['predictions'][arm]
                    if r['label']>=0:assert float(-lp[r['label']])==r['nll'][arm]
    evaluation=[w for w in windows if w['partition']=='evaluation'];activity={w['key']:sum(r['active'] for r in causal if r['key']==w['key']) for w in evaluation};chosen=[evaluation[0]]
    for w in sorted(evaluation,key=lambda w:-activity[w['key']]):
        if w not in chosen:chosen.append(w)
        if len(chosen)==3:break
    turns=active=0
    for arm in fit.ARMS:
        predictor=GoalExecutionPlanner(arm)
        for w in chosen:
            state=None
            for i,s in enumerate(w['steps']):
                value=predictor.predict(s['input'] if s['observed'] else None,maps[w['payload']],s['round'],s['previous'],s['previous_mask'],state,previous_moves=history[w['key']][i]);state=value['state'];turns+=1
                if not s['observed']:continue
                r=expected[(w['key'],i)];assert state['objective_identity']==r['selected'];active+=r['active'];own=s['input']['observation']['own'].get('position')
                if own is not None:
                    for field,index in (('objective_movement',r['predictions'][arm]),('routed_objective_movement',r['routed']),('conditional_movement',r['direct'])):
                        dx,dy=fit.model.OFFSETS[index];assert value[field]==(own['x']+dx,own['y']+dy)
    assert active>0
    immutable_json(fit.REPORT/'verification.json',dict(result_sha256=digest(fit.REPORT/'result.json'),source_sha256=digest(__file__),fold_measurements=40,optimizer_updates_accounted=updates,matched_schedules=True,diagnostic_rows=len(rows),causal_rows=len(causal),assessment_features_exact=True,goal_choices_preserved=True,streaming_turns=turns,active_streaming_queries=active,optimizer_replays=0,seconds=time.perf_counter()-start))
    print('VERIFIED goal execution diagnostics and causal runtime',flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('command',choices=('prefit','run'));globals()[p.parse_args().command]()
