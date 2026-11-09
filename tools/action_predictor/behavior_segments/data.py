"""Cached personal PREs and complete actor-turn chronology; no named goals."""
import argparse,gzip,hashlib,json
from collections import Counter
from itertools import groupby
from pathlib import Path
import numpy as np
from ..audit import cursor,immutable_json
from ..data import digest
from ..trajectory_history.audit import ROOT,eligible_jobs,label
from ..trajectory_history.feature_sources import load_game
from ..goal_position.evaluator import xy

REPORT=ROOT/'tools/action_predictor/experiments/v43/r2'
WORK=ROOT/'.cambc/action-predictor/v43/r2'
OLD=ROOT/'tools/action_predictor/experiments/v32'
SPLIT=ROOT/'tools/action_predictor/experiments/v42/r2/evaluator-plan.json'
FAMILIES=('move','attack','cast_0','cast_1','end','priority','recall','submit','shop','ward','cancel','altar','teleport','blocked','<unknown>')
ADMIN=frozenset(('priority','cancel','recall','end'))
FEATURES=[f'commands/{f}' for f in FAMILIES]+['walk_length','net_walk_distance','health_change','gems_change','gold_change','altar_distance_change','camp_distance_change','enemy_distance_change']


def distance(frame,route,kind):
    own=frame['observation']['own'];p=xy(own.get('position'))
    if p is None:return None
    if kind=='altar':targets=list(map(xy,route['altars']))
    else:
        targets=[xy(e['position']) for e in frame['observation']['entities'] if e.get('known',0)&1 and e.get('position') and e.get('health',0)>0 and
            (e['entity']['kind']==2 if kind=='camp' else e['entity']['kind']==1 and e.get('team')!=own['team'])]
    return min((max(abs(p[0]-q[0]),abs(p[1]-q[1])) for q in targets),default=None)


def descriptor(roots,frame,following,route):
    counts=Counter(x['family'] for x in roots);y=[np.log1p(counts[f]) for f in FAMILIES];mask=[1.]*len(y)
    moves=[x['step'] for x in roots if x['family']=='move']
    dx=sum(x['to']['x']-x['from']['x'] for x in moves);dy=sum(x['to']['y']-x['from']['y'] for x in moves)
    y += [np.log1p(len(moves)),np.log1p(max(abs(dx),abs(dy)))];mask += [1.,1.]
    for key in ('health','gems','gold'):
        a=frame['supplement']['own'].get(key) if frame else None;b=following['supplement']['own'].get(key) if following else None
        present=a is not None and b is not None;delta=b-a if present else 0
        y.append(np.sign(delta)*np.log1p(abs(delta)));mask.append(float(present))
    for kind in ('altar','camp','enemy'):
        a=distance(frame,route,kind) if frame else None;b=distance(following,route,kind) if following else None
        present=a is not None and b is not None;delta=b-a if present else 0
        y.append(np.sign(delta)*np.log1p(abs(delta)));mask.append(float(present))
    return y,mask


def freeze():
    source=json.loads(SPLIT.read_text());REPORT.mkdir(parents=True,exist_ok=True)
    immutable_json(REPORT/'data-plan.json',dict(split_sha256=digest(SPLIT),jobs=source['jobs'],
        source_sha256=digest(__file__),window_turns=32,windows_per_group=8,minimum_observed_queries=8,
        revision='V1 stopped at group23 because no32turn block had16observed queries. No fit ran. R2 retains exactly the same groups,32turn blocks andhash ordering, but requires8observed queries and explicitly masks missing observations; full indexed turns are never stitched.',
        selection='All consecutive full-index own turns for actors with Fish personal frames. First nonadministrative decision per turn is the query when its exact PRE exists. Nonoverlapping32turn blocks, at least8available query PREs, lowest fixed identity hashes; up to8per group, no replacement for missing groups.',
        missing='Missing turn observations remain explicit masks; all actual own-turn command counts remain available retrospectively. No turn is removed inside a window. Windows reset history. The final segment is right-censored for endpoint evaluation.',
        features=FEATURES,causality='Current query receives only its PRE and the preceding turn descriptor. Previous descriptor ends at current PRE; current descriptor and offline codes are targets only. Entire current map and known entities retained.',
        scope='Same32fit/8evaluation groups asV42, all previously exposed research. No original tuning/assessment/reserved payloads. No engine, download, runtime modification, or subagents.'))


