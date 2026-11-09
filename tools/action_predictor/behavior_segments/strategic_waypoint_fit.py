"""Bounded fit-fold waypoint experiment and descriptive goal-guided evaluation."""
import argparse,time
from pathlib import Path
import numpy as np
import torch
from . import trajectory_movement_fit as base,command_heading_audit as audit
from .strategic_waypoint import WaypointHead,features,labels,reachable_goal,route_move,position,commitment
from . import model
from ..audit import immutable_json
from ..data import digest

ROOT=base.ROOT;REPORT=ROOT/'tools/action_predictor/experiments/v60';WORK=ROOT/'.cambc/action-predictor/v60'
read,check,bindings=base.read,base.check,base.bindings


def freeze():
    REPORT.mkdir(parents=True,exist_ok=True);base.inputs();check(read(base.REPORT/'verification.json'))
    immutable_json(REPORT/'plan.json',dict(sources=bindings([Path(__file__),Path(__file__).with_name('strategic_waypoint.py'),Path(__file__).with_name('strategic_waypoint_predictor.py'),Path(__file__).with_name('test_strategic_waypoint.py')]),
        inputs=bindings([base.REPORT/n for n in ('plan.json','selection.json','refit.json','result.json','verification.json')]),
        seed=60001,horizon=8,epochs=32,evaluate_every=8,learning_rate=.001,batch_rows=128,seconds_cap=1200,
        selection='Four fitting-game folds, held canonical windows only. Minimize pooled mean Chebyshev endpoint error,then maximize within2,then earlier epoch. Epoch0 stay predictor eligible. Full refit selected duration only.',
        labels='Observed position eight own turns later within same32turn window. Require both endpoints observed/alive and every intervening observed position to agree with integrated executed movement; reject observed death or displacement inconsistent with walking. Missing intermediate observations remain missing, not imputed inputs. Future commands/positions only construct labels.',
        features='Frozen V59 causal state48,soft code8,current geometry540,observed-heading36,previous-command72. No current/future actions or endpoint labels in forward inputs. Freeze original model. Train704-128-2 waypoint MLP with SmoothL1(offset/8), then snap prediction to nearest static-reachable tile and use A* with actual current support.',
        baselines='Current position, prior direction extrapolated by8tiles, original V59 goal and V59 direct movement. Endpoint and far-displacement cohorts are reported separately. Baselines not used to select evaluation outputs.',
        success='Learned endpoint mean error lower than stay,heading8,andV59; far(with displacement>=3) within2 at least5points above best baseline; committed-goal-guided movement correct count exceeds V59 on all513 movement queries. Commit for eight own-turn queries or until reached; reset on observed missing position/window/actor. Missing frames age commitment without inventing observations. All required. Never automatic promotion.',
        limits='Future position is a replay-derived waypoint,not internal intent. Static route commitment is not an autonomous game rollout. Preexposed groups, inherited fitting exposure, teacher-forced history and missing intermediate observations limit causal/strategic claims. No subagents.'))


def inputs():
    plan=read(REPORT/'plan.json');check(plan);_,parent,architecture,cache,ids=base.inputs()
    return plan,parent,architecture,cache,ids


def selected(name,parent,architecture):
    net=base.warm(name,parent,architecture);e=read(base.REPORT/'selection.json')['selected']['epoch']
    path=base.WORK/'selected.pt' if name=='full' else base.WORK/'tuning'/name/f'epoch-{e:03d}.pt'
    net.load_state_dict(torch.load(path,weights_only=False)['model']);return net.eval()


@torch.no_grad()
def cached_features(name,parent,architecture,cache):
    net=selected(name,parent,architecture);data=base.dataset(name,cache);rows=[]
    for start in range(0,len(data['observed']),16):
        d=base.heading.first.take(data,slice(start,start+16));states=[];hook=net.backbone.code.register_forward_pre_hook(lambda module,args:states.append(args[0]))
        try:out=net(d)
        finally:hook.remove()
        rows.append(features(states[0],out['code'].softmax(-1),d['geometry'],d['heading'],d['command_heading']))
    return torch.cat(rows)


def prepare():
    plan,parent,architecture,cache,ids=inputs();torch.set_num_threads(1);WORK.mkdir(parents=True,exist_ok=False)
    windows,maps=base.heading.expanded.read();history,bound=audit.prior_moves(windows);records=[]
    for wi,w in enumerate(windows):
        assert w['partition']=='fit' and w['key']==ids[wi]['key']
        for r in labels(w,history[w['key']],plan['horizon']):records.append(dict(r,window=wi,**ids[wi],payload=w['payload']))
    assert len(records)>500 and len({r['group'] for r in records})==32
    immutable_json(WORK/'rows.json',records);torch.save(torch.tensor([r['offset'] for r in records],dtype=torch.float32),WORK/'targets.pt')
    for name in ['fold0','fold1','fold2','fold3','full']:
        all_x=cached_features(name,parent,architecture,cache)
        torch.save(torch.stack([all_x[r['window'],r['position']] for r in records]),WORK/(name+'.pt'))
    immutable_json(REPORT/'cache.json',dict(plan_sha256=digest(REPORT/'plan.json'),source_bindings=bound,bindings=bindings([p for p in WORK.iterdir() if p.is_file()]),
        rows=len(records),far_rows=sum(max(abs(v) for v in r['offset'])>=3 for r in records),groups=32))
    print('Prepared future waypoints',len(records),flush=True)


