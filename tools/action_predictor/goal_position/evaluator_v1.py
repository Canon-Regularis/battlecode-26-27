"""Infer event-anchored approach positions; never claim access to Fish intent."""
import argparse,gzip,hashlib,heapq,json
from collections import Counter
from pathlib import Path
import numpy as np
from ..audit import cursor,immutable_json
from ..data import digest
from ..algorithmic.library import field
from ..trajectory_history.audit import ROOT,eligible_jobs,label
from ..trajectory_history.feature_sources import load_game

REPORT=ROOT/'tools/action_predictor/experiments/v42'
WORK=ROOT/'.cambc/action-predictor/v42/goals'
OLD=ROOT/'tools/action_predictor/experiments/v32'
ANCHORS=frozenset(('attack','cast_0','cast_1','submit','altar','shop','ward'))
ADMIN=frozenset(('end','priority'))
MIN_MOVES=4
MAX_ROOTS=32


def xy(value):
    if not isinstance(value,dict) or type(value.get('x')) is not int or type(value.get('y')) is not int:return None
    return (value['x'],value['y'])


def neighbors(route,p):
    w,h=route['width'],route['height'];walls=set(route['blocked'])
    for dy in (-1,0,1):
        for dx in (-1,0,1):
            q=(p[0]+dx,p[1]+dy)
            if (dx or dy) and 0<=q[0]<w and 0<=q[1]<h and q[1]*w+q[0] not in walls:yield q


def astar(route,start,goal,first_steps=None):
    """Unit-cost eight-neighbor public-terrain hypothesis; optional legal first step."""
    w,h=route['width'],route['height'];walls=set(route['blocked'])
    if any(not (0<=p[0]<w and 0<=p[1]<h) or p[1]*w+p[0] in walls for p in (start,goal)):return None
    if start==goal:return [start]
    distance=lambda p:max(abs(p[0]-goal[0]),abs(p[1]-goal[1]))
    queue=[(distance(start),0,start[1],start[0])];cost={start:0};parent={}
    while queue:
        _,g,y,x=heapq.heappop(queue);p=(x,y)
        if g!=cost[p]:continue
        if p==goal:
            path=[p]
            while path[-1]!=start:path.append(parent[path[-1]])
            return path[::-1]
        for q in neighbors(route,p):
            if p==start and first_steps is not None and q not in first_steps:continue
            value=g+1
            if value<cost.get(q,10**9):
                cost[q]=value;parent[q]=p;heapq.heappush(queue,(value+distance(q),value,q[1],q[0]))
    return None


def infer_goal(roots,index,frames,minimum_moves=MIN_MOVES,maximum_roots=MAX_ROOTS):
    """First meaningful interaction terminates the segment, even if too near."""
    current=roots[index];frame=frames.get(current['event'])
    if current['family']!='move':return None,'not_movement'
    if frame is None:return None,'current_frame_missing'
    origin=xy(frame['observation']['own'].get('position'))
    if origin is None:return None,'current_position_missing'
    own=frame['observation']['own'];position=origin;moves=[];previous_event=None
    for offset,item in enumerate(roots[index:index+maximum_roots+1]):
        step=item['step'];family=item['family']
        if previous_event is not None and cursor(item['event'])<=cursor(previous_event):return None,'event_order_error'
        previous_event=item['event']
        if step.get('actor')!=own['entity'] or step.get('phase')!=10:return None,'unmodeled_actor_boundary'
        if family in ANCHORS:
            anchor=frames.get(item['event'])
            if len(moves)<minimum_moves:return None,'first_interaction_too_near'
            if anchor is None:return None,'anchor_frame_missing'
            endpoint=xy(anchor['observation']['own'].get('position'))
            if endpoint is None:return None,'anchor_position_missing'
            if endpoint!=position:return None,'position_discontinuity'
            return dict(goal=list(endpoint),origin=list(origin),anchor_event=item['event'],anchor_family=family,
                anchor_target=step.get('to'),own_root_horizon=offset,movement_steps=len(moves),
                demonstrated_path=[list(origin),*[list(p) for p in moves]],
                interpretation='Achieved approach position before the first interaction, inferred from future replay behavior; not verified internal intent.'),'available'
        if family=='move':
            start,end=xy(step.get('from')),xy(step.get('to'))
            if start!=position or end is None:return None,'position_discontinuity'
            if max(abs(start[0]-end[0]),abs(start[1]-end[1]))!=1:return None,'nonwalking_displacement'
            position=end;moves.append(end)
        elif family=='blocked':
            # A blocked attempt does not advance the reconstructed position.
            if xy(step.get('from')) not in (None,position):return None,'position_discontinuity'
        elif family not in ADMIN:return None,'intervening_'+family
    return None,('horizon_exhausted' if len(roots)-index>maximum_roots else 'actor_suffix_ended')


