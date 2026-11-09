"""Verify direct weight calibration, fold selection and causal streaming parity."""
import time
import numpy as np
import torch
from . import goal_execution_edit as fit
from .planner_weight_verify import equal
from .goal_execution_edit_predictor import CalibratedGoalExecutor
from ..audit import immutable_json
from ..data import digest


def run():
    start=time.perf_counter();p,parent,architecture,_,ids=fit.inputs();torch.set_num_threads(4)
    for name in ('inspection','cache','selection','result'):fit.check(fit.read(fit.REPORT/(name+'.json')))
    fit.prior.check(fit.read(fit.prior.REPORT/'fit.json'));selection=fit.read(fit.REPORT/'selection.json');result=fit.read(fit.REPORT/'result.json');banks=[]
    windows,maps=fit.prior.base.heading.expanded.read()
    for fold in range(4):
        ws=[w for i,w in enumerate(windows) if ids[i]['canonical'] and ids[i]['fold']==fold];actual=fit.build(ws,maps,f'fold{fold}',parent,architecture);saved=torch.load(fit.WORK/f'fold{fold}.pt',weights_only=False);assert equal(actual,saved);banks.append(saved);print('Verified calibrated-executor fold',fold,flush=True)
    torch.set_num_threads(1);rs=fit.read(fit.prior.WORK/'rows.json');diags=[torch.load(fit.prior.WORK/f'fold{k}.pt',weights_only=True) for k in range(4)];cs=[]
    for setting in fit.settings(p):
        values=[];diagnostics=[];squared=0.
        for fold,bank in enumerate(banks):
            changed=fit.edit(bank['weights'],**setting);values.append(fit.score(bank,changed));net=fit.prior.new('goal',fit.read(fit.prior.REPORT/'plan.json'));net.load_state_dict(changed);ix=np.array([i for i,r in enumerate(rs) if r['fold']==fold and r['canonical']]);diagnostics.append(fit.prior.score(net,diags[fold],rs,ix));squared+=sum(float((changed[k]-v).square().sum()) for k,v in bank['weights'].items())
        cs.append(dict(setting=setting,rows=sum(v['rows'] for v in values),correct=sum(v['correct'] for v in values),nll_sum=sum(v['nll_sum'] for v in values),diagnostic_rows=sum(v['rows'] for v in diagnostics),diagnostic_correct=sum(v['correct'] for v in diagnostics),edit_squared_norm=squared))
    assert cs==selection['candidates'] and fit.choose(cs,p)==selection['selected'];selected=torch.load(fit.WORK/'selected.pt',weights_only=True);original=fit.weights('full');assert equal(selected,fit.edit(original,**selection['selected']['setting']))
    changed=[k for k,v in selected.items() if not torch.equal(v,original[k])];scalar_changes=sum(int((v!=original[k]).sum()) for k,v in selected.items())
    initial=torch.load(fit.prior.WORK/'goal/refit/epoch-000.pt',weights_only=True);trained=torch.load(fit.prior.WORK/'goal/refit/final.pt',weights_only=False);group=trained['optimizer']['param_groups'][0];steps=int(next(iter(trained['optimizer']['state'].values()))['step'])
    radius_expected=initial['layers.0.weight'][:,134]*(1-group['lr']*group['weight_decay'])**steps;radius_error=float((original['layers.0.weight'][:,134]-radius_expected).abs().max());assert radius_error<2e-6
    assert torch.load(fit.prior.WORK/'full.pt',weights_only=True)['goal'][...,6].abs().sum()==0
    torch.set_num_threads(4);windows,maps=fit.prior.base.heading.original.load();exact={};old_rows=fit.read(fit.prior.WORK/'causal.json')
    for split in ('fit','evaluation'):
        actual=fit.build([w for w in windows if w['partition']==split],maps,'full',parent,architecture);saved=torch.load(fit.WORK/(split+'.pt'),weights_only=False);assert equal(actual,saved);value=fit.results(saved,selected);assert equal(value,result['results'][split]);exact[split]=len(saved['records'])
        old=[r for r in old_rows if r['split']==split];assert [(r['key'],r['position']) for r in old]==[(r['key'],r['position']) for r in saved['records']]
        assert [r['selected'] for r in old]==[r['selected'] for r in saved['records']]
        assert value['original']['predictions']==[r['predictions']['goal'] for r in old] and value['direct']['predictions']==[r['direct'] for r in old]
        for r,pred,direct in zip(saved['records'],value['edited']['predictions'],value['direct']['predictions']):
            if not r['active']:assert pred==direct
    bank=torch.load(fit.prior.WORK/'assessment-bank.pt',weights_only=True);rows=fit.read(fit.prior.WORK/'assessment-rows.json');net=fit.prior.new('goal',fit.read(fit.prior.REPORT/'plan.json'));net.load_state_dict(selected);ix=np.array([i for i,r in enumerate(rows) if r['split']=='evaluation']);diag=fit.prior.score(net,bank,rows,ix);assert equal(diag,result['diagnostic'])
    old=fit.read(fit.prior.REPORT/'result.json')['diagnostic']['evaluation']['goal'];x=result['results']['evaluation'];gates=dict(original=x['edited']['correct']>x['original']['correct'],direct=x['edited']['correct']>x['direct']['correct'],nll=x['edited']['nll_sum']<=x['direct']['nll_sum']+.01*x['edited']['rows'],diagnostic=diag['correct']>=old['correct']-.02*old['rows']);assert gates==result['checks'] and all(gates.values())==result['all_checks_pass'];assert result['target_met']==(x['edited']['rows']==513 and x['edited']['correct']>=411)
    _,history,_=fit.prior.base.prior.encoded(windows,maps,architecture);bank=torch.load(fit.WORK/'evaluation.pt',weights_only=False);expected={(r['key'],r['position']):(r,pred) for r,pred in zip(bank['records'],x['edited']['predictions'])};evaluation=[w for w in windows if w['partition']=='evaluation'];activity={w['key']:sum(r['active'] for r in bank['records'] if r['key']==w['key']) for w in evaluation};chosen=[evaluation[0]]
    for w in sorted(evaluation,key=lambda w:-activity[w['key']]):
        if w not in chosen:chosen.append(w)
        if len(chosen)==3:break
    predictor=CalibratedGoalExecutor();turns=active=0
    for w in chosen:
        state=None
        for i,s in enumerate(w['steps']):
            value=predictor.predict(s['input'] if s['observed'] else None,maps[w['payload']],s['round'],s['previous'],s['previous_mask'],state,previous_moves=history[w['key']][i]);state=value['state'];turns+=1
            if not s['observed']:continue
            r,pred=expected[(w['key'],i)];assert state['objective_identity']==r['selected'];active+=r['active'];own=s['input']['observation']['own'].get('position')
            if own is not None:
                dx,dy=fit.prior.model.OFFSETS[pred];assert value['goal_conditioned_movement']==(own['x']+dx,own['y']+dy)
    assert active>0
    immutable_json(fit.REPORT/'verification.json',dict(result_sha256=digest(fit.REPORT/'result.json'),source_sha256=digest(__file__),exact_fold_caches=4,settings_reproduced=len(cs),selected_weights_exact=True,changed_tensors=changed,changed_scalars=scalar_changes,radius_decay_max_error=radius_error,original_forecasts_preserved=True,exact_forecasts=exact,streaming_turns=turns,active_streaming_queries=active,optimizer_updates=0,seconds=time.perf_counter()-start));print('VERIFIED executor weight calibration',changed,scalar_changes,flush=True)


if __name__=='__main__':run()
