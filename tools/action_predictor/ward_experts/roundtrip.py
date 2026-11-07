"""Focused causal ward expert serving parity from raw PRE and earlier own roots."""
import gzip,json,sys,time
from pathlib import Path
from collections import defaultdict,Counter
import numpy as np
from .protocol import ROOT,BASE,JOBS,WORK,REPORT
from .predictor import WardPredictor
from ..proposal_data import evidence
from ..audit import cursor,immutable_json
from ..data import digest
from .. import reliable_train as rt

def run(name,placement_id=None,typing_id=None):
    rt.setup(20261112);cached={k:np.load(WORK/f'validation-{k}.npy',mmap_mode='r') for k in ('global','tile','mask')};stored={k:np.load(WORK/f'evaluations/{name}/validation-{k}.npz') for k in ('primary','joint_MAP')};supplied={}
    for kind,identifier in [('P',placement_id),('T',typing_id)]:
        if identifier:
            r=json.loads((REPORT/f'{identifier}.json').read_text());supplied[kind]=(WORK/f"runs/{identifier}/round-{r['selected_round']:02d}.pt",r['checkpoint_sha256'])
    counts=Counter();max_probability=0;timings=[];bindings=[]
    for job in [j for j in json.loads(JOBS.read_text()) if j['split']=='validation']:
        raw=job['record']['raw_sha256'];turns,supps,route=evidence(job);decisions=[(t,d) for t in turns for d in t['decisions']];events=defaultdict(list);index=Path(job['manifest']['source'])/'extracted'/raw/'index.jsonl'
        for line in index.open():
            t=json.loads(line)
            if t.get('record')=='turn':
                for root in t['roots']:events[t['actor']].append((root,t['round']))
        for r in events.values():r.sort(key=lambda r:cursor(r[0]['event']))
        states={};priority=BASE.parent/'v8/priority'/raw/'pre.jsonl.gz'
        with gzip.open(priority,'rt') as f:
            for line in f:
                r=json.loads(line)
                if r['record']=='priority_pre':states[r['event']]={k:r[k] for k in ('pre','actor','team','round','current','scheduled')}
        wp=WORK/'games'/raw/'personal.jsonl';wards={r['index']:r for r in map(json.loads,wp.open()) if r['record']=='ward_pre'};a=job['offset'];b=a+job['rows'];selection={0,len(decisions)//2,len(decisions)-1}
        for decoder in ('primary','joint_MAP'):
            predicted=stored[decoder]['prediction'][a:b]
            for family in np.unique(predicted):selection.add(int(np.flatnonzero(predicted==family)[0]))
        for condition in (cached['mask'][a:b].any(-1),~cached['mask'][a:b].any(-1)):
            ids=np.flatnonzero(condition)
            if len(ids):selection.add(int(ids[0]))
        actors={};pointers=Counter()
        for local in sorted(selection):
            t,d=decisions[local];idx=a+local;actor=t['actor']
            if actor not in actors:actors[actor]=WardPredictor(actor,supplied.get('P'),supplied.get('T'))
            predictor=actors[actor];roots=events[actor]
            while pointers[actor]<len(roots):
                root,rnd=roots[pointers[actor]]
                if cursor(root['event'])>cursor(d['pre_cursor']):break
                predictor.observe(root['event'],root['header']['step'],rnd);pointers[actor]+=1
            tick=time.perf_counter();out=predictor.predict(d['observation'],supps[d['id']],route,t['round'],d['pre_cursor'],states[d['event_cursor']],wards.get(idx));timings.append((time.perf_counter()-tick)*1000)
            np.testing.assert_allclose(out['global_features'],cached['global'][idx],rtol=0,atol=2e-6);np.testing.assert_array_equal(out['tile_features'],cached['tile'][idx]);np.testing.assert_array_equal(out['candidate_mask'],cached['mask'][idx])
            for decoder in ('primary','joint_MAP'):
                for field in ('prediction','coordinate','priority'):assert out[decoder][field][0]==stored[decoder][field][idx],(idx,decoder,field)
                max_probability=max(max_probability,abs(out[decoder]['command_log_probability'][0]-stored[decoder]['command_log_probability'][idx]))
            counts['cases']+=1;counts['engine_'+job['record']['engine_version']]+=1;counts['ward_predicted']+=int(out['primary']['prediction'][0]==14);counts['ward_state_available']+=int(idx in wards)
        bindings.append(dict(raw=raw,index=digest(index),priority=digest(priority),wards=digest(wp)))
        print('Ward raw PRE',name,len(bindings),'/25',flush=True)
    assert max_probability<1e-4;immutable_json(REPORT/f'{name}-causal-roundtrip.json',dict(counts=dict(counts),features_and_commands_parity=True,max_command_log_probability_discrepancy=float(max_probability),bindings=bindings,selection='First/middle/last plus firstpredictedfamily in eachdecoder and firstavailable/unavailablewardstate pergame;no truefamily/correctness selection.',serving_ms=dict(mean=float(np.mean(timings)),median=float(np.median(timings)),p95=float(np.quantile(timings,.95)),scope='Actual allfallbackheads pluswardexpert(s),featureconstruction,bothdecoders;initialization/actualpriorhistoryreplay/SDKstateacquisitionexcluded;notproductionlatency'),sources={str(p.relative_to(ROOT)):digest(p) for p in (Path(__file__),Path(__file__).with_name('predictor.py'))},new_fits=0,reserved_opened=0));print(name,dict(counts),max_probability,flush=True)

if __name__=='__main__':run(sys.argv[1],None if len(sys.argv)<3 or sys.argv[2]=='-' else sys.argv[2],None if len(sys.argv)<4 or sys.argv[3]=='-' else sys.argv[3])
