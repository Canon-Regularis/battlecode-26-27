"""Decode only frozen V5 TRAIN games using unchanged V4 sampling and encoding."""
from concurrent.futures import ThreadPoolExecutor,as_completed
import hashlib
import json
from pathlib import Path
import subprocess
import zipfile

from .more_replays import ROOT,WORK,REPORTS,frozen,sha,log_command,FISH
from . import rich_data,augment
from .audit import validate_decision
from .parallel_data import build as parallel_build


def context():
    membership=json.loads((REPORTS/'membership.json').read_text())
    assert membership['count']==500 and membership['inspected_behaviour'] is False
    old=json.loads((ROOT/'.cambc/action-predictor/data/dataset.json').read_text())
    reader=Path(old['source']).parents[2]/'tools/replay_eval'
    assets=next(Path(old['source']).parents[1].glob('asset-cache-5/*/visualiser/assets'))
    return membership,reader,assets


def execute_node(script,query,path):
    frozen(path,query)
    command=['node',str(script),str(path)]
    log_command(command,purpose='Frozen TRAIN-only recorded replay extraction',query_sha256=sha(path))
    p=subprocess.run(command,capture_output=True,text=True,encoding='utf-8',timeout=300)
    if p.returncode:raise ValueError(p.stderr[-4000:])


def one(record,reader,assets):
    if record['split']!='train':raise ValueError('Sealed/non-training record cannot be decoded')
    raw=record['raw_sha256'];folder=WORK/'source/extracted'/raw;folder.mkdir(parents=True,exist_ok=True)
    receipt_path=folder/'receipt.json'
    if receipt_path.exists():
        receipt=json.loads(receipt_path.read_text())
        if any(sha(folder/name)!=expected for name,expected in receipt['files'].items()):raise ValueError('Extraction changed')
        return receipt['recording']
    if sha(record['path'])!=record['bundle_sha256']:raise ValueError('Frozen bundle changed')
    with zipfile.ZipFile(record['path']) as z:payload=z.read('replay.repl26a')
    if hashlib.sha256(payload).hexdigest()!=raw:raise ValueError('Frozen payload changed')
    (folder/'raw.bin').write_bytes(payload)
    base=dict(raw=str((folder/'raw.bin').resolve()),raw_sha256=raw,reader=str(reader),assets=str(assets),
              maxTransitions=3000000,maxSeconds=180,maxBytes=128*1024*1024,maxReadTransitions=3000000)
    index=folder/'index.jsonl';effects=folder/'effects.jsonl'
    if not (folder/'index-complete.json').exists():
        q=base|dict(mode='index',output=str(index.resolve()),effectsOutput=str(effects.resolve()),terminalOutput=str((folder/'terminal.json').resolve()))
        execute_node(Path(__file__).with_name('index_more.cjs'),q,folder/'index-query.json')
        footer=json.loads(index.read_text().splitlines()[-1])
        if footer.get('status')!='complete':raise ValueError('Incomplete index')
        frozen(folder/'index-complete.json',dict(sha256=sha(index),effects_sha256=sha(effects)))
    indexed=[json.loads(line) for line in index.open()];footer=indexed[-1]
    fish=next(t for t in record['metadata']['teams'] if t['teamId']==FISH)
    if fish['side'] not in ('a','b'):raise ValueError('Unknown authoritative Fish side')
    team=0 if fish['side']=='a' else 1
    view=dict(cohort='expert',team_id=FISH,team=team,side=('teamA','teamB')[team],
              opponent=next(t['teamId'] for t in record['metadata']['teams'] if t['teamId']!=FISH))
    chosen=[]
    for who in footer['roster']:
        if who['team']!=team:continue
        population=[t for t in indexed[:-1] if t['actor']==who['entity']['index'] and t['complete']]
        def rank(turn):return hashlib.sha256('|'.join(['lowest-sha256-turn-v1','micro-v1-fixed',raw,turn['id']]).encode()).hexdigest()
        for t in sorted(population,key=lambda t:(rank(t),t['id']))[:32]:
            chosen.append(t|dict(view=view,diagnostic_only=False,sampling=dict(N=len(population),K=min(32,len(population)),
                       probability=f'{min(32,len(population))}/{len(population)}',population='complete',rank=rank(t),
                       version='lowest-sha256-turn-v1',seed='micro-v1-fixed')))
    chosen.sort(key=lambda t:t['occurrence'])
    turns=folder/'turns.jsonl'
    q=base|dict(mode='read',output=str(turns.resolve()),turns=chosen,roster=footer['roster'],
                provenance=dict(membership_sha256=sha(REPORTS/'membership.json'),raw_sha256=raw,engine_version=record['engine_version']))
    execute_node(reader/'frozen_v1_5/micro_playback.cjs',q,folder/'read-query.json')
    count=0
    for line in turns.open():
        t=json.loads(line)
        if t.get('record')=='turn':
            for d in t['decisions']:validate_decision(d,t);count+=1
    if json.loads(turns.read_text().splitlines()[-1]).get('status')!='complete':raise ValueError('Incomplete PRE read')
    derived=dict(match=record['metadata']['matchId'],group=record['group'],raw_sha256=raw,split='train',
                  engine_version=record['engine_version'],map_id=record['metadata']['mapId'],turns_sha256=sha(turns),
                  aliases=[dict(path=record['path'],bundle_sha256=record['bundle_sha256'])],views=[view])
    frozen(receipt_path,dict(status='complete',recording=derived,decisions=count,
                            files={n:sha(folder/n) for n in ['index.jsonl','effects.jsonl','turns.jsonl']}))
    return derived