def new(plan):torch.manual_seed(plan['seed']);return WaypointHead()


@torch.no_grad()
def score(net,x,rows,indices,maps):
    predictions=net(x[indices]).tolist();errors=[]
    for i,p in zip(indices,predictions):
        r=rows[i];q=reachable_goal(r['origin'],p,maps[r['payload']]);errors.append(max(abs(q[j]-r['goal'][j]) for j in (0,1)))
    return dict(rows=len(indices),error_sum=sum(errors),within2=sum(e<=2 for e in errors),predicted_offsets=predictions)


def train(x,y,rows,indices,held,maps,plan,epochs,directory,deadline):
    directory.mkdir(parents=True,exist_ok=False);net=new(plan);opt=torch.optim.AdamW(net.parameters(),lr=plan['learning_rate']);rng=np.random.default_rng(plan['seed']);trace=[]
    torch.save(net.state_dict(),directory/'epoch-000.pt');values={0:score(net,x,rows,held,maps)} if held is not None else {}
    for epoch in range(1,epochs+1):
        order=rng.permutation(indices);norms=[]
        for start in range(0,len(order),plan['batch_rows']):
            if time.perf_counter()>deadline:raise TimeoutError('Waypoint training cap')
            batch=order[start:start+plan['batch_rows']];loss=torch.nn.functional.smooth_l1_loss(net(x[batch])/8,y[batch]/8)
            opt.zero_grad();loss.backward();norm=torch.nn.utils.clip_grad_norm_(net.parameters(),5)
            assert torch.isfinite(loss) and torch.isfinite(norm);opt.step();norms.append(float(norm))
        trace.append(dict(epoch=epoch,order=order.tolist(),gradient_norms=norms))
        if epoch%plan['evaluate_every']==0:
            torch.save(net.state_dict(),directory/f'epoch-{epoch:03d}.pt')
            if held is not None:values[epoch]=score(net,x,rows,held,maps)
            print(directory.name,epoch,values.get(epoch,{}).get('error_sum'),flush=True)
    torch.save(dict(model=net.state_dict(),optimizer=opt.state_dict(),rng=rng.bit_generator.state),directory/'final.pt')
    immutable_json(directory/'trace.json',dict(epochs=trace,validation=values));return net,values


def fit():
    start=time.perf_counter();plan,_,_,_,_=inputs();check(read(REPORT/'cache.json'));torch.set_num_threads(1)
    rows=read(WORK/'rows.json');y=torch.load(WORK/'targets.pt',weights_only=True);_,maps=base.heading.expanded.read();values={}
    for fold in range(4):
        x=torch.load(WORK/f'fold{fold}.pt',weights_only=True);training=np.array([i for i,r in enumerate(rows) if r['fold']!=fold]);held=np.array([i for i,r in enumerate(rows) if r['fold']==fold and r['canonical']])
        _,v=train(x,y,rows,training,held,maps,plan,plan['epochs'],WORK/f'fold{fold}',start+plan['seconds_cap'])
        for e,s in v.items():values.setdefault(e,[]).append(s)
    candidates=[dict(epoch=e,rows=sum(s['rows'] for s in v),error_sum=sum(s['error_sum'] for s in v),within2=sum(s['within2'] for s in v)) for e,v in values.items()]
    chosen=min(candidates,key=lambda s:(s['error_sum']/s['rows'],-s['within2'],s['epoch']))
    immutable_json(REPORT/'selection.json',dict(selected=chosen,candidates=candidates,plan_sha256=digest(REPORT/'plan.json'),outer_evaluation_used=False))
    x=torch.load(WORK/'full.pt',weights_only=True);net,_=train(x,y,rows,np.arange(len(rows)),None,maps,plan,chosen['epoch'],WORK/'refit',start+plan['seconds_cap'])
    torch.save(dict(model=net.state_dict(),plan_sha256=digest(REPORT/'plan.json')),WORK/'selected.pt')
    bound=bindings([p for p in WORK.rglob('*') if p.is_file()]);elapsed=time.perf_counter()-start
    if elapsed>plan['seconds_cap']:raise TimeoutError('Waypoint publication cap')
    immutable_json(REPORT/'fit.json',dict(selection_sha256=digest(REPORT/'selection.json'),bindings=bound,seconds=elapsed,promoted=False));print('SELECTED',chosen,flush=True)


