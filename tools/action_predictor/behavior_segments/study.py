"""Frozen discovery plus a matched causal auxiliary-code experiment."""
import argparse,json,time
from collections import Counter
from pathlib import Path
import numpy as np
import torch
from .data import ROOT,REPORT,WORK,FEATURES,load
from . import segmentation,model
from ..goal_position import model as gm
from ..goal_position.evaluator import field,xy
from ..audit import immutable_json
from ..data import digest


def check(plan):
    for kind in ('sources','inputs'):
        for p,h in plan[kind].items():
            if digest(ROOT/p)!=h:raise ValueError('Frozen binding changed: '+p)


def freeze():
    receipt=json.loads((REPORT/'data.json').read_text())
    for p,h in receipt['output_bindings'].items():
        if digest(ROOT/p)!=h:raise ValueError('Data output changed')
    windows,maps=load();fit=[w for w in windows if w['partition']=='fit']
    keys=gm.schema([s['input'] for w in fit for s in w['steps'] if s['observed']])
    sources={str(p.relative_to(ROOT)):digest(p) for p in Path(__file__).parent.glob('*.py')}
    for name in ('goal_position/model.py','goal_position/evaluator.py','algorithmic/library.py','trajectory_history/feature_sources.py','trajectory_history/audit.py','observation_data.py'):
        p=ROOT/'tools/action_predictor'/name;sources[str(p.relative_to(ROOT))]=digest(p)
    inputs=dict(receipt['output_bindings']);inputs[str((REPORT/'data.json').relative_to(ROOT))]=digest(REPORT/'data.json')
    immutable_json(REPORT/'protocol.json',dict(sources=sources,inputs=inputs,schema=keys,codes=8,discovery_iterations=12,
        change_penalty=2.,minimum_duration=2,seed=43002,passes=6,learning_rate=.0003,weight_decay=.01,clip=5,
        goal_weight=.2,code_weight=.2,seconds_cap_per_arm=1200,selection='Final pass6 only, one matched seed, no repeats/extensions.',
        discovery='Minimum-duration switching centroid model. Fit-only masked normalization and12hard-EM iterations; exact dynamic-program assignment penalizes each code change. No named objective, action-specific boundary, absolute-coordinate descriptor or evaluation fitting. Window edges are administrative, never learned boundaries.',
        endpoint='Position at PRE of first query in the following learned segment. Rightmost segment has no endpoint target. Missing or statically unreachable endpoints remain masked. Each actual turn remains in sequence.',
        causality='Current full personal map/known entities, current round, missing mask and previous completed-turn descriptor. Offline labels and current/future descriptors never enter policy.forward. Recurrent state resets only at frozen32turn window boundaries.',
        contrast='Identical full-map recurrent architecture/initialization/schedules/data/goal and movement objectives. S00 code auxiliary weight0; S01 code auxiliary weight0.2. Both predict a soft code and use its embedding in goal and movement heads. Only S01 is taught the offline discovered code.',
        primary='Evaluation conditional first-movement accuracy at least3percentage points aboveS00; endpoint within2 accuracy at least3points aboveS00; lower mean endpoint error; movementNLL no more than0.01 worse. All required. Same learned endpoint labels in both arms; no claim this isolates segmentation vs fixed boundaries.',
        scope='Previously exposed32fit/8evaluation groups; selected available-PRE windows. Predicting a movement destination conditional on a recorded movement query is not full-command accuracy. No playing-strength/intent/promotion claim.',
        fit_windows=len(fit),updates_per_arm=len(fit)*6,row_presentations_per_arm=len(fit)*32*6,
        subagents=False,runtime_modified=False))


def endpoint_labels(window,codes,route):
    goals=[None]*len(codes);segments=list(segmentation.ranges(codes));counts=Counter()
    for a,b,code in segments:
        if b==len(codes):counts['right_censored_turns']+=b-a;continue
        end=window['steps'][b]
        if not end['observed']:counts['missing_endpoint_turns']+=b-a;continue
        goal=xy(end['input']['observation']['own'].get('position'))
        for i in range(a,b):
            s=window['steps'][i]
            if not s['observed']:counts['missing_current_turns']+=1;continue
            origin=xy(s['input']['observation']['own'].get('position'))
            if goal is None or origin is None:counts['missing_position_turns']+=1;continue
            d=field(route['width'],route['height'],tuple(route['blocked']),origin,0)
            if not(0<=goal[0]<route['width'] and 0<=goal[1]<route['height']) or d[goal[1]*route['width']+goal[0]]>=10000:
                counts['unreachable_endpoint_turns']+=1;continue
            goals[i]=list(goal);counts['goal_turns']+=1
    return goals,dict(counts)


