"""Additive checks for frozen priority extraction: upstream identity and alignment.

The original extractor and receipts remain byte-for-byte intact. Consumers must
use this verification, not the producer's permissive cache-return path.
"""
from bisect import bisect_right
from collections import defaultdict
import gzip
import json
from pathlib import Path
import sys
import numpy as np
from .category_study import ROOT,WORK,REPORTS
from .more_replays import sha,frozen
from .audit import cursor
from .rich_data import read_turns

def read(path):return json.loads(Path(path).read_text(encoding='utf-8'))

def validate_metadata(job,expected,receipt):
    assert job==expected,'Job differs from frozen membership/evidence'
    for field,value in [('raw_sha256',expected['record']['raw_sha256']),('split',expected['split']),
                         ('rows',expected['rows']),('engine',expected['record']['engine_version'])]:
        assert receipt[field]==value,'Receipt identity mismatch: '+field
    assert receipt['target_shard_sha256']==expected['shard_sha256']

def validate_arrays(arrays,n):
    assert set(arrays)=={'values','history','last_outside_window'}
    v,h,o=(arrays[key] for key in ('values','history','last_outside_window'))
    assert v.dtype==np.dtype('int64') and h.dtype==np.dtype('int64') and o.dtype==np.dtype('bool')
    assert v.shape==(n,7) and h.shape==(n,16,2) and o.shape==(n,)
    assert np.isin(v[:,[1,3,5]],[0,1]).all() and np.isin(h[:,:,1],[0,1]).all()
    assert (v[:,6]>=0).all()
    for value,mask in [(0,1),(2,3),(4,5)]:assert (v[v[:,mask]==0,value]==0).all()
    assert (v[v[:,5]==0,6]==0).all() and (h[:,:,0][h[:,:,1]==0]==0).all()
    assert np.array_equal(o,(v[:,5]>0)&~h[:,:,1].any(-1))
    for i in np.flatnonzero(h[:,:,1].any(-1)):
        assert v[i,5]==1 and v[i,4]==h[i,np.flatnonzero(h[i,:,1])[-1],0]

def validate_layout(jobs,totals):
    assert len({j['record']['raw_sha256'] for j in jobs})==len(jobs),'Duplicate game membership'
    assert set(j['split'] for j in jobs)<=set(totals)
    for split,n in totals.items():
        stop=0
        for job in sorted([j for j in jobs if j['split']==split],key=lambda j:j['offset']):
            assert job['rows']>0 and job['offset']==stop,'Coverage gap or overlap'
            stop+=job['rows']
        assert stop==n,'Split row total mismatch'

def validate_slice(merged,local,start,n):
    validate_arrays(local,n)
    for key in local:
        a,b=merged[key][start:start+n],local[key]
        assert a.dtype==b.dtype and a.shape==b.shape and a.tobytes()==b.tobytes(),'Merged alignment mismatch: '+key

def load_arrays(path):
    with np.load(path) as archive:return {key:archive[key] for key in archive.files}

