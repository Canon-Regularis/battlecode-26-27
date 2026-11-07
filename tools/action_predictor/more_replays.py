"""Metadata/payload-only collection of 500 new Fish games. No behaviour decoding."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import zipfile

from tools import download_replays as downloader

ROOT=Path(__file__).resolve().parents[2]
WORK=ROOT/'.cambc/action-predictor/v5'
REPORTS=ROOT/'tools/action_predictor/experiments/v5'
FISH='1890540d-1ffc-4847-adbf-d0d08772f268'
UUID_PATTERN=re.compile(r'[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}')


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def frozen(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    text=json.dumps(value,indent=2,ensure_ascii=False)+'\n'
    if path.exists() and path.read_text(encoding='utf-8')!=text:raise ValueError(f'Frozen artifact differs: {path}')
    path.write_text(text,encoding='utf-8')


def log_command(argv,**extra):
    WORK.mkdir(parents=True,exist_ok=True)
    with (WORK/'commands.jsonl').open('a',encoding='utf-8') as f:
        f.write(json.dumps(dict(at=datetime.now(timezone.utc).isoformat(),cwd=str(ROOT),argv=list(map(str,argv)),**extra))+'\n')


def payloads(path):
    result=[];errors=[]
    def inspect(data,label,depth=0):
        if data[:8]==b'a62per\0\0':
            result.append(dict(path=label,sha256=hashlib.sha256(data).hexdigest(),bytes=len(data),
                               match_ids=UUID_PATTERN.findall(label),engine_version='.'.join(map(str,data[8:11]))))
        elif data[:2]==b'PK' and depth<3:
            try:
                with zipfile.ZipFile(io.BytesIO(data)) as archive:
                    for entry in archive.infolist():
                        if entry.filename.endswith(('.repl26a','.zip')) and not entry.is_dir():
                            inspect(archive.read(entry),label+'#'+entry.filename,depth+1)
            except (OSError,zipfile.BadZipFile,RuntimeError) as e:errors.append(dict(path=label,error=str(e)))
    try:
        with Path(path).open('rb') as stream:prefix=stream.read(8)
        if prefix==b'a62per\0\0':inspect(Path(path).read_bytes(),str(path))
        elif prefix[:2]==b'PK':
            with zipfile.ZipFile(path) as archive:
                for entry in archive.infolist():
                    if entry.filename.endswith(('.repl26a','.zip')) and not entry.is_dir():
                        inspect(archive.read(entry),str(path)+'#'+entry.filename,1)
        elif str(path).endswith('.repl26a'):errors.append(dict(path=str(path),error='Not a replay/ZIP header'))
    except (OSError,zipfile.BadZipFile,RuntimeError) as e:errors.append(dict(path=str(path),error=str(e)))
    return result,errors


def inventory(refresh=False):
    target=WORK/('existing-refresh.json' if refresh else 'existing-inventory.json')
    if target.exists():return json.loads(target.read_text())
    roots=['F:/Code','C:/Users/Subhan']
    command=['rg','--files','--hidden','--no-ignore',*roots,'-g','*.repl26a','-g','*.zip','-g','*.bin',
             '-g','!**/.git/**','-g','!**/node_modules/**','-g','!**/site-packages/**','-g','!**/wasi-sdk-*/**']
    log_command(command,purpose='Existing replay inventory; names/magic, ZIP entries and payload hashes only')
    p=subprocess.run(command,capture_output=True,text=True,encoding='utf-8',errors='replace')
    files=sorted({str(Path(f).resolve()) for f in p.stdout.splitlines() if f.strip()
                  and not Path(f).resolve().is_relative_to(WORK.resolve())})
    entries=[];errors=[]
    with ThreadPoolExecutor(max_workers=4) as pool:
        for i,(rows,bad) in enumerate(pool.map(payloads,files),1):
            entries+=rows;errors+=bad
            if i%1000==0:print('Inventory files',i,'/',len(files),flush=True)
    result=dict(scanned_at=datetime.now(timezone.utc).isoformat(),roots=roots,candidate_files=len(files),
                payload_instances=len(entries),unique_payloads=len({e['sha256'] for e in entries}),entries=entries,
                unreadable_or_invalid=errors,scan_stderr=p.stderr.strip(),
                scope='Local user profile and F:/Code, including other worktrees and nested replay archives. Task collection itself excluded. No behaviour decoded.')
    frozen(target,result)
    print('Inventory:',len(entries),'instances;',result['unique_payloads'],'unique replay payloads',flush=True)
    return result


def api(cli,args,path):
    if path.exists():return json.loads(path.read_text())
    command=[*cli,*args]
    log_command(command,purpose='Metadata listing only')
    response=downloader.invoke(cli,*args,as_json=True)
    frozen(path,response)
    return response


def candidates(existing,cli):
    extended=WORK/'candidate-groups-extended.json'
    if extended.exists():return json.loads(extended.read_text())
    path=WORK/'candidate-groups.json'
    if path.exists():return json.loads(path.read_text())
    known_ids={i.casefold() for e in existing['entries'] for i in e['match_ids']}
    # Known IDs in metadata prevent collecting a partly downloaded existing group.
    groups={};cursor=None;seen=set();start=datetime.now(timezone.utc).isoformat()
    for page in range(200):
        args=['matches','list','--team',FISH,'--kind','ranked','--limit','50','--json']
        if cursor:args+=['--cursor',cursor]
        response=api(cli,args,WORK/'listing'/f'page-{page:03d}.json')
        for match in response['matches']:
            if match.get('kind')!='ranked' or match.get('status')!='finished':continue
            if not any(t['teamId']==FISH for t in match['teams']):raise ValueError('Wrong team in listing')
            groups.setdefault(match['groupId'],{})[match['matchId']]=match
        eligible=[(g,list(ms.values())) for g,ms in groups.items()
                  if len(ms)==5 and {m['position'] for m in ms.values()}==set(range(1,6))
                  and not any(m['matchId'].casefold() in known_ids for m in ms.values())]
        print('Listed page',page+1,'complete new-ID groups',len(eligible),flush=True)
        cursor=response.get('nextCursor')
        if len(eligible)>=125 or not cursor:break
        if cursor in seen:raise ValueError('Repeated listing cursor')
        seen.add(cursor)
    eligible=sorted(eligible,key=lambda g:(max(m['createdAt'] for m in g[1]),g[0]),reverse=True)
    if len(eligible)<100:raise ValueError(f'Only {len(eligible)} complete new-ID groups found')
    result=dict(started_at=start,groups=[dict(group=g,matches=sorted(ms,key=lambda m:m['position'])) for g,ms in eligible],
                ordering='Newest complete metadata groups, no outcome/behaviour-based selection',expected_group_positions=[1,2,3,4,5])
    frozen(path,result)
    return result


def extend_candidates():
    """Continue the same metadata listing when payload dedup needs more groups."""
    existing=inventory();known={i.casefold() for e in existing['entries'] for i in e['match_ids']}
    cli=downloader.find_cli();groups={};cursor=None;eligible=[]
    for page in range(200):
        args=['matches','list','--team',FISH,'--kind','ranked','--limit','50','--json']
        if cursor:args+=['--cursor',cursor]
        response=api(cli,args,WORK/'listing'/f'page-{page:03d}.json')
        for m in response['matches']:
            if m.get('status')=='finished' and m.get('kind')=='ranked' and any(t['teamId']==FISH for t in m['teams']):
                groups.setdefault(m['groupId'],{})[m['matchId']]=m
        eligible=[(g,list(ms.values())) for g,ms in groups.items() if len(ms)==5
                  and {m['position'] for m in ms.values()}==set(range(1,6))
                  and not any(m['matchId'].casefold() in known for m in ms.values())]
        cursor=response.get('nextCursor')
        if page%10==0:print('Extended metadata page',page+1,'candidate groups',len(eligible),flush=True)
        if len(eligible)>=300 or not cursor:break
    original=json.loads((WORK/'candidate-groups.json').read_text())
    eligible.sort(key=lambda g:(max(m['createdAt'] for m in g[1]),g[0]),reverse=True)
    frozen(WORK/'candidate-groups-extended.json',dict(started_at=original['started_at'],
        groups=[dict(group=g,matches=sorted(ms,key=lambda m:m['position'])) for g,ms in eligible],
        ordering=original['ordering'],expected_group_positions=[1,2,3,4,5],
        extends_sha256=sha(WORK/'candidate-groups.json'),reason='Payload duplicates require replacement whole groups; no behaviour-based selection.'))
    print('Extended to',len(eligible),'candidate groups',flush=True)


def collect():
    WORK.mkdir(parents=True,exist_ok=True);REPORTS.mkdir(parents=True,exist_ok=True)
    if (REPORTS/'membership.json').exists():
        print('Membership already frozen; collection not repeated');return
    before=inventory();cli=downloader.find_cli();catalogue=candidates(before,cli)
    old_hashes={e['sha256'] for e in before['entries']};accepted=[];new_hashes=set();rejected=[]
    groups=catalogue['groups'];offset=0;batch=0
    while len(accepted)<100:
        selection=WORK/'collection'/f'selection-{batch:03d}.json'
        if selection.exists():
            previous=json.loads(selection.read_text())['matches']
            group_ids=list(dict.fromkeys(m['groupId'] for m in previous))
            chosen=groups[offset:offset+len(group_ids)]
            if [g['group'] for g in chosen]!=group_ids:raise ValueError('Frozen selection order changed')
        else:
            needed=100-len(accepted);chosen=groups[offset:offset+needed]
        offset+=len(chosen)
        if not chosen:raise ValueError('Not enough distinct complete groups after payload deduplication')
        frozen(selection,dict(matches=[m for g in chosen for m in g['matches']]))
        out=WORK/'collection'/f'batch-{batch:03d}'
        command=['uv','run','--locked','python','tools/download_replays.py','--team',FISH,'--selection',str(selection),
                 '--workers','1','--out',str(out)]
        for attempt in range(3):
            log_command(command,selection_sha256=sha(selection),attempt=attempt+1,purpose='Bulk downloader; no behaviour inspection')
            with (WORK/f'download-{batch:03d}-{attempt}.log').open('w',encoding='utf-8') as output:
                result=subprocess.run(command,cwd=ROOT,stdout=output,stderr=subprocess.STDOUT)
            if result.returncode==0:break
        if result.returncode:raise ValueError(f'Bulk download failed: see {WORK}/download-{batch:03d}-*.log')
        for group in chosen:
            records=[];hashes=[]
            for match in group['matches']:
                file=out/(match['matchId']+'.repl26a')
                rows,bad=payloads(file)
                if bad or len(rows)!=1:raise ValueError('Invalid downloaded replay payload')
                row=rows[0];hashes.append(row['sha256'])
                records.append(dict(metadata=match,path=str(file.resolve()),raw_sha256=row['sha256'],bundle_sha256=sha(file),
                                    engine_version=row['engine_version']))
            reason='existing payload' if old_hashes.intersection(hashes) else 'duplicate new payload' if new_hashes.intersection(hashes) or len(set(hashes))!=5 else None
            if reason:rejected.append(dict(group=group['group'],reason=reason));continue
            accepted.append(dict(group=group['group'],records=records));new_hashes.update(hashes)
        print('Accepted',len(accepted)*5,'new payloads;',len(rejected),'groups rejected',flush=True);batch+=1
    # Recheck other concurrent download work before sealing membership.
    refreshed=inventory(refresh=True);concurrent={e['sha256'] for e in refreshed['entries']}
    if concurrent.intersection(new_hashes):
        raise ValueError('Another local collection now contains selected payloads; preserve downloads and rerun selection after resolving concurrent duplicates')
    ordered=sorted(accepted,key=lambda g:hashlib.sha256(('fish-more-500-v1|'+g['group']).encode()).hexdigest())
    records=[]
    for i,group in enumerate(ordered):
        split='test' if i<15 else 'validation' if i<30 else 'train'
        for record in group['records']:records.append(record|dict(group=group['group'],split=split))
    membership=dict(schema=5,fish_team_id=FISH,fish_name='Intercontinental Fish',created_at=datetime.now(timezone.utc).isoformat(),
        collection_started_at=catalogue['started_at'],count=500,groups=100,
        split_counts={s:dict(games=sum(r['split']==s for r in records),groups=len({r['group'] for r in records if r['split']==s})) for s in ('train','validation','test')},
        split_rule='SHA256(fish-more-500-v1|groupId), first15 groups test, next15 validation, remaining70 training; all five positions retained.',
        records=records,rejected_groups=rejected,existing_inventory_sha256=sha(WORK/'existing-inventory.json'),
        refreshed_inventory_sha256=sha(WORK/'existing-refresh.json'),catalogue_sha256=sha(WORK/'candidate-groups.json'),
        inspected_behaviour=False,final_test_policy='SEALED: hashing/metadata/CRC only; no action extraction, features, labels, summaries or scoring.',
        training_experiment='Unchanged V4 E06 architecture, encoding, sampling/rare augmentation, training settings and original validation benchmark. New validation remains separate. No final test evaluation.',
        unchanged_benchmark_sha256=sha(ROOT/'tools/action_predictor/experiments/v4/benchmark.json'),
        downloader_sha256=sha(ROOT/'tools/download_replays.py'),uv_lock_sha256=sha(ROOT/'uv.lock'))
    frozen(REPORTS/'membership.json',membership)
    frozen(REPORTS/'collection-summary.json',{k:v for k,v in membership.items() if k!='records'})
    print('Frozen 500 additional games:',membership['split_counts'],flush=True)


if __name__=='__main__':
    extend_candidates() if '--extend' in sys.argv else collect()
