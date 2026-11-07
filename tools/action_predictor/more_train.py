"""Single matched-seed retrain: frozen V4 model/method/validation, more TRAIN data."""
import json
from pathlib import Path

import numpy as np
import torch

from .more_replays import ROOT,WORK,REPORTS,frozen,sha,log_command
from . import reliable_train as rt
from .group_uncertainty import bootstrap,paired
from .development import gates

OLD=ROOT/'.cambc/action-predictor/v4'
OLD_REPORTS=ROOT/'tools/action_predictor/experiments/v4'


def combined_data():
    output=WORK/'combined-train.npz'
    if output.exists():
        if sha(output)!=json.loads((REPORTS/'combined-training-data.json').read_text())['sha256']:
            raise ValueError('Combined training data changed')
        with np.load(output,allow_pickle=False) as archive:return {k:archive[k] for k in archive.files}
    old_meta=json.loads((OLD/'train-aug-data.json').read_text());new_meta=json.loads((WORK/'train-aug-data.json').read_text())
    if old_meta['feature_names']!=new_meta['feature_names'] or old_meta['labels']!=new_meta['labels']:
        raise ValueError('Observation/label encoding changed')
    old=np.load(OLD/'train-aug.npz',allow_pickle=False);new=np.load(WORK/'train-aug.npz',allow_pickle=False)
    if set(old.files)!=set(new.files):raise ValueError('Training tensor schema changed')
    arrays={}
    for key in old.files:
        a,b=old[key],new[key]
        if key=='group':b=b+len(old_meta['groups'])
        arrays[key]=np.concatenate((a,b))
    np.savez_compressed(output,**arrays)
    frozen(REPORTS/'combined-training-data.json',dict(sha256=sha(output),old_train_sha256=sha(OLD/'train-aug.npz'),
           new_train_sha256=sha(WORK/'train-aug.npz'),old_actions=old_meta['rows'],new_actions=new_meta['rows'],
           total_actions=len(arrays['y']),old_games=120,new_games=350,total_games=470,
           new_groups=70,original_groups=24,features_unchanged=True,labels_unchanged=True))
    return arrays


