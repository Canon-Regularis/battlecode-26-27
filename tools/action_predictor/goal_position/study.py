"""One bounded, final-checkpoint goal-learning pilot. No policy promotion."""
import argparse,gzip,json,time
from pathlib import Path
import numpy as np
import torch
from . import model
from .evaluator import ROOT,REPORT,WORK,field,xy
from ..audit import immutable_json
from ..data import digest

OUT=REPORT.parent/'predictor'
RUN=ROOT/'.cambc/action-predictor/v42/predictor'


def load(split):
    audit=json.loads((REPORT/'evaluator.json').read_text());rows=[];targets=[];routes={}
    for g in audit['games']:
        if g['partition']!=split:continue
        directory=WORK/g['payload'];route=json.loads((directory/'map.json').read_text());routes[g['payload']]=route
        with gzip.open(directory/'inputs.jsonl.gz','rt') as f:inputs=list(map(json.loads,f))
        with gzip.open(directory/'labels.jsonl.gz','rt') as f:labels=list(map(json.loads,f))
        if len(inputs)!=len(labels):raise ValueError('Input/label alignment')
        for r,y in zip(inputs,labels):
            if r['event']!=y['event']:raise ValueError('Event alignment')
            rows.append(r);targets.append(y)
    return rows,targets,routes


