"""Every-decision scoped order recovery from eligible recordings, no fitting."""
from concurrent.futures import ThreadPoolExecutor,as_completed
import json
import re
import subprocess
import sys
import time
import traceback
from pathlib import Path

import numpy as np

from ..audit import immutable_json,validate_decision,cursor
from ..data import digest
from ..rich_data import read_turns
from .protocol import ROOT,OUT,LOCAL,ROWS,freeze,source_gate


def validate_jobs(jobs):
    if len(jobs)!=495 or {j['split'] for j in jobs}!={'train','validation'}:raise RuntimeError('Ineligible or incomplete jobs')
    if len({j['record']['raw_sha256'] for j in jobs})!=len(jobs):raise RuntimeError('Duplicate payload jobs')
    for j in jobs:
        if not re.fullmatch('[0-9a-f]{64}',j['record']['raw_sha256']) or j['record']['engine_version'] not in ('2.0.0','3.0.0'):
            raise RuntimeError('Unsupported eligible recording metadata')
    for split,total in ROWS.items():
        ordered=sorted([j for j in jobs if j['split']==split],key=lambda j:j['offset']);offset=0
        if len(ordered)!={'train':470,'validation':25}[split]:raise RuntimeError('Game denominator changed')
        for j in ordered:
            if j['offset']!=offset or j['rows']<=0:raise RuntimeError('Job rows overlap or have a gap')
            offset+=j['rows']
        if offset!=total:raise RuntimeError('Row denominator changed')


def request_row(index,turn,decision,values,team):
    if turn['view']['team']!=team:raise RuntimeError('Personal team mismatch')
    if values.shape!=(7,) or values.dtype!=np.int64 or values[1] not in (0,1) or values[3] not in (0,1):
        raise RuntimeError('Own PRE control schema changed')
    return dict(row=int(index),actor=int(turn['actor']),round=int(turn['round']),pre=decision['pre_cursor'],
                current=int(values[0]),scheduled=int(values[2]),current_available=bool(values[1]),scheduled_available=bool(values[3]))


def validate_row(row,expected):
    if row['record']!='order_pre' or any(row[key]!=expected[key] for key in ('row','actor','pre')):
        raise RuntimeError('Recovered PRE identity mismatch')
    if 'round' in row and row['round']!=expected['round']:raise RuntimeError('Recovered round mismatch')
    for time in ('current','scheduled'):
        flag=row['own'][time+'_available'];value=row['own'][time]
        if type(flag) is not bool or flag!=expected[time+'_available'] or (flag and value!=expected[time]) or (not flag and value is not None):
            raise RuntimeError('Recovered own field differs from immutable PRE control')
    for unit in row['others']:
        if unit.get('known') is not True or unit['role'] not in ('ally','enemy'):raise RuntimeError('Unknown or invalid unit retained')
        for time in ('current','scheduled'):
            flag=unit[time+'_available'];value=unit[time]
            if type(flag) is not bool or (flag and (type(value) is not int or not -(2**31)<=value<2**31)) or (not flag and value is not None):
                raise RuntimeError('Other field availability/integer contract changed')
    # Explicit permitted fields only; no answer, transaction or source-status feature.
    own={key:row['own'][key] for key in ('current','current_available','scheduled','scheduled_available')}
    others=[{key:unit[key] for key in ('known','role','current','current_available','scheduled','scheduled_available')} for unit in row['others']]
    return dict(record='order_pre',row=expected['row'],pre=expected['pre'],actor=expected['actor'],round=expected['round'],own=own,others=others)


