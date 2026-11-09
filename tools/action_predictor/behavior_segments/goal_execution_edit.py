"""Bounded weight calibration for short-goal to distant-objective transfer."""
import argparse,time
from pathlib import Path
import numpy as np
import torch
from torch.nn import functional as F
from . import goal_execution_fit as prior
from .goal_execution import local_features,goal_geometry
from ..audit import immutable_json
from ..data import digest

ROOT=prior.ROOT;REPORT=ROOT/'tools/action_predictor/experiments/v67';WORK=ROOT/'.cambc/action-predictor/v67'
read,check,bindings=prior.read,prior.check,prior.bindings


def edit(weights,distance_scale=1.,zero_radius=False,output_scale=1.):
    result={k:v.clone() for k,v in weights.items()}
    result['layers.0.weight'][:,128:133]*=distance_scale
    if zero_radius:result['layers.0.weight'][:,134]=0
    result['layers.2.weight']*=output_scale;result['layers.2.bias']*=output_scale
    return result


def inspect():
    REPORT.mkdir(parents=True,exist_ok=True);prior.inputs();check(read(prior.REPORT/'verification.json'))
    bank=torch.load(prior.WORK/'full.pt',weights_only=True);weights=torch.load(prior.WORK/'goal-selected.pt',weights_only=True);x=torch.cat((local_features(bank['context']),bank['goal']),-1).reshape(-1,136)
    windows,maps=prior.base.heading.original.load();wanted={(r['key'],r['position']):r for r in read(prior.WORK/'causal.json') if r['split']=='fit' and r['active']};values=[]
    for w in windows:
        if w['partition']!='fit':continue
        for i,s in enumerate(w['steps']):
            r=wanted.get((w['key'],i))
            if r is None:continue
            c=next(q for q in prior.candidates(s['input'],maps[w['payload']]) if q['key']==r['selected']);values.append(goal_geometry(s['input'],maps[w['payload']],c['goal'],c['radius']))
    current=torch.stack(values).reshape(-1,8);training=x[:,128:];lo=training.min(0).values;hi=training.max(0).values
    immutable_json(REPORT/'inspection.json',dict(bindings=bindings([prior.WORK/'full.pt',prior.WORK/'goal-selected.pt',prior.WORK/'causal.json']),
        zero_training_columns=(x.abs().max(0).values==0).nonzero().flatten().tolist(),training_goal_min=lo.tolist(),training_goal_max=hi.tolist(),predicted_fitting_goal_min=current.min(0).values.tolist(),predicted_fitting_goal_max=current.max(0).values.tolist(),outside_training_range=((current<lo)|(current>hi)).float().mean(0).tolist(),predicted_fitting_goals=len(values),
        goal_column_weight_norms=weights['layers.0.weight'][:,128:].norm(dim=0).tolist(),
        interpretation='Achieved goals were within8tiles; predicted fitting goals can be about90tiles away. Radius was alwayszero while its weights remain nonzero; they received no training signal beyond weight decay. These facts motivate calibration but do not prove this mismatch caused the errors. Statistics include all9candidate slots,including unsupported ones. Evaluation rows were not inspected for calibration design.'))


def freeze():
    prior.inputs();check(read(REPORT/'inspection.json'));immutable_json(REPORT/'plan.json',dict(sources=bindings([Path(__file__),Path(__file__).with_name('goal_execution_edit_predictor.py'),Path(__file__).with_name('test_goal_execution_edit.py')]),
        inputs=bindings([prior.REPORT/n for n in ('plan.json','cache.json','fit.json','selection.json','result.json','verification.json')]+[REPORT/'inspection.json']),distance_scales=[.1,.25,.5,1.],zero_radius=[False,True],output_scales=[.5,.75,1.],diagnostic_allowance=.02,causal_nll_allowance=.01,
        intervention='24 direct edits of corresponding V66 goal head weights. Scale first-layer columns128:133 (five absolute/relative distance inputs),optionally zero untrained radius column134,scale final output weight+bias. Leave route-progress column133,availability135,other inputs,V59,V62 goal choices,support and inference unchanged. No optimizer updates or new parameters.',
        selection='Four fitting-game folds. Maximize combined movement count with predicted V62 goals on all original held movement queries. Require supplied-goal diagnostic accuracy no more than2points below original V66 head and predicted-goal NLL no more than0.01 above original head. Tie least squared weight-change norm summed across folds,then deterministic grid order. The unedited head is eligible. Disabled correction is a diagnostic control only,not eligible.',
        success='Selected head must beat V66 original316 and direct318 on unchanged513 evaluation movement queries,with NLL<=direct+0.01 and hindsight diagnostic accuracy loss<=2points. All are required;80percent still411/513. No evaluation-dependent calibration or promotion.',
        limits='Calibration targets observed fitting input shift,not proof of its unique causal role. Uniform distance scaling also changes near-goal responses; zeroing radius does not remove region-distance differences. Hindsight diagnostic remains privileged,teacher-forced/reused research games and one seed remain. No subagents.'))


