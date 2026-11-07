"""R01 fixed movement diagnostics; oracles are explanations, not predictions."""
import json
from pathlib import Path
from collections import Counter,defaultdict
import numpy as np
from .saved import ROOT,OLD,WORK,REPORT,read,arrays,joint
from ..algorithmic.library import field,dist,xy
from ..observation_data import compact_supplement
from ..rich_data import read_turns
from ..audit import immutable_json
from ..data import digest

def hypotheses(obs,supp,route,history):
    p=xy(obs['own']['position']);own=obs['own'];visible=[e for e in obs['entities'] if e.get('known',0)&1 and e.get('position') and e.get('health',0)>0];camps=[e for e in visible if e['entity']['kind']==2];enemies=[e for e in visible if e['entity']['kind']==1 and e['team']!=own['team']]
    def entity(es,hp=False):return xy(min(es,key=lambda e:(e['health'] if hp else dist(p,xy(e['position'])),e['position']['y'],e['position']['x']))['position']) if es else None
    bank=min(map(xy,route['altars']),key=lambda g:(dist(p,g),g[1],g[0]),default=None);s=route['spawns'][own['team']];home=min(((x,y) for y in range(s['minY'],s['maxY']) for x in range(s['minX'],s['maxX'])),key=lambda g:(dist(p,g),g[1],g[0]));goals=[entity(camps),entity(camps,True),entity(enemies),bank,home];radii=[int(own.get('attackRange',1))]*3+[int(route['submit_range']),0];steps=sorted({xy(q) for q in supp['movement']}-{p});optimal=[set(),set()];progress=set();predictions={};at_goal=False
    if not steps:return dict(optimal=optimal,progress=progress,predictions={},at_goal=False,visible_camps=len(camps))
    prior=[]
    for row in history:
        if row[8]>0 and row[15]<=.030001:
            end=np.array(p)+np.rint(row[16:18]*32).astype(int);delta=np.rint(row[18:20]*8).astype(int);prior.append((tuple(end-delta),tuple(end)))
    scores=[]
    for k,(g,radius) in enumerate(zip(goals,radii)):
        if g is None:scores.append(-1e9);continue
        scores.append(sum(.7**age*(dist(a,g)-dist(b,g)) for age,(a,b) in enumerate(reversed(prior[-5:]))))
        origin=max(0,dist(p,g)-radius);at_goal|=origin==0
        def dc(q):return max(0,dist(q,g)-radius)
        progress.update(q for q in steps if dc(q)<origin)
        distances=[dc(q) for q in steps];best=min(distances)
        if best<origin:optimal[0].update(q for q,d in zip(steps,distances) if d==best)
        f=field(route['width'],route['height'],tuple(route['blocked']),g,radius);cost=[f[q[1]*route['width']+q[0]] for q in steps];bestfield=min(cost)
        if bestfield<f[p[1]*route['width']+p[0]]:optimal[1].update(q for q,d in zip(steps,cost) if d==bestfield)
        for planner,values in [('greedy',distances),('field',cost)]:
            for tie in ('yx','xy'):
                q=min(zip(steps,values),key=lambda item:(item[1],*(item[0][::-1] if tie=='yx' else item[0])))[0]
                predictions[(k,planner,tie)]=q if min(values)<(origin if planner=='greedy' else f[p[1]*route['width']+p[0]]) else None
    forecasts={}
    for planner in ('greedy','field'):
        for tie in ('yx','xy'):
            forecasts[f'nearest_camp/{planner}/{tie}']=predictions.get((0,planner,tie))
            if prior:
                selected=min(range(5),key=lambda k:(-scores[k],dist(p,goals[k]) if goals[k] else 100000,k));forecasts[f'past5_goal/{planner}/{tie}']=predictions.get((selected,planner,tie))
            else:forecasts[f'past5_goal/{planner}/{tie}']=None
    return dict(optimal=optimal,progress=progress,predictions=forecasts,at_goal=at_goal,visible_camps=len(camps),history_available=bool(prior))

