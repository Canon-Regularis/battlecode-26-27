import argparse,time
import numpy as np
import torch
from . import bounded_goal_execution_fit as fit
from .goal_execution_verify import audit_run
from .planner_weight_verify import equal
from .bounded_goal_execution_predictor import BoundedGoalPlanner
from ..audit import immutable_json
from ..data import digest


def prefit():
    p=fit.inputs();torch.set_num_threads(1);fit.check(fit.read(fit.prior.REPORT/'result.json'));rows=fit.read(fit.prior.WORK/'rows.json');ranges={}
    for name in ['fold0','fold1','fold2','fold3','full']:
        data=fit.bank(name);assert torch.isfinite(data['goal']).all() and data['goal'].abs().max()<=1
        net=fit.prior.new('goal',p);path=fit.prior.WORK/'goal'/('refit' if name=='full' else name)/'epoch-000.pt';assert equal(net.state_dict(),torch.load(path,weights_only=True))
        pred=net(data['context'][:128],data['goal'][:128],data['baseline'][:128]);assert torch.equal(pred,data['baseline'][:128]);loss=torch.nn.functional.cross_entropy(pred.masked_fill(~data['support'][:128],-1e9),data['labels'][:128]);loss.backward();assert all(x.grad is None or torch.isfinite(x.grad).all() for x in net.parameters())
        ranges[name]=dict(minimum=data['goal'].reshape(-1,8).min(0).values.tolist(),maximum=data['goal'].reshape(-1,8).max(0).values.tolist())
    predicted=fit.causal_bank('fit')['goal'];assert predicted.abs().max()<=1 and torch.isfinite(predicted).all()
    immutable_json(fit.REPORT/'prefit-verification.json',dict(plan_sha256=digest(fit.REPORT/'plan.json'),source_sha256=digest(__file__),matched_initializations=5,rows=len(rows),ranges=ranges,predicted_fitting_goals_bounded=True,zero_residual_exact=True,finite_backward=True,optimizer_updates=0));print('Verified bounded executor prefit',len(rows),flush=True)


def run():
    start=time.perf_counter();p=fit.inputs();torch.set_num_threads(1);proof=fit.read(fit.REPORT/'prefit-verification.json');assert proof['plan_sha256']==digest(fit.REPORT/'plan.json')
    fit.check(fit.read(fit.REPORT/'fit.json'));fit.check(fit.read(fit.REPORT/'result.json'));rows=fit.read(fit.prior.WORK/'rows.json');selection=fit.read(fit.REPORT/'selection.json');values={};updates=0
    for fold in range(4):
        data=fit.bank(f'fold{fold}');training=np.array([i for i,r in enumerate(rows) if r['fold']!=fold]);held=np.array([i for i,r in enumerate(rows) if r['fold']==fold and r['canonical']]);v,u,_=audit_run(fit.WORK/f'fold{fold}','goal',data,rows,training,p,p['epochs'],held);updates+=u
        original=fit.read(fit.prior.WORK/'goal'/f'fold{fold}'/'trace.json');current=fit.read(fit.WORK/f'fold{fold}'/'trace.json');assert [e['order'] for e in original['epochs']]==[e['order'] for e in current['epochs']]
        assert equal(torch.load(fit.WORK/f'fold{fold}'/'epoch-000.pt',weights_only=True),torch.load(fit.prior.WORK/'goal'/f'fold{fold}'/'epoch-000.pt',weights_only=True))
        for e,s in v.items():values.setdefault(e,[]).append(s)
    cs=[dict(epoch=e,**{k:sum(v[k] for v in vs) for k in ('rows','correct','nll_sum')}) for e,vs in values.items()];assert cs==selection['candidates'] and fit.prior.select(cs)==selection['selected']
    _,u,final=audit_run(fit.WORK/'refit','goal',fit.bank('full'),rows,np.arange(len(rows)),p,selection['selected']['epoch']);updates+=u;selected=torch.load(fit.WORK/'selected.pt',weights_only=True);assert equal(selected,final['model'])
    torch.set_num_threads(4);result=fit.read(fit.REPORT/'result.json');reproduced=fit.assessment();assert all(equal(v,result[k]) for k,v in reproduced.items())
    _,parent,architecture,_,_=fit.prior.inputs();windows,maps=fit.prior.base.heading.original.load();_,history,_=fit.prior.base.prior.encoded(windows,maps,architecture);bank=fit.causal_bank('evaluation');x=result['causal']['evaluation'];expected={(r['key'],r['position']):(r,pred) for r,pred in zip(bank['records'],x['predictions'])}
    for split in ('fit','evaluation'):
        bank=fit.causal_bank(split);direct=fit.read(fit.calibration.REPORT/'result.json')['results'][split]['direct']['predictions']
        for r,pred,old in zip(bank['records'],result['causal'][split]['predictions'],direct):
            if not r['active']:assert pred==old
    bank=fit.causal_bank('evaluation');evaluation=[w for w in windows if w['partition']=='evaluation'];activity={w['key']:sum(r['active'] for r in bank['records'] if r['key']==w['key']) for w in evaluation};chosen=[evaluation[0]]
    for w in sorted(evaluation,key=lambda w:-activity[w['key']]):
        if w not in chosen:chosen.append(w)
        if len(chosen)==3:break
    predictor=BoundedGoalPlanner();turns=active=0
    for w in chosen:
        state=None
        for i,s in enumerate(w['steps']):
            value=predictor.predict(s['input'] if s['observed'] else None,maps[w['payload']],s['round'],s['previous'],s['previous_mask'],state,previous_moves=history[w['key']][i]);state=value['state'];turns+=1
            if not s['observed']:continue
            r,pred=expected[(w['key'],i)];assert state['objective_identity']==r['selected'];active+=r['active'];own=s['input']['observation']['own'].get('position')
            if own is not None:
                dx,dy=fit.prior.model.OFFSETS[pred];assert value['goal_conditioned_movement']==(own['x']+dx,own['y']+dy)
    assert active>0
    immutable_json(fit.REPORT/'verification.json',dict(result_sha256=digest(fit.REPORT/'result.json'),source_sha256=digest(__file__),fold_measurements=20,optimizer_updates_accounted=updates,matched_original_schedules=True,selected_weights_exact=True,all_summaries_reproduced=True,causal_goals_unchanged=True,streaming_turns=turns,active_streaming_queries=active,optimizer_replays=0,seconds=time.perf_counter()-start));print('VERIFIED bounded goal execution',flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('command',choices=('prefit','run'));globals()[p.parse_args().command]()
