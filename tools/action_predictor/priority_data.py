"""Recover personal PRE priorities for unchanged eligible target rows only."""
from collections import defaultdict,Counter
from concurrent.futures import ProcessPoolExecutor,as_completed
import gzip
import json
from pathlib import Path
import subprocess
import sys
import numpy as np

from .category_study import WORK,REPORTS,ROOT
from .more_replays import frozen,sha
from .rich_data import read_turns
from .audit import cursor
from .priority_inputs import PriorityMemory,FIELDS

def read(path):return json.loads(Path(path).read_text(encoding='utf-8'))
def log(command,**extra):
    with (WORK/'commands.jsonl').open('a',encoding='utf-8') as stream:
        stream.write(json.dumps(dict(argv=list(map(str,command)),**extra))+'\n')

def sources():
    return {str(Path(__file__).with_name(name)):sha(Path(__file__).with_name(name)) for name in
            ('priority_data.py','priority_inputs.py','priority_context.cjs')}

def get_jobs():
    path=ROOT/'.cambc/action-predictor/v7/jobs.json';jobs=read(path)
    member=read(ROOT/'tools/action_predictor/experiments/v5/membership.json')
    reserved={r['raw_sha256'] for r in member['records'] if r['split']!='train'}
    assert len(jobs)==495 and len({j['record']['raw_sha256'] for j in jobs})==495
    assert not reserved&{j['record']['raw_sha256'] for j in jobs}
    assert sum(j['split']=='train' for j in jobs)==470 and sum(j['rows'] for j in jobs if j['split']=='train')==433071
    assert sum(j['rows'] for j in jobs if j['split']=='validation')==14439
    frozen(REPORTS/'priority-extraction-plan.json',dict(jobs_sha256=sha(path),sources=sources(),
        eligible_games=495,train_games=470,validation_games=25,train_rows=433071,validation_rows=14439,
        feature_fields=list(FIELDS),history_shape=[16,2],integer_storage='int64; unscaled, unclipped; availability distinct from zero',
        provenance='Reuse frozen v7 target membership/order and full own-event indexes. Verify raw payload, index and current target shard receipts.',
        chronology='Own observed priority setter event <= target PRE < target event. Include latest setter outside window. Full own action stream, not sampled-turn adjacency.',
        personal='Read own priority and nextPriority from personal PRE snapshot before replayNext. No current target header/POST value in input arrays.',
        post_audits='Read-only recorded POST setter checks and round rollover diagnostics in separate audit footer only, never feature arrays.',
        missing='Preserve all rows with explicit availability masks; unexplained extraction failure stops before fitting.',
        unchanged_setters='Count any recorded setter whose argument equals PRE scheduled value. If none, do not conclude the bot never calls unchanged setters: replay omission remains unresolved without version-specific command-recording semantics.',
        reserved='All75newvalidation+75finaltest unopened; no oldtest; no additional downloads/matches/bot changes/PR in this extraction.',
        fits_started=0))
    return jobs

