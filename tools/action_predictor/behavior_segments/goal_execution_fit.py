"""Matched replay-goal execution probe; predicted-goal assessment is separate."""
import argparse,time
from pathlib import Path
import numpy as np
import torch
from torch.nn import functional as F
from . import trajectory_movement_fit as base,strategic_waypoint_fit as waypoint,planner_weight_edit as planner
from . import strategic_waypoint as future,model,code_weight_fit as recurrent
from .goal_execution import GoalExecutor,goal_geometry
from .objective_policy import candidates,choose,movement
from ..audit import immutable_json
from ..data import digest

ROOT=base.ROOT;REPORT=ROOT/'tools/action_predictor/experiments/v66';WORK=ROOT/'.cambc/action-predictor/v66'
read,check,bindings=base.read,base.check,base.bindings
ARMS=('control','goal')


def freeze():
    REPORT.mkdir(parents=True,exist_ok=True);base.inputs();check(read(planner.REPORT/'verification.json'))
    immutable_json(REPORT/'plan.json',dict(sources=bindings([Path(__file__).with_name(n) for n in ('goal_execution.py','goal_execution_fit.py','goal_execution_predictor.py','test_goal_execution.py')]),
        inputs=bindings([base.REPORT/n for n in ('plan.json','selection.json','refit.json','result.json','verification.json')]+[waypoint.REPORT/n for n in ('plan.json','cache.json','verification.json')]+[planner.REPORT/n for n in ('plan.json','selection.json','result.json','verification.json')]),
        seed=66001,horizons=[2,4,8],epochs=16,every=4,lr=.001,batch=128,clip=5.,fit_seconds_cap=900,assessment_seconds_cap=600,
        architecture='Freeze V59 and V62 objective head. Add shared per-move136-64-1 tanh residual with zero output initialization (8833 parameters).128 existing local/state features plus8 supplied-goal geometry features. Control zeros goal features; matched parameter shapes,initial tensors,sampling,rows,optimizer and checkpoint opportunities.',
        goals='Training goals are validated achieved PRE positions2,4,8 own turns ahead within existing32turn windows. Require endpoints observed/alive and integrated intervening executed walking to agree with every available observed position. No new replay restoration. Goals are achieved destinations,not internal Fish intent. Distinct horizon examples have equal weight; roots can repeat across horizons.',
        selection='Four fitting-game folds,all expanded other24game examples train; canonical held8game examples validate. Independently choose each arm by highest conditional movement count,then lowest NLL,then earliest epoch among0,4,8,12,16. Identical opportunities and matched initialization. One full refit per arm. No evaluation-guided selection.',
        diagnostic='Compare goal-conditioned,goal-blind control,V59 direct,and existing routing on identical supplied future goals. Future goals are intentional hindsight information ONLY in this labeled diagnostic. Require goal arm at least3points above control,direct and routing,lower NLL than control,and positive gain on endpoints>=3tiles away. Report horizons and unique-query averages. This is NOT deployable or strategic accuracy.',
        causal='Use frozen V62 current-input predicted objectives and retention decisions. Both execution heads receive identical current state and selected goal; control masks goal features. No selected goal means unchanged V59 direct fallback. Runtime never receives replay future goals. Compare all513 movement queries with V62 routing,V59 direct and matched control; report activity,overrides and paired changes.',
        success='Causal goal executor must exceed both V62 and V59 direct and matched control,without movementNLL worsening>0.01 vs direct. Goal choices and inferred-code outputs stay exact.80percent is separate and requires411/513. Diagnostic gains alone do not permit promotion.',
        limits='Bounded first execution experiment,not value learning or autonomous RL. No true outcome rewards,learned termination or simulator rollouts. Point goals in training versus region goals at inference are a transfer limitation. Preexposed research groups,inherited fitting-fold exposure,teacher-forced histories,no verified intent or playing-strength claim. No subagents.'))