def assemble():
    plan=json.loads((REPORT/'data-plan.json').read_text())
    if digest(__file__)!=plan['source_sha256'] or digest(SPLIT)!=plan['split_sha256']:raise ValueError('Data plan changed')
    directory=WORK/'data';directory.mkdir(parents=True,exist_ok=False)
    records={r['payload']:r for r in json.loads((OLD/'window-validation.json').read_text())['games']}
    jobs={j['record']['raw_sha256']:j for j in eligible_jobs()};summaries=[];bindings={};windows=[]
    for number,s in enumerate(plan['jobs'],1):
        payload=s['payload'];record=records[payload]
        if record['partition']!='fit':raise ValueError('Original partition violation')
        v=load_game(jobs[payload],record);bindings.update(v['bindings']);candidates=[];actors={f['actor'] for f in v['frames'].values()}
        for actor in sorted(actors):
            roots=sorted(v['actors'][actor],key=lambda r:cursor(r['event']))
            turns=[list(rs) for _,rs in groupby(roots,key=lambda r:r['turn'])];frames=[];queries=[]
            for rs in turns:
                q=next((x for x in rs if x['family'] not in ADMIN),None);f=v['frames'].get(q['event']) if q else None
                if f:label(q['indexed_turn'],q['root'],f)
                queries.append(q);frames.append(f)
            for start in range(0,len(turns)-31,32):
                if sum(f is not None for f in frames[start:start+32])<plan['minimum_observed_queries']:continue
                key=f"{payload}:{actor}:{turns[start][0]['event']}";candidate=dict(**s,actor=actor,start_turn=start,key=key,steps=[])
                for i in range(start,start+32):
                    rs=turns[i];f=frames[i];following=frames[i+1] if i+1<len(frames) else None;q=queries[i]
                    y,m=descriptor(rs,f,following,v['route'])
                    # Do not let the final window descriptor inspect outside its right edge.
                    if i==start+31:y,m=descriptor(rs,f,None,v['route'])
                    previous,previous_mask=descriptor(turns[i-1],frames[i-1],f,v['route']) if i>start else ([0.]*len(FEATURES),[0.]*len(FEATURES))
                    if f and i>start and cursor(turns[i-1][-1]['event'])>cursor(f['pre']):raise ValueError('History crosses query PRE')
                    movement=None
                    if f and q['family']=='move':movement=[q['step']['to']['x']-q['step']['from']['x'],q['step']['to']['y']-q['step']['from']['y']]
                    candidate['steps'].append(dict(event=q['event'] if q else rs[0]['event'],round=rs[0]['round'],
                        observed=f is not None,input=None if f is None else dict(observation=f['observation'],supplement=f['supplement']),
                        previous=previous,previous_mask=previous_mask,behavior=y,behavior_mask=m,movement=movement))
                candidates.append(candidate)
        chosen=sorted(candidates,key=lambda w:hashlib.sha256(('segment-v1:'+w['key']).encode()).hexdigest())[:plan['windows_per_group']]
        if not chosen:raise ValueError('No windows in group; no replacement authorized')
        windows.extend(chosen);immutable_json(directory/(payload+'-map.json'),v['route'])
        summaries.append(dict(**s,candidates=len(candidates),selected=len(chosen),observed=sum(x['observed'] for w in chosen for x in w['steps'])))
        print('Segment data',number,'/40',s['partition'],'windows',len(chosen),'of',len(candidates),flush=True)
    with gzip.open(directory/'windows.jsonl.gz','wt',encoding='utf-8') as f:
        for w in windows:f.write(json.dumps(w,separators=(',',':'))+'\n')
    outputs={str(p.relative_to(ROOT)):digest(p) for p in directory.iterdir() if p.is_file()}
    immutable_json(REPORT/'data.json',dict(plan_sha256=digest(REPORT/'data-plan.json'),groups=summaries,
        splits={split:dict(windows=sum(w['partition']==split for w in windows),observed=sum(x['observed'] for w in windows if w['partition']==split for x in w['steps'])) for split in ('fit','evaluation')},
        source_bindings=bindings,output_bindings=outputs))


def load():
    with gzip.open(WORK/'data/windows.jsonl.gz','rt',encoding='utf-8') as f:windows=list(map(json.loads,f))
    maps={p.stem[:-4]:json.loads(p.read_text()) for p in (WORK/'data').glob('*-map.json')}
    return windows,maps


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('command',choices=('freeze','assemble'));a=p.parse_args()
    freeze() if a.command=='freeze' else assemble()