def game_job(job):
    raw=job['record']['raw_sha256'];directory=WORK/'priority'/raw;directory.mkdir(parents=True,exist_ok=True)
    receipt=directory/'receipt.json';code=sources()
    if receipt.exists():
        result=read(receipt);assert result['code_hashes']==code
        for name,digest in result['files'].items():assert sha(directory/name)==digest
        return result
    shard=Path(job['shard']);assert sha(shard)==job['shard_sha256']
    source=Path(job['manifest']['source'])/'extracted'/raw
    index=source/'index.jsonl';assert sha(index)==read(source/'receipt.json')['files']['index.jsonl']
    turns=[json.loads(line) for line in index.open(encoding='utf-8')]
    assert turns[-1]['status']=='complete'
    originals=read_turns(job['manifest'],job['record'])
    targets=[(turn,decision) for turn in originals for decision in turn['decisions']]
    assert len(targets)==job['rows'];actors={t['actor'] for t,d in targets};team=originals[0]['view']['team']
    selected={d['event_cursor'] for t,d in targets};assert len(selected)==len(targets)
    own=defaultdict(list);by_event={};query_turns=[]
    for turn in turns:
        if turn.get('record')!='turn' or turn['actor'] not in actors:continue
        roots=[]
        for root in turn['roots']:
            event=dict(root=root,round=turn['round'],turn=turn['id'],actor=turn['actor'])
            assert root['event'] not in by_event;by_event[root['event']]=event;own[turn['actor']].append(event)
            if root['event'] in selected or root['classification']=='priority':roots.append(root|dict(target=root['event'] in selected))
        if roots:query_turns.append(dict(id=turn['id'],actor=turn['actor'],round=turn['round'],entry=turn['entry'],roots=roots))
    for rows in own.values():rows.sort(key=lambda row:cursor(row['root']['event']))
    old_source=Path(read(ROOT/'.cambc/action-predictor/data/dataset.json')['source'])
    reader=old_source.parents[2]/'tools/replay_eval';assets=next(old_source.parents[1].glob('asset-cache-5/*/visualiser/assets'))
    raw_path=Path(job['work'])/'supplement'/raw/'raw.bin';assert sha(raw_path)==raw
    query=dict(raw=str(raw_path),raw_sha256=raw,team=team,reader=str(reader),assets=str(assets),
        output=str(directory/'pre.jsonl.gz'),turns=query_turns)
    query_path=directory/'query.json';frozen(query_path,query)
    node_receipt=directory/'node-receipt.json';output=directory/'pre.jsonl.gz'
    if node_receipt.exists():assert sha(output)==read(node_receipt)['sha256']
    else:
        assert not output.exists(),'Partial extraction preserved; inspect before retry'
        command=['node',str(Path(__file__).with_name('priority_context.cjs')),str(query_path)]
        log(command,query_sha256=sha(query_path))
        proc=subprocess.run(command,capture_output=True,text=True,encoding='utf-8',timeout=600)
        assert proc.returncode==0,proc.stderr[-3000:]
        frozen(node_receipt,dict(sha256=sha(output),query_sha256=sha(query_path),code_hashes=code))
    snapshots={};footer=None
    with gzip.open(output,'rt',encoding='utf-8') as stream:
        for line in stream:
            row=json.loads(line)
            if row['record']=='audit_complete':footer=row;continue
            assert row['record']=='priority_pre' and row['event'] not in snapshots
            e=by_event[row['event']]
            assert row['actor']==e['actor'] and row['team']==team and row['round']==e['round']
            assert row['pre']==e['root']['pre'] and cursor(row['pre'])<cursor(row['event'])
            assert row['current_available']==(row['current'] is not None) and row['scheduled_available']==(row['scheduled'] is not None)
            snapshots[row['event']]=row
    assert footer and footer['rows']==len(snapshots) and selected=={k for k,v in snapshots.items() if v['target']}
    n=len(targets);values=np.zeros((n,len(FIELDS)),np.int64);history=np.zeros((n,16,2),np.int64)
    memories={actor:PriorityMemory(actor) for actor in actors};positions=dict.fromkeys(actors,0);outside=np.zeros(n,bool)
    for i in sorted(range(n),key=lambda i:cursor(targets[i][1]['event_cursor'])):
        turn,decision=targets[i];actor=turn['actor'];pre=cursor(decision['pre_cursor']);event=by_event[decision['event_cursor']]
        assert event['round']==turn['round'] and event['root']['pre']==decision['pre_cursor']
        rows=own[actor];offset=positions[actor];memory=memories[actor]
        while offset<len(rows) and cursor(rows[offset]['root']['event'])<=pre:
            prior=rows[offset];memory.observe(prior['root']['header']['step'],prior['root']['event'],prior['round']);offset+=1
        positions[actor]=offset;assert rows[offset]['root']['event']==decision['event_cursor']
        snapshot=snapshots[decision['event_cursor']]
        values[i],history[i]=memory.inputs(snapshot,decision['pre_cursor'],turn['round'])
        outside[i]=bool(values[i,5] and not history[i,:,1].any())
        # Independent index calculation checks streaming inference parity.
        earlier=[e for e in rows[:offset] if e['root']['classification']=='priority']
        if earlier:assert values[i,4]==earlier[-1]['root']['header']['step']['priority'] and values[i,5]==1
        else:assert values[i,5]==0
        expected=np.zeros((16,2),np.int64)
        for j,e in enumerate(rows[max(0,offset-16):offset],16-min(16,offset)):
            if e['root']['classification']=='priority':expected[j]=[e['root']['header']['step']['priority'],1]
        assert np.array_equal(history[i],expected)
    np.savez_compressed(directory/'inputs.npz',values=values,history=history,last_outside_window=outside)
    result=dict(raw_sha256=raw,split=job['split'],rows=n,engine=job['record']['engine_version'],code_hashes=code,
        index_sha256=sha(index),target_shard_sha256=sha(shard),streaming_index_parity=True,
        current_available=int(values[:,1].sum()),scheduled_available=int(values[:,3].sum()),
        last_available=int(values[:,5].sum()),last_outside_window=int(outside.sum()),
        audit_only=footer['stats'],files={name:sha(directory/name) for name in ('pre.jsonl.gz','query.json','inputs.npz','node-receipt.json')})
    frozen(receipt,result);return result

