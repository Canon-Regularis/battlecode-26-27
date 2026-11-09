"""Real original-development replay parity; no fitting or reserved games."""
from collections import defaultdict
import gzip
import json
from pathlib import Path
import sys
import numpy as np
import torch
from . import reliable_train as rt
from .category_study import ROOT,WORK,REPORTS
from .more_replays import frozen,sha
from .priority_predictor import PriorityPredictor
from .priority_head import flatten
from .priority_fit_v2 import BASE,VAL,load_base,context_directory
from .rich_data import read_turns
from .observation_data import compact_supplement
from .audit import cursor

def run(identifier=None):
    rt.setup(26);base,saved=load_base()
    with np.load(VAL) as z:raw={key:z[key] for key in z.files}
    data,_=rt.model_data(raw,saved['config'],(saved['mean'],saved['std']))
    with np.load(WORK/'priority-validation.npz') as z:extra_raw=flatten(z['values'],z['history'])
    norm=context_directory()/'extra-normalization.npz'
    with np.load(norm) as z:extra=torch.from_numpy((extra_raw.astype(np.float32)-z['mean'])/z['std'])
    head_checkpoint=WORK/'runs'/identifier/'model.pt' if identifier else None
    jobs=[job for job in json.loads((ROOT/'.cambc/action-predictor/v7/jobs.json').read_text()) if job['split']=='validation']
    maximum=0.;cases=0
    for job in jobs:
        raw_hash=job['record']['raw_sha256'];source=Path(job['manifest']['source'])/'extracted'/raw_hash;events=defaultdict(list)
        for line in (source/'index.jsonl').open():
            turn=json.loads(line)
            if turn.get('record')=='turn':
                for root in turn['roots']:events[turn['actor']].append((root,turn['round']))
        for rows in events.values():rows.sort(key=lambda pair:cursor(pair[0]['event']))
        states={}
        with gzip.open(WORK/'priority'/raw_hash/'pre.jsonl.gz','rt') as stream:
            for line in stream:
                row=json.loads(line)
                if row['record']=='priority_pre':states[row['event']]=row
        route=None;supplements={}
        for line in (Path(job['work'])/'supplement'/raw_hash/'pre.jsonl').open():
            row=json.loads(line)
            if row['record']=='map':route=row['route']
            elif row['record']=='pre':supplements[row['id']]=compact_supplement(row)
        targets=[(turn,decision) for turn in read_turns(job['manifest'],job['record']) for decision in turn['decisions']]
        for local in sorted({0,len(targets)//2,len(targets)-1}):
            turn,decision=targets[local];index=job['offset']+local
            predictor=PriorityPredictor(BASE/'runs/M01/model.pt',norm,head_checkpoint,actor=turn['actor'])
            for root,round_number in events[turn['actor']]:
                if cursor(root['event'])>cursor(decision['pre_cursor']):break
                predictor.observe(root['event'],root['header']['step'],round_number)
            args=(decision['observation'],supplements[decision['id']],route,turn['round'],decision['pre_cursor'],states[decision['event_cursor']])
            actual=predictor.inputs(*args)
            expected=dict(x=data['x'][index:index+1],history=data['history'][index:index+1],extra=extra[index:index+1],
                grid=data['grid'][index:index+1].float(),valid=data['valid'][index:index+1],rules=data['rules'][index:index+1])
            for key in expected:assert torch.equal(actual[key],expected[key]),(key,index)
            with torch.no_grad():
                logits,context=base(expected['x'],expected['history']);family=logits.argmax(-1)
                probabilities=base.parameter_logits(context,expected['grid'],expected['valid'],family,expected['rules']).softmax(-1)
                expected_priority=predictor.head(context,expected['extra'])
            output=predictor.distributions(actual)
            errors=[float((output['action']-logits.softmax(-1)).abs().max()),float((output['coordinate']-probabilities).abs().max()),
                    float((output['priority_raw']-expected_priority).abs().max())]
            maximum=max(maximum,*errors);assert max(errors)<2e-6,(index,errors)
            forecast=predictor.predict(*args);assert forecast['action']==rt.LABELS[int(family)]
            if identifier:
                with np.load(WORK/'runs'/identifier/'validation-predictions.npz') as z:
                    assert int(family)==int(z['prediction'][index])
                    assert int((output['priority_raw'][0,0]*100).round())==int(z['priority'][index])
            cases+=1
    frozen(REPORTS/((identifier+'-inference-roundtrip.json') if identifier else 'priority-initial-inference-roundtrip-v2.json'),dict(
        passed=True,cases=cases,games=len(jobs),selection='First/middle/last target by row index per original dev game, never selected by correctness',
        inputs_exact=True,predicted_family_probability_maximum_error=maximum,tolerance=2e-6,
        grid_precision='float16 quantization then float32, exactly matching frozen training grid',
        baseline_sha256=sha(BASE/'runs/M01/model.pt'),head_sha256=sha(head_checkpoint) if identifier else None,
        source_sha256=sha(__file__),reserved_games_opened=0,new_fits=0))
    print('Priority inference probability/input roundtrip passed',cases,'targets',flush=True)

if __name__=='__main__':
    with (WORK/'commands.jsonl').open('a') as f:f.write(json.dumps(dict(argv=[sys.executable,'-m','tools.action_predictor.priority_roundtrip_v2',*sys.argv[1:]]))+'\n')
    run(sys.argv[1] if len(sys.argv)>1 else None)
