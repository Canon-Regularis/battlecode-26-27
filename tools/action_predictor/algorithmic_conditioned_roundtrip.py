"""A01 causal PRE-to-command reproduction, no archives or game simulation."""
from collections import defaultdict,Counter
import gzip,json,sys,time
from pathlib import Path
import numpy as np
import torch
from .algorithmic.study import ROOT,WORK,REPORT,JOBS
from .algorithmic_fit import load
from .algorithmic_conditioned_predictor import AlgorithmicPredictor
from .movement_predictor import MovementMixturePredictor
from .priority_fit_v3 import BASE,context_directory
from .priority_residual_fit import VOCAB
from .rich_data import read_turns
from .observation_data import compact_supplement
from .audit import cursor,immutable_json
from .data import digest
from . import reliable_train as rt

def run():
    rt.setup(26);info=json.loads((REPORT/'A01.json').read_text());data=load('validation');stored=np.load(WORK/'runs/A01/validation-predictions.npz');descriptors=np.load(WORK/'validation-candidate-descriptors.f16.npy',mmap_mode='r');jobs=[j for j in json.loads(JOBS.read_text()) if j['split']=='validation'];gcp=BASE.parent/'v9/runs/G00/model.pt';g=json.loads((REPORT.parent/'v9/G00.json').read_text());acp=WORK/f"runs/A01/round-{info['selected_round']:02d}.pt";counts=Counter();maxerror=0;timings=[];bindings=[]
    for job in jobs:
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
        supplements={};sp=Path(job['work'])/'supplement'/raw/'pre.jsonl'
        for line in sp.open():
            r=json.loads(line)
            if r['record']=='map':route=r['route']
            elif r['record']=='pre':supplements[r['id']]=compact_supplement(r)
        targets=[(t,d) for t in read_turns(job['manifest'],job['record']) for d in t['decisions']];a=job['offset'];b=a+job['rows'];selection={0,len(targets)//2,len(targets)-1}
        for family in np.unique(stored['prediction'][a:b]):selection.add(int(np.flatnonzero(stored['prediction'][a:b]==family)[0]))
        for mode in (False,True):
            idx=np.flatnonzero(stored['fallback'][a:b]==mode)
            if len(idx):selection.add(int(idx[0]))
        for mask in (np.all(data['raw']['history'][a:b]==0,axis=(1,2)),data['raw']['x'][a:b,200]==0):
            idx=np.flatnonzero(mask)
            if len(idx):selection.add(int(idx[0]))
        for local in sorted(selection):
            turn,d=targets[local];idx=a+local;fallback=MovementMixturePredictor(BASE/'runs/M01/model.pt',context_directory()/'extra-normalization.npz',json.loads(VOCAB.read_text()),BASE.parent/'v8/runs/P05/model.pt',gcp,g['checkpoint_sha256'],turn['actor']);predictor=AlgorithmicPredictor(fallback,acp,info['checkpoint_sha256'])
            for root,rnd in events[turn['actor']]:
                if cursor(root['event'])>cursor(d['pre_cursor']):break
                predictor.observe(root['event'],root['header']['step'],rnd)
            start=time.perf_counter();out=predictor.predict(d['observation'],supplements[d['id']],route,turn['round'],d['pre_cursor'],states[d['event_cursor']]);timings.append((time.perf_counter()-start)*1000)
            np.testing.assert_array_equal(out['candidate_descriptors'],descriptors[idx]);np.testing.assert_array_equal(out['selector_features'],data['x'][idx]);np.testing.assert_array_equal(out['commands'],data['c'][idx]);error=float(np.abs(out['weights']-stored['selector_weights'][idx]).max());maxerror=max(error,maxerror);assert error<2e-6
            assert out['used_fallback']==bool(stored['fallback'][idx])
            for key in ('prediction','coordinate','priority'):assert out['prediction'][key][0]==stored[key][idx],(idx,key)
            counts['cases']+=1;counts['fallback' if out['used_fallback'] else 'point']+=1;counts['engine_'+job['record']['engine_version']]+=1;counts['predicted_'+rt.LABELS[int(stored['prediction'][idx])]]+=1
            counts['missing_position']+=int(not d['observation']['own'].get('position'));counts['empty_history']+=int(not data['raw']['history'][idx].any())
        bindings.append(dict(raw=raw,index=digest(index),priority=digest(statefile),supplement=digest(sp)))
    immutable_json(REPORT/'A01-causal-roundtrip.json',dict(counts=dict(counts),games=len(jobs),inputs_and_commands_exact=True,selector_probability_max_error=maxerror,tolerance=2e-6,selection='first/middle/last plus first predicted family, routing mode, unavailable position/history per game; no correctness/currentlabel selection',causal_boundary='PRE-only supplement allowlist and current/scheduled personal priority. Every earlier actual own root replayed into memory only through PRE. No sampled-row stitching. No archive decoding or simulation.',timing_ms=dict(mean=float(np.mean(timings)),median=float(np.median(timings)),p95=float(np.quantile(timings,.95)),scope='actual candidate+feature+G00+selector forward; initialization and history replay excluded; not production latency'),sources={str(p.relative_to(ROOT)):digest(p) for p in (Path(__file__),Path(__file__).with_name('algorithmic_conditioned_predictor.py'))},bindings=bindings,reserved_opened=0))
    print(dict(counts),maxerror,flush=True)

if __name__=='__main__':run()
