"""Trace frozen destination rivals to current personal-PRE feature evidence."""
import gzip
import hashlib
import json
from pathlib import Path
import numpy as np
from ..audit import immutable_json
from ..data import digest,features
from ..targets import OFFSETS,point
from ..rich_data import candidate_grid,extra_features
from ..gradient_routing.data import load_subset
from ..trajectory_history.assemble import ROOT,WORK as DATA_WORK,REPORT as DATA_REPORT
from ..trajectory_history.audit import eligible_jobs
from ..trajectory_history.feature_sources import load_game
from ..priority_broad.guard import committed_sources
from ..priority_regularized.safety import dependency_files

REPORT=ROOT/'tools/action_predictor/experiments/v37'
WORK=ROOT/'.cambc/action-predictor/v37'
PREVIOUS=ROOT/'tools/action_predictor/experiments/v36'
GROUPS={'offset':[0,1],'move_length':[2],'support':[3,5],'static_destination':[4,6],
        'entity_distances':[7,8,9],'entity_counts':[10,11,12],'entity_hp':[13,14,15],
        'altar_distance':[16],'own_tile':[17],'previous_vector':[18,19],
        'task_channels':[4,6,7,8,9,10,11,12,13,14,15,16],'all_except_xy':list(range(2,20))}


def source_gate():
    return committed_sources(ROOT,dependency_files(ROOT,('tools.action_predictor.destination_audit.audit',
        'tools.action_predictor.destination_audit.test_audit')))


def freeze():
    commit,sources=source_gate();bindings={}
    def bind(p):bindings[str(Path(p).resolve())]=digest(p)
    prior=json.loads((PREVIOUS/'protocol.json').read_text())
    for key,expected in prior['sources'].items():
        if digest(ROOT/key)!=expected:raise ValueError('Prior source changed')
    for name in ('protocol.json','selection.json','R00.json','R01.json','R00-review.json','R01-review.json'):
        bind(PREVIOUS/name)
    for arm in ('R00','R01'):
        result=json.loads((PREVIOUS/f'{arm}.json').read_text())
        review=json.loads((PREVIOUS/f'{arm}-review.json').read_text())
        if review['verdict']!='APPROVE' or review['result_sha256']!=digest(PREVIOUS/f'{arm}.json'):
            raise ValueError('Actual result review not bound')
        for filename in ('final-movement.npz','final-predictions.npz'):
            p=ROOT/f'.cambc/action-predictor/v36/runs/{arm}/{filename}'
            if digest(p)!=result['bindings'][str(p.relative_to(ROOT))]:raise ValueError('Forecast changed')
            bind(p)
    bind(DATA_REPORT/'assembly.json');bind(DATA_WORK/'normalizer.npz');bind(DATA_REPORT/'window-validation.json')
    manifest=json.loads((DATA_REPORT/'assembly.json').read_text())
    for game in manifest['games']:
        if game['partition']!='fit':continue
        for key,value in game['input_bindings'].items():
            if digest(key)!=value:raise ValueError('Personal source changed')
            bind(key)
        for name in ('data.npz','rows.json'):bind(DATA_WORK/'games'/game['payload']/name)
    immutable_json(REPORT/'plan.json',dict(source_commit=commit,sources=sources,inputs=bindings,
        population='All 2669 direction-change rows in the already frozen V36 fitting windows, all40groups. R00 primary, R01 descriptive replication; do not select a preferred checkpoint or cohort.',
        rival='Highest archived conditional-log-probability outcome excluding gold and exact previous displacement, tie broken by original vocabulary index. Retain special/unsupported rivals in accounting; trace tile pairs separately. This is target-conditioned diagnosis, not a decoder or achieved policy accuracy.',
        comparisons='Exact stored float16 candidate-channel distinctions; signed gold/rival contrasts; 3x3 destination-neighborhood blocked/boundary pattern, with in-grid coverage; nearest entity sets and their coverage in current nearest-three summaries; Chebyshev attack-range boundaries for represented versus omitted entities. Range geometry is not attack legality or preferred movement.',
        input_scope='Only current personal PRE frames and public route for fitting groups; reconstruct current x/grid/valid exactly. No new frames, outcomes, future labels, model training or new forecasts.',
        examples='At most one R00 rival-outranks-gold example per fitting group, chosen by fixed SHA256 of payload/event after cohort definition. Examples are descriptive, not a random sample or evidence of intent.',
        decision='If distinctions already reside in current context, do not call them missing inputs. If they lie in other grid cells, identify the pointwise readout restriction and prior V6 evidence. If attributes of omitted entities differ, quantify current-summary coverage without claiming full-history insufficiency. Any new representation intervention needs a matched separately reviewed protocol; no automatic allocation threshold.',
        limits='All destination offsets are distinct; equality of a selected feature subset is never a full-input collision or an achievable-accuracy ceiling. Candidate ranking cannot establish why Fish chose a destination. Preexposed fitting groups and observed histories remain.',new_fits=0,optimizer_updates=0))