def inputs():
    p=read(REPORT/'plan.json');check(p);_,parent,architecture,cache,ids=base.inputs();return p,parent,architecture,cache,ids


def new(arm,p):torch.manual_seed(p['seed']);return GoalExecutor(arm=='goal')


def records(windows,maps,history,ids,horizons):
    rows=[];geometries=[]
    for wi,w in enumerate(windows):
        _,labels=model.move_support(w)
        for horizon in horizons:
            for r in future.labels(w,history[w['key']],horizon):
                i=r['position']
                if labels[i]<0:continue
                g=goal_geometry(w['steps'][i]['input'],maps[w['payload']],r['goal'])
                if g is None:continue
                rows.append(dict(r,window=wi,key=w['key'],group=w['group'],split=w['partition'],fold=ids[wi]['fold'],canonical=ids[wi]['canonical'],horizon=horizon,label=int(labels[i]),far=max(abs(v) for v in r['offset'])>=3));geometries.append(g)
    return rows,torch.stack(geometries)


@torch.no_grad()
def feature_bank(name,parent,architecture,cache,rows,goals,windows,maps):
    context=waypoint.cached_features(name,parent,architecture,cache);net=waypoint.selected(name,parent,architecture);data=base.dataset(name,cache);logits=[]
    for start in range(0,len(data['observed']),16):logits.append(net(recurrent.take(data,slice(start,start+16)))['move'])
    logits=torch.cat(logits);x=torch.stack([context[r['window'],r['position']] for r in rows]);raw=torch.stack([logits[r['window'],r['position']] for r in rows]);support=torch.stack([data['support'][r['window'],r['position']] for r in rows]);routed=[]
    for r,b,s in zip(rows,raw,support):
        w=windows[r['window']];current=w['steps'][r['position']]['input'];prob=b.masked_fill(~s,-1e9).softmax(-1).tolist();routed.append(movement(dict(goal=r['goal'],radius=0),current,maps[w['payload']],prob))
    return dict(context=x,goal=goals,baseline=raw,support=support,labels=torch.tensor([r['label'] for r in rows]),routed=torch.tensor(routed))


def prepare():
    p,parent,architecture,cache,ids=inputs();torch.set_num_threads(1);WORK.mkdir(parents=True,exist_ok=False);windows,maps=base.heading.expanded.read();history,bound=waypoint.audit.prior_moves(windows)
    assert all(w['partition']=='fit' and w['key']==ids[i]['key'] for i,w in enumerate(windows));rows,goals=records(windows,maps,history,ids,p['horizons'])
    assert len(rows)>=1000 and len({r['group'] for r in rows})==32
    immutable_json(WORK/'rows.json',rows)
    for name in ['fold0','fold1','fold2','fold3','full']:
        torch.save(feature_bank(name,parent,architecture,cache,rows,goals,windows,maps),WORK/(name+'.pt'));print('Prepared goal executor',name,len(rows),flush=True)
    immutable_json(REPORT/'cache.json',dict(bindings=bindings(list(WORK.iterdir())),source_bindings=bound,rows=len(rows),unique_queries=len({(r['key'],r['position']) for r in rows}),groups=32,horizons={str(h):sum(r['horizon']==h for r in rows) for h in p['horizons']},evaluation_used=False))


def measure(lp,y):
    return dict(rows=len(y),correct=int((lp.argmax(-1)==y).sum()),nll_sum=float((-lp.gather(1,y[:,None]).squeeze(1)).double().sum()))


@torch.no_grad()
def score(net,bank,rows,indices):
    predictions=[];losses=[]
    for start in range(0,len(indices),256):
        ix=indices[start:start+256];lp=net(bank['context'][ix],bank['goal'][ix],bank['baseline'][ix]).masked_fill(~bank['support'][ix],-1e9).log_softmax(-1);y=bank['labels'][ix]
        predictions.extend(lp.argmax(-1).tolist());losses.extend((-lp.gather(1,y[:,None]).squeeze(1)).tolist())
    return summarize(rows,indices,predictions,losses)