def run():
    membership,reader,assets=context();records=[r for r in membership['records'] if r['split']=='train']
    if len(records)!=350:raise ValueError('Unexpected frozen training count')
    freeze=dict(membership_sha256=sha(REPORTS/'membership.json'),architecture='Unchanged V4 E06',seed=26,
        primary_validation='Exact original V4 validation arrays, unchanged metrics, reference models and checkpoint selection rule.',
        original_validation_sha256=sha(ROOT/'.cambc/action-predictor/v4/validation.npz'),
        new_validation_policy='Membership frozen, not needed for this initial controlled retrain; no extraction.',
        final_test_policy='75 new test games in 15 groups stay sealed; no extraction/scoring.',
        sampling='Same lowest-sha256-turn-v1 / micro-v1-fixed, 32 complete turns per actor; same bounded rare augmentation.',
        scope='Only more training replays change; observational cohort/time/engine composition may also change and must be reported.')
    frozen(REPORTS/'retrain-plan.json',freeze)
    derived=[]
    with ThreadPoolExecutor(max_workers=4) as pool:
        jobs=[pool.submit(one,r,reader,assets) for r in records]
        for i,job in enumerate(as_completed(jobs),1):
            try:
                derived.append(job.result())
            except Exception as error:
                print('TRAIN extraction failed:',repr(error),flush=True)
                for pending in jobs:pending.cancel()
                raise
            if i%10==0 or i==len(jobs):print('TRAIN recorded indexes/PRE',i,'/',len(jobs),flush=True)
    derived.sort(key=lambda r:r['match'])
    frozen(WORK/'source/frozen.json',dict(recordings=derived,membership_sha256=sha(REPORTS/'membership.json')))
    old=json.loads((ROOT/'.cambc/action-predictor/data/dataset.json').read_text())
    manifest=dict(source=str((WORK/'source').resolve()),reader_root=str(reader),assets_root=str(assets),
                  fish_team_id=FISH,labels=old['labels'],recordings=derived)
    frozen(WORK/'training-source.json',manifest)
    # These module globals are scoped to this standalone process; V4 artifacts remain untouched.
    rich_data.WORK=WORK;rich_data.REPORTS=REPORTS;rich_data.load_manifest=lambda:manifest
    original={r['raw_sha256']:r for r in derived}
    with ThreadPoolExecutor(max_workers=4) as pool:
        jobs=[pool.submit(rich_data.supplement_one,manifest,r,original) for r in derived]
        for i,job in enumerate(as_completed(jobs),1):
            job.result()
            if i%10==0 or i==len(jobs):print('TRAIN personal queries',i,'/',len(jobs),flush=True)
    parallel_build(manifest,WORK,REPORTS,('train',))
    augment.WORK=WORK;augment.REPORTS=REPORTS;augment.load_manifest=lambda:manifest
    augment.build=lambda splits,augment=False:parallel_build(manifest,WORK,REPORTS,splits,augment=augment)
    augment.run()
    frozen(REPORTS/'training-data-ready.json',dict(base=sha(WORK/'train.npz'),augmented=sha(WORK/'train-aug.npz'),
          source_manifest_sha256=sha(WORK/'training-source.json'),membership_sha256=sha(REPORTS/'membership.json'),
          train_games=350,new_validation_games_opened=0,new_test_games_opened=0))


if __name__=='__main__':run()
