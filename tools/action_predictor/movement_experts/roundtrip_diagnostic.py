"""Numerical attribution after original X00 logp tolerance failed; no new fit."""
import gzip,json,sys,time
from collections import defaultdict,Counter
from pathlib import Path
import numpy as np
import torch
from .protocol import ROOT,BASE,WORK,REPORT,JOBS
from .data import load,batch,read
from .model import MovementExpert
from .predictor import Predictor
from ..proposal_data import evidence
from ..audit import cursor,immutable_json
from ..data import digest

def run(identifier):
    torch.set_num_threads(4);info=json.loads((REPORT/f'{identifier}.json').read_text());path=WORK/f"runs/{identifier}/round-{info['selected_round']:02d}.pt";saved=torch.load(path,weights_only=False);model=MovementExpert(saved['mixture'],saved['counts']);model.load_state_dict(saved['state']);model.eval();d=load('validation');p=read(WORK/f'runs/{identifier}/validation-predictions.npz');counts=Counter();timings=[];max_context=0;max_probability=0;bindings=[];violations=[];fixed_input_max=0;max_mass_difference=0
    for job in [j for j in json.loads(JOBS.read_text()) if j['split']=='validation']:
        turns,supps,route=evidence(job);decisions=[(t,x) for t in turns for x in t['decisions']];raw=job['record']['raw_sha256'];events=defaultdict(list);index=Path(job['manifest']['source'])/'extracted'/raw/'index.jsonl'
        for line in index.open():
            t=json.loads(line)
            if t.get('record')=='turn':
                for root in t['roots']:events[t['actor']].append((root,t['round']))
        for roots in events.values():roots.sort(key=lambda row:cursor(row[0]['event']))
        states={};priority=BASE.parent/'v8/priority'/raw/'pre.jsonl.gz'
        with gzip.open(priority,'rt') as f:
            for line in f:
                r=json.loads(line)
                if r['record']=='priority_pre':states[r['event']]={k:r[k] for k in ('pre','actor','team','round','current','scheduled')}
        a=job['offset'];b=a+job['rows'];selection={0,len(decisions)//2,len(decisions)-1}
        for values,codes in [(d['raw']['y'][a:b],[3,8]),(p['prediction'][a:b],[3,8]),(d['direction'][a:b],[1,2,3]),(d['available'][a:b],[0,16])]:
            for code in codes:
                ix=np.flatnonzero(values==code)
                if len(ix):selection.add(int(ix[0]))
        actors={};pointers=Counter()
        for local in sorted(selection):
            t,decision=decisions[local];idx=a+local;actor=t['actor'];predictor=actors.setdefault(actor,None)
            if predictor is None:predictor=Predictor(actor,path,info['checkpoint_sha256']);actors[actor]=predictor
            roots=events[actor]
            while pointers[actor]<len(roots) and cursor(roots[pointers[actor]][0]['event'])<=cursor(decision['pre_cursor']):
                root,rnd=roots[pointers[actor]];predictor.observe(root['event'],root['header']['step'],rnd);pointers[actor]+=1
            tick=time.perf_counter();out=predictor.predict(decision['observation'],supps[decision['id']],route,t['round'],decision['pre_cursor'],states[decision['event_cursor']]);timings.append((time.perf_counter()-tick)*1000);max_context=max(max_context,float(np.abs(out['global_features'][:128]-d['x'][idx,:128]).max()));np.testing.assert_allclose(out['global_features'][:128],d['x'][idx,:128],atol=1e-5,rtol=0);np.testing.assert_array_equal(out['global_features'][128:],d['x'][idx,128:]);np.testing.assert_array_equal(out['grid'],d['raw']['grid'][idx].astype(np.float32));np.testing.assert_array_equal(out['valid'],d['raw']['valid'][idx]);cached_entities,_=d['entities'].batch([idx]);np.testing.assert_array_equal(out['entities'].astype(np.float32),cached_entities[0].numpy())
            # Unused priority/coordinate slots may differ; compare actual command.
            assert int(out['command'][0])==int(p['prediction'][idx])
            if p['prediction'][idx] in (3,8):assert int(out['command'][1])==int(p['proposed_coordinate'][idx])
            for code,key in [(8,'move_logp'),(3,'blocked_logp')]:
                with torch.no_grad():lp,_=model(*batch(d,np.array([idx]),saved['mean'],saved['std'],np.array([code])))
                difference=float(np.abs(lp[0].numpy()-out[key]).max());max_probability=max(max_probability,difference);max_mass_difference=max(max_mass_difference,float(np.abs(np.exp(lp[0].numpy())-np.exp(out[key])).max()))
                if difference>2e-5:violations.append(dict(index=idx,family=code,max_logp_difference=difference))
                # Replay new head with exactly the RAW neural context. Every other
                # input has already matched bit-for-bit. This attributes numerical
                # differences without raising or concealing the original tolerance.
                args=list(batch(d,np.array([idx]),saved['mean'],saved['std'],np.array([code])));args[0]=torch.from_numpy(np.clip((out['global_features'][None]-saved['mean'])/saved['std'],-10,10))
                with torch.no_grad():fixed,_=model(*args)
                fixed_input_max=max(fixed_input_max,float(np.abs(fixed[0].numpy()-out[key]).max()));np.testing.assert_array_equal(fixed[0].numpy(),out[key])
            counts['cases']+=1;counts['engine_'+job['record']['engine_version']]+=1;counts['forecast_'+str(p['prediction'][idx])]+=1
        bindings.append(dict(raw=raw,index_sha256=digest(index),priority_sha256=digest(priority)));print('Movement PRE',identifier,len(bindings),'/25',flush=True)
    immutable_json(REPORT/f'{identifier}-causal-roundtrip.json',dict(counts=dict(counts),bindings=bindings,checkpoint_sha256=digest(path),max_context_difference=max_context,max_logp_difference=max_probability,inference_ms=dict(mean=float(np.mean(timings)),median=float(np.median(timings)),p95=float(np.quantile(timings,.95))),timing_scope='Actual PRE feature construction + frozen G00/P05 distributions + new move AND blocked probabilities; initialization/history replay excluded. Two expert-family calls are both timed; not a production latency claim.',original_probability_test_passed=len(violations)==0,original_atol=2e-5,original_tolerance_violations=violations,fixed_raw_context_logp_max_difference=fixed_input_max,max_absolute_probability_mass_difference=max_mass_difference,qualification='Original absolute logp tolerance remains unmet where listed; no threshold was raised. Exact commands/raw nonneural inputs retained. Replaying new head with identical raw context gives bit-identical probabilities; residual cached-vsraw difference is attributable to the frozen128context rounding within its existing1e-5 tolerance. Not a proof of all-row raw command identity or production numerical robustness.',preflight_sha256=digest(REPORT/'X00-roundtrip-preflight.json'),source_sha256=digest(__file__),new_fits=0,reserved_opened=0));print(identifier,dict(counts),max_context,max_probability,flush=True)

if __name__=='__main__':run(sys.argv[1])