def score_goal(route,frame,target):
    start=tuple(target['origin']);goal=tuple(target['goal']);actual=tuple(target['demonstrated_path'][1])
    allowed={xy(p) for p in frame['supplement']['movement']};allowed.discard(None);allowed.discard(start)
    w=route['width'];distances=field(w,route['height'],tuple(route['blocked']),goal,0)
    origin_distance=distances[start[1]*w+start[0]]
    costs={p:distances[p[1]*w+p[0]] for p in allowed if 0<=p[0]<w and 0<=p[1]<route['height']}
    best=min(costs.values(),default=10000)
    optimal={p for p,cost in costs.items() if cost==best} if best<origin_distance else set()
    path=astar(route,start,goal,allowed)
    greedy=min(allowed,key=lambda p:(max(abs(p[0]-goal[0]),abs(p[1]-goal[1])),p[1],p[0]),default=None)
    return dict(reachable=origin_distance<10000,goal_distance=int(origin_distance),
        actual_in_current_movement_mask=actual in allowed,oracle_optimal_step=actual in optimal,
        optimal_ties=len(optimal),oracle_astar_step=path is not None and len(path)>1 and path[1]==actual,
        astar_path_length=None if path is None else len(path)-1,
        oracle_greedy_step=greedy==actual,goal_equals_current=goal==start,
        path_excess=None if origin_distance>=10000 else target['movement_steps']-int(origin_distance))


def freeze():
    REPORT.mkdir(parents=True,exist_ok=True)
    records=json.loads((OLD/'window-validation.json').read_text())['games']
    selected=[r for r in records if r['partition']=='fit']
    groups=sorted({r['group'] for r in selected},key=lambda g:hashlib.sha256(('goal-position-v1:'+g).encode()).hexdigest())
    if len(groups)!=40 or len(selected)!=40:raise ValueError('Expected existing forty fitting groups')
    mapping={g:('fit' if i<32 else 'evaluation') for i,g in enumerate(groups)}
    inputs={str(OLD/'window-validation.json'):digest(OLD/'window-validation.json')}
    for r in selected:inputs.update(r['bindings'])
    immutable_json(REPORT/'evaluator-plan.json',dict(source_sha256=digest(__file__),input_bindings=inputs,
        groups=mapping,jobs=[dict(payload=r['payload'],group=r['group'],partition=mapping[r['group']]) for r in selected],
        target='First attack/cast0/cast1/submit/altar/shop/ward approach PRE position, reached after at least4successful walking steps and at most32own roots from the query. First interaction always terminates; never skip an inconvenient near interaction. Recall/teleport/cancel/unmodeled roots or position discontinuity censor.',
        population='Every retained V32 movement PRE in the forty existing fit groups. Full indexed actor chronology supplies label suffixes; no stitching sampled rows. Future anchor PRE must exist and match reconstructed walking position.',
        split='32fitting/8evaluation whole groups, hash fixed before label collection. Evaluation groups are preexposed research data, but excluded from the prospective goal-predictor optimization. No original tuning/assessment/DEV/reserved groups loaded.',
        inputs='Store current personal observation with all known entities, current supplement, and complete public map separately from future labels. Future goal/path/anchor/category/availability never enter learned inputs. Unknown entity dynamic fields must remain masked by a later encoder.',
        oracle='A* and shortest-path optimal-set agreement using inferred future goal are target-quality diagnostics, not deployable scores. Eight-neighbor unit-cost static terrain; current first step constrained by actual personal movement mask. Dynamic future blocking, danger costs and Fish tie rules remain unknown.',
        feasibility=dict(fit_rows_min=500,fit_groups_min=20,evaluation_rows_min=100,evaluation_groups_min=5,oracle_optimal_step_fraction_min=.8),
        purpose='Build and assess the inferred-goal evaluator BEFORE fitting a full-map goal predictor or integrating predicted-goal movement.',new_fits=0,optimizer_updates=0,subagents=False))


