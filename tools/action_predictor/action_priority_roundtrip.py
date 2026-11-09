"""Causal personal-PRE to mode probabilities/decoded command parity."""
from collections import defaultdict
import gzip,json,sys
from pathlib import Path
import numpy as np
import torch
from . import reliable_train as rt
from .category_study import ROOT,WORK,REPORTS
from .more_replays import frozen,sha
from .action_priority_predictor import ActionPriorityPredictor
from .priority_head import flatten
from .priority_fit_v3 import BASE,VAL,load_base,context_directory
from .priority_dependencies_v3 import verify_roundtrip_bindings
from .action_priority_fit import verify_protocol,head,read,PLAN,SOURCES,log,PRIORITY
from .priority_residual_fit import head as priority_head,VOCAB
from .action_priority_head import classifier_features
from unittest.mock import patch
from .rich_data import read_turns,SPATIAL
from .observation_data import compact_supplement
from .audit import cursor
from .targets import OFFSETS


def run(identifier=None,use_inputs=False):
    verify_protocol();verify_roundtrip_bindings()
    if identifier:
        assert identifier in ('C01','C02');use_inputs=identifier=='C02';info=read(REPORTS/(identifier+'.json'));directory=WORK/'runs'/identifier
        assert info['fingerprint']['plan_sha256']==sha(PLAN) and info['fingerprint']['sources_sha256']==sha(SOURCES)
        assert sha(directory/'model.pt')==info['checkpoint_sha256']
        assert sha(directory/'validation-predictions.npz')==info['predictions_sha256']
        assert sha(directory/'action-logits.npy')==info['action_logits_sha256']
        stored_outputs=np.load(directory/'action-logits.npy')
        with np.load(directory/'validation-predictions.npz') as z:stored={k:z[k] for k in z.files}
    rt.setup(26);base,saved=load_base();reference=head(base.action,use_inputs);priority_reference=priority_head(base.priority);priority_reference.load_state_dict(torch.load(PRIORITY/'model.pt',weights_only=True)['head_state'])
    if identifier:reference.load_state_dict(torch.load(directory/'model.pt',weights_only=True)['head_state'])
    with np.load(VAL) as z:raw={k:z[k] for k in z.files}
    data,_=rt.model_data(raw,saved['config'],(saved['mean'],saved['std']))
    with np.load(WORK/'priority-validation.npz') as z:extra_raw=flatten(z['values'],z['history']);priority_values=torch.from_numpy(z['values'])
    norm=context_directory()/'extra-normalization.npz'
    with np.load(norm) as z:extra=torch.from_numpy((extra_raw.astype(np.float32)-z['mean'])/z['std'])
    vocab=read(VOCAB)
    checkpoint=directory/'model.pt' if identifier else None
    jobs=[j for j in read(ROOT/'.cambc/action-predictor/v7/jobs.json') if j['split']=='validation']
    maximum=0.;cases=0;forced_cases=0
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
            predictor=ActionPriorityPredictor(BASE/'runs/M01/model.pt',norm,vocab,PRIORITY/'model.pt',use_inputs,checkpoint,actor=turn['actor'])
            for root,round_number in events[turn['actor']]:
                if cursor(root['event'])>cursor(d['pre_cursor']):break
                predictor.observe(root['event'],root['header']['step'],round_number)
            args=(d['observation'],supplements[d['id']],route,turn['round'],d['pre_cursor'],states[d['event_cursor']])
            actual=predictor.inputs(*args)
            expected=dict(priority_values=priority_values[index:index+1],x=data['x'][index:index+1],history=data['history'][index:index+1],extra=extra[index:index+1],grid=data['grid'][index:index+1].float(),valid=data['valid'][index:index+1],rules=data['rules'][index:index+1])
            expected['classifier_features']=classifier_features(expected['extra'],expected['priority_values'])
            for key in expected:assert torch.equal(actual[key],expected[key]),(index,key)
            with torch.no_grad():
                _,context=base(expected['x'],expected['history']);logits=reference(context,expected['classifier_features']);family=logits.argmax(-1)
                spatial=base.parameter_logits(context,expected['grid'],expected['valid'],family,expected['rules']).softmax(-1)
                expected_raw=priority_reference(context,expected['extra'])
            output=predictor.distributions(actual)
            candidates,expected_logp=priority_reference.candidate_log_masses(expected_raw,expected['priority_values'])
            actual_candidates,actual_logp=predictor.head.candidate_log_masses(output['priority_raw'],actual['priority_values'])
            assert torch.equal(candidates,actual_candidates)
            errors=[float((output['action']-logits.softmax(-1)).abs().max()),float((output['coordinate']-spatial).abs().max()),float((actual_logp.exp()-expected_logp.exp()).abs().max())]
            maximum=max(maximum,*errors);assert max(errors)<2e-6,(index,errors)
            forecast=predictor.predict(*args);assert forecast['action']==rt.LABELS[int(family)]
            predicted_integer=int(priority_reference.integer(expected_raw,expected['priority_values'])[0])
            if forecast['action']=='priority':assert forecast['parameter']['priority']==predicted_integer
            if identifier:
                assert int(family)==int(stored['prediction'][index])
                assert predicted_integer==int(stored['priority'][index])
                saved_raw=torch.from_numpy(stored_outputs[index:index+1])
                maximum=max(maximum,float((saved_raw.softmax(-1)-output['action']).abs().max()))
                assert maximum<2e-6
                if forecast['action'] in SPATIAL:
                    code=int(stored['proposed_coordinate'][index]);pos=d['observation']['own'].get('position')
                    if code<289 and pos is not None:
                        assert forecast['parameter']['position']==dict(x=pos['x']+int(OFFSETS[code,0]),y=pos['y']+int(OFFSETS[code,1]))
            # Force each spatial prediction without changing model weights or using y.
            for name in SPATIAL:
                forced=torch.full_like(logits,-100.);code=rt.LABELS.index(name);forced[:,code]=100.
                with patch.object(predictor.classifier,'forward',return_value=forced):
                    rerouted=predictor.distributions(actual)
                with torch.no_grad():
                    wanted=base.parameter_logits(context,expected['grid'],expected['valid'],torch.tensor([code]),expected['rules']).softmax(-1)
                error=float((rerouted['coordinate']-wanted).abs().max());maximum=max(maximum,error)
                assert error<2e-6 and torch.equal(rerouted['priority_raw'],output['priority_raw'])
                forced_cases+=1
            cases+=1
    frozen(REPORTS/((identifier+'-inference-roundtrip.json') if identifier else ('action-priority-initial-'+('treatment' if use_inputs else 'control')+'-roundtrip.json')),dict(passed=True,cases=cases,games=len(jobs),
        selection='First/middle/last target by row index per original development game; not selected by correctness',inputs_exact=True,forced_spatial_family_cases=forced_cases,priority_argument_checkpoint_sha256=sha(PRIORITY/'model.pt'),probability_maximum_error=maximum,tolerance=2e-6,
        priority_decoding='Global absolute/causally shifted residual mixture mode; duplicate masses summed, unrestricted floor/ceiling fallback candidates',plan_sha256=sha(PLAN),sources_sha256=sha(SOURCES),
        head_sha256=sha(checkpoint) if identifier else None,new_fits=0,reserved_games_opened=0))
    print('Classifier and frozen-argument causal inference/input/probability roundtrip passed',cases,'targets',flush=True)

if __name__=='__main__':
    log([sys.executable,'-m','tools.action_predictor.action_priority_roundtrip',*sys.argv[1:]])
    run(sys.argv[1] if len(sys.argv)>1 else None)