def rivals(logp,gold,last):
    score=logp.copy();rows=np.arange(len(gold));score[rows,gold]=-np.inf;score[rows,last]=-np.inf
    candidate=score.argmax(1)
    return candidate,logp[rows,candidate]-logp[rows,gold]


def category(e,team):
    return 2 if e['entity']['kind']==2 else int(e.get('team')==team)


def entity_trace(obs,gold_xy,rival_xy):
    own=obs['own'];origin=np.array([own['position'][k] for k in ('x','y')]);answer={}
    visible=[e for e in obs['entities'] if e.get('known',0)&1 and point(e.get('position')) and e.get('health',0)>0]
    for code,name in enumerate(('enemy','ally','camp')):
        units=[e for e in visible if category(e,own['team'])==code]
        if not units:
            answer[name]=dict(available=False);continue
        xy=np.array([[e['position'][k] for k in ('x','y')] for e in units]);relative=xy-origin
        own_distance=np.abs(relative).max(1);gd=np.abs(xy-gold_xy).max(1);rd=np.abs(xy-rival_xy).max(1)
        # Match features(): only champion/camp kinds, stable sort by distance,dx,dy.
        ranked=sorted([i for i,e in enumerate(units) if e['entity']['kind'] in (1,2)],
            key=lambda i:(own_distance[i],relative[i,0],relative[i,1]))
        top=set(ranked[:3]);gn=set(np.flatnonzero(gd==gd.min()));rn=set(np.flatnonzero(rd==rd.min()))
        ranges=[i for i,e in enumerate(units) if isinstance(e.get('attackRange'),(int,float)) and e['attackRange']>=0]
        differences={i for i in ranges if (gd[i]<=units[i]['attackRange'])!=(rd[i]<=units[i]['attackRange'])}
        answer[name]=dict(available=True,living_known=len(units),current_top3=len(top),
            nearest_distance_equal=bool(gd.min()==rd.min()),nearest_entities_differ=gn!=rn,
            nearest_union_fully_in_current_top3=(gn|rn)<=top,
            raw_nearest_distance_clipped_collision=bool(min(gd.min(),64)==min(rd.min(),64) and gd.min()!=rd.min()),
            represented_range_boundary_diff=bool(differences&top),
            omitted_range_boundary_diff=bool(differences-top))
    return answer


def neighborhood(route,xy):
    w,h=route['width'],route['height'];blocked=set(route['blocked']);values=[]
    for dy in (-1,0,1):
        for dx in (-1,0,1):
            if dx==dy==0:continue
            x,y=int(xy[0]+dx),int(xy[1]+dy)
            values.append(2 if not(0<=x<w and 0<=y<h) else int(y*w+x in blocked))
    return values