def summarize(rows,indices,predictions,losses):
    rs=[rows[int(i)] for i in indices];correct=[a==r['label'] for a,r in zip(predictions,rs)];byquery={}
    for r,c in zip(rs,correct):byquery.setdefault((r['key'],r['position']),[]).append(int(c))
    cohorts={}
    for h in (2,4,8):
        ix=[i for i,r in enumerate(rs) if r['horizon']==h];cohorts[str(h)]=dict(rows=len(ix),correct=sum(correct[i] for i in ix),nll_sum=sum(losses[i] for i in ix))
    return dict(rows=len(rs),correct=sum(correct),nll_sum=sum(losses),far_rows=sum(r['far'] for r in rs),far_correct=sum(c and r['far'] for c,r in zip(correct,rs)),unique_queries=len(byquery),query_mean_accuracy=sum(sum(v)/len(v) for v in byquery.values())/len(byquery),horizons=cohorts,predictions=predictions,losses=losses)


def train(arm,bank,rows,indices,held,p,epochs,directory,deadline):
    directory.mkdir(parents=True,exist_ok=False);net=new(arm,p);opt=torch.optim.AdamW(net.parameters(),lr=p['lr']);rng=np.random.default_rng(p['seed']);trace=[]
    torch.save(net.state_dict(),directory/'epoch-000.pt');values={0:score(net,bank,rows,held)} if held is not None else {}
    for epoch in range(1,epochs+1):
        order=rng.permutation(indices);norms=[]
        for start in range(0,len(order),p['batch']):
            if time.perf_counter()>=deadline:raise TimeoutError('Goal execution paired budget exceeded')
            ix=order[start:start+p['batch']];logits=net(bank['context'][ix],bank['goal'][ix],bank['baseline'][ix]).masked_fill(~bank['support'][ix],-1e9);loss=F.cross_entropy(logits,bank['labels'][ix]);opt.zero_grad();loss.backward();norm=torch.nn.utils.clip_grad_norm_(net.parameters(),p['clip']);assert torch.isfinite(loss) and torch.isfinite(norm);opt.step();norms.append(float(norm))
        trace.append(dict(epoch=epoch,order=order.tolist(),norms=norms))
        if epoch%p['every']==0:
            torch.save(net.state_dict(),directory/f'epoch-{epoch:03d}.pt')
            if held is not None:values[epoch]=score(net,bank,rows,held)
            print(directory.name,epoch,values.get(epoch,{}).get('correct'),flush=True)
    torch.save(dict(model=net.state_dict(),optimizer=opt.state_dict(),rng=rng.bit_generator.state),directory/'final.pt');immutable_json(directory/'trace.json',dict(epochs=trace,validation=values));return net,values


def select(cs):return min(cs,key=lambda c:(-c['correct'],c['nll_sum']/c['rows'],c['epoch']))


def fit():
    start=time.perf_counter();p,_,_,_,_=inputs();check(read(REPORT/'cache.json'));torch.set_num_threads(1);rows=read(WORK/'rows.json');selected={};all_candidates={}
    for arm in ARMS:
        values={}
        for fold in range(4):
            bank=torch.load(WORK/f'fold{fold}.pt',weights_only=True);training=np.array([i for i,r in enumerate(rows) if r['fold']!=fold]);held=np.array([i for i,r in enumerate(rows) if r['fold']==fold and r['canonical']])
            _,v=train(arm,bank,rows,training,held,p,p['epochs'],WORK/arm/f'fold{fold}',start+p['fit_seconds_cap'])
            for e,s in v.items():values.setdefault(e,[]).append(s)
        cs=[dict(epoch=e,**{k:sum(v[k] for v in vs) for k in ('rows','correct','nll_sum')}) for e,vs in values.items()];selected[arm]=select(cs);all_candidates[arm]=cs
    immutable_json(REPORT/'selection.json',dict(selected=selected,candidates=all_candidates,evaluation_used=False))
    for arm in ARMS:
        bank=torch.load(WORK/'full.pt',weights_only=True);net,_=train(arm,bank,rows,np.arange(len(rows)),None,p,selected[arm]['epoch'],WORK/arm/'refit',start+p['fit_seconds_cap']);torch.save(net.state_dict(),WORK/(arm+'-selected.pt'))
    bound=bindings([q for q in WORK.rglob('*') if q.is_file()]);elapsed=time.perf_counter()-start
    if elapsed>=p['fit_seconds_cap']:raise TimeoutError('Goal execution fit publication exceeded')
    immutable_json(REPORT/'fit.json',dict(bindings=bound,seconds=elapsed));print('SELECTED',selected,flush=True)


