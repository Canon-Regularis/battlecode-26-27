"""Causal personal-PRE to mode probabilities/decoded command parity."""
from collections import defaultdict
import gzip,json,sys
from pathlib import Path
import numpy as np
import torch
from . import reliable_train as rt
from .category_study import ROOT,WORK,REPORTS
from .more_replays import frozen,sha
from .priority_modes_control_predictor import PriorityModesControlPredictor
from .priority_head import flatten
from .priority_fit_v3 import BASE,VAL,load_base,context_directory
from .priority_dependencies_v3 import verify_roundtrip_bindings
from .priority_modes_control import verify_protocol,head,read,PLAN,SOURCES,VOCAB,log
from .rich_data import read_turns,SPATIAL
from .observation_data import compact_supplement
from .audit import cursor
from .targets import OFFSETS


def run(identifier=None):
    verify_protocol();verify_roundtrip_bindings()
    if identifier:
        assert identifier=='P04';info=read(REPORTS/'P04.json');directory=WORK/'runs/P04'
        assert info['fingerprint']['plan_sha256']==sha(PLAN) and info['fingerprint']['sources_sha256']==sha(SOURCES)
        assert sha(directory/'model.pt')==info['checkpoint_sha256']
        assert sha(directory/'validation-predictions.npz')==info['predictions_sha256']
        assert sha(directory/'priority-outputs.npy')==info['priority_outputs_sha256']
        stored_outputs=np.load(directory/'priority-outputs.npy')
        with np.load(directory/'validation-predictions.npz') as z:stored={k:z[k] for k in z.files}
    rt.setup(26);base,saved=load_base();reference=head(base.priority)
    if identifier:reference.load_state_dict(torch.load(directory/'model.pt',weights_only=True)['head_state'])
    with np.load(VAL) as z:raw={k:z[k] for k in z.files}
    data,_=rt.model_data(raw,saved['config'],(saved['mean'],saved['std']))
    with np.load(WORK/'priority-validation.npz') as z:extra_raw=flatten(z['values'],z['history'])
    norm=context_directory()/'extra-normalization.npz'
    with np.load(norm) as z:extra=torch.from_numpy((extra_raw.astype(np.float32)-z['mean'])/z['std'])
    vocab=read(VOCAB)
    checkpoint=directory/'model.pt' if identifier else None
    jobs=[j for j in read(ROOT/'.cambc/action-predictor/v7/jobs.json') if j['split']=='validation']
    maximum=0.;cases=0
    for job in jobs:
        digest=job['record']['raw_sha256'];source=Path(job['manifest']['source'])/'extracted'/digest;events=defaultdict(list)
        for line in (source/'index.jsonl').open():
            turn=json.loads(line)
            if turn.get('record')=='turn':
                for root in turn['roots']:events[turn['actor']].append((root,turn['round']))
        for rows in events.values():rows.sort(key=lambda p:cursor(p[0]['event']))
        states={}
        with gzip.open(WORK/'priority'/digest/'pre.jsonl.gz','rt') as stream:
            for line in stream:
                row=json.loads(line)
                if row['record']=='priority_pre':states[row['event']]=row
        route=None;supplements={}
        for line in (Path(job['work'])/'supplement'/digest/'pre.jsonl').open():
            row=json.loads(line)
            if row['record']=='map':route=row['route']
            elif row['record']=='pre':supplements[row['id']]=compact_supplement(row)
        targets=[(turn,d) for turn in read_turns(job['manifest'],job['record']) for d in turn['decisions']]
        for local in sorted({0,len(targets)//2,len(targets)-1}):
            turn,d=targets[local];index=job['offset']+local
            predictor=PriorityModesControlPredictor(BASE/'runs/M01/model.pt',norm,vocab['values'],vocab['counts'],checkpoint,actor=turn['actor'])
            for root,round_number in events[turn['actor']]:
                if cursor(root['event'])>cursor(d['pre_cursor']):break
                predictor.observe(root['event'],root['header']['step'],round_number)
            args=(d['observation'],supplements[d['id']],route,turn['round'],d['pre_cursor'],states[d['event_cursor']])
            actual=predictor.inputs(*args)
            expected=dict(x=data['x'][index:index+1],history=data['history'][index:index+1],extra=extra[index:index+1],grid=data['grid'][index:index+1].float(),valid=data['valid'][index:index+1],rules=data['rules'][index:index+1])
            for key in expected:assert torch.equal(actual[key],expected[key]),(index,key)
            with torch.no_grad():
                logits,context=base(expected['x'],expected['history']);family=logits.argmax(-1)
                spatial=base.parameter_logits(context,expected['grid'],expected['valid'],family,expected['rules']).softmax(-1)
                expected_raw=reference(context,expected['extra'])
            output=predictor.distributions(actual)
            candidates,expected_logp=reference.candidate_log_masses(expected_raw)
            actual_candidates,actual_logp=predictor.head.candidate_log_masses(output['priority_raw'])
            assert torch.equal(candidates,actual_candidates)
            errors=[float((output['action']-logits.softmax(-1)).abs().max()),float((output['coordinate']-spatial).abs().max()),float((actual_logp.exp()-expected_logp.exp()).abs().max())]
            maximum=max(maximum,*errors);assert max(errors)<2e-6,(index,errors)
            forecast=predictor.predict(*args);assert forecast['action']==rt.LABELS[int(family)]
            predicted_integer=int(reference.integer(expected_raw)[0])
            if forecast['action']=='priority':assert forecast['parameter']['priority']==predicted_integer
            if identifier:
                assert int(family)==int(stored['prediction'][index])
                assert predicted_integer==int(stored['priority'][index])
                saved_raw=torch.from_numpy(stored_outputs[index:index+1])
                saved_candidates,saved_logp=reference.candidate_log_masses(saved_raw)
                assert torch.equal(candidates,saved_candidates)
                maximum=max(maximum,float((saved_logp.exp()-actual_logp.exp()).abs().max()))
                assert maximum<2e-6
                if forecast['action'] in SPATIAL:
                    code=int(stored['proposed_coordinate'][index]);pos=d['observation']['own'].get('position')
                    if code<289 and pos is not None:
                        assert forecast['parameter']['position']==dict(x=pos['x']+int(OFFSETS[code,0]),y=pos['y']+int(OFFSETS[code,1]))
            cases+=1
    frozen(REPORTS/('P04-inference-roundtrip.json' if identifier else 'priority-modes-control-initial-roundtrip.json'),dict(passed=True,cases=cases,games=len(jobs),
        selection='First/middle/last target by row index per original development game; not selected by correctness',inputs_exact=True,probability_maximum_error=maximum,tolerance=2e-6,
        priority_decoding='Global mixture mode, using training-derived values plus unrestricted rounded fallback mean',plan_sha256=sha(PLAN),sources_sha256=sha(SOURCES),
        head_sha256=sha(checkpoint) if identifier else None,new_fits=0,reserved_games_opened=0))
    print('Mode-head causal inference/input/probability roundtrip passed',cases,'targets',flush=True)

if __name__=='__main__':
    log([sys.executable,'-m','tools.action_predictor.priority_modes_control_roundtrip',*sys.argv[1:]])
    run(sys.argv[1] if len(sys.argv)>1 else None)