def pair_trace(frame,route,grid,gold,rival):
    origin=np.array([frame['observation']['own']['position'][k] for k in ('x','y')])
    gxy=origin+OFFSETS[gold];rxy=origin+OFFSETS[rival]
    equal={name:bool(np.array_equal(grid[gold,cols],grid[rival,cols])) for name,cols in GROUPS.items()}
    entities=entity_trace(frame['observation'],gxy,rxy)
    for code,name in enumerate(('enemy','ally','camp')):
        e=entities[name]
        e['candidate_summary_equal']=bool(np.array_equal(grid[gold,[7+code,10+code,13+code]],grid[rival,[7+code,10+code,13+code]]))
    gp,rp=neighborhood(route,gxy),neighborhood(route,rxy)
    inside=bool(np.abs(OFFSETS[[gold,rival]]).max()<=7)
    return dict(equal=equal,entities=entities,
        neighbor_patterns_differ=gp!=rp,neighbor_counts_differ=sum(v>0 for v in gp)!=sum(v>0 for v in rp),
        both_neighborhoods_inside_candidate_grid=inside,
        gold_neighbor_obstacles=sum(v>0 for v in gp),rival_neighbor_obstacles=sum(v>0 for v in rp),
        gold_offset=OFFSETS[gold].tolist(),rival_offset=OFFSETS[rival].tolist(),
        signed_candidate_difference=(grid[gold].astype(float)-grid[rival].astype(float)).tolist())


def summarize(records):
    output={}
    for arm in ('R00','R01'):
        rows=[r for r in records if r['arm']==arm];scopes={}
        for name,selected in [('all_changes',rows),('rival_outranks_gold',[r for r in rows if r['margin']>0])]:
            tiles=[r for r in selected if 'trace' in r];equal={k:sum(r['trace']['equal'][k] for r in tiles) for k in GROUPS}
            entity={}
            for cat in ('enemy','ally','camp'):
                items=[r['trace']['entities'][cat] for r in tiles];present=[e for e in items if e['available']]
                collisions=[e for e in present if e['candidate_summary_equal'] and e['nearest_entities_differ']]
                entity[cat]=dict(available=len(present),same_summary_different_nearest_entities=len(collisions),
                    those_with_all_nearest_entities_in_current_top3=sum(e['nearest_union_fully_in_current_top3'] for e in collisions),
                    those_with_some_nearest_entities_omitted=len(collisions)-sum(e['nearest_union_fully_in_current_top3'] for e in collisions),
                    represented_range_boundary_diff=sum(e['represented_range_boundary_diff'] for e in present),
                    omitted_range_boundary_diff=sum(e['omitted_range_boundary_diff'] for e in present),
                    distance_clipping_collisions=sum(e['raw_nearest_distance_clipped_collision'] for e in present))
            scopes[name]=dict(rows=len(selected),tile_pairs=len(tiles),special_rivals=sum(r['rival']>=289 for r in selected),
                unsupported_tile_rivals=sum(not r['rival_supported'] for r in tiles),equal_channels=equal,entities=entity,
                same_static_destination_different_neighborhood=sum(r['trace']['equal']['static_destination'] and r['trace']['neighbor_patterns_differ'] for r in tiles),
                same_static_destination_different_neighborhood_fully_inside_grid=sum(r['trace']['equal']['static_destination'] and r['trace']['neighbor_patterns_differ'] and r['trace']['both_neighborhoods_inside_candidate_grid'] for r in tiles))
        output[arm]=scopes
    return output