def run():
    plan=json.loads((REPORT/'evaluator-plan.json').read_text())
    if plan['source_sha256']!=digest(__file__):raise ValueError('Evaluator source changed')
    for p,value in plan['input_bindings'].items():
        if digest(p)!=value:raise ValueError('Frozen source input changed')
    WORK.mkdir(parents=True,exist_ok=False)
    records={r['payload']:r for r in json.loads((OLD/'window-validation.json').read_text())['games']}
    jobs={j['record']['raw_sha256']:j for j in eligible_jobs()};summaries=[];bindings={};all_rows=[]
    for number,selected in enumerate(plan['jobs'],1):
        payload=selected['payload'];record=records[payload]
        if record['partition']!='fit':raise ValueError('Forbidden original partition')
        loaded=load_game(jobs[payload],record);bindings.update(loaded['bindings'])
        directory=WORK/payload;directory.mkdir();immutable_json(directory/'map.json',loaded['route'])
        counts=Counter();family_counts=Counter();kept=[];labels=[]
        for actor,roots in sorted(loaded['actors'].items()):
            roots=sorted(roots,key=lambda r:cursor(r['event']))
            for index,item in enumerate(roots):
                if item['event'] not in loaded['keep'] or item['family']!='move':continue
                counts['movement_queries']+=1;frame=loaded['frames'][item['event']]
                label(item['indexed_turn'],item['root'],frame)
                target,reason=infer_goal(roots,index,loaded['frames']);counts[reason]+=1
                if target is None:continue
                score=score_goal(loaded['route'],frame,target);family_counts[target['anchor_family']]+=1
                identity=dict(payload=payload,group=selected['group'],partition=selected['partition'],actor=actor,event=item['event'])
                row=dict(**identity,**target,**score);labels.append(row);all_rows.append(row)
                # Whitelist current input sources; the target dictionary is never copied here.
                kept.append(dict(event=item['event'],pre=frame['pre'],observation=frame['observation'],supplement=frame['supplement']))
        for name,rows in [('inputs',kept),('labels',labels)]:
            with gzip.open(directory/(name+'.jsonl.gz'),'wt',encoding='utf-8') as f:
                for row in rows:f.write(json.dumps(row,separators=(',',':'))+'\n')
        summaries.append(dict(**selected,counts=dict(counts),anchor_families=dict(family_counts),
            distinct_episodes=len({(r['actor'],r['anchor_event']) for r in labels}),map_width=loaded['route']['width'],map_height=loaded['route']['height']))
        print('Goal evaluator',number,'/40',selected['partition'],dict(counts),flush=True)
    aggregate={}
    for split in ('fit','evaluation'):
        rows=[r for r in all_rows if r['partition']==split];groups={r['group'] for r in rows}
        aggregate[split]=dict(rows=len(rows),groups=len(groups),episodes=len({(r['payload'],r['actor'],r['anchor_event']) for r in rows}),
            oracle_optimal_step_fraction=sum(r['oracle_optimal_step'] for r in rows)/len(rows) if rows else None,
            oracle_astar_step_fraction=sum(r['oracle_astar_step'] for r in rows)/len(rows) if rows else None,
            oracle_greedy_step_fraction=sum(r['oracle_greedy_step'] for r in rows)/len(rows) if rows else None,
            reachable=sum(r['reachable'] for r in rows),goal_equals_current=sum(r['goal_equals_current'] for r in rows),
            actual_in_movement_mask=sum(r['actual_in_current_movement_mask'] for r in rows),
            median_goal_distance=float(np.median([r['goal_distance'] for r in rows])) if rows else None,
            median_movement_horizon=float(np.median([r['movement_steps'] for r in rows])) if rows else None)
    limits=plan['feasibility'];a,b=aggregate['fit'],aggregate['evaluation']
    checks=dict(fit_rows=a['rows']>=limits['fit_rows_min'],fit_groups=a['groups']>=limits['fit_groups_min'],
        evaluation_rows=b['rows']>=limits['evaluation_rows_min'],evaluation_groups=b['groups']>=limits['evaluation_groups_min'],
        fit_oracle_alignment=a['oracle_optimal_step_fraction'] is not None and a['oracle_optimal_step_fraction']>=limits['oracle_optimal_step_fraction_min'],
        evaluation_oracle_alignment=b['oracle_optimal_step_fraction'] is not None and b['oracle_optimal_step_fraction']>=limits['oracle_optimal_step_fraction_min'])
    outputs={str(p.relative_to(ROOT)):digest(p) for p in WORK.rglob('*') if p.is_file()}
    immutable_json(REPORT/'evaluator.json',dict(plan_sha256=digest(REPORT/'evaluator-plan.json'),games=summaries,summary=aggregate,
        feasibility_checks=checks,feasible=all(checks.values()),source_bindings=bindings,output_bindings=outputs,
        qualification='Replay-inferred approach locations, not internal Fish goals. Oracle path agreement uses future labels and is not achievable movement performance. Missing goal labels remain in coverage denominators.',new_fits=0,optimizer_updates=0,reserved_opened=0))
    print(json.dumps(dict(summary=aggregate,checks=checks),indent=2),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('command',choices=('freeze','run'));args=parser.parse_args()
    freeze() if args.command=='freeze' else run()
