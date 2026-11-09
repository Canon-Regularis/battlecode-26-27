"""Freeze executable provenance and audit eligible evidence before fitting."""
from collections import Counter
import json
from pathlib import Path
import platform
import subprocess
import sys
import time

import numpy as np
import torch

from .more_replays import frozen,sha
from .observation_study import ROOT,WORK,REPORTS,OLD,MORE,freeze_plan,log_command


def sealed_audit():
    membership_path=ROOT/'tools/action_predictor/experiments/v5/membership.json'
    membership=json.loads(membership_path.read_text())
    reserved=[r for r in membership['records'] if r['split']!='train']
    assert len(reserved)==150
    jobs=json.loads((WORK/'jobs.json').read_text());allowed={j['record']['raw_sha256'] for j in jobs}
    for record in reserved:
        hashed=record['raw_sha256'];assert hashed not in allowed
        assert sha(record['path'])==record['bundle_sha256'],'Opaque reserved bundle bytes changed'
        for directory in (MORE/'source/extracted',MORE/'supplement',MORE/'augmentation',WORK/'games'):
            assert not (directory/hashed).exists(),str(directory/hashed)
        assert not (WORK/'targets'/(hashed+'.npz')).exists()
    assert {p.name for p in (WORK/'games').iterdir() if p.is_dir()}==allowed
    assert {p.stem for p in (WORK/'targets').glob('*.npz')}==allowed
    return dict(membership_sha256=sha(membership_path),new_validation_games=75,new_validation_groups=15,
        final_test_games=75,final_test_groups=15,opaque_bundle_hashes_unchanged=True,
        reserved_decoders=0,reserved_features=0,reserved_labels_or_scores=0,eligible_history_games=len(allowed),
        policy='Only opaque archive SHA256 and existing membership metadata inspected for the reserved partitions; no decoding or behaviour inspection.')


def audit_data():
    ready=json.loads((REPORTS/'data-ready.json').read_text())
    for name,digest in ready['files'].items():assert sha(WORK/name)==digest,name
    assert sha(WORK/'row-frame-manifest.json')==ready['manifest_sha256']
    jobs=json.loads((WORK/'jobs.json').read_text());assert len(jobs)==495
    splits={name:[j for j in jobs if j['split']==name] for name in ('train','validation')}
    assert [len(splits[name]) for name in splits]==[470,25]
    train={j['record']['raw_sha256'] for j in splits['train']};val={j['record']['raw_sha256'] for j in splits['validation']}
    assert len(train)==470 and len(val)==25 and not train&val
    tg={j['record']['group'] for j in splits['train']};vg={j['record']['group'] for j in splits['validation']}
    assert len(tg)==94 and len(vg)==5 and not tg&vg
    frame_count=0;support={};receipt_hashes={}
    for job in jobs:
        raw=job['record']['raw_sha256'];directory=WORK/'games'/raw
        receipt=json.loads((directory/'receipt.json').read_text())
        assert receipt['rows']==job['rows'] and receipt['shard_sha256']==sha(job['shard'])
        assert receipt['chronology_alignment'] and receipt['action_history_bitwise_identical']
        assert receipt['missing_observation_frames']==0
        for name,digest in receipt['code_hashes'].items():assert sha(ROOT/'tools/action_predictor'/name)==digest
        for name,digest in receipt['files'].items():assert sha(directory/name)==digest
        frame_count+=receipt['frames'];receipt_hashes[raw]=sha(directory/'receipt.json')
    assert frame_count==ready['frames']
    for split,n in [('train',433071),('validation',14439)]:
        sequence=np.load(WORK/(split+'-sequence.npy'),mmap_mode='r');gaps=np.load(WORK/(split+'-gaps.npy'),mmap_mode='r')
        available=np.load(WORK/(split+'-available.npy'),mmap_mode='r')
        assert len(sequence)==n and np.array_equal((sequence>0).sum(-1),available)
        assert np.array_equal(sequence>0,gaps[:,:,1]>0) and np.array_equal(gaps[:,:,0],gaps[:,:,1])
        assert np.all((sequence>=0)&(sequence<=frame_count))
        assert np.isfinite(gaps).all() and np.all((gaps>=0)&(gaps<=1))
        support[split]=dict(rows=n,available_history_counts=dict(Counter(map(int,available))),missing_observations=0)
    return dict(passed=True,duplicate_payloads_across_training_validation=0,whole_groups_disjoint=True,
        train_games=470,train_groups=94,validation_games=25,validation_groups=5,
        all_target_rows_retained=True,all_current_features_and_previous_action_tokens_bitwise_identical=True,
        all_prior_snapshots_personal_and_causal=True,receipt_sha256=receipt_hashes,history_support=support)