def run():
    plan=read(REPORT/'R00-plan.json');assert 'past5' in plan['movement'];jobs=read(OLD/'v7/jobs.json');chosen=[]
    for version in ('2.0.0','3.0.0'):chosen.extend([j for j in jobs if j['split']=='train' and j['record']['engine_version']==version][:12])
    chosen.extend(j for j in jobs if j['split']=='validation');natural=np.load(OLD/'v9/frequency/natural-mask.npy');raw={};pred={};candidates={};aux={}
    for split,path in [('train',OLD/'v5/combined-train.npz'),('validation',OLD/'v4/validation.npz')]:
        raw[split]=arrays(path,['y','py','group']);pred[split]=arrays(OLD/f'v9/runs/G00/{split}-predictions.npz');candidates[split]=np.load(OLD/f'v10/{split}-candidates.npy',mmap_mode='r');aux[split]={k:np.load(OLD/f'v7/{split}-{k}.npy',mmap_mode='r') for k in ('direction','available','near_obstacle','visible_change')}
    rows=[];bindings=[]
    for number,job in enumerate(chosen,1):
        split=job['split'];record=job['record'];supps={}
        for suffix in ('supplement','augmentation'):
            p=Path(job['work'])/suffix/record['raw_sha256']/'pre.jsonl'
            if not p.exists():continue
            for line in p.open():
                r=json.loads(line)
                if r['record']=='map':route=r['route']
                elif r['record']=='pre':supps[r['id']]=compact_supplement(r)
        with np.load(job['shard']) as z:history=z['history']
        i=0
        for t in read_turns(job['manifest'],record):
            for d in t['decisions']:
                idx=job['offset']+i;h=history[i];i+=1
                if raw[split]['y'][idx]!=8 or (split=='train' and not natural[idx]):continue
                # Score only after constructing all hypotheses without answer.
                result=hypotheses(d['observation'],supps[d['id']],route,h);actual=xy(d['label']['to']);point=int(raw[split]['py'][idx]);lib=candidates[split][idx,1];covered=bool(((lib[:,0]==8)&(lib[:,1]==point)).any());greedy=actual in result['optimal'][0];terrain=actual in result['optimal'][1];progress=actual in result['progress'];correct=bool(pred[split]['prediction'][idx]==8 and pred[split]['proposed_coordinate'][idx]==point)
                category='covered_by_fixed_library' if covered else 'alternative_optimal_greedy_tie' if greedy else 'terrain_field_optimum_only' if terrain else 'progress_but_not_declared_optimum' if progress else 'no_progress_to_current_goal_family'
                rows.append(dict(split=split,index=idx,group=int(raw[split]['group'][idx]),engine=record['engine_version'],direction=int(aux[split]['direction'][idx]),G00_joint=correct,G00_true_family_parameter=bool(pred[split]['coordinate'][idx]==point),point_library=covered,greedy_optimum_oracle=greedy,terrain_optimum_oracle=terrain,progress_oracle=progress,relationship=category,at_any_goal=result['at_goal'],history_available=result['history_available'],available=int(aux[split]['available'][idx]),near_obstacle=bool(aux[split]['near_obstacle'][idx]),visible_change=int(aux[split]['visible_change'][idx]),visible_camps=result['visible_camps'],forecasts={name:dict(available=q is not None,correct=q==actual) for name,q in result['predictions'].items()}))
        bindings.append(dict(raw=record['raw_sha256'],split=split,rows=job['rows'],turns_sha256=record.get('augmented_sha256',record['turns_sha256']),shard_sha256=job['shard_sha256']))
        if number%10==0 or number==len(chosen):print('R01 geometry',number,'/',len(chosen),flush=True)
    summaries={}
    for split in ('train','validation'):
        selected=[r for r in rows if r['split']==split];contexts={'all':selected,'continuing':[r for r in selected if r['direction']==2],'change':[r for r in selected if r['direction']==3],'G00_errors':[r for r in selected if not r['G00_joint']]};summary={}
        for name,rs in contexts.items():
            summary[name]=dict(rows=len(rs),relationships=dict(Counter(r['relationship'] for r in rs)),G00_joint=sum(r['G00_joint'] for r in rs),G00_true_family_parameter=sum(r['G00_true_family_parameter'] for r in rs),greedy_optimum_oracle=sum(r['greedy_optimum_oracle'] for r in rs),terrain_optimum_oracle=sum(r['terrain_optimum_oracle'] for r in rs),progress_oracle=sum(r['progress_oracle'] for r in rs),at_any_goal=sum(r['at_any_goal'] for r in rs),fixed_forecasts={key:dict(available=sum(r['forecasts'][key]['available'] for r in rs),correct=sum(r['forecasts'][key]['correct'] for r in rs)) for key in (rs[0]['forecasts'] if rs else [])})
        summaries[split]=summary
    # Entire naturalTRAIN/allDEV context rates reuse saved outputs, no replay work.
    all_contexts={}
    for split in raw:
        base=(raw[split]['y']==8)&(natural if split=='train' else True);all_contexts[split]={}
        for name,m in [('all',np.ones(len(base),bool)),('history16',aux[split]['available']==16),('history_lt16',aux[split]['available']<16),('near_obstacle',aux[split]['near_obstacle'].astype(bool)),('away_obstacle',~aux[split]['near_obstacle'].astype(bool)),('visible_set_changed',aux[split]['visible_change']==2),('visible_set_same',aux[split]['visible_change']==1)]:
            for context,code in [('continuing',2),('change',3)]:
                mask=base&m&(aux[split]['direction']==code);j=(pred[split]['prediction']==8)&(pred[split]['proposed_coordinate']==raw[split]['py']);param=pred[split]['coordinate']==raw[split]['py'];all_contexts[split][name+'/'+context]=dict(rows=int(mask.sum()),joint=int(j[mask].sum()),true_family_destination=int(param[mask].sum()))
    out=WORK/'R01-row-diagnostics.jsonl';assert not out.exists();out.write_text(''.join(json.dumps(r)+'\n' for r in rows),encoding='utf-8');immutable_json(REPORT/'R01-movement.json',dict(plan_sha256=digest(REPORT/'R00-plan.json'),source_sha256=digest(__file__),summaries=summaries,full_context_rates=all_contexts,bindings=bindings,row_diagnostics_sha256=digest(out),interpretation='Relationship partitions are diagnostic compatibility with declared5goals/costs,not trueFishintent or definitive causalattribution. Optimal tie/progress sets are broader oracle diagnostics,not actual candidate-librarycoverage. Uniform8neighbourterrainfield not verified historical route cost. Fixedpast5goal scoring is causal earliertrajectory proxy,not recoveredpersistentstate. All originalDEVmovement rows scored;TRAINgeometry is24game naturalrows subset.',new_fits=0,reserved_opened=0))
    print(json.dumps(summaries,indent=2),flush=True)

if __name__=='__main__':run()