def freeze():
    audit=json.loads((REPORT/'evaluator.json').read_text())
    if not audit['feasible']:raise ValueError('Goal evaluator is not feasible')
    for p,h in audit['output_bindings'].items():
        if digest(ROOT/p)!=h:raise ValueError('Evaluator output changed')
    rows,targets,_=load('fit');keys=model.schema(rows)
    OUT.mkdir(parents=True,exist_ok=True)
    immutable_json(OUT/'protocol.json',dict(evaluator_sha256=digest(REPORT/'evaluator.json'),
        sources={str(p.relative_to(ROOT)):digest(p) for p in Path(__file__).parent.glob('*.py')},
        input_bindings=audit['output_bindings'],schema=keys,seed=43001,passes=12,batch_size=16,
        learning_rate=.0003,weight_decay=.01,clip=5,seconds_cap=1200,selection='Final pass12 only; no early selection, repeats or extra seeds.',
        rows=len(rows),groups=len({y['group'] for y in targets}),updates=12*((len(rows)+15)//16),
        objective='Categorical cross-entropy over every statically reachable map tile, predicting the inferred future approach position. Each fitting query has equal weight; overlapping suffixes are not independent.',
        architecture='Full-resolution public terrain/altar/spawn/movement/coordinate/distance rasters; all known entity numeric fields and own current supplement with presence masks; entity embeddings scattered at observed positions and globally pooled. Four residual dilated convolutions plus whole-map pooling produce categorical tile logits. No nearest-k cutoff, future labels, replay identifiers, or learned historical checkpoint.',
        feature_limits='Numeric categorical codes and list-index fields are not dedicated semantic embeddings. Fit-only field dictionary omits new evaluation fields and reports their count. Unknown entities supply static kind/team/type/known only; hidden dynamic state is excluded. This is all available current map extent, not omniscient hidden state.',
        baselines=['current_position','nearest_known_camp_approach','nearest_altar_approach'],
        evaluation='Eight presplit whole groups excluded from goal-model training; previously exposed research games. Evaluate goals and A* next steps separately. Oracle-goal A* is diagnostic only. No full-command or playing-strength claim.',
        allocation_gate='On evaluation, lower mean goal Chebyshev error and higher within2 accuracy than every baseline; predicted-goal A* exact next-step accuracy at least5percentage points above every baseline. Passing supports a later matched whole-policy study, never direct promotion.',
        runtime_modified=False,subagents=False))


def check(plan):
    if digest(REPORT/'evaluator.json')!=plan['evaluator_sha256']:raise ValueError('Evaluator changed')
    for k in ('sources','input_bindings'):
        for p,h in plan[k].items():
            if digest(ROOT/p)!=h:raise ValueError('Frozen binding changed: '+p)


def baseline(row,route,kind):
    own=row['observation']['own'];origin=xy(own['position']);w=route['width'];h=route['height']
    if kind=='current_position':return origin
    if kind=='nearest_known_camp_approach':
        goals=[xy(e['position']) for e in row['observation']['entities'] if e.get('known',0)&1 and e['entity']['kind']==2 and e.get('health',0)>0 and e.get('position')]
        radius=int(own.get('attackRange',1))
    else:goals=list(map(xy,route['altars']));radius=route['submit_range']
    distances=field(w,h,tuple(route['blocked']),origin,0);candidates=set()
    for x,y in goals:
        for b in range(max(0,y-radius),min(h,y+radius+1)):
            for a in range(max(0,x-radius),min(w,x+radius+1)):
                if distances[b*w+a]<10000:candidates.add((a,b))
    return min(candidates,key=lambda p:(distances[p[1]*w+p[0]],p[1],p[0]),default=origin)


def metrics(records):
    if not records:return dict(rows=0)
    return dict(rows=len(records),exact_goal=sum(r['goal_error']==0 for r in records)/len(records),
        goal_within2=sum(r['goal_error']<=2 for r in records)/len(records),mean_goal_chebyshev=float(np.mean([r['goal_error'] for r in records])),
        next_step_accuracy=sum(r['step_correct'] for r in records)/len(records),path_available=sum(r['path_available'] for r in records)/len(records))


def prediction_record(row,target,route,goal):
    goal=tuple(goal);step=model.goal_guided_move(route,row,goal);truth=target['goal']
    return dict(event=target['event'],payload=target['payload'],group=target['group'],goal=list(goal),
        step=None if step is None else list(step),goal_error=max(abs(goal[0]-truth[0]),abs(goal[1]-truth[1])),
        step_correct=step==tuple(target['demonstrated_path'][1]),path_available=step is not None)


@torch.no_grad()
def evaluate(net,keys,split,bs,deadline):
    rows,targets,routes=load(split);encoded=[model.encode(r,routes[y['payload']],keys) for r,y in zip(rows,targets)]
    records=[];losses=[];net.eval()
    for start in range(0,len(rows),bs):
        if time.perf_counter()>=deadline:raise TimeoutError('Pilot budget exceeded')
        batch=model.batch(encoded[start:start+bs]);logits=net(**batch);w=logits.shape[-1]
        truth=torch.tensor([y['goal'][1]*w+y['goal'][0] for y in targets[start:start+bs]])
        losses.extend(torch.nn.functional.cross_entropy(logits.flatten(1),truth,reduction='none').tolist())
        pred=logits.flatten(1).argmax(1).tolist()
        for j,k in enumerate(pred):
            i=start+j;records.append(prediction_record(rows[i],targets[i],routes[targets[i]['payload']],(k%w,k//w)))
    baselines={}
    for kind in ('current_position','nearest_known_camp_approach','nearest_altar_approach'):
        baselines[kind]=[prediction_record(r,y,routes[y['payload']],baseline(r,routes[y['payload']],kind)) for r,y in zip(rows,targets)]
    oracle=[prediction_record(r,y,routes[y['payload']],y['goal']) for r,y in zip(rows,targets)]
    summary=dict(model=dict(**metrics(records),goal_nll=float(np.mean(losses))),
        baselines={k:metrics(v) for k,v in baselines.items()},oracle_goal_astar=metrics(oracle),
        unencoded_field_occurrences=sum(x['unencoded_fields'] for x in encoded),
        groups={g:dict(model=metrics([r for r in records if r['group']==g]),
            baselines={k:metrics([r for r in v if r['group']==g]) for k,v in baselines.items()}) for g in sorted({r['group'] for r in records})})
    return dict(summary=summary,model=records,baselines=baselines,oracle=oracle,goal_losses=losses)


def fit():
    plan=json.loads((OUT/'protocol.json').read_text());check(plan)
    RUN.mkdir(parents=True,exist_ok=False);started=time.perf_counter();deadline=started+plan['seconds_cap']
    torch.set_num_threads(4);torch.manual_seed(plan['seed']);rng=np.random.default_rng(plan['seed'])
    rows,targets,routes=load('fit');keys=plan['schema']
    data=[model.encode(r,routes[y['payload']],keys) for r,y in zip(rows,targets)]
    net=model.GoalMap(keys);initial={k:v.detach().clone() for k,v in net.state_dict().items()}
    torch.save(initial,RUN/'initial.pt');opt=torch.optim.AdamW(net.parameters(),lr=plan['learning_rate'],weight_decay=plan['weight_decay'])
    trace=[];updates=0;bs=plan['batch_size'];clipped=0
    for epoch in range(plan['passes']):
        order=rng.permutation(len(data));loss_sum=0;net.train()
        for start in range(0,len(order),bs):
            if time.perf_counter()>=deadline:raise TimeoutError('Pilot budget exceeded')
            ids=order[start:start+bs];batch=model.batch([data[i] for i in ids]);logits=net(**batch);w=logits.shape[-1]
            truth=torch.tensor([targets[i]['goal'][1]*w+targets[i]['goal'][0] for i in ids])
            loss=torch.nn.functional.cross_entropy(logits.flatten(1),truth)
            if not torch.isfinite(loss):raise ValueError('Nonfinite goal loss')
            opt.zero_grad();loss.backward();norm=torch.nn.utils.clip_grad_norm_(net.parameters(),plan['clip'])
            if not torch.isfinite(norm):raise ValueError('Nonfinite gradient')
            clipped+=int(norm>plan['clip']);opt.step();updates+=1;loss_sum+=float(loss.detach())*len(ids)
        trace.append(dict(pass_number=epoch+1,updates=updates,online_goal_nll=loss_sum/len(data),schedule=order.tolist()))
        print('Goal model pass',epoch+1,'updates',updates,'NLL',loss_sum/len(data),flush=True)
    if updates!=plan['updates']:raise ValueError('Update count mismatch')
    torch.save(dict(model=net.state_dict(),optimizer=opt.state_dict(),protocol_sha256=digest(OUT/'protocol.json')),RUN/'final.pt')
    summaries={}
    for split in ('fit','evaluation'):
        result=evaluate(net,keys,split,bs,deadline);summaries[split]=result['summary']
        immutable_json(RUN/(split+'-predictions.json'),result)
    e=summaries['evaluation'];m=e['model'];baselines=e['baselines'].values()
    checks=dict(goal_error=all(m['mean_goal_chebyshev']<b['mean_goal_chebyshev'] for b in baselines),
        goal_within2=all(m['goal_within2']>b['goal_within2'] for b in baselines),
        predicted_goal_astar=all(m['next_step_accuracy']>=b['next_step_accuracy']+.05 for b in baselines))
    immutable_json(RUN/'trace.json',trace)
    bindings={str(p.relative_to(ROOT)):digest(p) for p in RUN.iterdir() if p.is_file()}
    elapsed=time.perf_counter()-started
    if elapsed>=plan['seconds_cap']:raise TimeoutError('Pilot budget exceeded')
    immutable_json(OUT/'result.json',dict(protocol_sha256=digest(OUT/'protocol.json'),summary=summaries,
        allocation_checks=checks,all_checks_pass=all(checks.values()),updates=updates,presentations=len(data)*plan['passes'],
        parameters=sum(p.numel() for p in net.parameters()),changed_tensors=sum(not torch.equal(v,initial[k]) for k,v in net.state_dict().items()),
        clipped_updates=clipped,seconds=elapsed,bindings=bindings,
        qualification='Separate replay-inferred goal-learning pilot. Conditional on retrospectively labelable movement queries. No full-command, autonomous-strategy, playing-strength or promotion result.'))
    print(json.dumps(dict(summary={k:{a:b for a,b in v.items() if a!='groups'} for k,v in summaries.items()},checks=checks),indent=2),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('command',choices=('freeze','fit'));args=p.parse_args()
    freeze() if args.command=='freeze' else fit()