def inputs():
    p=read(REPORT/'plan.json');check(p);_,parent,architecture,cache,ids=prior.inputs();return p,parent,architecture,cache,ids


def weights(name):
    epoch=read(prior.REPORT/'selection.json')['selected']['goal']['epoch'];path=prior.WORK/'goal-selected.pt' if name=='full' else prior.WORK/'goal'/name/f'epoch-{epoch:03d}.pt';return torch.load(path,weights_only=True)


@torch.no_grad()
def build(windows,maps,name,parent,architecture):
    encoded,_,bound=prior.base.prior.encoded(windows,maps,architecture);policy=prior.base.inference(prior.waypoint.selected(name,parent,architecture));head=prior.planner.old.new(read(prior.planner.old.REPORT/'plan.json'))
    e=read(prior.planner.old.REPORT/'selection.json')['selected']['epoch'];path=prior.planner.old.WORK/'selected.pt' if name=='full' else prior.planner.old.WORK/name/f'epoch-{e:03d}.pt';s=read(prior.planner.REPORT/'selection.json')['selected'];head.load_state_dict(prior.planner.edit(torch.load(path,weights_only=True),s['scale'],s['shift']))
    records=[];context=[];goals=[];raw=[];supports=[]
    for w in windows:
        states=[];hook=policy.parent.parent.backbone.code.register_forward_pre_hook(lambda module,args:states.append(args[0]))
        try:out=policy(**encoded[w['key']])
        finally:hook.remove()
        args=encoded[w['key']];x=prior.waypoint.features(states[0],out['code'].softmax(-1),args['geometry'],args['heading'],args['command_heading']);support,labels=prior.model.move_support(w);remembered=None
        for i,step in enumerate(w['steps']):
            if not step['observed']:continue
            cs=prior.candidates(step['input'],maps[w['payload']]);scores=head(torch.stack([torch.cat((x[i,:56],torch.tensor(c['features']))) for c in cs])).tolist() if cs else []
            chosen,remembered,_=prior.choose(cs,scores,remembered,.15);g=goal_geometry(step['input'],maps[w['payload']],chosen['goal'],chosen['radius']) if chosen is not None else torch.zeros(9,8);assert g is not None
            records.append(dict(key=w['key'],position=i,group=w['group'],split=w['partition'],label=int(labels[i]),selected=remembered,active=chosen is not None));context.append(x[i]);raw.append(out['move'][i]);supports.append(support[i]);goals.append(g)
    return dict(records=records,context=torch.stack(context),goal=torch.stack(goals),baseline=torch.stack(raw),support=torch.stack(supports),weights=weights(name),source_bindings=bound)


def prepare():
    _,parent,architecture,_,ids=inputs();torch.set_num_threads(4);WORK.mkdir(parents=True,exist_ok=False);windows,maps=prior.base.heading.expanded.read()
    for fold in range(4):
        ws=[w for i,w in enumerate(windows) if ids[i]['canonical'] and ids[i]['fold']==fold];torch.save(build(ws,maps,f'fold{fold}',parent,architecture),WORK/f'fold{fold}.pt');print('Prepared weight calibration',fold,flush=True)
    immutable_json(REPORT/'cache.json',dict(bindings=bindings(list(WORK.iterdir())),evaluation_used=False))


@torch.no_grad()
def score(bank,edited):
    net=prior.new('goal',read(prior.REPORT/'plan.json'));net.load_state_dict(edited);active=torch.tensor([r['active'] for r in bank['records']]);labels=torch.tensor([r['label'] for r in bank['records']]);predictions=[];losses=[];mask=labels>=0
    for start in range(0,len(labels),256):
        sl=slice(start,start+256);raw=net(bank['context'][sl],bank['goal'][sl],bank['baseline'][sl]);raw=torch.where(active[sl,None],raw,bank['baseline'][sl]);lp=raw.masked_fill(~bank['support'][sl],-1e9).log_softmax(-1);y=labels[sl];predictions.extend(lp.argmax(-1).tolist());losses.extend((-lp.gather(1,y.clamp_min(0)[:,None]).squeeze(1)).tolist())
    correct=sum(p==r['label'] for p,r in zip(predictions,bank['records']) if r['label']>=0);nll=sum(v for v,r in zip(losses,bank['records']) if r['label']>=0)
    return dict(rows=int(mask.sum()),correct=correct,nll_sum=nll,active_queries=int(active.sum()),predictions=predictions,losses=losses)


