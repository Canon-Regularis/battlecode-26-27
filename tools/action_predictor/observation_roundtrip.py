"""Replay-to-offline-inference parity on existing development targets only."""
from collections import Counter,defaultdict
import gzip
import json
from pathlib import Path
import sys

import numpy as np
import torch

from . import reliable_train as rt
from .audit import cursor
from .more_replays import frozen,sha
from .observation_study import WORK,REPORTS,OLD,log_command
from .observation_data import compact_supplement
from .observation_inputs import ObservationInputs
from .observation_predictor import ObservationPredictor
from .rich_data import read_turns,SPATIAL


def verify(identifiers=('H01','H02')):
    rt.setup(26)
    with np.load(OLD/'validation.npz') as archive:raw={key:archive[key] for key in archive.files}
    jobs=[job for job in json.loads((WORK/'jobs.json').read_text()) if job['split']=='validation']
    cases=[];source_hashes={};engines=set()
    # Fixed first/middle/last target per eligible original validation game.
    # This selection uses row positions, never forecast correctness or loss.
    for job in jobs:
        hashed=job['record']['raw_sha256'];directory=WORK/'games'/hashed
        index=Path(job['manifest']['source'])/'extracted'/hashed/'index.jsonl'
        roots=defaultdict(list)
        for line in index.open(encoding='utf-8'):
            turn=json.loads(line)
            if turn.get('record')=='turn':
                for root in turn['roots']:roots[turn['actor']].append(dict(root=root,turn=turn['id'],round=turn['round']))
        for rows in roots.values():rows.sort(key=lambda row:cursor(row['root']['event']))
        frames={}
        with gzip.open(directory/'frames.jsonl.gz','rt',encoding='utf-8') as stream:
            for line in stream:
                frame=json.loads(line);frames[frame['event']]=frame
        supplement={};route=None
        work=Path(job['work'])
        for line in (work/'supplement'/hashed/'pre.jsonl').open(encoding='utf-8'):
            row=json.loads(line)
            if row['record']=='map':route=row['route']
            elif row['record']=='pre':supplement[row['id']]=compact_supplement(row)
        decisions=[(turn,decision) for turn in read_turns(job['manifest'],job['record']) for decision in turn['decisions']]
        selected=sorted({0,len(decisions)//2,len(decisions)-1})
        for local in selected:
            turn,decision=decisions[local]
            previous=[row for row in roots[turn['actor']] if cursor(row['root']['event'])<=cursor(decision['pre_cursor'])]
            assert all(row['root']['event'] in frames for row in previous[-16:])
            cases.append(dict(row=job['offset']+local,turn=turn,decision=decision,supplement=supplement[decision['id']],
                route=route,previous=previous,frames=frames))
        source_hashes[hashed]=dict(index=sha(index),evidence=sha(directory/'frames.jsonl.gz'))
        engines.add(job['record']['engine_version'])
    results={}
    for identifier in identifiers:
        checkpoint=WORK/'runs'/identifier/'model.pt'
        predictor=ObservationPredictor(checkpoint)
        normalizer=(predictor.mean,predictor.std)
        data,_=rt.model_data(raw,predictor.config,normalizer);bank=ObservationInputs('validation',normalizer)
        saved=np.load(WORK/'runs'/identifier/'validation-predictions.npz')
        available=[];present=[];maximum_error=0.
        for case in cases:
            predictor=ObservationPredictor(checkpoint,actor=case['turn']['actor'])
            for prior in case['previous']:
                root=prior['root'];frame=case['frames'].get(root['event'])
                predictor.observe(frame['observation'] if frame else None,frame['supplement'] if frame else None,
                    case['route'],prior['round'],prior['turn'],root['pre'],root['event'],root['header']['step'])
            turn,decision=case['turn'],case['decision'];index=case['row']
            arguments=(decision['observation'],case['supplement'],case['route'],turn['round'],turn['id'],decision['pre_cursor'])
            actual=predictor.inputs(*arguments)
            obs,gaps=bank.batch(torch.tensor([index]))
            expected=(data['x'][index:index+1],data['history'][index:index+1],obs,gaps)
            for a,b in zip(actual,expected):
                error=float((a-b).abs().max());maximum_error=max(maximum_error,error)
                assert torch.equal(a,b),(identifier,index,error)
            with torch.no_grad():
                logits,context=predictor.model(*actual)
                family=logits.argmax(-1)
                proposed=predictor.model.parameter_logits(context,data['grid'][index:index+1].float(),
                    data['valid'][index:index+1],family,data['rules'][index:index+1]).argmax(-1)
                truth=data['y'][index:index+1];py=int(data['py'][index])
                conditional=predictor.model.parameter_logits(context,data['grid'][index:index+1].float(),
                    data['valid'][index:index+1],truth,data['rules'][index:index+1]).log_softmax(-1)
                loss=-logits.log_softmax(-1)[0,truth.item()]
                if py>=0:loss-=conditional[0,py]
                if rt.LABELS[truth.item()]=='priority':
                    from .reliable_model import priority_log_mass
                    loss-=priority_log_mass(predictor.model.priority(context),data['priority'][index:index+1])[0]
            assert int(family)==int(saved['prediction'][index])
            assert int(proposed)==int(saved['proposed_coordinate'][index])
            assert abs(float(loss)-float(saved['nll'][index]))<2e-5
            result=predictor.predict(*arguments)
            assert result['action']==rt.LABELS[int(family)]
            if result['action'] in SPATIAL and int(proposed)<289:
                from .targets import OFFSETS
                pos=decision['observation']['own'].get('position')
                if pos is not None:
                    expected_point=dict(x=pos['x']+int(OFFSETS[int(proposed),0]),y=pos['y']+int(OFFSETS[int(proposed),1]))
                    assert result['parameter']['position']==expected_point
            elif result['action']=='priority':assert result['parameter']['priority']==int(saved['priority'][index])
            available.append(result['available_history']);present.append(result['present_history'])
        results[identifier]=dict(checkpoint_sha256=sha(checkpoint),cases=len(cases),all_four_input_tensors_bitwise_equal=True,
            maximum_input_error=maximum_error,action_and_parameter_decoding_matches_saved_batch=True,
            observed_joint_loss_maximum_tolerance=2e-5,available_history_counts=dict(Counter(available)),
            present_history_counts=dict(Counter(present)))
    frozen(REPORTS/'inference-roundtrip.json',dict(passed=True,selection='First/middle/last original development target per game; selected by row index only',
        validation_sha256=sha(OLD/'validation.npz'),games=len(jobs),engines=sorted(engines),source_hashes=source_hashes,models=results,
        new_validation_games_opened=0,final_test_games_opened=0))
    print('Real replay inference roundtrip passed:',len(cases),'targets per model',flush=True)


if __name__=='__main__':
    log_command([sys.executable,'-m','tools.action_predictor.observation_roundtrip',*sys.argv[1:]],purpose='Real personal-history offline inference parity, original development games only')
    verify(tuple(sys.argv[1:]) or ('H01','H02'))
