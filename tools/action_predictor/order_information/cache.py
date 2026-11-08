"""New personal order fields for the fixed TRAIN diagnostic cohort only."""
import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor,as_completed
from pathlib import Path

import numpy as np

from ..audit import immutable_json,validate_decision,cursor
from ..data import digest
from ..rich_data import read_turns
from ..priority_broad.guard import committed_sources
from ..priority_regularized.safety import reject_optimized_python,dependency_files
from .anchored import ROOT,anchored_inputs
from .schema import FIELDS,encode,normalizer

LOCAL=ROOT/'.cambc/action-predictor/v23'
OUT=ROOT/'tools/action_predictor/experiments/v23'
HISTORICAL='275b717b01b2f45341de341d65b28cbe248691d1'


def sources():
    here=Path(__file__).parent
    return dependency_files(ROOT,('tools.action_predictor.order_information.cache',
        'tools.action_predictor.order_information.test_anchored',
        'tools.action_predictor.order_information.test_schema')) + [
            here/n for n in ('getter.cjs','test_getter.cjs','capture.cjs')]


def prepare():
    reject_optimized_python()
    commit,code=committed_sources(ROOT,sources())
    for command in ([sys.executable,'-m','unittest','tools.action_predictor.order_information.test_anchored',
                     'tools.action_predictor.order_information.test_schema'],
                    ['node',str(Path(__file__).with_name('test_getter.cjs'))]):
        subprocess.run(command,cwd=ROOT,check=True)
    fit,controls,input_bindings=anchored_inputs()
    all_data=[fit,controls['same_fit_groups'],controls['held_groups']]
    lookup={}
    for d in all_data:
        for index,values in zip(d['index'].tolist(),d['values'].tolist()):
            if index in lookup and lookup[index]!=values:
                raise RuntimeError('Cohort own-priority inputs disagree')
            lookup[index]=values
    indices=np.asarray(sorted(lookup),dtype=np.int64)
    if len(indices)!=6132:
        raise RuntimeError('Fixed feature-query population changed')
    jobs_path=ROOT/'.cambc/action-predictor/v7/jobs.json'
    if digest(jobs_path)!='80c61417faed19ebcb8f8f59db35ba0588d7862ff68dfa3eff58f7de4aab14ba':
        raise RuntimeError('Eligible job table changed')
    jobs=[j for j in json.loads(jobs_path.read_text()) if j['split']=='train' and
          ((indices>=j['offset'])&(indices<j['offset']+j['rows'])).any()]
    assigned=np.concatenate([indices[(indices>=j['offset'])&(indices<j['offset']+j['rows'])] for j in jobs])
    np.testing.assert_array_equal(np.sort(assigned),indices)
    ready_path=ROOT/'tools/action_predictor/experiments/v8/priority-data-ready.json'
    old_blob=subprocess.run(['git','show',HISTORICAL+':'+ready_path.relative_to(ROOT).as_posix()],cwd=ROOT,
                            check=True,capture_output=True).stdout
    if ready_path.read_bytes()!=old_blob:
        raise RuntimeError('Historical priority receipt table changed')
    old_ready=json.loads(old_blob)
    plan=dict(id='order-input-cache',source_commit=commit,sources=code,
        inputs={**input_bindings,str(jobs_path.relative_to(ROOT)):digest(jobs_path),
                str(ready_path.relative_to(ROOT)):digest(ready_path)},
        fields=list(FIELDS),rows=6132,fit_rows=5876,games=len(jobs),
        population='Identical PC01/PC02 natural TRAIN fitting rows plus both unchanged controls; '
                   'original128fit subset included. Queries selected for training/conditional '
                   'diagnostic membership, not oracle action routing in a complete predictor.',
        features='For known other champions only, scoped API current/next priority with masks. '
                 'Allies/enemies separately: availability,count,min/max/mean offset from own '
                 'corresponding priority,below/equal/above fractions. Every known unit included; '
                 'no nearest-k cutoff, unit/game IDs or target command in feature inputs.',
        normalization='Mean/std from5876fitting rows only, std floor.01; controls excluded. '
                      'Zero-information comparison receives literal32zeros after normalization.',
        contract='Every query PRE actor/round/order checked; own API values equal bound causal '
                 'priority cache. Getter successes match personal snapshot; failure97 masks '
                 'unavailable. Unknown units never queried/retained. Header/state unchanged. '
                 'Raw rows archived before validation; incomplete jobs preserved and not merged.',
        evaluation='Conditional priority diagnostic only. Full-policy use later requires inputs '
                   'for every evaluation row, predicted families and normalized joint decoding. '
                   'Current cache must never be oracle-routed into complete predictions.',
        constraints='Existing eligibleTRAINrecordings only; no DEV/reserved payloads, actions, '
                    'matches, branches, bots, deployment or replay downloads.',
        new_fits=0,reserved_opened=0)
    immutable_json(OUT/'order-cache-plan.json',plan)
    plan_hash=digest(OUT/'order-cache-plan.json')
    shared={str(ROOT/name):expected for name,expected in code.items()}

    def capture(job):
        raw=job['record']['raw_sha256']
        directory=LOCAL/'games'/raw
        directory.mkdir(parents=True,exist_ok=True)
        receipt_path=directory/'receipt.json'
        if receipt_path.exists():
            receipt=json.loads(receipt_path.read_text())
            if receipt['plan_sha256']!=plan_hash or digest(directory/'raw.jsonl')!=receipt['raw_sha256']:
                raise RuntimeError('Completed order cache changed')
            return receipt
        if (directory/'raw.jsonl').exists():
            raise RuntimeError('Incomplete order query preserved; inspect/version before retry')
        old_dir=ROOT/'.cambc/action-predictor/v8/priority'/raw
        old_receipt_path=old_dir/'receipt.json'
        if digest(old_receipt_path)!=old_ready['receipts'][raw]:
            raise RuntimeError('Independently anchored replay receipt changed')
        old_receipt=json.loads(old_receipt_path.read_text())
        old_query_path=old_dir/'query.json'
        if digest(old_query_path)!=old_receipt['files']['query.json']:
            raise RuntimeError('Historical replay query changed')
        old_query=json.loads(old_query_path.read_text())
        selected=indices[(indices>=job['offset'])&(indices<job['offset']+job['rows'])]
        turns=read_turns(job['manifest'],job['record'])
        decisions=[(t,d) for t in turns for d in t['decisions']]
        if len(decisions)!=job['rows']:
            raise RuntimeError('Target row order changed')
        requests=[]
        for index in selected:
            turn,decision=decisions[int(index)-job['offset']]
            validate_decision(decision,turn)
            if turn['view']['team']!=old_query['team']:
                raise RuntimeError('Personal team mismatch')
            values=lookup[int(index)]
            if values[1]!=1 or values[3]!=1:
                raise RuntimeError('Expected own priority reference unavailable')
            requests.append(dict(row=int(index),actor=turn['actor'],round=turn['round'],pre=decision['pre_cursor'],
                                 current=values[0],scheduled=values[2]))
        requests.sort(key=lambda r:cursor(r['pre']))
        bindings={**shared,str(old_query_path):digest(old_query_path),
                  str(old_receipt_path):digest(old_receipt_path)}
        for name in ('micro_playback.cjs','playback.cjs'):
            path=Path(old_query['reader'])/'frozen_v1_5'/name
            bindings[str(path)]=digest(path)
        query=dict(raw=old_query['raw'],raw_sha256=raw,reader=old_query['reader'],assets=old_query['assets'],
            team=old_query['team'],expected_engine='v'+job['record']['engine_version'].replace('.','_'),
            rows=requests,bindings=bindings,output=str(directory/'raw.jsonl'))
        query_path=directory/'query.json'
        immutable_json(query_path,query)
        command=['node',str(Path(__file__).with_name('capture.cjs')),str(query_path)]
        result=subprocess.run(command,cwd=ROOT,capture_output=True,text=True,encoding='utf-8',
            creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        if result.returncode:
            immutable_json(directory/'failure.json',dict(returncode=result.returncode,
                stderr=result.stderr,stdout=result.stdout,query_sha256=digest(query_path)))
            raise RuntimeError('Order capture failed: '+raw+' '+result.stderr[-1500:])
        footer=None
        found=[]
        for line in (directory/'raw.jsonl').open(encoding='utf-8'):
            row=json.loads(line)
            if row['record']=='order_pre':found.append(row['row'])
            if row['record']=='complete':footer=row
        if footer is None or sorted(found)!=selected.tolist() or len(found)!=len(set(found)):
            raise RuntimeError('Order capture incomplete or duplicated')
        receipt=dict(rows=len(found),row_indices=sorted(found),engine=footer['engine'],stats=footer['stats'],
            plan_sha256=plan_hash,query_sha256=digest(query_path),raw_sha256=digest(directory/'raw.jsonl'),
            old_receipt_sha256=digest(old_receipt_path),raw_payload_sha256=raw)
        immutable_json(receipt_path,receipt)
        return receipt

    receipts=[]
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures=[pool.submit(capture,job) for job in jobs]
        for n,future in enumerate(as_completed(futures),1):
            receipts.append(future.result())
            if n%20==0 or n==len(jobs):
                print('Personal order games',n,'/',len(jobs),flush=True)
    raw_features=np.zeros((len(indices),32),np.float32)
    seen=np.zeros(len(indices),bool)
    for receipt in receipts:
        path=LOCAL/'games'/receipt['raw_payload_sha256']/'raw.jsonl'
        for line in path.open(encoding='utf-8'):
            row=json.loads(line)
            if row['record']!='order_pre':continue
            at=int(np.searchsorted(indices,row['row']))
            if at==len(indices) or indices[at]!=row['row'] or seen[at]:
                raise RuntimeError('Order merge row alignment/duplication')
            raw_features[at]=encode(row);seen[at]=True
    if not seen.all():raise RuntimeError('Order rows missing')
    fit_at=np.searchsorted(indices,fit['index'].numpy())
    mean,std=normalizer(raw_features[fit_at])
    normalized=(raw_features-mean)/std
    files={}
    for name,value in [('index',indices),('raw-features',raw_features),('features',normalized)]:
        path=LOCAL/(name+'.npy')
        if path.exists():raise FileExistsError(path)
        np.save(path,value);files[str(path.relative_to(ROOT))]=digest(path)
    path=LOCAL/'normalizer.npz'
    if path.exists():raise FileExistsError(path)
    np.savez_compressed(path,mean=mean,std=std);files[str(path.relative_to(ROOT))]=digest(path)
    support={}
    for name,d in [('broad_fit',fit),('original_fit',controls['fit']),
                   ('same_fit_groups',controls['same_fit_groups']),('held_groups',controls['held_groups'])]:
        rows=raw_features[np.searchsorted(indices,d['index'].numpy())]
        available=(rows[:,[0,8,16,24]]>0).any(1)
        support[name]=dict(rows=len(rows),some_order_available=int(available.sum()),
                           all_order_unavailable=int((~available).sum()))
    immutable_json(OUT/'order-cache-ready.json',dict(plan_sha256=plan_hash,files=files,rows=6132,
        support=support,receipts={r['raw_payload_sha256']:digest(LOCAL/'games'/r['raw_payload_sha256']/'receipt.json') for r in receipts},
        source_commit=commit,fields=list(FIELDS),normalizer_fit_rows=5876,new_fits=0,reserved_opened=0))
    print('Order cache ready',support,flush=True)


if __name__=='__main__':prepare()
