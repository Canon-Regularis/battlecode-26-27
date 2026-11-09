"""Prospective fitting-only utility training and causal objective reevaluation."""
import argparse,time
from pathlib import Path
import numpy as np
import torch
from . import strategic_waypoint_fit as prior,trajectory_movement_fit as base
from . import command_heading_audit as audit
from .strategic_waypoint import labels,position
from .objective_policy import candidates,utility,choose,movement,ObjectiveHead
from ..audit import immutable_json
from ..data import digest

ROOT=base.ROOT;REPORT=ROOT/'tools/action_predictor/experiments/v61';WORK=ROOT/'.cambc/action-predictor/v61'
read,check,bindings=base.read,base.check,base.bindings


def freeze():
    REPORT.mkdir(parents=True,exist_ok=True);base.inputs();check(read(prior.REPORT/'result.json'))
    immutable_json(REPORT/'plan.json',dict(sources=bindings([Path(__file__),Path(__file__).with_name('objective_policy.py'),Path(__file__).with_name('objective_predictor.py'),Path(__file__).with_name('test_objective_policy.py')]),
        inputs=bindings([base.REPORT/'plan.json',base.REPORT/'verification.json',prior.REPORT/'result.json']),seed=61001,epochs=16,lr=.001,batch=256,horizon=4,margin=.15,cap=1800,
        hypothesis='Replace averaged future coordinate with current known camp/enemy/altar/home identities. Predict four-turn future walking progress per executed step for each candidate. Reevaluate held identity at each available PRE; switch if another predicted utility exceeds it by0.15, or held utility becomes nonpositive. Abstain when all utilities nonpositive. Remove unavailable/reached goals. No fixed commitment duration.',
        features='Frozen V59 causal recurrent state48 and soft code8 plus12 current candidate features; identity only indexes memory, never learned input. Future commands only supply utility labels. Original decoder breaks equal-shortest-path step ties. No current command input.',
        selection='Four fitting-game folds; epochs4,8,12,16; minimize held canonical candidate utility MSE. One full refit. Evaluation used only after selection. Matched no-persistence and heuristic nearest-goal references reported.',
        audit_gate='Before optimization require candidate reducing-step coverage at least80percent of valid canonical fitting movement queries and best retrospective future progress at least0.5 on60percent of labeled canonical queries. Oracle diagnostics,not achieved accuracy.',
        success='Evaluation selected objective mean four-turn utility must exceed nearest-goal and equal-weight candidates; learned persistence must improve complete conditional movement count over both V59 and always-reselect variant on same513moves. All required. No strategy/promotion claim merely from persistence.',
        limitations='Replay inferred utility is not verified intent or reward; moving entities held at current positions for supervision/planning. Observed histories, preexposed groups, one seed, partial visibility. No game rollouts or subagents.'))


def inputs():
    p=read(REPORT/'plan.json');check(p);_,parent,architecture,cache,ids=base.inputs();return p,parent,architecture,cache,ids


def examples(windows,maps,history,ids):
    rows=[]
    for wi,w in enumerate(windows):
        for r in labels(w,history[w['key']],4):
            i=r['position'];path=[tuple(r['origin'])]
            for j in range(i+1,i+5):
                for dx,dy in history[w['key']][j]:path.append((path[-1][0]+dx,path[-1][1]+dy))
            if len(path)<2:continue
            cs=candidates(w['steps'][i]['input'],maps[w['payload']]);valid=[]
            for c in cs:
                u=utility(c,path,maps[w['payload']])
                if u is not None:valid.append(dict(c,utility=u))
            if valid:rows.append(dict(window=wi,position=i,key=w['key'],group=w['group'],fold=ids[wi]['fold'],canonical=ids[wi]['canonical'],candidates=valid))
    return rows