def discover():
    plan=json.loads((REPORT/'protocol.json').read_text());check(plan);windows,maps=load()
    pairs=[(np.asarray([s['behavior'] for s in w['steps']]),np.asarray([s['behavior_mask'] for s in w['steps']])) for w in windows if w['partition']=='fit']
    fitted=segmentation.fit(pairs,k=plan['codes'],iterations=plan['discovery_iterations'],penalty=plan['change_penalty'],minimum=plan['minimum_duration'],seed=plan['seed'])
    labels={};summary={};endpoints={};coverage=Counter()
    for split in ('fit','evaluation'):
        durations=[];occupancy=Counter();boundaries=0;goal_turns=0;observed=0;move_rows=0
        for w in windows:
            if w['partition']!=split:continue
            code=segmentation.assign([s['behavior'] for s in w['steps']],[s['behavior_mask'] for s in w['steps']],fitted)
            labels[w['key']]=code.tolist();segments=list(segmentation.ranges(code));durations += [b-a for a,b,k in segments]
            occupancy.update(map(int,code));boundaries+=len(segments)-1
            goals,counts=endpoint_labels(w,code,maps[w['payload']]);endpoints[w['key']]=goals
            coverage.update({split+'/'+k:v for k,v in counts.items()});goal_turns+=sum(g is not None for g in goals)
            observed+=sum(s['observed'] for s in w['steps']);move_rows+=sum(s['movement'] is not None for s in w['steps'])
        summary[split]=dict(turns=sum(occupancy.values()),observed_queries=observed,movement_queries=move_rows,goal_queries=goal_turns,
            active_codes=len(occupancy),occupancy=dict(occupancy),learned_boundaries=boundaries,segments=len(durations),
            median_duration=float(np.median(durations)),duration_histogram=dict(Counter(durations)))
    feasible=summary['fit']['goal_queries']>=200 and summary['evaluation']['goal_queries']>=50 and summary['fit']['active_codes']>=2
    immutable_json(REPORT/'discovery.json',dict(protocol_sha256=digest(REPORT/'protocol.json'),fitted=fitted,labels=labels,endpoints=endpoints,
        summary=summary,coverage=dict(coverage),feasible=feasible,qualification='Unnamed hindsight behavior codes, not verified objectives; evaluation sequences use frozen fitting prototypes.'))
    print(json.dumps(dict(summary=summary,feasible=feasible),indent=2))


def targets(w,goals,width):
    support,movement=model.move_support(w)
    goal=torch.tensor([-1 if g is None else g[1]*width+g[0] for g in goals],dtype=torch.long)
    return support,movement,goal


def loss_terms(output,support,movement,goals,codes,observed):
    move_logits=output['move'].masked_fill(~support,-1e9);move_mask=movement>=0;goal_mask=goals>=0
    zero=output['code'].sum()*0
    move=torch.nn.functional.cross_entropy(move_logits[move_mask],movement[move_mask],reduction='sum') if move_mask.any() else zero
    goal=torch.nn.functional.cross_entropy(output['goal'].flatten(1)[goal_mask],goals[goal_mask],reduction='sum') if goal_mask.any() else zero
    code=torch.nn.functional.cross_entropy(output['code'][observed.bool()],codes[observed.bool()],reduction='sum')
    return move/len(observed),goal/len(observed),code/len(observed)