def run():
    _,sources=source_gate();plan=json.loads((REPORT/'plan.json').read_text())
    if sources!=plan['sources']:raise ValueError('Frozen audit source changed')
    for key,expected in plan['inputs'].items():
        if digest(key)!=expected:raise ValueError('Frozen audit input changed: '+key)
    if WORK.exists():raise FileExistsError('Preserve prior audit')
    data=load_subset();raw=data['arrays'];records=[];by_source={}
    for arm in ('R00','R01'):
        with np.load(ROOT/f'.cambc/action-predictor/v36/runs/{arm}/final-movement.npz') as z:
            ids=z['ids'];choose=raw['direction'][ids]==3;ids=ids[choose];lp=z['move_logp'][choose]
        gold=raw['py'][ids];prior=raw['grid'][ids,:,18]
        if len(ids)!=2669 or not np.all(prior.max(1)>0):raise ValueError('Changed cohort')
        last=prior.argmax(1);rival,margin=rivals(lp,gold,last)
        if not np.all(raw['y'][ids]==8) or not np.all(gold!=last):raise ValueError('Not recorded movement changes')
        for i,row in enumerate(ids):
            record=dict(arm=arm,row=int(row),source_id=int(data['source_ids'][row]),group=int(data['group'][row]),
                gold=int(gold[i]),last=int(last[i]),rival=int(rival[i]),margin=float(margin[i]),
                rival_supported=bool(rival[i]<289 and raw['valid'][row,rival[i]] and raw['grid'][row,rival[i],5]>0))
            records.append(record);by_source.setdefault(record['source_id'],[]).append(record)
    manifest=json.loads((DATA_REPORT/'assembly.json').read_text());jobs={j['record']['raw_sha256']:j for j in eligible_jobs()}
    validation={r['payload']:r for r in json.loads((DATA_REPORT/'window-validation.json').read_text())['games']}
    with np.load(DATA_WORK/'normalizer.npz') as z:mean,std=z['mean'],z['std']
    offset=0;checked=0;game_count=0
    for game in manifest['games']:
        if game['partition']!='fit':continue
        identities=json.loads((DATA_WORK/'games'/game['payload']/'rows.json').read_text())
        selected=[(i,by_source[offset+i]) for i in range(game['rows']) if offset+i in by_source];offset+=game['rows']
        if not selected:continue
        loaded=load_game(jobs[game['payload']],validation[game['payload']]);route=loaded['route']
        for key,expected in loaded['bindings'].items():
            if plan['inputs'].get(str(Path(key).resolve()))!=expected:raise ValueError('Unbound personal source')
        for i,pairs in selected:
            frame=loaded['frames'][identities[i]['event']];row=pairs[0]['row'];last=OFFSETS[pairs[0]['last']]
            basic,_=features(frame['observation']);extra,_=extra_features(frame['observation'],frame['supplement'],route,frame['round'])
            np.testing.assert_array_equal((np.r_[basic,extra]-mean)/std,raw['x'][row])
            grid,valid,_=candidate_grid(frame['observation'],frame['supplement'],route,last)
            grid=grid.astype(np.float16);np.testing.assert_array_equal(grid,raw['grid'][row]);np.testing.assert_array_equal(valid,raw['valid'][row]);checked+=1
            for record in pairs:
                record['payload']=game['payload'];record['event']=identities[i]['event']
                if record['rival']<289:record['trace']=pair_trace(frame,route,grid,record['gold'],record['rival'])
        game_count+=1;print('Audited fitting group',game_count,'of40',flush=True)
    if checked!=2669 or game_count!=40:raise ValueError('Incomplete PRE coverage')
    examples=[]
    for group in sorted(set(r['group'] for r in records)):
        candidates=[r for r in records if r['arm']=='R00' and r['group']==group and r['margin']>0 and 'trace' in r]
        if candidates:examples.append(min(candidates,key=lambda r:hashlib.sha256((r['payload']+':'+r['event']).encode()).hexdigest()))
    WORK.mkdir(parents=True)
    archive=WORK/'pairs.jsonl.gz'
    with gzip.open(archive,'wt',encoding='utf-8') as f:
        for r in records:f.write(json.dumps(r,separators=(',',':'))+'\n')
    immutable_json(REPORT/'audit.json',dict(plan_sha256=digest(REPORT/'plan.json'),sources=sources,
        archive=str(archive.relative_to(ROOT)),archive_sha256=digest(archive),current_PRE_parity_rows=checked,
        groups=game_count,results=summarize(records),examples=examples,new_fits=0,optimizer_updates=0,
        limitations=plan['limits']))
    print('Destination discrimination audit complete; no fitting or new forecasts',flush=True)


if __name__=='__main__':
    import sys
    {'freeze':freeze,'run':run}[sys.argv[1]]()
