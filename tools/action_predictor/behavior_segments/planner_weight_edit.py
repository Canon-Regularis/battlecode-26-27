"""Bounded edits to the existing objective readout, selected on fitting folds."""
import argparse,time,copy
from pathlib import Path
import torch
from torch.nn import functional as F
from . import objective_experiment as old,strategic_waypoint_fit as prior
from .objective_policy import candidates,choose,movement
from . import model
from ..audit import immutable_json
from ..data import digest

ROOT=old.ROOT;REPORT=ROOT/'tools/action_predictor/experiments/v62';WORK=ROOT/'.cambc/action-predictor/v62'
read,check,bindings=old.read,old.check,old.bindings


def edit(weights,scale,shift):
    result={k:v.clone() for k,v in weights.items()}
    result['net.2.weight']=result['net.2.weight']*scale
    result['net.2.bias']=result['net.2.bias']*scale+shift
    return result


def freeze():
    REPORT.mkdir(parents=True,exist_ok=True);old.inputs();check(read(old.REPORT/'verification.json'))
    weights=torch.load(old.WORK/'selected.pt',weights_only=True);saved=read(old.WORK/'predictions.json')['records']
    scores=torch.tensor([v for r in saved if r['split']=='fit' for v in r['scores']]);mx=torch.tensor([max(r['scores']) for r in saved if r['split']=='fit' and r['scores']])
    immutable_json(REPORT/'inspection.json',dict(weights={k:dict(shape=list(v.shape),norm=float(v.norm()),minimum=float(v.min()),maximum=float(v.max())) for k,v in weights.items()},
        fitting_candidate_quantiles=torch.quantile(scores,torch.tensor([0.,.1,.5,.9,1.])).tolist(),fitting_maximum_quantiles=torch.quantile(mx,torch.tensor([0.,.1,.5,.9,1.])).tolist(),positive_scores=int((scores>0).sum()),scores=len(scores),
        interpretation='Readout has positive bias and many positive fitting scores. This motivates testing calibration,not a causal diagnosis or evidence weights are defective.'))
    immutable_json(REPORT/'plan.json',dict(sources=bindings([Path(__file__),Path(__file__).with_name('planner_weight_predictor.py'),Path(__file__).with_name('test_planner_weight_edit.py')]),
        inputs=bindings([old.REPORT/n for n in ('plan.json','fit.json','result.json','verification.json')]),scales=[.5,1.,2.],shifts=[-1.,-.75,-.5,-.25,0.,.25],minimum_activation=.10,
        selection='Four matched fitting-fold V59/V61 checkpoints; original canonical held windows only. Select maximum movement correctness subject to at least10percent of candidate-available observed queries retaining/selecting a goal and nonnegative mean selected recorded utility. Tie lower combined squared coefficient edit norm,then scale,shift. Original identity eligible only under same guards. If none eligible stop. No evaluation-dependent weight selection.',
        intervention='Multiply existing final Linear weight and bias by scale,then add shift to existing bias. Tanh and all goal candidates, routing, .15 retention margin, recurrent/code/movement weights remain unchanged. No optimizer updates. Zero weights/bias=-1 is a separately reported disabled-planner control,not eligible for selection.',
        success='Must improve over original combined planner,exceed V59 movement correctness,keep selected utility positive,and remain at least10percent active on evaluation. All required for improvement beyond direct predictor. Preserved original model; no promotion.',
        limits='Repeatedly exposed research groups,original fold exposure,teacher-forced history,conditional moves,utility proxy. Score scale also changes effective .15 retention behavior; not isolated calibration or learned strategy.'))


def inputs():
    p=read(REPORT/'plan.json');check(p);_,parent,architecture,cache,ids=old.inputs();return p,parent,architecture,cache,ids


@torch.no_grad()
def build(windows,maps,name,parent,architecture,utility_rows):
    net=prior.selected(name,parent,architecture);policy=old.base.inference(net)
    p=read(old.REPORT/'plan.json');head=old.new(p);epoch=read(old.REPORT/'selection.json')['selected']['epoch']
    path=old.WORK/'selected.pt' if name=='full' else old.WORK/name/f'epoch-{epoch:03d}.pt';weights=torch.load(path,weights_only=True);head.load_state_dict(weights)
    encoded,_,bound=old.base.prior.encoded(windows,maps,architecture);records=[]
    for w in windows:
        states=[];hook=policy.parent.parent.backbone.code.register_forward_pre_hook(lambda module,args:states.append(args[0]))
        try:out=policy(**encoded[w['key']])
        finally:hook.remove()
        contexts=torch.cat((states[0],out['code'].softmax(-1)),-1);support,labels=model.move_support(w);probs=out['move'].masked_fill(~support,-1e9).softmax(-1)
        for i,s in enumerate(w['steps']):
            if not s['observed']:continue
            cs=candidates(s['input'],maps[w['payload']]);x=torch.stack([torch.cat((contexts[i],torch.tensor(c['features']))) for c in cs]) if cs else torch.empty(0,68)
            hidden=head.net[1](head.net[0](x));base=int(probs[i].argmax());routes=[movement(c,s['input'],maps[w['payload']],probs[i].tolist()) for c in cs]
            target=utility_rows.get((w['key'],i))
            records.append(dict(key=w['key'],position=i,group=w['group'],split=w['partition'],label=int(labels[i]),baseline=base,candidates=[dict(key=c['key']) for c in cs],routes=routes,hidden=hidden.clone(),
                utilities=None if target is None else {c['key']:c['utility'] for c in target['candidates']}))
    return dict(records=records,weights=weights,source_bindings=bound)