@torch.no_grad()
def assess():
    start=time.perf_counter();p,parent,architecture,_,_=inputs();check(read(REPORT/'fit.json'));torch.set_num_threads(4);windows,maps=base.heading.original.load();encoded,history,bound=base.prior.encoded(windows,maps,architecture)
    rows,goals=records(windows,maps,history,[dict(fold=-1,canonical=True) for w in windows],p['horizons']);lookup={(r['window'],r['position'],r['horizon']):i for i,r in enumerate(rows)}
    policy=base.policy(read(base.REPORT/'plan.json'),parent,architecture);objective=planner.old.new(read(planner.old.REPORT/'plan.json'));objective.load_state_dict(torch.load(planner.WORK/'selected.pt',weights_only=True));nets={arm:new(arm,p) for arm in ARMS}
    for arm in ARMS:nets[arm].load_state_dict(torch.load(WORK/(arm+'-selected.pt'),weights_only=True))
    contexts=[];raws=[];supports=[];diag_routes=[];diag_order=[];causal=[]
    for wi,w in enumerate(windows):
        args=encoded[w['key']];states=[];hook=policy.parent.parent.backbone.code.register_forward_pre_hook(lambda module,args:states.append(args[0]))
        try:out=policy(**args)
        finally:hook.remove()
        x=waypoint.features(states[0],out['code'].softmax(-1),args['geometry'],args['heading'],args['command_heading']);support,labels=model.move_support(w);lp=out['move'].masked_fill(~support,-1e9).log_softmax(-1);remembered=None
        for i,s in enumerate(w['steps']):
            if not s['observed']:continue
            cs=candidates(s['input'],maps[w['payload']]);scores=objective(torch.stack([torch.cat((x[i,:56],torch.tensor(c['features']))) for c in cs])).tolist() if cs else []
            chosen,remembered,_=choose(cs,scores,remembered,.15);outputs={a:lp[i] for a in ARMS};routed=int(lp[i].argmax());g=None
            if chosen is not None:
                routed=movement(chosen,s['input'],maps[w['payload']],lp[i].exp().tolist());g=goal_geometry(s['input'],maps[w['payload']],chosen['goal'],chosen['radius']);assert g is not None
                outputs={a:nets[a](x[i],g,out['move'][i]).masked_fill(~support[i],-1e9).log_softmax(-1) for a in ARMS}
            causal.append(dict(key=w['key'],position=i,group=w['group'],split=w['partition'],label=int(labels[i]),direct=int(lp[i].argmax()),routed=routed,selected=remembered,active=chosen is not None,predictions={a:int(v.argmax()) for a,v in outputs.items()},nll={a:float(-v[labels[i]]) if labels[i]>=0 else None for a,v in outputs.items()},direct_nll=float(-lp[i,labels[i]]) if labels[i]>=0 else None))
            for h in p['horizons']:
                j=lookup.get((wi,i,h))
                if j is None:continue
                contexts.append(x[i]);raws.append(out['move'][i]);supports.append(support[i]);diag_order.append(j);diag_routes.append(movement(dict(goal=rows[j]['goal'],radius=0),s['input'],maps[w['payload']],lp[i].exp().tolist()))
    bank=dict(context=torch.stack(contexts),goal=goals[diag_order],baseline=torch.stack(raws),support=torch.stack(supports),labels=torch.tensor([rows[j]['label'] for j in diag_order]),routed=torch.tensor(diag_routes));rows=[rows[j] for j in diag_order];torch.save(bank,WORK/'assessment-bank.pt');immutable_json(WORK/'assessment-rows.json',rows);immutable_json(WORK/'causal.json',causal)
    result=summaries(nets,bank,rows,causal);bound_files=bindings([WORK/'assessment-bank.pt',WORK/'assessment-rows.json',WORK/'causal.json',*(WORK/(a+'-selected.pt') for a in ARMS)]);elapsed=time.perf_counter()-start
    if elapsed>=p['assessment_seconds_cap']:raise TimeoutError('Goal execution assessment exceeded')
    immutable_json(REPORT/'result.json',dict(**result,bindings=bound_files,source_bindings=bound,seconds=elapsed,promoted=False));print('RESULT',result['checks'],result['causal']['evaluation'],flush=True)


