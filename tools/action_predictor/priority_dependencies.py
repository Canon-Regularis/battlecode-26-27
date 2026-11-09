"""Bind frozen predictions and all local executable dependencies before use."""
import json
from pathlib import Path
import sys
import numpy as np
import torch
from .category_study import ROOT,WORK,REPORTS
from .more_replays import frozen,sha

MANIFEST=REPORTS/'priority-dependencies-v2.json'
BASE_REPORT=ROOT/'tools/action_predictor/experiments/v5/M01.json'
BASE_PREDICTIONS=ROOT/'.cambc/action-predictor/v5/runs/M01/validation-predictions.npz'

def read(path):return json.loads(Path(path).read_text(encoding='utf-8'))

def check_hashes(mapping):
    for path,digest in mapping.items():assert sha(path)==digest,'Dependency or baseline mismatch: '+path

def baseline_binding():
    original=read(BASE_REPORT)
    assert sha(BASE_PREDICTIONS)==original['predictions_sha256'],'Baseline prediction archive mismatch'
    return dict(report_sha256=sha(BASE_REPORT),predictions_sha256=original['predictions_sha256'])

def freeze_dependencies():
    # Original source locks remain authoritative; never update them to fit live edits.
    old=read(ROOT/'tools/action_predictor/experiments/v7/execution-lock.json')
    check_hashes(old['training_sources']);check_hashes(old['preserved_checkpoints']);check_hashes(old['runtime_assets'])
    entry=read(REPORTS/'entry-audit.json');check_hashes(entry['source_hashes'])
    directory=ROOT/'tools/action_predictor'
    paths=sorted([*directory.glob('*.py'),*directory.glob('*.cjs')])
    sources=dict(old['training_sources'])|{str(path):sha(path) for path in paths}
    snapshots=WORK/'dependencies-v2';snapshots.mkdir(exist_ok=True)
    for path,digest in sources.items():
        source=Path(path);copy=snapshots/(digest+'_'+source.name)
        if not copy.exists():copy.write_bytes(source.read_bytes())
        assert sha(copy)==digest
    frozen(MANIFEST,dict(sources=sources,baseline=baseline_binding(),
        baseline_paths={str(BASE_REPORT):sha(BASE_REPORT),str(BASE_PREDICTIONS):sha(BASE_PREDICTIONS)},
        preserved_checkpoints=old['preserved_checkpoints'],runtime_assets=old['runtime_assets'],
        python=sys.version,torch=str(torch.__version__),numpy=np.__version__,
        prior_v1_design_sha256=sha(REPORTS/'priority-logistic-design.json'),fits_started=0))

def verify_dependencies():
    manifest=read(MANIFEST)
    check_hashes(manifest['sources']);check_hashes(manifest['baseline_paths'])
    check_hashes(manifest['preserved_checkpoints']);check_hashes(manifest['runtime_assets'])
    assert manifest['baseline']==baseline_binding()
    assert (manifest['python'],manifest['torch'],manifest['numpy'])==(sys.version,str(torch.__version__),np.__version__)
    return sha(MANIFEST)
