"""Encode saved verified getter records; never re-query replays."""
import json
from pathlib import Path

import numpy as np

from ..audit import immutable_json
from ..data import digest
from ..priority_broad.guard import committed_sources
from ..priority_regularized.safety import dependency_files,reject_optimized_python
from .anchored import ROOT,anchored_inputs
from .schema_asinh import FIELDS,encode,normalizer

LOCAL=ROOT/'.cambc/action-predictor/v23'
OUT=ROOT/'tools/action_predictor/experiments/v23'


def run():
    reject_optimized_python()
    commit,sources=committed_sources(ROOT,dependency_files(ROOT,(
        'tools.action_predictor.order_information.cache_asinh',
        'tools.action_predictor.order_information.test_asinh')))
    ready_path=OUT/'order-cache-ready.json'
    from .anchored import committed_manifest
    ready,bindings=committed_manifest(commit,ready_path.relative_to(ROOT).as_posix())
    fit,controls,more=anchored_inputs();bindings.update(more)
    for name,expected in ready['files'].items():
        if digest(ROOT/name)!=expected:raise RuntimeError('Raw input cache changed')
        bindings[name]=expected
    plan=dict(source_commit=commit,sources=sources,inputs=bindings,fields=list(FIELDS),
        reason='TRAIN raw gaps reach2080375424. Signed asinh per-unit int64 delta keeps '
               'ordinary gaps comparable without clipping. Below/equal/above fractions remain '
               'exact integer comparisons; count/availability unchanged.',
        computation='Only saved API records consumed. Preserve original raw-gap encoding and '
                    'all rows. No model/prediction/control-outcome selection; no new replay query.',
        normalization='Mean/std on5876fit rows only, stdfloor.01, no control values in fit statistics.',
        new_fits=0,engine_queries=0,reserved_opened=0)
    immutable_json(OUT/'order-asinh-plan.json',plan)
    indices=np.load(LOCAL/'index.npy')
    raw=np.zeros((len(indices),32),np.float32);seen=np.zeros(len(indices),bool)
    receipts={}
    for payload,expected in ready['receipts'].items():
        path=LOCAL/'games'/payload/'receipt.json'
        if digest(path)!=expected:raise RuntimeError('Getter receipt changed')
        receipt=json.loads(path.read_text())
        source=path.with_name('raw.jsonl')
        if digest(source)!=receipt['raw_sha256']:raise RuntimeError('Getter raw archive changed')
        receipts[str(path.relative_to(ROOT))]=expected
        for line in source.open(encoding='utf-8'):
            row=json.loads(line)
            if row['record']!='order_pre':continue
            at=int(np.searchsorted(indices,row['row']))
            if at==len(indices) or indices[at]!=row['row'] or seen[at]:raise RuntimeError('Order row alignment')
            raw[at]=encode(row);seen[at]=True
    if not seen.all():raise RuntimeError('Order rows missing')
    at=np.searchsorted(indices,fit['index'].numpy())
    np.testing.assert_array_equal(indices[at],fit['index'].numpy())
    mean,std=normalizer(raw[at]);features=(raw-mean)/std
    files={}
    for name,value in [('asinh-raw-features',raw),('asinh-features',features)]:
        path=LOCAL/(name+'.npy')
        if path.exists():raise FileExistsError(path)
        np.save(path,value);files[str(path.relative_to(ROOT))]=digest(path)
    path=LOCAL/'asinh-normalizer.npz'
    if path.exists():raise FileExistsError(path)
    np.savez_compressed(path,mean=mean,std=std);files[str(path.relative_to(ROOT))]=digest(path)
    immutable_json(OUT/'order-asinh-ready.json',dict(plan_sha256=digest(OUT/'order-asinh-plan.json'),
        files=files,index_sha256=digest(LOCAL/'index.npy'),rows=len(indices),fit_rows=5876,
        raw_receipts=receipts,fields=list(FIELDS),source_commit=commit,new_fits=0,engine_queries=0,reserved_opened=0))
    print('TRAIN-scaled order encoding ready; saved getter records reused, queries0.',flush=True)


if __name__=='__main__':run()