def validate_game(job,expected,plan):
    directory=WORK/'priority'/job['record']['raw_sha256'];receipt=read(directory/'receipt.json')
    validate_metadata(job,expected,receipt)
    assert receipt['code_hashes']==plan['sources'],'Extraction source identity mismatch'
    raw=expected['record']['raw_sha256'];source=Path(expected['manifest']['source'])/'extracted'/raw
    index=source/'index.jsonl';index_receipt=read(source/'receipt.json')
    assert sha(index)==index_receipt['files']['index.jsonl']==receipt['index_sha256']
    raw_path=Path(expected['work'])/'supplement'/raw/'raw.bin'
    assert sha(raw_path)==raw and sha(expected['shard'])==expected['shard_sha256']
    with np.load(expected['shard']) as target:assert len(target['y'])==expected['rows']
    turns=[json.loads(line) for line in index.open(encoding='utf-8')]
    assert turns[-1]['status']=='complete'
    originals=read_turns(expected['manifest'],expected['record'])
    targets=[(turn,decision) for turn in originals for decision in turn['decisions']]
    assert len(targets)==expected['rows'];selected={d['event_cursor'] for t,d in targets}
    assert len(selected)==len(targets)
    actors={t['actor'] for t,d in targets};team=originals[0]['view']['team']
    assert all(t['view']['team']==team for t,d in targets)
    query_turns=[];own=defaultdict(list);by_event={}
    for turn in turns:
        if turn.get('record')!='turn' or turn['actor'] not in actors:continue
        roots=[]
        for root in turn['roots']:
            assert root['event'] not in by_event
            item=dict(root=root,actor=turn['actor'],round=turn['round'],turn=turn['id'])
            by_event[root['event']]=item;own[turn['actor']].append(item)
            if root['event'] in selected or root['classification']=='priority':roots.append(root|dict(target=root['event'] in selected))
        if roots:query_turns.append(dict(id=turn['id'],actor=turn['actor'],round=turn['round'],entry=turn['entry'],roots=roots))
    old_source=Path(read(ROOT/'.cambc/action-predictor/data/dataset.json')['source'])
    expected_query=dict(raw=str(raw_path),raw_sha256=raw,team=team,reader=str(old_source.parents[2]/'tools/replay_eval'),
        assets=str(next(old_source.parents[1].glob('asset-cache-5/*/visualiser/assets'))),output=str(directory/'pre.jsonl.gz'),turns=query_turns)
    query=directory/'query.json';assert read(query)==expected_query,'Query differs from frozen evidence'
    node=read(directory/'node-receipt.json')
    assert node['query_sha256']==sha(query) and node['code_hashes']==plan['sources']
    assert node['sha256']==sha(directory/'pre.jsonl.gz')
    assert set(receipt['files'])=={'pre.jsonl.gz','query.json','inputs.npz','node-receipt.json'}
    for name,digest in receipt['files'].items():assert sha(directory/name)==digest
    snapshots={};footer=None
    with gzip.open(directory/'pre.jsonl.gz','rt',encoding='utf-8') as stream:
        for line in stream:
            row=json.loads(line)
            if row['record']=='audit_complete':
                assert footer is None;footer=row;continue
            assert footer is None and row['record']=='priority_pre' and row['event'] not in snapshots
            assert set(row)=={'record','actor','team','turn','round','pre','event','current','scheduled','current_available','scheduled_available','target'}
            e=by_event[row['event']]
            assert row['actor']==e['actor'] and row['team']==team and row['round']==e['round'] and row['turn']==e['turn']
            assert row['pre']==e['root']['pre'] and cursor(row['pre'])<cursor(row['event'])
            for value,available in [('current','current_available'),('scheduled','scheduled_available')]:
                assert isinstance(row[available],bool) and row[available]==(row[value] is not None)
                assert row[value] is None or (type(row[value]) is int and abs(row[value])<=2**53-1)
            assert type(row['target']) is bool and row['target']==(row['event'] in selected)
            snapshots[row['event']]=row
    assert footer and footer['rows']==len(snapshots) and footer['stats']==receipt['audit_only']
    assert set(snapshots)=={r['event'] for t in query_turns for r in t['roots']}
    # Independent binary-search reconstruction, not PriorityMemory or producer flags.
    event_keys={};priority_rows={};priority_keys={}
    for actor,rows in own.items():
        rows.sort(key=lambda e:cursor(e['root']['event']));event_keys[actor]=[cursor(e['root']['event']) for e in rows]
        priority_rows[actor]=[e for e in rows if e['root']['classification']=='priority']
        priority_keys[actor]=[cursor(e['root']['event']) for e in priority_rows[actor]]
    values=np.zeros((len(targets),7),np.int64);history=np.zeros((len(targets),16,2),np.int64)
    for i,(turn,decision) in enumerate(targets):
        actor=turn['actor'];pre=cursor(decision['pre_cursor']);event=decision['event_cursor'];snap=snapshots[event]
        assert snap['pre']==decision['pre_cursor'] and snap['actor']==actor and snap['round']==turn['round']
        end=bisect_right(event_keys[actor],pre)
        assert own[actor][end]['root']['event']==event and pre<cursor(event)
        for vi,mi,key in [(0,1,'current'),(2,3,'scheduled')]:
            if snap[key] is not None:values[i,vi]=snap[key];values[i,mi]=1
        earlier=bisect_right(priority_keys[actor],pre)
        if earlier:
            previous=priority_rows[actor][earlier-1]
            values[i,4:]=[previous['root']['header']['step']['priority'],1,turn['round']-previous['round']]
        for j,e in enumerate(own[actor][max(0,end-16):end],16-min(16,end)):
            if e['root']['classification']=='priority':history[i,j]=[e['root']['header']['step']['priority'],1]
    reconstructed=dict(values=values,history=history,last_outside_window=(values[:,5]>0)&~history[:,:,1].any(-1))
    local=load_arrays(directory/'inputs.npz');validate_arrays(local,len(targets));validate_slice(reconstructed,local,0,len(targets))
    for field,total in [('current_available',values[:,1].sum()),('scheduled_available',values[:,3].sum()),
                        ('last_available',values[:,5].sum()),('last_outside_window',reconstructed['last_outside_window'].sum())]:
        assert receipt[field]==int(total),'Receipt support total mismatch'
    return local,sha(directory/'receipt.json')