def prepare():
    _,parent,architecture,_,ids=inputs();torch.set_num_threads(4);WORK.mkdir(parents=True,exist_ok=False)
    windows,maps=old.base.heading.expanded.read();original=[w for i,w in enumerate(windows) if ids[i]['canonical']];bykey={r['key']:r for r in ids}
    targets={(r['key'],r['position']):r for r in read(old.WORK/'rows.json')}
    for fold in range(4):
        ws=[w for w in original if bykey[w['key']]['fold']==fold];assert all(w['partition']=='fit' for w in ws)
        torch.save(build(ws,maps,'fold'+str(fold),parent,architecture,targets),WORK/f'fold{fold}.pt');print('Cached readout fold',fold,flush=True)
    immutable_json(REPORT/'cache.json',dict(bindings=bindings(list(WORK.glob('fold*.pt'))),evaluation_used=False))


def simulate(bank,scale=1.,shift=0.,disabled=False):
    weights=edit(bank['weights'],scale,shift)
    if disabled:weights['net.2.weight'].zero_();weights['net.2.bias'].fill_(-1)
    remembered=None;key=None;correct=baseline=rows=active=available=utility_rows=0;total=0.;predictions=[];selected=[]
    for r in bank['records']:
        if key!=r['key']:remembered=None;key=r['key']
        scores=torch.tanh(F.linear(r['hidden'],weights['net.2.weight'],weights['net.2.bias'])).flatten().tolist()
        chosen,remembered,reason=choose(r['candidates'],scores,remembered,.15)
        prediction=r['baseline'] if chosen is None else r['routes'][next(i for i,c in enumerate(r['candidates']) if c['key']==chosen['key'])]
        available+=bool(r['candidates']);active+=chosen is not None
        if r['label']>=0:rows+=1;correct+=prediction==r['label'];baseline+=r['baseline']==r['label']
        if r['utilities'] is not None:utility_rows+=1;total+=r['utilities'].get(remembered,0.)
        predictions.append(prediction);selected.append(remembered)
    return dict(rows=rows,correct=correct,baseline=baseline,active=active,available=available,utility_rows=utility_rows,utility_sum=total,predictions=predictions,selected=selected)


def combined(scores):
    return {k:sum(s[k] for s in scores) for k in ('rows','correct','baseline','active','available','utility_rows','utility_sum')}


def choose_edit(candidates,p):
    eligible=[s for s in candidates if s['active']>=p['minimum_activation']*s['available'] and s['utility_sum']>=0]
    if not eligible:raise ValueError('No weight edit passes frozen fitting guards')
    return min(eligible,key=lambda s:(-s['correct'],(s['scale']-1)**2+s['shift']**2,s['scale'],s['shift']))


def select():
    p,_,_,_,_=inputs();check(read(REPORT/'cache.json'));banks=[torch.load(WORK/f'fold{k}.pt',weights_only=False) for k in range(4)];cs=[]
    for scale in p['scales']:
        for shift in p['shifts']:cs.append(dict(scale=scale,shift=shift,**combined([simulate(b,scale,shift) for b in banks])))
    chosen=choose_edit(cs,p);original=torch.load(old.WORK/'selected.pt',weights_only=True);torch.save(edit(original,chosen['scale'],chosen['shift']),WORK/'selected.pt')
    immutable_json(REPORT/'selection.json',dict(selected=chosen,candidates=cs,disabled_control=combined([simulate(b,disabled=True) for b in banks]),bindings=bindings([WORK/'selected.pt']),evaluation_used=False,optimizer_updates=0));print('SELECTED',chosen,flush=True)


def assess():
    _,parent,architecture,_,_=inputs();check(read(REPORT/'selection.json'));torch.set_num_threads(4);windows,maps=old.base.heading.original.load();_,history,_=old.base.prior.encoded(windows,maps,architecture)
    targets=old.examples(windows,maps,history,[dict(fold=-1,canonical=True) for w in windows]);targets={(r['key'],r['position']):r for r in targets}
    chosen=read(REPORT/'selection.json')['selected'];results={}
    for split in ('fit','evaluation'):
        bank=build([w for w in windows if w['partition']==split],maps,'full',parent,architecture,targets);torch.save(bank,WORK/(split+'.pt'))
        scores=dict(edited=simulate(bank,chosen['scale'],chosen['shift']),original=simulate(bank),disabled=simulate(bank,disabled=True));results[split]=scores
    x=results['evaluation']['edited'];b=results['evaluation']['original'];gates=dict(combined_gain=x['correct']>b['correct'],direct_gain=x['correct']>x['baseline'],utility=x['utility_sum']>0,active=x['active']>=.1*x['available'])
    immutable_json(REPORT/'result.json',dict(results=results,checks=gates,all_checks_pass=all(gates.values()),bindings=bindings([WORK/'selected.pt',WORK/'fit.pt',WORK/'evaluation.pt']),promoted=False));print('EVALUATION',{k:{a:v[a] for a in ('correct','rows','active','available','utility_sum','utility_rows')} for k,v in results['evaluation'].items()},gates,flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('command',choices=('freeze','prepare','select','assess'));globals()[p.parse_args().command]()