def summaries(nets,bank,rows,causal):
    diagnostic={};usable={}
    for split in ('fit','evaluation'):
        ix=np.array([i for i,r in enumerate(rows) if r['split']==split]);diagnostic[split]={a:score(nets[a],bank,rows,ix) for a in ARMS}
        lp=bank['baseline'][ix].masked_fill(~bank['support'][ix],-1e9).log_softmax(-1);loss=(-lp.gather(1,bank['labels'][ix,None]).squeeze(1)).tolist()
        diagnostic[split]['direct']=summarize(rows,ix,lp.argmax(-1).tolist(),loss);diagnostic[split]['routing']=summarize(rows,ix,bank['routed'][ix].tolist(),[0.]*len(ix));diagnostic[split]['routing'].pop('nll_sum');diagnostic[split]['routing'].pop('losses')
        for cohort in diagnostic[split]['routing']['horizons'].values():cohort.pop('nll_sum')
        rs=[r for r in causal if r['split']==split and r['label']>=0];allrows=[r for r in causal if r['split']==split]
        usable[split]=dict(rows=len(rs),active_queries=sum(r['active'] for r in allrows),active_movement=sum(r['active'] for r in rs),direct=sum(r['direct']==r['label'] for r in rs),routing=sum(r['routed']==r['label'] for r in rs),direct_nll=sum(r['direct_nll'] for r in rs)/len(rs))
        for a in ARMS:usable[split][a]=dict(correct=sum(r['predictions'][a]==r['label'] for r in rs),nll=sum(r['nll'][a] for r in rs)/len(rs),rescues_vs_routing=sum(r['routed']!=r['label'] and r['predictions'][a]==r['label'] for r in rs),regressions_vs_routing=sum(r['routed']==r['label'] and r['predictions'][a]!=r['label'] for r in rs),overrides_direct=sum(r['predictions'][a]!=r['direct'] for r in rs))
    d=diagnostic['evaluation'];c=usable['evaluation'];n=d['goal']['rows'];checks=dict(diagnostic_control=d['goal']['correct']-d['control']['correct']>=.03*n,diagnostic_direct=d['goal']['correct']-d['direct']['correct']>=.03*n,diagnostic_routing=d['goal']['correct']-d['routing']['correct']>=.03*n,diagnostic_nll=d['goal']['nll_sum']<d['control']['nll_sum'],diagnostic_far=d['goal']['far_correct']>d['control']['far_correct'],causal_routing=c['goal']['correct']>c['routing'],causal_direct=c['goal']['correct']>c['direct'],causal_control=c['goal']['correct']>c['control']['correct'],causal_nll=c['goal']['nll']<=c['direct_nll']+.01)
    return dict(diagnostic=diagnostic,causal=usable,checks=checks,all_checks_pass=all(checks.values()),target_met=c['rows']==513 and c['goal']['correct']>=411)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('command',choices=('freeze','prepare','fit','assess'));globals()[p.parse_args().command]()