def settings(p):return [dict(distance_scale=d,zero_radius=z,output_scale=o) for d in p['distance_scales'] for z in p['zero_radius'] for o in p['output_scales']]


def choose(cs,p):
    original=next(c for c in cs if c['setting']==dict(distance_scale=1.,zero_radius=False,output_scale=1.));eligible=[c for c in cs if c['diagnostic_correct']>=original['diagnostic_correct']-p['diagnostic_allowance']*c['diagnostic_rows'] and c['nll_sum']/c['rows']<=original['nll_sum']/original['rows']+p['causal_nll_allowance']]
    return min(eligible,key=lambda c:(-c['correct'],c['edit_squared_norm'],cs.index(c)))


def select():
    p,_,_,_,_=inputs();check(read(REPORT/'cache.json'));torch.set_num_threads(1);rs=read(prior.WORK/'rows.json');cs=[]
    banks=[torch.load(WORK/f'fold{k}.pt',weights_only=False) for k in range(4)];diags=[torch.load(prior.WORK/f'fold{k}.pt',weights_only=True) for k in range(4)]
    for setting in settings(p):
        values=[];diagnostics=[];squared=0.
        for fold,bank in enumerate(banks):
            changed=edit(bank['weights'],**setting);values.append(score(bank,changed));net=prior.new('goal',read(prior.REPORT/'plan.json'));net.load_state_dict(changed);ix=np.array([i for i,r in enumerate(rs) if r['fold']==fold and r['canonical']]);diagnostics.append(prior.score(net,diags[fold],rs,ix));squared+=sum(float((changed[k]-v).square().sum()) for k,v in bank['weights'].items())
        cs.append(dict(setting=setting,rows=sum(v['rows'] for v in values),correct=sum(v['correct'] for v in values),nll_sum=sum(v['nll_sum'] for v in values),diagnostic_rows=sum(v['rows'] for v in diagnostics),diagnostic_correct=sum(v['correct'] for v in diagnostics),edit_squared_norm=squared))
    selected=choose(cs,p);torch.save(edit(weights('full'),**selected['setting']),WORK/'selected.pt');immutable_json(REPORT/'selection.json',dict(selected=selected,candidates=cs,evaluation_used=False,optimizer_updates=0,bindings=bindings([WORK/'selected.pt'])));print('SELECTED',selected,flush=True)


def results(bank,edited):
    value=score(bank,edited);original=score(bank,bank['weights']);disabled=score(bank,edit(bank['weights'],output_scale=0.));return dict(edited=value,original=original,direct=disabled)


@torch.no_grad()
def assess():
    _,parent,architecture,_,_=inputs();check(read(REPORT/'selection.json'));torch.set_num_threads(4);windows,maps=prior.base.heading.original.load();selected=torch.load(WORK/'selected.pt',weights_only=True);values={}
    for split in ('fit','evaluation'):
        bank=build([w for w in windows if w['partition']==split],maps,'full',parent,architecture);torch.save(bank,WORK/(split+'.pt'));values[split]=results(bank,selected)
    diag=torch.load(prior.WORK/'assessment-bank.pt',weights_only=True);rows=read(prior.WORK/'assessment-rows.json');net=prior.new('goal',read(prior.REPORT/'plan.json'));net.load_state_dict(selected);ix=np.array([i for i,r in enumerate(rows) if r['split']=='evaluation']);diagnostic=prior.score(net,diag,rows,ix)
    old=read(prior.REPORT/'result.json')['diagnostic']['evaluation']['goal'];x=values['evaluation'];gates=dict(original=x['edited']['correct']>x['original']['correct'],direct=x['edited']['correct']>x['direct']['correct'],nll=x['edited']['nll_sum']<=x['direct']['nll_sum']+.01*x['edited']['rows'],diagnostic=diagnostic['correct']>=old['correct']-.02*old['rows'])
    immutable_json(REPORT/'result.json',dict(results=values,diagnostic=diagnostic,checks=gates,all_checks_pass=all(gates.values()),target_met=x['edited']['rows']==513 and x['edited']['correct']>=411,bindings=bindings([WORK/'selected.pt',WORK/'fit.pt',WORK/'evaluation.pt']),promoted=False));print('RESULT',gates,{k:(v['correct'],v['rows'],v['nll_sum']/v['rows']) for k,v in x.items()},flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('command',choices=('inspect','freeze','prepare','select','assess'));globals()[p.parse_args().command]()