def run():
    commit,_=source_gate()
    commands=([sys.executable,'-m','unittest','tools.action_predictor.policy_priority_integration.test_recover','-v'],
              ['node',str(ROOT/'tools/action_predictor/order_information/test_getter.cjs')],
              ['node',str(ROOT/'tools/action_predictor/policy_priority_integration/test_capture.cjs')])
    tests=[]
    for command in commands:
        result=subprocess.run(command,cwd=ROOT,capture_output=True,text=True)
        tests.append(dict(command=command,returncode=result.returncode,stdout=result.stdout,stderr=result.stderr))
        if result.returncode:
            immutable_json(OUT/f'JP-prerequisite-failure-{time.time_ns()}.json',dict(source_commit=commit,tests=tests))
            raise RuntimeError('Recovery prerequisite failed; no query started')
    plan,receipts,bindings=freeze();plan_hash=digest(OUT/'JP-plan.json')
    if (OUT/'JP-fields-ready.json').exists():raise FileExistsError('Fields already complete; consume immutable cache, do not rerun')
    jobs=json.loads((ROOT/'.cambc/action-predictor/v7/jobs.json').read_text());validate_jobs(jobs)
    own={}
    for split in ROWS:
        with np.load(ROOT/f'.cambc/action-predictor/v8/priority-{split}.npz') as z:own[split]=z['values']
        if own[split].shape!=(ROWS[split],7) or own[split].dtype!=np.int64:raise RuntimeError('Own controls changed shape/dtype')

    def capture(job):
        raw=job['record']['raw_sha256'];directory=LOCAL/'games'/raw;directory.mkdir(parents=True,exist_ok=True)
        receipt_path=directory/'receipt.json'
        if receipt_path.exists():
            saved=json.loads(receipt_path.read_text())
            if saved['plan_sha256']!=plan_hash:raise RuntimeError('Completed per-game plan changed')
            for name,expected in saved['files'].items():
                if digest(directory/name)!=expected:raise RuntimeError('Completed per-game artifact changed')
            return job,saved
        if any(directory.iterdir()):raise RuntimeError('Incomplete recovery retained; inspect/version before retry: '+raw)
        old_dir=ROOT/'.cambc/action-predictor/v8/priority'/raw
        old_receipt_path=old_dir/'receipt.json';old_query_path=old_dir/'query.json'
        if digest(old_receipt_path)!=receipts['priority']['receipts'][raw]:raise RuntimeError('Old eligible receipt changed')
        old_receipt=json.loads(old_receipt_path.read_text())
        if digest(old_query_path)!=old_receipt['files']['query.json']:raise RuntimeError('Old eligible query changed')
        old_query=json.loads(old_query_path.read_text())
        turns=read_turns(job['manifest'],job['record']);decisions=[(t,d) for t in turns for d in t['decisions']]
        if len(decisions)!=job['rows']:raise RuntimeError('Original row table changed')
        expected={}
        for local,(turn,decision) in enumerate(decisions):
            validate_decision(decision,turn);index=job['offset']+local
            expected[index]=request_row(index,turn,decision,own[job['split']][index],old_query['team'])
        reused={};lineage={str(old_receipt_path):digest(old_receipt_path),str(old_query_path):digest(old_query_path)}
        if raw in receipts['old_fields']['receipts']:
            old_fields=ROOT/'.cambc/action-predictor/v23/games'/raw
            rp=old_fields/'receipt.json'
            if digest(rp)!=receipts['old_fields']['receipts'][raw]:raise RuntimeError('Old getter receipt changed')
            saved=json.loads(rp.read_text());query_path=old_fields/'query.json';raw_path=old_fields/'raw.jsonl'
            if digest(query_path)!=saved['query_sha256'] or digest(raw_path)!=saved['raw_sha256']:raise RuntimeError('Old getter chain changed')
            old_items={r['row']:r for r in json.loads(query_path.read_text())['rows']}
            for line in raw_path.open(encoding='utf-8'):
                row=json.loads(line)
                if row['record']!='order_pre':continue
                index=row['row']
                if index not in expected or index in reused:raise RuntimeError('Old getter row membership changed')
                if any(old_items[index][key]!=expected[index][key] for key in ('actor','round','pre','current','scheduled')):
                    raise RuntimeError('Old getter PRE binding changed')
                reused[index]=validate_row(row,expected[index])
            if sorted(reused)!=saved['row_indices']:raise RuntimeError('Old getter completeness changed')
            for p in (rp,query_path,raw_path):lineage[str(p)]=digest(p)
        pending=sorted([item for index,item in expected.items() if index not in reused],key=lambda r:cursor(r['pre']))
        query_bindings=dict(lineage)
        for p in (ROOT/'tools/action_predictor/policy_priority_integration/capture.cjs',ROOT/'tools/action_predictor/order_information/getter.cjs',
                  ROOT/'.cambc/action-predictor/v7/jobs.json'):
            expected_hash=plan['sources'].get(p.relative_to(ROOT).as_posix(),plan['inputs'].get(str(p.relative_to(ROOT))))
            if expected_hash is None or digest(p)!=expected_hash:raise RuntimeError('Frozen query code/input changed: '+str(p))
            query_bindings[str(p)]=expected_hash
        for name in ('micro_playback.cjs','playback.cjs'):
            p=Path(old_query['reader'])/'frozen_v1_5'/name
            matches=[v for k,v in receipts['runtime'].items() if Path(k)==p]
            if len(matches)!=1 or digest(p)!=matches[0]:raise RuntimeError('Unpinned historical reader: '+str(p))
            query_bindings[str(p)]=matches[0]
        query=dict(split=job['split'],raw=old_query['raw'],raw_sha256=raw,reader=old_query['reader'],assets=old_query['assets'],
            team=old_query['team'],expected_engine='v'+job['record']['engine_version'].replace('.','_'),rows=pending,
            bindings=query_bindings,output=str(directory/'raw.jsonl'))
        immutable_json(directory/'query.json',query);recovered={}
        if pending:
            result=subprocess.run(['node',str(ROOT/'tools/action_predictor/policy_priority_integration/capture.cjs'),str(directory/'query.json')],
                cwd=ROOT,capture_output=True,text=True,encoding='utf-8',creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            if result.returncode:
                immutable_json(directory/'failure.json',dict(returncode=result.returncode,stderr=result.stderr,stdout=result.stdout,
                    query_sha256=digest(directory/'query.json')))
                raise RuntimeError('Personal field recovery failed: '+raw+' '+result.stderr[-1200:])
            footer=None
            for line in (directory/'raw.jsonl').open(encoding='utf-8'):
                row=json.loads(line)
                if row['record']=='complete':footer=row
                if row['record']!='order_pre':continue
                if row['row'] not in expected or row['row'] in reused or row['row'] in recovered:raise RuntimeError('New getter row duplicated/outside job')
                recovered[row['row']]=validate_row(row,expected[row['row']])
            if footer is None or footer['rows']!=len(pending) or footer['engine']!=query['expected_engine']:
                raise RuntimeError('Incomplete new getter output')
        if set(reused)|set(recovered)!=set(expected):raise RuntimeError('Original rows missing from fields')
        with (directory/'rows.jsonl').open('x',encoding='utf-8') as f:
            for index in sorted(expected):f.write(json.dumps((reused if index in reused else recovered)[index])+'\n')
        saved=dict(split=job['split'],rows=job['rows'],offset=job['offset'],raw_sha256=raw,
            reused_rows=len(reused),new_query_rows=len(recovered),engine=query['expected_engine'],plan_sha256=plan_hash,
            lineage=lineage,files={p.name:digest(p) for p in directory.iterdir() if p.is_file()})
        immutable_json(receipt_path,saved)
        return job,saved

    # One TRAIN game per historical engine catches new recovery assumptions before broad work.
    pilots=[]
    for engine in ('2.0.0','3.0.0'):pilots.append(next(j for j in jobs if j['split']=='train' and j['record']['engine_version']==engine))
    completed=[]
    for job in pilots:
        completed.append(capture(job));print('JP field pilot complete',job['record']['engine_version'],job['rows'],flush=True)
    remaining=[j for j in jobs if j['record']['raw_sha256'] not in {p['record']['raw_sha256'] for p in pilots}]
    pool=ThreadPoolExecutor(max_workers=4);futures=[]
    try:
        futures=[pool.submit(capture,j) for j in remaining]
        for future in as_completed(futures):
            completed.append(future.result())
            if len(completed)%10==0 or len(completed)==len(jobs):print('JP personal fields',len(completed),'/',len(jobs),flush=True)
    except BaseException:
        for f in futures:f.cancel()
        raise
    finally:pool.shutdown(wait=True,cancel_futures=True)
    compact(completed,bindings,plan,tests)


def compact(completed,bindings,plan,tests):
    directory=LOCAL/'data'
    if directory.exists():raise FileExistsError('Preserve prior compact-array attempt')
    directory.mkdir(parents=True);results={};receipts={}
    for job,saved in completed:
        path=LOCAL/'games'/job['record']['raw_sha256']/'receipt.json';receipts[job['record']['raw_sha256']]=digest(path)
    for split,n in ROWS.items():
        lengths=np.zeros(n,np.int64);seen=np.zeros(n,bool);selected=[(j,s) for j,s in completed if j['split']==split]
        for job,saved in selected:
            path=LOCAL/'games'/job['record']['raw_sha256']/'rows.jsonl'
            if digest(path)!=saved['files']['rows.jsonl']:raise RuntimeError('Combined field rows changed')
            for line in path.open(encoding='utf-8'):
                row=json.loads(line);index=row['row']
                if index<job['offset'] or index>=job['offset']+job['rows'] or seen[index]:raise RuntimeError('Compact row identity invalid')
                seen[index]=True;lengths[index]=len(row['others'])
        if not seen.all():raise RuntimeError('Every-decision coverage incomplete')
        offsets=np.r_[np.int64(0),lengths.cumsum()];m=int(offsets[-1])
        priorities=np.lib.format.open_memmap(directory/f'{split}-priorities.npy',mode='w+',dtype=np.int64,shape=(m,2))
        available=np.lib.format.open_memmap(directory/f'{split}-available.npy',mode='w+',dtype=np.bool_,shape=(m,2))
        roles=np.lib.format.open_memmap(directory/f'{split}-roles.npy',mode='w+',dtype=np.int8,shape=(m,))
        for job,saved in selected:
            path=LOCAL/'games'/job['record']['raw_sha256']/'rows.jsonl'
            for line in path.open(encoding='utf-8'):
                row=json.loads(line);start=int(offsets[row['row']])
                for j,unit in enumerate(row['others']):
                    roles[start+j]=0 if unit['role']=='ally' else 1
                    for t,time in enumerate(('current','scheduled')):
                        available[start+j,t]=unit[time+'_available'];priorities[start+j,t]=unit[time] if unit[time+'_available'] else 0
        for a in (priorities,available,roles):a.flush()
        np.save(directory/f'{split}-offsets.npy',offsets)
        results[split]=dict(rows=n,games=len(selected),unit_tokens=m,rows_without_known_other_units=int((lengths==0).sum()),
            available_fields=int(available.sum()),unavailable_fields=int((~available).sum()),
            reused_rows=sum(s['reused_rows'] for _,s in selected),new_query_rows=sum(s['new_query_rows'] for _,s in selected))
    files={str(p.relative_to(ROOT)):digest(p) for p in directory.iterdir()}
    immutable_json(OUT/'JP-fields-ready.json',dict(source_commit=plan['source_commit'],sources=plan['sources'],
        plan_sha256=digest(OUT/'JP-plan.json'),inputs=bindings,receipts=receipts,files=files,results=results,tests=tests,
        fields=['exactint64current/scheduled','pairedavailability','ally/enemyrole','raggedrowoffsets'],
        metadata_not_features=['game/row/entityidentities','reusedvsnewsource','engine/group'],
        new_fits=0,optimizer_updates=0,reserved_opened=0,command='python -m tools.action_predictor.policy_priority_integration.recover'))
    print('Every-decision personal fields complete',results,flush=True)


if __name__=='__main__':run()
