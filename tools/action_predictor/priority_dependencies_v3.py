"""Bind frozen predictions and all local executable dependencies before use."""
import json
from pathlib import Path
import sys
import numpy as np
import torch
from .category_study import ROOT,WORK,REPORTS
from .more_replays import frozen,sha
from . import reliable_train as rt

MANIFEST=REPORTS/'priority-dependencies-v3.json'
BASE_REPORT=ROOT/'tools/action_predictor/experiments/v5/M01.json'
BASE_PREDICTIONS=ROOT/'.cambc/action-predictor/v5/runs/M01/validation-predictions.npz'

def read(path):return json.loads(Path(path).read_text(encoding='utf-8'))

def check_hashes(mapping):
    for path,digest in mapping.items():assert sha(path)==digest,'Dependency or baseline mismatch: '+path

def baseline_binding():
    original=read(BASE_REPORT)
    assert sha(BASE_PREDICTIONS)==original['predictions_sha256'],'Baseline prediction archive mismatch'
    return dict(report_sha256=sha(BASE_REPORT),predictions_sha256=original['predictions_sha256'])

def verify_label_schema():
    reviewed=REPORTS/'audit-amendment-01.json';labels=read(reviewed)['labels']
    dataset=ROOT/'.cambc/action-predictor/data/dataset.json'
    benchmark=ROOT/'tools/action_predictor/experiments/v4/benchmark.json'
    assert sha(dataset)==read(benchmark)['original_dataset_sha256'],'Dataset label metadata changed'
    assert rt.LABELS==labels,'Runtime label order differs from reviewed schema'
    metadata=[reviewed,dataset,benchmark,REPORTS/'success-definition.json']
    assert read(dataset)['labels']==labels
    assert read(REPORTS/'success-definition.json')['categories']==labels[1:]
    for relative in ('v4/validation-data.json','v4/train-data.json','v4/train-aug-data.json','v5/train-data.json','v5/train-aug-data.json'):
        path=ROOT/'.cambc/action-predictor'/relative
        assert read(path)['labels']==labels,'Receipt label order differs: '+relative
        metadata.append(path)
    checkpoint=ROOT/'.cambc/action-predictor/v5/runs/M01/model.pt'
    assert sha(checkpoint)==read(BASE_REPORT)['checkpoint_sha256']
    saved=torch.load(checkpoint,weights_only=True,map_location='cpu')
    assert saved['labels']==labels,'Checkpoint label order differs'
    return labels,{str(path):sha(path) for path in metadata}

def freeze_dependencies():
    # Original source locks remain authoritative; never update them to fit live edits.
    old=read(ROOT/'tools/action_predictor/experiments/v7/execution-lock.json')
    check_hashes(old['training_sources']);check_hashes(old['preserved_checkpoints']);check_hashes(old['runtime_assets'])
    entry=read(REPORTS/'entry-audit.json');check_hashes(entry['source_hashes']);labels,metadata=verify_label_schema()
    directory=ROOT/'tools/action_predictor'
    paths=sorted([*(ROOT/'tools').rglob('*.py'),*(ROOT/'tools').rglob('*.cjs')])
    sources=dict(old['training_sources'])|{str(path):sha(path) for path in paths}
    snapshots=WORK/'dependencies-v3';snapshots.mkdir(exist_ok=True)
    for path,digest in sources.items():
        source=Path(path);copy=snapshots/(digest+'_'+source.name)
        if not copy.exists():copy.write_bytes(source.read_bytes())
        assert sha(copy)==digest
    frozen(MANIFEST,dict(sources=sources,labels=labels,metadata=metadata,baseline=baseline_binding(),
        baseline_paths={str(BASE_REPORT):sha(BASE_REPORT),str(BASE_PREDICTIONS):sha(BASE_PREDICTIONS)},
        preserved_checkpoints=old['preserved_checkpoints'],runtime_assets=old['runtime_assets'],
        python=sys.version,torch=str(torch.__version__),numpy=np.__version__,
        prior_v1_design_sha256=sha(REPORTS/'priority-logistic-design.json'),fits_started=0))

def verify_dependencies():
    labels,metadata=verify_label_schema()
    manifest=read(MANIFEST)
    assert manifest['labels']==labels and manifest['metadata']==metadata
    check_hashes(manifest['metadata'])
    check_hashes(manifest['sources']);check_hashes(manifest['baseline_paths'])
    check_hashes(manifest['preserved_checkpoints']);check_hashes(manifest['runtime_assets'])
    assert manifest['baseline']==baseline_binding()
    assert (manifest['python'],manifest['torch'],manifest['numpy'])==(sys.version,str(torch.__version__),np.__version__)
    return sha(MANIFEST)

def verify_roundtrip_bindings(identifier=None):
    """Check every frozen artifact the standalone parity entry will consume."""
    audit_path=REPORTS/'priority-recovery-audit.json';audit=read(audit_path)
    approval=read(REPORTS/'priority-data-review-approval.json')
    assert approval['verdict']=='APPROVE' and sha(audit_path)==approval['audit_sha256']
    assert sha(REPORTS/'priority-chain-verification.json')==approval['chain_sha256']==audit['chain_verification_sha256']
    ready_path=REPORTS/'priority-data-ready.json';ready=read(ready_path)
    assert sha(ready_path)==audit['data_ready_sha256']
    plan_path=REPORTS/'priority-extraction-plan.json';plan=read(plan_path)
    assert sha(plan_path)==audit['plan_sha256']
    jobs_path=ROOT/'.cambc/action-predictor/v7/jobs.json';assert sha(jobs_path)==plan['jobs_sha256']
    for path,digest in audit['input_hashes'].items():assert sha(path)==digest
    assert sha(WORK/'priority-validation.npz')==ready['files']['validation']
    from .priority_fit_v3 import context_directory
    context_ready=read(REPORTS/'priority-context-ready-v3.json')
    assert context_ready['design_sha256']==sha(REPORTS/'priority-logistic-design-v3.json')
    assert context_ready['directory']==str(context_directory())
    for split,digest in context_ready['contexts'].items():assert sha(context_directory()/(split+'.npy'))==digest
    assert sha(context_directory()/'extra-normalization.npz')==context_ready['normalizer_sha256']
    for job in read(jobs_path):
        if job['split']!='validation':continue
        raw=job['record']['raw_sha256'];directory=WORK/'priority'/raw
        receipt=read(directory/'receipt.json');assert sha(directory/'receipt.json')==ready['receipts'][raw]
        assert sha(Path(job['manifest']['source'])/'extracted'/raw/'index.jsonl')==receipt['index_sha256']
        assert sha(directory/'pre.jsonl.gz')==receipt['files']['pre.jsonl.gz']
        supplements=Path(job['work'])/'supplement'/raw
        assert sha(supplements/'pre.jsonl')==read(supplements/'receipt.json')['sha256']
    if identifier:
        info=read(REPORTS/(identifier+'.json'))
        assert sha(WORK/'runs'/identifier/'model.pt')==info['checkpoint_sha256']
        assert sha(WORK/'runs'/identifier/'validation-predictions.npz')==info['predictions_sha256']