def run():
    if not (REPORTS/'training-data-ready.json').exists():raise ValueError('Frozen TRAIN extraction is incomplete')
    membership=json.loads((REPORTS/'membership.json').read_text())
    # Prove reserved new games have not been sent to any decoder stage.
    for record in membership['records']:
        if record['split']!='train' and (WORK/'source/extracted'/record['raw_sha256']).exists():
            raise ValueError('Reserved new replay was decoded')
    if not (REPORTS/'benchmark.json').exists():
        (REPORTS/'benchmark.json').write_bytes((OLD_REPORTS/'benchmark.json').read_bytes())
    if sha(REPORTS/'benchmark.json')!=sha(OLD_REPORTS/'benchmark.json'):
        raise ValueError('Benchmark contract changed')
    old_info=json.loads((OLD_REPORTS/'E06.json').read_text());original=old_info['config']
    config=original|dict(id='M01',name=original['name'])
    assert {k:v for k,v in config.items() if k!='id'}=={k:v for k,v in original.items() if k!='id'}
    # Keep the exact old validation tensor bytes. No old/new final test is read.
    val=rt.load_data('validation')
    if sha(OLD/'validation.npz')!=json.loads((REPORTS/'retrain-plan.json').read_text())['original_validation_sha256']:
        raise ValueError('Primary validation changed')
    rt.setup(26)
    saved=torch.load(OLD/'runs/E06/model.pt',weights_only=True,map_location='cpu')
    val_old,_=rt.model_data(val,original,(saved['mean'],saved['std']))
    baseline=rt.JointModel(len(saved['mean']),val_old['history'].shape[-1],len(saved['labels']),original)
    baseline.load_state_dict(saved['state_dict'])
    old_prediction=rt.infer(baseline,val_old);old_score=rt.summarize(val,old_prediction)
    for key in ('joint_nll','macro_f1','accuracy'):
        if abs(old_score[key]-old_info['validation'][key])>1e-6:raise ValueError('Original validation result did not reproduce')
    train=combined_data()
    fresh=rt.JointModel(train['x'].shape[1],train['history'].shape[-1],len(rt.LABELS),config)
    if {k:tuple(v.shape) for k,v in fresh.state_dict().items()}!={k:tuple(v.shape) for k,v in baseline.state_dict().items()}:
        raise ValueError('GRU architecture changed')
    del fresh
    frozen(REPORTS/'controlled-retrain.json',dict(original_config=original,new_config=config,seed=26,
           architecture_state_shapes_identical=True,benchmark_sha256=sha(OLD_REPORTS/'benchmark.json'),
           training_settings=rt.BENCH['training'],original_checkpoint_sha256=sha(OLD/'runs/E06/model.pt'),
           original_validation_sha256=sha(OLD/'validation.npz'),old_validation_reproduced=True,
           changes='Training replay volume/composition only. Normalization and class weights refit on training data by the unchanged procedure.',
           caveat='New recordings may differ in time, engine, opponent/draft and Fish policy. The unchanged epoch/patience budget allows more optimizer updates on more data; this is not randomized or equal-compute evidence of a pure volume effect.'))
    rt.WORK=WORK;rt.REPORTS=REPORTS
    if (REPORTS/'M01.json').exists():
        info=json.loads((REPORTS/'M01.json').read_text())
    else:info=rt.fit(config,26,train,val,train_source=WORK/'combined-train.npz',validation_source=OLD/'validation.npz')
    with np.load(WORK/'runs/M01/validation-predictions.npz',allow_pickle=False) as archive:new_prediction={k:archive[k] for k in archive.files}
    new_score=rt.summarize(val,new_prediction);ci,_,_=bootstrap(val,new_prediction)
    old_ci,_,_=bootstrap(val,old_prediction)
    frozen_evaluation=json.loads((OLD_REPORTS/'validation-evaluation.json').read_text())
    references=json.loads((OLD_REPORTS/'selection-lock.json').read_text())['references']
    evidence=gates(new_score,references,frozen_evaluation['models'])
    comparison=dict(old=old_score,more_data=new_score,old_group_intervals=old_ci,new_group_intervals=ci,
        paired_changes=paired(val,new_prediction,old_prediction),unchanged_target_gates=evidence,
        primary_validation='Same 14,439 original validation actions in five whole match groups.',
        new_validation_games_opened=0,new_final_test_games_opened=0,old_test_games_scored=0,
        checkpoint_sha256=sha(WORK/'runs/M01/model.pt'),old_checkpoint_sha256=sha(OLD/'runs/E06/model.pt'))
    frozen(REPORTS/'validation-comparison.json',comparison)
    sealed=[r for r in membership['records'] if r['split']=='test']
    for record in sealed:
        if sha(record['path'])!=record['bundle_sha256']:raise ValueError('Sealed test bundle changed')
    frozen(REPORTS/'sealed-test-audit.json',dict(games=len(sealed),groups=len({r['group'] for r in sealed}),
        membership_sha256=sha(REPORTS/'membership.json'),bundle_hashes_unchanged=True,
        decoder_directories_present=0,features_extracted=0,labels_inspected=0,predictions_or_scores=0,
        source_policy='Metadata, archive CRC and raw payload hashing only before freeze; no test behaviour inspection.'))
    lines=['# Additional Fish data: controlled first retrain','',
           'Architecture, feature definitions, sampling, training settings, seed and original validation benchmark are unchanged.',
           '500 additional distinct games were collected in 100 complete groups; 350 train, 75 validation and 75 sealed test.',
           'The initial experiment uses only the 350 new training games plus the original 120 training games. Both new reserved partitions remain unopened.', '',
           '| Metric on original validation | Original E06 | More-data M01 |','|---|---:|---:|']
    for name,key in [('Macro F1','macro_f1'),('Action accuracy','accuracy'),('Joint observed NLL','joint_nll'),('Joint recorded-parameter accuracy','strict_full_command_accuracy')]:
        lines.append(f'| {name} | {old_score[key]:.4f} | {new_score[key]:.4f} |')
    for key in ('exact_accuracy','top3_accuracy','top5_accuracy','penalized_mean_chebyshev_error'):
        lines.append(f'| Movement {key} | {old_score["parameters"]["move"][key]:.4f} | {new_score["parameters"]["move"][key]:.4f} |')
    lines+=['','All per-action precision/recall/F1/support, confusion matrices, partial observable-invalid rates and paired whole-group uncertainty are in `validation-comparison.json`.',
            'This is one matched seed, not a three-seed reliability claim. New games can change policy/engine/opponent composition. The unchanged epoch/patience budget also allows more optimizer updates; this is not an equal-compute comparison or a causal claim about volume alone.',
            'Original API arguments and full engine legality retain the V4 limitations. No final test was evaluated; no matches, deployments or PRs were created.',
            '', 'Exact commands are recorded in `.cambc/action-predictor/v5/commands.jsonl`; downloaded metadata pages, source queries, receipts and hashes are retained locally.']
    (REPORTS/'RESULTS.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(json.dumps(dict(macro_f1=new_score['macro_f1'],joint_nll=new_score['joint_nll'],movement=new_score['parameters']['move']['exact_accuracy'],sealed_test_games=len(sealed))),flush=True)


if __name__=='__main__':run()