def prepare(audit=False):
    jobs=get_jobs()
    if audit:jobs=[next(j for j in jobs if j['split']=='train' and j['record']['engine_version']==version) for version in ('2.0.0','3.0.0')]
    receipts={}
    with ProcessPoolExecutor(max_workers=4) as pool:
        futures={pool.submit(game_job,j):j for j in jobs}
        for i,future in enumerate(as_completed(futures),1):
            job=futures[future];receipts[job['record']['raw_sha256']]=future.result()
            if i%10==0 or i==len(jobs):print('Personal PRE priority games',i,'/',len(jobs),flush=True)
    if audit:
        frozen(REPORTS/'priority-two-engine-audit.json',dict(passed=True,games=receipts,new_fits=0));return
    merge(jobs,receipts)

def merge(jobs,receipts):
    for split,n in [('train',433071),('validation',14439)]:
        values=np.zeros((n,len(FIELDS)),np.int64);history=np.zeros((n,16,2),np.int64);outside=np.zeros(n,bool)
        for job in jobs:
            if job['split']!=split:continue
            with np.load(WORK/'priority'/job['record']['raw_sha256']/'inputs.npz') as z:
                start=job['offset'];end=start+job['rows'];values[start:end]=z['values'];history[start:end]=z['history'];outside[start:end]=z['last_outside_window']
        np.savez_compressed(WORK/('priority-'+split+'.npz'),values=values,history=history,last_outside_window=outside)
    frozen(REPORTS/'priority-data-ready.json',dict(games=495,train_rows=433071,validation_rows=14439,features=list(FIELDS),
        files={split:sha(WORK/('priority-'+split+'.npz')) for split in ('train','validation')},
        receipts={raw:sha(WORK/'priority'/raw/'receipt.json') for raw in receipts},
        observed_support={split:{field:sum(r[field] for r in receipts.values() if r['split']==split) for field in
            ('rows','current_available','scheduled_available','last_available','last_outside_window')} for split in ('train','validation')},
        new_fits=0,all_rows_retained=True,reserved_games_opened=0))
    print('Causal priority input recovery complete; fits:0',flush=True)

if __name__=='__main__':
    log([sys.executable,'-m','tools.action_predictor.priority_data',*sys.argv[1:]])
    prepare('--audit' in sys.argv)
