"""Focused new goal-memory and probability parity; no unchanged replay audit."""
import gzip,json,time,sys
from pathlib import Path
from collections import defaultdict,Counter
import numpy as np
from .consistent_data import ROOT,BASE,WORK,REPORT,JOBS,evidence
from .consistent_predictor import ConsistentPredictor
from .command_mixture import log_mass,target_commands
from .audit import cursor,immutable_json
from .data import digest
from . import reliable_train as rt

def run(variant='U00'):
    rt.setup(20261110);cached={k:np.load(WORK/f'validation-{k}.npy',mmap_mode='r') for k in ('x','c','desc','point-logq','modes','mode-logq')};checkpoint=None;info=None
    if variant!='U00':
        info=json.loads((REPORT/f'{variant}.json').read_text());checkpoint=WORK/f"runs/{variant}/round-{info['selected_round']:02d}.pt";stored=np.load(WORK/f'runs/{variant}/validation-predictions.npz')
    else:stored=np.load(WORK/'controls/U00-validation.npz')
    counts=Counter();max_q_error=0;max_weight_error=0;max_conf_error=0;timings=[];bindings=[]
    for job in [j for j in json.loads(JOBS.read_text()) if j['split']=='validation']:
        raw=job['record']['raw_sha256'];turns,supps,route=evidence(job);decisions=[(t,d) for t in turns for d in t['decisions']];index=Path(job['manifest']['source'])/'extracted'/raw/'index.jsonl';events=defaultdict(list)
        for line in index.open():
            t=json.loads(line)
            if t.get('record')=='turn':
                for root in t['roots']:events[t['actor']].append((root,t['round']))
        for r in events.values():r.sort(key=lambda r:cursor(r[0]['event']))
        frames={};framepath=BASE.parent/'v7/games'/raw/'frames.jsonl.gz'
        with gzip.open(framepath,'rt',encoding='utf-8') as stream:
            for line in stream:
                r=json.loads(line);frames[r['event']]=r
        for t,d in decisions:frames[d['event_cursor']]=dict(observation=d['observation'])
        states={};statepath=BASE.parent/'v8/priority'/raw/'pre.jsonl.gz'
        with gzip.open(statepath,'rt') as stream:
            for line in stream:
                r=json.loads(line)
                if r['record']=='priority_pre':states[r['event']]={k:r[k] for k in ('pre','actor','team','round','current','scheduled')}
        targetpath=BASE.parent/'v12/targets'/raw/'pre.jsonl';targets={r['index']:r for r in map(json.loads,targetpath.open()) if r['record']=='personal_targets'}
        a=job['offset'];b=a+job['rows'];selection={0,len(decisions)//2,len(decisions)-1}
        for family in np.unique(stored['prediction'][a:b]):selection.add(int(np.flatnonzero(stored['prediction'][a:b]==family)[0]))
        for mask in (np.array([not d['observation']['own'].get('position') for _,d in decisions]),cached['x'][a:b,495]>0):
            z=np.flatnonzero(mask)
            if len(z):selection.add(int(z[0]))
        actors={};pointers=Counter()
        for local in sorted(selection):
            t,d=decisions[local];actor=t['actor'];idx=a+local
            if actor not in actors:actors[actor]=ConsistentPredictor(actor,checkpoint,info['checkpoint_sha256'] if info else None)
            p=actors[actor];roots=events[actor]
            while pointers[actor]<len(roots):
                root,rnd=roots[pointers[actor]]
                if cursor(root['event'])>cursor(d['pre_cursor']):break
                f=frames.get(root['event']);p.observe(root['event'],root['header']['step'],rnd,f['observation'] if f else None,route);pointers[actor]+=1
            tick=time.perf_counter();out=p.predict(d['observation'],supps[d['id']],route,t['round'],d['pre_cursor'],states[d['event_cursor']],targets.get(idx));timings.append((time.perf_counter()-tick)*1000)
            np.testing.assert_array_equal(out['features'],cached['x'][idx]);np.testing.assert_array_equal(out['descriptors'],cached['desc'][idx]);np.testing.assert_array_equal(out['commands'],cached['c'][idx]);np.testing.assert_array_equal(out['modes'],cached['modes'][idx])
            for key in ('point_logq','mode_logq'):
                ref=cached[key.replace('_','-')][idx];finite=np.isfinite(ref)&np.isfinite(out[key]);assert np.array_equal(np.isfinite(ref),np.isfinite(out[key]));max_q_error=max(max_q_error,float(np.abs(out[key][finite]-ref[finite]).max(initial=0)))
            ref=np.array([stored['prediction'][idx],stored['coordinate'][idx],stored['priority'][idx]]);np.testing.assert_array_equal(out['command'],ref);max_conf_error=max(max_conf_error,abs(out['command_log_probability']-float(stored['command_log_probability'][idx])));max_weight_error=max(max_weight_error,float(np.abs(out['log_weights']-stored['log_weights'][idx])[np.isfinite(stored['log_weights'][idx])].max(initial=0)))
            counts['cases']+=1;counts['engine_'+job['record']['engine_version']]+=1;counts['missing_position']+=int(not d['observation']['own'].get('position'));counts['memory_available']+=int(p.memory.roots>0);counts['prior_PRE_missing']+=int(p.memory.missing>0)
        bindings.append(dict(raw=raw,index=digest(index),frames=digest(framepath),priority=digest(statepath)))
        print('Consistent raw PRE',variant,len(bindings),'/25',flush=True)
    assert max_q_error<2e-4 and max_weight_error<1e-4 and max_conf_error<1e-4
    immutable_json(REPORT/f'{variant}-causal-roundtrip.json',dict(counts=dict(counts),features_descriptors_commands_modes_exact=True,max_logq_discrepancy=max_q_error,max_log_weight_discrepancy=max_weight_error,max_command_log_probability_discrepancy=max_conf_error,bindings=bindings,selection='First/middle/last and firstpredictedfamily/missingposition/historycontext pergame; no truefamily/correctness selection.',timing_ms=dict(mean=float(np.mean(timings)),median=float(np.median(timings)),p95=float(np.quantile(timings,.95)),scope='Actual all-head probability/proposal/goal-memory feature/scorer/MAP forwards; excludesinitialization and earlierhistory replay; notproductionlatency'),sources={str(p.relative_to(ROOT)):digest(p) for p in (Path(__file__),Path(__file__).with_name('consistent_predictor.py'))},new_fits=0,reserved_opened=0))
    print(variant,dict(counts),max_q_error,max_weight_error,max_conf_error,flush=True)

if __name__=='__main__':run(sys.argv[1] if len(sys.argv)>1 else 'U00')
