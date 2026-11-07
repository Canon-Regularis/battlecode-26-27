"""Append reproducible audit/blocked-outcome amendments without altering studies."""
import json
from pathlib import Path
import sys
import numpy as np
from .category_study import ROOT,WORK,REPORTS
from .more_replays import frozen,sha
from . import reliable_train as rt
from .observation_metrics import correctness

def read(path):return json.loads(Path(path).read_text(encoding='utf-8'))

def run():
    audit=read(REPORTS/'entry-audit.json');direction_path=ROOT/'.cambc/action-predictor/v7/validation-direction.npy'
    ready=ROOT/'tools/action_predictor/experiments/v7/data-ready.json'
    assert sha(direction_path)==read(ready)['files'][direction_path.name]
    inputs={str(direction_path):sha(direction_path),str(ready):sha(ready)}
    sources=[('v4/train.npz',ROOT/'.cambc/action-predictor/v4/train-data.json'),
             ('v5/train.npz',ROOT/'.cambc/action-predictor/v5/train-data.json'),
             ('v5/combined-train.npz',ROOT/'tools/action_predictor/experiments/v5/combined-training-data.json')]
    natural=np.zeros(len(rt.LABELS),np.int64);augmented=None
    for relative,receipt in sources:
        path=ROOT/'.cambc/action-predictor'/relative
        assert sha(path)==read(receipt)['sha256'],relative
        inputs[str(path)]=sha(path);inputs[str(receipt)]=sha(receipt)
        with np.load(path) as z:counts=np.bincount(z['y'],minlength=len(rt.LABELS))
        if relative.endswith('combined-train.npz'):augmented=counts
        else:natural+=counts
    for name,counts in [('natural',natural),('augmented',augmented)]:
        assert dict(zip(rt.LABELS,map(int,counts)))==audit['training_frequencies'][name]
    manifest=ROOT/'.cambc/action-predictor/v4/validation-data.json'
    assert read(manifest)['labels']==rt.LABELS
    inputs[str(manifest)]=sha(manifest)
    for path,digest in audit['source_hashes'].items():assert sha(path)==digest;inputs[path]=digest
    for path in (ROOT/'tools/action_predictor').glob('*.py'):
        inputs[str(path)]=sha(path)
    with np.load(ROOT/'.cambc/action-predictor/v4/validation.npz') as z:raw={k:z[k] for k in z.files}
    with np.load(ROOT/'.cambc/action-predictor/v5/runs/M01/validation-predictions.npz') as z:pred={k:z[k] for k in z.files}
    parameter,joint=correctness(raw,pred);y=raw['y'];p=pred['prediction'];c=pred['proposed_coordinate']
    invalid=rt.invalid_rate(raw,pred)
    output={}
    for name in ('move','blocked'):
        selected=p==rt.LABELS.index(name);idx=np.flatnonzero(selected);known=c[idx]<289
        rejected=int((~known).sum()+(~raw['move_mask'][idx[known],c[idx[known]]]).sum())
        actual=y==rt.LABELS.index(name)
        output[name]=dict(predicted_support=int(selected.sum()),personal_success_mask_rejections=rejected,
            actual_support=int(actual.sum()),conditional_destination_correct=int((actual&parameter).sum()),
            joint_outcome_and_destination_correct=int((actual&joint).sum()),
            interpretation=('Successful move-mask violations' if name=='move' else
                            'Rejected destination may be consistent with forecasting a blocked attempt; not an engine-illegal command count'))
    assert output['move']['personal_success_mask_rejections']==0 and output['blocked']['personal_success_mask_rejections']==92
    direction=np.load(direction_path);move=raw['y']==rt.LABELS.index('move')
    assert int((move&~parameter&(direction==3)).sum())==881
    priority=y==rt.LABELS.index('priority')
    amendment=dict(input_hashes=inputs,labels=rt.LABELS,entry_audit_sha256=sha(REPORTS/'entry-audit.json'),
        source_receipts_verified=True,training_counts_reproduced=True,direction_counts_reproduced=True,
        historical_partial_metric_unchanged=invalid,outcome_aware_mask_diagnostic=output,
        other_readiness_resource_flags=invalid['invalid']-92,full_engine_illegal_action_rate=None,
        frozen_action_priority_joint_ceiling=dict(type_correct=int((priority&(p==y)).sum()),support=int(priority.sum()),
            ceiling=float((p[priority]==y[priority]).mean())),
        scoring_code_snapshot_policy='Every hashed Python scoring/audit source copied verbatim under v8/provenance; original reports and code unchanged')
    snapshots=WORK/'provenance';snapshots.mkdir(parents=True,exist_ok=True)
    for path,digest in inputs.items():
        source=Path(path)
        if source.suffix=='.py':
            copy=snapshots/(digest+'_'+source.name)
            if not copy.exists():copy.write_bytes(source.read_bytes())
            assert sha(copy)==digest
    frozen(REPORTS/'audit-amendment-01.json',amendment)
    frozen(REPORTS/'review-ledger-01.json',dict(review_model='gpt-6.1-sol',reasoningEffort='xhigh',
        task_id='node:delegated-task:command%3Amcp%3A1e4504f0-6ae0-470c-9fc4-3fd23d1dae37%3Adelegate-task%3A4a180a9c-8ad9-4098-8a48-a4f0ce432128',
        verdict='CHANGES',findings={
          'R01':'Addressed by additive audit-amendment-01.json: all extra inputs/receipts, label manifest and scoring/audit sources verified and hashed; Python source snapshots retained.',
          'R02':'Open: next milestone causal current/scheduled and full-index historical priority recovery. Copy is a negative control; discrete modes plus full-support fallback needed.',
          'R03':'Addressed in success-definition and amendment: parameter-only priority ceiling343/576; first branch isolation is not a replacement claim; later separate action-discrimination experiment required.',
          'R04':'Addressed by outcome-aware decomposition, historical109 flag metric unchanged;92 blocked rejections are not automatically illegal; full legality unassessed.',
          'R05':'Open: new V8 inference must quantize generated grids through float16 before float32 and compare probabilities. Do not edit historical M01 artifacts.',
          'R06':'Open: purchase command fields not exposed by reader; unique version-specific inversion unproven; all43 shop arguments remain unassessed failures.'},
        new_training_fits=0,prior_objections='Prior complete review is in parent thread; future reviewers must read it and full history.'))
    with (WORK/'commands.jsonl').open('a') as stream:
        stream.write(json.dumps(dict(argv=[sys.executable,'-m','tools.action_predictor.category_amendment'],source_sha256=sha(__file__)))+'\n')
    print('Additive provenance/outcome amendment verified; old artifacts unchanged; new fits:0')

if __name__=='__main__':run()