def verify(probes=False):
    plan=read(REPORTS/'priority-extraction-plan.json');jobs_path=ROOT/'.cambc/action-predictor/v7/jobs.json'
    assert sha(jobs_path)==plan['jobs_sha256'];jobs=read(jobs_path)
    validate_layout(jobs,dict(train=433071,validation=14439))
    assert len(jobs)==495 and sum(j['split']=='train' for j in jobs)==470
    for path,digest in plan['sources'].items():assert sha(path)==digest
    selected=jobs
    if probes:
        audited=read(REPORTS/'priority-two-engine-audit.json')['games']
        selected=[j for j in jobs if j['record']['raw_sha256'] in audited];assert len(selected)==2
    merged={};ready=None
    if not probes:
        ready=read(REPORTS/'priority-data-ready.json')
        for split,n in [('train',433071),('validation',14439)]:
            path=WORK/('priority-'+split+'.npz');assert sha(path)==ready['files'][split]
            merged[split]=load_arrays(path);validate_arrays(merged[split],n)
        assert set(ready['receipts'])=={j['record']['raw_sha256'] for j in jobs}
    hashes={};totals={s:dict.fromkeys(('rows','current_available','scheduled_available','last_available','last_outside_window'),0) for s in ('train','validation')}
    for i,job in enumerate(selected,1):
        local,digest=validate_game(job,job,plan);raw=job['record']['raw_sha256'];hashes[raw]=digest
        if not probes:
            assert digest==ready['receipts'][raw]
            validate_slice(merged[job['split']],local,job['offset'],job['rows'])
        r=read(WORK/'priority'/raw/'receipt.json')
        for field in totals[job['split']]:totals[job['split']][field]+=r[field]
        if i%25==0 or i==len(selected):print('Verified priority evidence/alignment',i,'/',len(selected),flush=True)
    if not probes:assert totals==ready['observed_support']
    result=dict(passed=True,scope='two-engine completed probes' if probes else 'complete495games',
        games=len(selected),jobs_sha256=sha(jobs_path),plan_sha256=sha(REPORTS/'priority-extraction-plan.json'),
        per_game_receipts=hashes,exact_merged_slices_verified=not probes,exact_offset_coverage=True,
        full_upstream_chain_verified=True,independent_index_feature_reconstruction=True,support_totals=totals,
        validator_source_sha256=sha(__file__),original_extraction_sources_unchanged=True,new_fits=0)
    frozen(REPORTS/('priority-probe-chain-verification.json' if probes else 'priority-chain-verification.json'),result)
    return result

if __name__=='__main__':
    with (WORK/'commands.jsonl').open('a') as stream:stream.write(json.dumps(dict(argv=[sys.executable,'-m','tools.action_predictor.priority_verify',*sys.argv[1:]],code_sha256=sha(__file__)))+'\n')
    verify('--probes' in sys.argv)
