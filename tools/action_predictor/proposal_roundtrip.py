"""Focused raw personal PRE -> all frozen heads -> repaired command parity."""
import gzip,json,time
from pathlib import Path
from collections import defaultdict,Counter
import numpy as np
from .proposal_data import ROOT,BASE,WORK,REPORT,selected_jobs,evidence
from .proposal_predictor import load_proposal_predictor
from .proposal_generator import SPATIAL,NAMES,encode
from .audit import cursor,immutable_json
from .data import digest
from . import reliable_train as rt

def run():
    rt.setup(26);saved=np.load(WORK/'validation-candidates.npy',mmap_mode='r');table=np.load(BASE.parent/'v9/frequency/validation-family-argmax.npy',mmap_mode='r');pv=np.load(WORK/'validation-priority.npy');blocked=np.load(WORK/'validation-prefer-blocked.npy')
    with np.load(BASE.parent/'v9/runs/G00/validation-predictions.npz') as z:pred=z['prediction']
    count=Counter();timings=[];bindings=[]
    for job in selected_jobs('validation'):
        raw=job['record']['raw_sha256'];events=defaultdict(list);index=Path(job['manifest']['source'])/'extracted'/raw/'index.jsonl'
        for line in index.open():
            t=json.loads(line)
            if t.get('record')=='turn':
                for r in t['roots']:events[t['actor']].append((r,t['round']))
        for roots in events.values():roots.sort(key=lambda r:cursor(r[0]['event']))
        states={};statefile=BASE.parent/'v8/priority'/raw/'pre.jsonl.gz'
        with gzip.open(statefile,'rt') as stream:
            for line in stream:
                r=json.loads(line)
                if r['record']=='priority_pre':states[r['event']]={k:r[k] for k in ('pre','actor','team','round','current','scheduled')}
        targetpath=WORK/'targets'/raw/'pre.jsonl';targets={r['index']:r for r in map(json.loads,targetpath.open()) if r['record']=='personal_targets'}
        turns,supps,route=evidence(job);decisions=[(t,d) for t in turns for d in t['decisions']];a=job['offset'];b=a+job['rows'];selection={0,len(decisions)//2,len(decisions)-1}
        for family in np.unique(pred[a:b]):selection.add(int(np.flatnonzero(pred[a:b]==family)[0]))
        for mask in ((pv[a:b]!=0)&(pred[a:b]!=9),np.array([not d['observation']['own'].get('position') for _,d in decisions])):
            candidates=np.flatnonzero(mask)
            if len(candidates):selection.add(int(candidates[0]))
        if targets:selection.add(min(targets)-a)
        actors={};pointers=Counter()
        for local in sorted(selection):
            t,d=decisions[local];actor=t['actor'];idx=a+local
            if actor not in actors:actors[actor]=load_proposal_predictor(actor)
            p=actors[actor];roots=events[actor]
            while pointers[actor]<len(roots):
                root,rnd=roots[pointers[actor]]
                if cursor(root['event'])>cursor(d['pre_cursor']):break
                p.observe(root['event'],root['header']['step'],rnd);pointers[actor]+=1
            start=time.perf_counter();out=p.propose(d['observation'],supps[d['id']],route,t['round'],d['pre_cursor'],states[d['event_cursor']],targets.get(idx));timings.append((time.perf_counter()-start)*1000)
            arguments=out['conditional_arguments']
            for action in SPATIAL:assert arguments['coordinates'][action]==table[idx,rt.LABELS.index(action)],(idx,action,arguments['coordinates'][action],table[idx,rt.LABELS.index(action)])
            assert arguments['priority']==int(pv[idx]),(idx,'priority');assert arguments['prefer_blocked']==bool(blocked[idx])
            commands=np.full((len(NAMES),3),-1,np.int64)
            for c in out['proposals']:
                value=encode(c,d['observation']['own'].get('position'),rt.LABELS)
                if value is not None:commands[NAMES.index(c.source)]=value
            np.testing.assert_array_equal(commands,saved[idx])
            count['cases']+=1;count['engine_'+job['record']['engine_version']]+=1;count['nonzero_priority']+=int(arguments['priority']!=0);count['nonpriority_G00_nonzero_P05']+=int(pred[idx]!=9 and arguments['priority']!=0);count['missing_position']+=int(not d['observation']['own'].get('position'));count['personal_locks_available']+=int(targets.get(idx) is not None);count['observed_enemy_lock']+=int(any(e['team']!=d['observation']['own']['team'] for e in targets.get(idx,{}).get('altar_locks',[])))
        bindings.append(dict(raw=raw,index_sha256=digest(index),priority_PRE_sha256=digest(statefile),target_sha256=digest(targetpath)))
        print('Raw PRE parity',len(bindings),'/25',flush=True)
    immutable_json(REPORT/'C03-causal-roundtrip.json',dict(counts=dict(count),games=len(bindings),all_nine_family_argmaxes_exact=True,P05_integer_exact_independent_of_chosen_action=True,outcome_preference_exact=True,all_proposals_exact=True,
        selection='First/middle/last,firstG00predictedfamily,firstnonzeroP05withnonpriorityG00,missingposition,causallyqueryablealtarlockPREpergame. No currenttruefamily/correctness selection.',
        boundary='Personal PRE allowlist; only earlier actual own roots through PRE; P05 current/scheduled personal priority and anchors; explicit unavailable personal locks. No current answer, future states, sampled-row stitching or hypothetical actions.',
        serving_timing_ms=dict(mean=float(np.mean(timings)),median=float(np.median(timings)),p95=float(np.quantile(timings,.95)),scope='Actual all-head/P05/proposal forwards including input encoding; excludes initialization/history replay; no production latency claim'),
        sources={str(p.relative_to(ROOT)):digest(p) for p in (Path(__file__),Path(__file__).with_name('proposal_predictor.py'),Path(__file__).with_name('proposal_generator.py'))},plan_sha256=digest(REPORT/'C03-plan.json'),arguments_receipt_sha256=digest(REPORT/'C03-arguments.json'),coverage_receipt_sha256=digest(REPORT/'C03-validation.json'),bindings=bindings,new_fits=0,reserved_opened=0))
    print(dict(count),flush=True)

if __name__=='__main__':run()
