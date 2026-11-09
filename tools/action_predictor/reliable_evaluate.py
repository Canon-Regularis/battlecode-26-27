"""Final locked evaluation and group uncertainty. Does not train or select models."""
import csv
import json
from pathlib import Path

import numpy as np
import torch

from .audit import immutable_json
from .benchmark import REPORTS,WORK
from .data import digest
from .development import gates
from .group_uncertainty import bootstrap,paired
from .reliable_baselines import predict as baseline_predict
from .reliable_model import JointModel
from .reliable_train import load_data,model_data,infer,summarize,LABELS,setup


def evaluate_checkpoint(identifier,raw,split):
    report=json.loads((REPORTS/f'{identifier}.json').read_text())
    path=WORK/'runs'/identifier/'model.pt'
    if digest(path)!=report['checkpoint_sha256']:
        raise ValueError('Locked checkpoint changed')
    saved=torch.load(path,weights_only=True,map_location='cpu')
    if saved['benchmark_sha256']!=digest(REPORTS/'benchmark.json'):
        raise ValueError('Wrong benchmark')
    data,_=model_data(raw,saved['config'],(saved['mean'],saved['std']))
    model=JointModel(len(saved['mean']),data['history'].shape[-1],len(LABELS),saved['config'])
    model.load_state_dict(saved['state_dict'])
    predictions=infer(model,data)
    np.savez_compressed(WORK/'runs'/identifier/f'{split}-final-predictions.npz',**predictions)
    score=summarize(raw,predictions);intervals,_,_=bootstrap(raw,predictions)
    return score,predictions,intervals


def run():
    setup(26)
    candidate=json.loads((REPORTS/'final-candidate-lock.json').read_text())
    selection=json.loads((REPORTS/'selection-lock.json').read_text())
    if digest(REPORTS/'selection-lock.json')!=candidate['selection_sha256']:
        raise ValueError('Winner changed after lock')
    if candidate['experiment_count']!=10:
        raise ValueError('Expected the frozen ten-run experiment budget')
    for identifier,expected in candidate['checkpoints'].items():
        if digest(WORK/'runs'/identifier/'model.pt')!=expected:raise ValueError('Checkpoint lock mismatch')
    val=load_data('validation');test=load_data('test')
    baseline_source=json.loads((REPORTS/'simple-baselines.json').read_text())
    fitted={k:np.asarray(v) if isinstance(v,list) else v for k,v in baseline_source['fitted'].items()}
    simple_names=list(baseline_source['validation'])
    if (REPORTS/'additional-simple-baselines.json').exists():simple_names+=list(json.loads((REPORTS/'additional-simple-baselines.json').read_text())['validation'])
    grus=[selection['winner']['id'],'E07','E08'];stateless=[selection['stateless']['id'],'E09','E10']
    all_names=set(grus+stateless+simple_names+list(selection['references']['targeting'].values())+[selection['references']['loss'],selection['references']['movement']])
    results={};preds={};uncertainty={};validation_results={}
    for split,raw in [('validation',val),('test',test)]:
        results[split]={};preds[split]={};uncertainty[split]={}
        for name in sorted(all_names):
            if name in simple_names:
                action,parameter=name.split('-',1)
                pred=baseline_predict(raw,fitted,action,parameter)
                score=summarize(raw,pred);ci,_,_=bootstrap(raw,pred)
            else:
                score,pred,ci=evaluate_checkpoint(name,raw,split)
            results[split][name]=score;preds[split][name]=pred;uncertainty[split][name]=ci
        comparisons={}
        for i,identifier in enumerate(grus):
            base={k:v for k,v in results[split].items()}
            references=dict(selection['references'])
            # If a learned stateless loss/target reference won, use its matching-seed fit.
            if references['loss']==selection['stateless']['id']:references['loss']=stateless[i]
            references['targeting']={f:(stateless[i] if b==selection['stateless']['id'] else b) for f,b in references['targeting'].items()}
            evidence=gates(results[split][identifier],references,base)
            evidence['paired_loss_uncertainty']=paired(raw,preds[split][identifier],preds[split][references['loss']])
            evidence['paired_movement_uncertainty']=paired(raw,preds[split][identifier],preds[split][references['movement']])
            evidence['targeting_uncertainty']={family:paired(raw,preds[split][identifier],preds[split][base_name])[family+'_exact_gain']
                                                for family,base_name in references['targeting'].items()}
            evidence['groups']=len(np.unique(raw['group']));evidence['references']=references
            comparisons[identifier]=evidence
        immutable_json(REPORTS/f'{split}-evaluation.json',dict(models=results[split],uncertainty=uncertainty[split],comparisons=comparisons,
                       labels=LABELS,bootstrap_resamples=2000,unit='whole game groups',
                       untouched_fish_games=0,test_status='Previously exposed, not pristine',
                       full_engine_illegal_action_rate=None))
        if split=='validation':validation_results=comparisons
    consistent=all(all(c['passed'].values()) and c['paired_loss_uncertainty']['joint_loss_reduction']['low']>0
                   and c['paired_movement_uncertainty']['movement_gain']['low']>0 for c in validation_results.values())
    immutable_json(REPORTS/'conclusion.json',dict(proposed_targets_met_consistently=consistent,
                   selected_gru=selection['winner'],selected_stateless=selection['stateless'],
                   gru_runs=grus,stateless_runs=stateless,total_substantive_experiments=10,
                   heldout_status='No certified untouched Fish games; the old exposed test partition was preserved and used only after the final candidate lock.',
                   remaining_limits=['Original shop item/count and original attack/cast entity IDs are not identifiable from root events.',
                                     'Joint NLL is a partially observed recorded-label likelihood; strict full-command accuracy counts unsupported shop arguments as failures.',
                                     'Illegal-action rate is only observable violations; full engine legality is unassessed.',
                                     'Only five validation and five exposed test groups; one game group is five related maps.'],
                   validation_gates=validation_results))
    print('Finished locked evaluation. Consistent targets met:',consistent)


if __name__=='__main__':run()