def aggregate(records):
    moves=[r for r in records if r['move_label'] is not None];goals=[r for r in records if r['goal_label'] is not None]
    return dict(rows=len(records),movement_rows=len(moves),goal_rows=len(goals),
        movement_accuracy=sum(r['move_prediction']==r['move_label'] for r in moves)/len(moves) if moves else None,
        movement_nll=float(np.mean([r['movement_nll'] for r in moves])) if moves else None,
        goal_within2=sum(r['goal_error']<=2 for r in goals)/len(goals) if goals else None,
        goal_exact=sum(r['goal_error']==0 for r in goals)/len(goals) if goals else None,
        mean_goal_error=float(np.mean([r['goal_error'] for r in goals])) if goals else None,
        goal_nll=float(np.mean([r['goal_nll'] for r in goals])) if goals else None,
        astar_movement_accuracy=sum(r['astar_correct'] for r in moves)/len(moves) if moves else None,
        code_accuracy=sum(r['code_prediction']==r['code_label'] for r in records)/len(records) if records else None)


@torch.no_grad()
def evaluate(net,windows,maps,cache,discovery,split,deadline):
    net.eval();records=[]
    for w in windows:
        if w['partition']!=split:continue
        if time.perf_counter()>=deadline:raise TimeoutError('Evaluation budget exceeded')
        args=cache[w['key']];output=net(**args);width=maps[w['payload']]['width']
        support,movement,goals=targets(w,discovery['endpoints'][w['key']],width)
        move_lp=output['move'].masked_fill(~support,-1e9).log_softmax(-1);goal_lp=output['goal'].flatten(1).log_softmax(-1)
        move_pred=move_lp.argmax(-1).tolist();goal_pred=goal_lp.argmax(-1).tolist();code_pred=output['code'].argmax(-1).tolist()
        for i,s in enumerate(w['steps']):
            if not s['observed']:continue
            p=(goal_pred[i]%width,goal_pred[i]//width);g=discovery['endpoints'][w['key']][i]
            step=gm.goal_guided_move(maps[w['payload']],s['input'],p) if s['movement'] is not None else None
            origin=xy(s['input']['observation']['own'].get('position'));actual=(origin[0]+s['movement'][0],origin[1]+s['movement'][1]) if s['movement'] is not None else None
            records.append(dict(key=w['key'],event=s['event'],group=w['group'],position=i,
                code_label=discovery['labels'][w['key']][i],code_prediction=code_pred[i],
                move_label=int(movement[i]) if movement[i]>=0 else None,move_prediction=move_pred[i],
                movement_nll=float(-move_lp[i,movement[i]]) if movement[i]>=0 else None,
                goal_prediction=list(p) if origin is not None else None,goal_label=g,goal_error=max(abs(p[0]-g[0]),abs(p[1]-g[1])) if g is not None else None,
                goal_nll=float(-goal_lp[i,goals[i]]) if goals[i]>=0 else None,astar_correct=step==actual if actual is not None else None))
    return dict(summary=aggregate(records),groups={g:aggregate([r for r in records if r['group']==g]) for g in sorted({r['group'] for r in records})},records=records)


def fit_arm(arm):
    plan=json.loads((REPORT/'protocol.json').read_text());check(plan);discovery=json.loads((REPORT/'discovery.json').read_text())
    if discovery['protocol_sha256']!=digest(REPORT/'protocol.json') or not discovery['feasible']:raise ValueError('Discovery not feasible/bound')
    windows,maps=load();directory=WORK/(arm+'-run');directory.mkdir(parents=True,exist_ok=False)
    start=time.perf_counter();deadline=start+plan['seconds_cap_per_arm'];torch.set_num_threads(4)
    cache={};unknown=Counter()
    for w in windows:cache[w['key']],n=model.encode_window(w,maps[w['payload']],plan['schema']);unknown[w['partition']]+=n
    torch.manual_seed(plan['seed']);net=model.SegmentPolicy(plan['schema'],plan['codes']);initial={k:v.clone() for k,v in net.state_dict().items()}
    torch.save(initial,directory/'initial.pt');opt=torch.optim.AdamW(net.parameters(),lr=plan['learning_rate'],weight_decay=plan['weight_decay'])
    fitting=[w for w in windows if w['partition']=='fit'];rng=np.random.default_rng(plan['seed']);trace=[];updates=0;clipped=0
    for epoch in range(plan['passes']):
        order=rng.permutation(len(fitting));totals=np.zeros(3);net.train()
        for j in order:
            if time.perf_counter()>=deadline:raise TimeoutError('Fitting budget exceeded')
            w=fitting[j];args=cache[w['key']];out=net(**args);support,move,goal=targets(w,discovery['endpoints'][w['key']],maps[w['payload']]['width'])
            codes=torch.tensor(discovery['labels'][w['key']]);terms=loss_terms(out,support,move,goal,codes,args['observed'])
            loss=terms[0]+plan['goal_weight']*terms[1]+(plan['code_weight'] if arm=='S01' else 0)*terms[2]
            opt.zero_grad();loss.backward();norm=torch.nn.utils.clip_grad_norm_(net.parameters(),plan['clip'])
            if not torch.isfinite(loss) or not torch.isfinite(norm):raise ValueError('Nonfinite loss/gradient')
            opt.step();updates+=1;clipped+=int(norm>plan['clip']);totals += [float(t.detach()) for t in terms]
        trace.append(dict(pass_number=epoch+1,order=order.tolist(),updates=updates,mean_losses=(totals/len(fitting)).tolist()))
        print(arm,'pass',epoch+1,'updates',updates,'movement/goal/code',trace[-1]['mean_losses'],flush=True)
    assert updates==plan['updates_per_arm']
    torch.save(dict(model=net.state_dict(),optimizer=opt.state_dict(),protocol_sha256=digest(REPORT/'protocol.json'),discovery_sha256=digest(REPORT/'discovery.json')),directory/'final.pt')
    summaries={}
    for split in ('fit','evaluation'):
        value=evaluate(net,windows,maps,cache,discovery,split,deadline);summaries[split]=dict(summary=value['summary'],groups=value['groups'])
        immutable_json(directory/(split+'-predictions.json'),value)
    immutable_json(directory/'trace.json',trace)
    bindings={str(p.relative_to(ROOT)):digest(p) for p in directory.iterdir() if p.is_file()}
    elapsed=time.perf_counter()-start
    if elapsed>=plan['seconds_cap_per_arm']:raise TimeoutError('Publication budget exceeded')
    immutable_json(REPORT/(arm+'.json'),dict(arm=arm,protocol_sha256=digest(REPORT/'protocol.json'),discovery_sha256=digest(REPORT/'discovery.json'),
        summaries=summaries,updates=updates,presentations=updates*32,seconds=elapsed,clipped_updates=clipped,unknown_fields=dict(unknown),
        parameters=sum(p.numel() for p in net.parameters()),changed_tensors=sum(not torch.equal(v,initial[k]) for k,v in net.state_dict().items()),bindings=bindings))
    print(json.dumps({k:v['summary'] for k,v in summaries.items()},indent=2))


def compare():
    a=json.loads((REPORT/'S00.json').read_text());b=json.loads((REPORT/'S01.json').read_text())
    if a['protocol_sha256']!=b['protocol_sha256'] or a['discovery_sha256']!=b['discovery_sha256']:raise ValueError('Unmatched study')
    x=a['summaries']['evaluation']['summary'];y=b['summaries']['evaluation']['summary']
    checks=dict(movement_gain=y['movement_accuracy']>=x['movement_accuracy']+.03,
        goal_within2_gain=y['goal_within2']>=x['goal_within2']+.03,goal_error=y['mean_goal_error']<x['mean_goal_error'],
        movement_nll=y['movement_nll']<=x['movement_nll']+.01)
    immutable_json(REPORT/'comparison.json',dict(control_sha256=digest(REPORT/'S00.json'),treatment_sha256=digest(REPORT/'S01.json'),
        checks=checks,passed=all(checks.values()),deltas={k:y[k]-x[k] for k in x if isinstance(x[k],(int,float)) and x[k] is not None and y[k] is not None},
        qualification='Matched code-supervision contrast on the same learned segment endpoints. No claim of verified objective discovery, improvement over historical full-command policies, or playing strength.'))
    print(json.dumps(dict(checks=checks,passed=all(checks.values())),indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('command',choices=('freeze','discover','S00','S01','compare'));a=p.parse_args()
    if a.command=='freeze':freeze()
    elif a.command=='discover':discover()
    elif a.command=='compare':compare()
    else:fit_arm(a.command)