def prepare():
    p,parent,architecture,cache,ids=inputs();WORK.mkdir(parents=True,exist_ok=False);torch.set_num_threads(1)
    windows,maps=base.heading.expanded.read();history,bound=audit.prior_moves(windows);rows=examples(windows,maps,history,ids)
    gold_rows=0;covered=0;canonical=[r for r in rows if r['canonical']]
    for r in canonical:
        w=windows[r['window']];s=w['steps'][r['position']]
        if s['movement'] is None:continue
        gold_rows+=1;origin=position(s);dest=(origin[0]+s['movement'][0],origin[1]+s['movement'][1])
        covered+=any(utility(c,[origin,dest],maps[w['payload']])>0 for c in r['candidates'])
    useful=sum(max(c['utility'] for c in r['candidates'])>=.5 for r in canonical)
    eligible=gold_rows>0 and covered/gold_rows>=.8 and useful/len(canonical)>=.6
    immutable_json(REPORT/'audit.json',dict(rows=len(rows),canonical_rows=len(canonical),movement_rows=gold_rows,oracle_step_coverage=covered/gold_rows,useful_queries=useful,eligible=eligible,source_bindings=bound))
    immutable_json(WORK/'rows.json',rows)
    if not eligible:print('AUDIT FAILED: no optimizer updates',flush=True);return
    identities=[];targets=[]
    for ri,r in enumerate(rows):
        for c in r['candidates']:identities.append(ri);targets.append(c['utility'])
    torch.save(dict(target=torch.tensor(targets),row=torch.tensor(identities)),WORK/'targets.pt')
    for name in ['fold0','fold1','fold2','fold3','full']:
        all_x=prior.cached_features(name,parent,architecture,cache)[...,:56]
        x=torch.stack([torch.cat((all_x[r['window'],r['position']],torch.tensor(c['features']))) for r in rows for c in r['candidates']])
        torch.save(x,WORK/(name+'.pt'))
    immutable_json(REPORT/'cache.json',dict(bindings=bindings([q for q in WORK.iterdir() if q.is_file()]),examples=len(targets)))
    print('PREPARED',len(rows),'queries;',len(targets),'candidate examples; audit',eligible,flush=True)


def new(p):torch.manual_seed(p['seed']);return ObjectiveHead()


def train(x,y,indices,held,p,directory,epochs,deadline):
    directory.mkdir(parents=True,exist_ok=False);net=new(p);opt=torch.optim.AdamW(net.parameters(),lr=p['lr']);rng=np.random.default_rng(p['seed']);trace=[]
    torch.save(net.state_dict(),directory/'initial.pt')
    for epoch in range(1,epochs+1):
        order=rng.permutation(indices);norms=[]
        for start in range(0,len(order),p['batch']):
            if time.perf_counter()>deadline:raise TimeoutError('Objective budget exceeded')
            b=order[start:start+p['batch']];loss=(net(x[b])-y[b]).square().mean();opt.zero_grad();loss.backward();norm=torch.nn.utils.clip_grad_norm_(net.parameters(),5)
            assert torch.isfinite(norm) and torch.isfinite(loss);opt.step();norms.append(float(norm))
        entry=dict(epoch=epoch,order=order.tolist(),norms=norms)
        if epoch%4==0:
            with torch.no_grad():entry['held_sum']=float((net(x[held])-y[held]).square().double().sum()) if held is not None else None
            torch.save(net.state_dict(),directory/f'epoch-{epoch:03d}.pt');print(directory.name,epoch,entry['held_sum'],flush=True)
        trace.append(entry)
    torch.save(dict(model=net.state_dict(),optimizer=opt.state_dict(),rng=rng.bit_generator.state),directory/'final.pt');immutable_json(directory/'trace.json',trace);return net,trace


def fit():
    start=time.perf_counter();p,_,_,_,_=inputs();assert read(REPORT/'audit.json')['eligible'];check(read(REPORT/'cache.json'));torch.set_num_threads(1)
    rows=read(WORK/'rows.json');d=torch.load(WORK/'targets.pt',weights_only=True);y=d['target'];ri=d['row'].tolist();scores={}
    for fold in range(4):
        training=np.array([i for i,r in enumerate(ri) if rows[r]['fold']!=fold]);held=np.array([i for i,r in enumerate(ri) if rows[r]['fold']==fold and rows[r]['canonical']])
        _,trace=train(torch.load(WORK/f'fold{fold}.pt',weights_only=True),y,training,held,p,WORK/f'fold{fold}',p['epochs'],start+p['cap'])
        for e in trace:
            if e.get('held_sum') is not None:scores.setdefault(e['epoch'],[]).append((e['held_sum'],len(held)))
    cs=[dict(epoch=e,mse=sum(s for s,n in v)/sum(n for s,n in v)) for e,v in scores.items()];chosen=min(cs,key=lambda c:(c['mse'],c['epoch']))
    immutable_json(REPORT/'selection.json',dict(selected=chosen,candidates=cs,outer_evaluation_used=False))
    net,_=train(torch.load(WORK/'full.pt',weights_only=True),y,np.arange(len(y)),None,p,WORK/'refit',chosen['epoch'],start+p['cap']);torch.save(net.state_dict(),WORK/'selected.pt')
    bound=bindings([q for q in WORK.rglob('*') if q.is_file()]);elapsed=time.perf_counter()-start
    if elapsed>p['cap']:raise TimeoutError('Objective publication budget exceeded')
    immutable_json(REPORT/'fit.json',dict(bindings=bound,seconds=elapsed));print('SELECTED',chosen,flush=True)


if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('command',choices=('freeze','prepare','fit'));globals()[a.parse_args().command]()
