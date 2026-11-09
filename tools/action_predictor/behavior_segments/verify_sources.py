"""Bounded raw-cache reconstruction across both engine versions; no fitting."""
import hashlib,json
from collections import Counter
from itertools import groupby
import numpy as np
from .data import ROOT,REPORT,OLD,ADMIN,FAMILIES,descriptor,load
from ..trajectory_history.audit import eligible_jobs
from ..trajectory_history.feature_sources import load_game
from ..audit import cursor,immutable_json
from ..data import digest


def run():
    windows,maps=load();records={r['payload']:r for r in json.loads((OLD/'window-validation.json').read_text())['games']}
    jobs={j['record']['raw_sha256']:j for j in eligible_jobs()};chosen={}
    for w in windows:
        if w['partition']=='fit':chosen.setdefault(json.dumps(records[w['payload']]['engine'],sort_keys=True),w['payload'])
    reports=[]
    for engine,payload in chosen.items():
        v=load_game(jobs[payload],records[payload]);assert v['route']==maps[payload];candidates=[];lookup={}
        for actor in sorted({f['actor'] for f in v['frames'].values()}):
            roots=sorted(v['actors'][actor],key=lambda x:cursor(x['event']));turns=[list(rs) for _,rs in groupby(roots,key=lambda x:x['turn'])]
            queries=[next((x for x in rs if x['family'] not in ADMIN),None) for rs in turns]
            frames=[v['frames'].get(q['event']) if q else None for q in queries];lookup[actor]=(turns,queries,frames)
            for start in range(0,len(turns)-31,32):
                if sum(f is not None for f in frames[start:start+32])>=8:candidates.append(f"{payload}:{actor}:{turns[start][0]['event']}")
        expected=sorted(candidates,key=lambda k:hashlib.sha256(('segment-v1:'+k).encode()).hexdigest())[:8]
        selected=[w for w in windows if w['payload']==payload];assert [w['key'] for w in selected]==expected
        n=0
        for w in selected:
            turns,queries,frames=lookup[w['actor']];start=w['start_turn']
            for offset,s in enumerate(w['steps']):
                i=start+offset;rs=turns[i];q=queries[i];f=frames[i];next_frame=frames[i+1] if offset<31 and i+1<len(frames) else None
                assert s['event']==(q['event'] if q else rs[0]['event'])
                assert s['input']==(dict(observation=f['observation'],supplement=f['supplement']) if f else None)
                y,m=descriptor(rs,f,next_frame,v['route']);np.testing.assert_array_equal(y,s['behavior']);np.testing.assert_array_equal(m,s['behavior_mask'])
                counts=Counter(r['family'] for r in rs);np.testing.assert_allclose(np.expm1(y[:15]),[counts[k] for k in FAMILIES],atol=1e-12)
                if offset:
                    py,pm=descriptor(turns[i-1],frames[i-1],f,v['route']);assert py==s['previous'] and pm==s['previous_mask']
                    if f:assert cursor(turns[i-1][-1]['event'])<=cursor(f['pre'])
                else:assert not any(s['previous_mask'])
                n+=1
        reports.append(dict(engine=json.loads(engine),payload=payload,selected_windows=len(selected),reconstructed_turns=n))
    assert len(reports)==2
    immutable_json(REPORT/'source-probe.json',dict(source_sha256=digest(__file__),data_sha256=digest(REPORT/'data.json'),
        probes=reports,qualification='Bounded full-index/raw-current-PRE reconstruction. Full corpus integrity relies on bound source hashes and the assembly checks. No optimizer updates.'))
    print(json.dumps(reports,indent=2))


if __name__=='__main__':run()
