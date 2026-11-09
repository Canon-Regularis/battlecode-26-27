"""Add bounded rare-action TRAIN turns from the existing frozen replay indexes."""
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
from pathlib import Path
import subprocess

from .audit import immutable_json
from .benchmark import WORK, REPORTS
from .data import digest
from .rich_data import read_turns, load_manifest, build


def one(record,m):
    root=WORK/'augmentation'/record['raw_sha256'];root.mkdir(parents=True,exist_ok=True)
    result_path=root/'turns.jsonl'
    if (root/'receipt.json').exists():
        receipt=json.loads((root/'receipt.json').read_text())
        if digest(result_path)!=receipt['augmented_sha256']:
            raise ValueError('Augmented turns changed')
        return record['raw_sha256'],receipt
    original=read_turns(m,record);used={t['id'] for t in original};view=original[0]['view']
    source=Path(m['source'])/'extracted'/record['raw_sha256']
    index=[json.loads(line) for line in (source/'index.jsonl').open()]
    actors={e['entity']['index'] for e in index[-1]['roster'] if e['team']==view['team']}
    eligible=[t for t in index[:-1] if t['actor'] in actors and t['complete'] and t['id'] not in used and
              not any(r['classification'] in ('unknown','unknown_root','error','rollover','resign') for r in t['roots'])]
    rare=['teleport','altar','submit','shop','ward','blocked'];selected={}
    buckets={kind:sorted([t for t in eligible if any(r['classification']==kind for r in t['roots'])],
                         key=lambda t:hashlib.sha256((record['raw_sha256']+'|'+t['id']).encode()).hexdigest()) for kind in rare}
    # Bounded round robin, starting with the rarest classes; targets are training labels only.
    while len(selected)<64 and any(buckets.values()):
        for kind in rare:
            while buckets[kind] and buckets[kind][0]['id'] in selected:
                buckets[kind].pop(0)
            if buckets[kind] and len(selected)<64:
                t=buckets[kind].pop(0);selected[t['id']]=t
    turns=list(selected.values())
    query=json.loads((WORK/'supplement'/record['raw_sha256']/'query.json').read_text())
    output=root/'pre.jsonl'
    query.update(output=str(output.resolve()),includeObservation=True,
                 turns=[dict(entry=t['entry'],actor=t['actor'],team=view['team'],roots=t['roots']) for t in turns])
    (root/'query.json').write_text(json.dumps(query))
    if output.exists():output.unlink()
    if turns:
        p=subprocess.run(['node',str(Path(__file__).with_name('supplement.cjs')),str(root/'query.json')],capture_output=True,text=True,timeout=300)
        if p.returncode:raise ValueError(p.stderr[-3000:])
        rows=[json.loads(l) for l in output.open()]
        if rows[-1]!={'record':'complete','decisions':sum(len(t['roots']) for t in turns)}:
            raise ValueError('Incomplete augmentation')
        evidence={r['id']:r for r in rows if r['record']=='pre'}
        for t in turns:
            t['view']=view;t['decisions']=[];t['diagnostic_only']=False
            for r in t['roots']:
                s=r['header']['step'];row=evidence[record['raw_sha256']+'/main/'+r['event']]
                t['decisions'].append(dict(id=row['id'],pre_cursor=r['pre'],event_cursor=r['event'],observation=row['observation'],
                    label={'kind':s['kind'],'root_class':r['classification'],'slot':s.get('abilitySlot'),'from':s['from'],'to':s['to']},
                    audit=dict(pre_header=row['pre_header'],header=r['header'],post_move_matches=row.get('post_move_matches'))))
    # Original sampled turns and new turns remain distinct, each with PRE evidence.
    combined=sorted(original+turns,key=lambda t:t['occurrence'])
    ids=[d['id'] for t in combined for d in t['decisions']]
    if len(set(ids))!=len(ids):raise ValueError('Duplicated augmentation decisions')
    with result_path.open('w') as f:
        for t in combined:f.write(json.dumps(t)+'\n')
    receipt=dict(augmented_path=str(result_path.resolve()),augmented_sha256=digest(result_path),
                 extra_turns=len(turns),extra_actions=sum(len(t['decisions']) for t in turns),
                 supplement_code=digest(Path(__file__).with_name('supplement.cjs')))
    immutable_json(root/'receipt.json',receipt)
    return record['raw_sha256'],receipt


def run():
    m=load_manifest();records=[r for r in m['recordings'] if r['split']=='train'];results={}
    with ThreadPoolExecutor(max_workers=2) as pool:
        jobs=[pool.submit(one,r,m) for r in records]
        for i,f in enumerate(as_completed(jobs),1):
            key,value=f.result();results[key]=value
            if i%10==0 or i==len(jobs):print(f'Rare training extraction {i}/{len(jobs)}',flush=True)
    immutable_json(WORK/'augmentation.json',dict(sorted(results.items())))
    immutable_json(REPORTS/'augmentation.json',dict(training_only=True,maximum_extra_turns_per_game=64,
        extra_turns=sum(r['extra_turns'] for r in results.values()),extra_actions=sum(r['extra_actions'] for r in results.values()),
        manifest_sha256=digest(WORK/'augmentation.json'),labels_used_for_training_sampling=['teleport','altar','submit','shop','ward','blocked'],
        validation_and_test_unchanged=True))
    build(('train',),augment=True)


if __name__=='__main__':run()
