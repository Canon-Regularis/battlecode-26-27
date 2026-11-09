"""Reconstruct fallback inputs, training accounting, selection and runtime outputs."""
import time
import numpy as np
import torch
from . import universal_execution_fit as fit
from .goal_execution_verify import audit_run
from .planner_weight_verify import equal
from .universal_execution_predictor import UniversalExecutionPlanner
from ..audit import immutable_json
from ..data import digest


def run():
    start=time.perf_counter();p,parent,architecture,cache,ids=fit.inputs();torch.set_num_threads(4)
    for name in ('cache','fit','result'):fit.check(fit.read(fit.REPORT/(name+'.json')))
    rows=fit.records(fit.prior.base.dataset('full',cache),ids);assert rows==fit.read(fit.WORK/'rows.json')
    for name in ['fold0','fold1','fold2','fold3','full']:
        actual=fit.feature_bank(name,parent,architecture,cache,rows);saved=torch.load(fit.WORK/(name+'.pt'),weights_only=True);assert equal(actual,saved);print('Verified universal features',name,flush=True)
    torch.set_num_threads(1);selection=fit.read(fit.REPORT/'selection.json');validation=fit.read(fit.WORK/'fold-validation.json');values={};updates=0
    for fold in range(4):
        name=f'fold{fold}';data=torch.load(fit.WORK/(name+'.pt'),weights_only=True);training=np.array([i for i,r in enumerate(rows) if r['fold']!=fold]);_,u,_=audit_run(fit.WORK/name,'control',data,rows,training,p,p['epochs']);updates+=u
        held=torch.load(fit.calibration.WORK/(name+'.pt'),weights_only=False);goal=fit.goal_weights(name)
        held_keys={q['key'] for q in ids if q['fold']==fold and q['canonical']}
        assert all(r['key'] in held_keys for r in held['records'])
        for epoch in range(0,p['epochs']+1,p['every']):
            weights=torch.load(fit.WORK/name/f'epoch-{epoch:03d}.pt',weights_only=True);s=fit.score(held,weights,goal);assert equal(s,validation[str(epoch)][fold]);values.setdefault(epoch,[]).append(s)
            if epoch==0:
                previous=fit.calibration.score(held,goal);assert s['predictions']==previous['predictions'] and s['losses']==previous['losses']
    cs=[dict(epoch=e,**{k:sum(v[k] for v in vs) for k in ('rows','correct','nll_sum')}) for e,vs in values.items()];assert cs==selection['candidates'] and fit.select(cs)==selection['selected']
    _,u,final=audit_run(fit.WORK/'refit','control',torch.load(fit.WORK/'full.pt',weights_only=True),rows,np.arange(len(rows)),p,selection['selected']['epoch']);updates+=u
    selected=torch.load(fit.WORK/'selected.pt',weights_only=True);assert equal(selected,final['model']);assert equal(fit.goal_weights('full'),torch.load(fit.calibration.WORK/'selected.pt',weights_only=True))
    torch.set_num_threads(4);result=fit.read(fit.REPORT/'result.json');actual=fit.assessment();assert all(equal(v,result[k]) for k,v in actual.items())
    windows,maps=fit.prior.base.heading.original.load();_,history,_=fit.prior.base.prior.encoded(windows,maps,architecture);bank=torch.load(fit.calibration.WORK/'evaluation.pt',weights_only=False)
    expected={(r['key'],r['position']):(r,pred) for r,pred in zip(bank['records'],result['results']['evaluation']['predictions'])};evaluation=[w for w in windows if w['partition']=='evaluation'];activity={w['key']:sum(r['active'] for r in bank['records'] if r['key']==w['key']) for w in evaluation};chosen=[evaluation[0]]
    for w in sorted(evaluation,key=lambda w:-activity[w['key']]):
        if w not in chosen:chosen.append(w)
        if len(chosen)==3:break
    predictor=UniversalExecutionPlanner();turns=active=fallback=0
    for w in chosen:
        state=None
        for i,s in enumerate(w['steps']):
            value=predictor.predict(s['input'] if s['observed'] else None,maps[w['payload']],s['round'],s['previous'],s['previous_mask'],state,previous_moves=history[w['key']][i]);state=value['state'];turns+=1
            if not s['observed']:continue
            r,pred=expected[(w['key'],i)];assert state['objective_identity']==r['selected'];active+=r['active'];own=s['input']['observation']['own'].get('position')
            if own is not None:
                dx,dy=fit.prior.model.OFFSETS[pred];assert value['goal_conditioned_movement']==(own['x']+dx,own['y']+dy);assert value['fallback_execution_used']==(not r['active']);fallback+=value['fallback_execution_used']
    assert active>0 and fallback>0
    initial=torch.load(fit.WORK/'refit/epoch-000.pt',weights_only=True);changes={k:float((v-initial[k]).norm()) for k,v in selected.items()}
    immutable_json(fit.REPORT/'verification.json',dict(result_sha256=digest(fit.REPORT/'result.json'),source_sha256=digest(__file__),feature_banks_reconstructed=5,rows_reconstructed=len(rows),fold_measurements=20,optimizer_updates_accounted=updates,initial_hybrid_exact=True,selected_weights_exact=True,weight_change_norms=changes,all_summaries_reproduced=True,active_goal_predictions_preserved=True,streaming_turns=turns,active_streaming_queries=active,fallback_streaming_queries=fallback,optimizer_replays=0,seconds=time.perf_counter()-start));print('VERIFIED universal fallback',updates,turns,active,fallback,flush=True)


if __name__=='__main__':run()