def loaded():
    plan,parent,architecture,_,_=inputs();check(read(REPORT/'fit.json'));saved=torch.load(WORK/'selected.pt',weights_only=False)
    assert saved['plan_sha256']==digest(REPORT/'plan.json');head=new(plan);head.load_state_dict(saved['model']);return head.eval(),base.policy(read(base.REPORT/'plan.json'),parent,architecture)


@torch.no_grad()
def evaluate():
    plan,parent,architecture,_,_=inputs();torch.set_num_threads(4);head,policy=loaded();windows,maps=base.heading.original.load()
    encoded,history,bound=base.prior.encoded(windows,maps,architecture);records=[];moves=[];all_offsets={}
    for w in windows:
        args=encoded[w['key']];states=[];hook=policy.parent.parent.backbone.code.register_forward_pre_hook(lambda module,args:states.append(args[0]))
        try:out=policy(**args)
        finally:hook.remove()
        x=features(states[0],out['code'].softmax(-1),args['geometry'],args['heading'],args['command_heading']);offsets=head(x);all_offsets[w['key']]=offsets.tolist()
        route=maps[w['payload']];support,target=model.move_support(w);pred=out['move'].masked_fill(~support,-1e9).argmax(-1)
        targets={r['position']:r for r in labels(w,history[w['key']],plan['horizon'])};committed=None
        for i,s in enumerate(w['steps']):
            origin=position(s)
            if origin is None:
                if s['observed']:committed=None
                elif committed is not None:committed=dict(committed,remaining=committed['remaining']-1)
                continue
            goal=reachable_goal(origin,offsets[i],route);last=args['command_heading'][i,:,1];direction=model.OFFSETS[int(last.argmax())] if float(last.max()) else (0,0)
            baseline_goal=reachable_goal(origin,[8*d for d in direction],route)
            committed_goal,committed=commitment(origin,goal,committed)
            if i in targets:
                r=targets[i];width=route['width'];old=int(out['goal'][i].flatten().argmax());alternatives=dict(learned=goal,stay=origin,heading8=baseline_goal,v59=(old%width,old//width))
                records.append(dict(key=w['key'],group=w['group'],split=w['partition'],position=i,origin=list(origin),goal=r['goal'],far=max(abs(v) for v in r['offset'])>=3,
                    errors={k:max(abs(p[j]-r['goal'][j]) for j in (0,1)) for k,p in alternatives.items()}))
            if target[i]>=0:
                dx,dy=model.OFFSETS[int(pred[i])];fallback=(origin[0]+dx,origin[1]+dy);move=route_move(s['input'],route,goal,fallback);gold=model.OFFSETS[int(target[i])]
                committed_move=route_move(s['input'],route,committed_goal,fallback)
                moves.append(dict(key=w['key'],split=w['partition'],position=i,baseline=int(pred[i])==int(target[i]),routed=move==(origin[0]+gold[0],origin[1]+gold[1]),committed=committed_move==(origin[0]+gold[0],origin[1]+gold[1])))
    summaries={}
    for split in ('fit','evaluation'):
        rs=[r for r in records if r['split']==split];ms=[r for r in moves if r['split']==split];summaries[split]={}
        for cohort,subset in [('all',rs),('far',[r for r in rs if r['far']])]:
            summaries[split][cohort]={k:dict(rows=len(subset),mean_error=sum(r['errors'][k] for r in subset)/len(subset),within2=sum(r['errors'][k]<=2 for r in subset)/len(subset)) for k in ('learned','stay','heading8','v59')}
        summaries[split]['movement']=dict(rows=len(ms),baseline=sum(r['baseline'] for r in ms),routed=sum(r['routed'] for r in ms),committed=sum(r['committed'] for r in ms))
    x=summaries['evaluation'];gates=dict(endpoint=all(x['all']['learned']['mean_error']<x['all'][k]['mean_error'] for k in ('stay','heading8','v59')),
        far=x['far']['learned']['within2']>=max(x['far'][k]['within2'] for k in ('stay','heading8','v59'))+.05,movement=x['movement']['committed']>x['movement']['baseline'])
    return dict(summary=summaries,checks=gates,all_checks_pass=all(gates.values()),records=records,moves=moves,offsets=all_offsets,source_bindings=bound)


def assess():
    value=evaluate();immutable_json(WORK/'predictions.json',value)
    immutable_json(REPORT/'result.json',dict(summary=value['summary'],checks=value['checks'],all_checks_pass=value['all_checks_pass'],bindings=bindings([WORK/'predictions.json',WORK/'selected.pt']),promoted=False))
    print(value['summary']['evaluation'],value['checks'],flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('command',choices=('freeze','prepare','fit','assess'));globals()[p.parse_args().command]()