def freeze_execution():
    freeze_plan()
    assert not (WORK/'fit-ledger.json').exists(),'Execution must be frozen before any substantive fit'
    audit=audit_data();frozen(REPORTS/'causal-data-audit.json',audit)
    frozen(REPORTS/'sealed-test-audit-before.json',sealed_audit())
    command=[sys.executable,'-m','unittest','tools.action_predictor.test_observation_history','-v']
    log_command(command,purpose='Causal, missing-history, matching and accounting verification before fits')
    started=time.time();result=subprocess.run(command,capture_output=True,text=True,encoding='utf-8')
    (WORK/'verification-before-fitting.txt').write_text(result.stdout+result.stderr,encoding='utf-8')
    assert result.returncode==0,result.stderr
    frozen(REPORTS/'verification-before-fitting.json',dict(passed=True,command=command,exit_code=result.returncode,
        log_sha256=sha(WORK/'verification-before-fitting.txt'),started_at_unix=started))
    source_paths=sorted([* (ROOT/'tools/action_predictor').glob('*.py'),*(ROOT/'tools/action_predictor').glob('*.cjs')])
    old_manifest=json.loads((ROOT/'.cambc/action-predictor/data/dataset.json').read_text())
    source=Path(old_manifest['source']);reader=source.parents[2]/'tools/replay_eval/frozen_v1_5'
    source_paths+=sorted(reader.glob('*.cjs'))
    source_paths.append(reader.parent/'decisions/destinations_static.cjs')
    snapshots=WORK/'provenance';snapshots.mkdir(exist_ok=True)
    hashes={};copies={}
    for path in source_paths:
        digest=sha(path);snapshot=snapshots/(digest+'_'+path.name)
        if not snapshot.exists():snapshot.write_bytes(path.read_bytes())
        assert sha(snapshot)==digest
        if path.name not in ('observation_roundtrip.py','observation_report.py'):
            hashes[str(path)]=digest
        copies[str(path)]=dict(path=str(snapshot),sha256=digest)
    assets=next(source.parents[1].glob('asset-cache-5/*/visualiser/assets'))
    runtime_assets={str(assets/name):sha(assets/name) for name in
        ('index-B7p3Cpbd.js','PanelChrome-DRtW3oWL.js','v2_0_0-hWOQ1R8f.wasm','v3_0_0-DBS2ESWO.wasm')}
    checkpoints={str(path):sha(path) for version in ('v4','v5','v6') for path in (ROOT/'.cambc/action-predictor'/version/'runs').glob('*/model.pt')}
    checkpoints[str(ROOT/'.cambc/action-predictor/run-1/model.pt')]=sha(ROOT/'.cambc/action-predictor/run-1/model.pt')
    frozen(REPORTS/'execution-lock.json',dict(training_sources=hashes,source_snapshots=copies,
        preserved_checkpoints=checkpoints,runtime_assets=runtime_assets,plan_sha256=sha(REPORTS/'plan.json'),data_ready_sha256=sha(REPORTS/'data-ready.json'),
        causal_audit_sha256=sha(REPORTS/'causal-data-audit.json'),python=sys.version,executable=sys.executable,
        torch=torch.__version__,numpy=np.__version__,platform=platform.platform(),processor=platform.processor(),
        frozen_before_training=True,substantive_fits_started=0))
    print('Observation-history execution locked; causal evidence, fixed rows and reserved partitions verified.',flush=True)


if __name__=='__main__':
    log_command([sys.executable,'-m','tools.action_predictor.observation_validate',*sys.argv[1:]],purpose='Freeze executable/data provenance and check reserved partitions')
    freeze_execution()
