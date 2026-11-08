"""Freeze bounded historical personal-query checks from existing eligible replays."""
import gzip
import hashlib
import json
import subprocess
from pathlib import Path

import numpy as np

from ..audit import immutable_json,cursor
from ..data import digest
from .trajectory import ROOT,OUT


def run():
    jobs_path=ROOT/'.cambc/action-predictor/v7/jobs.json'
    if digest(jobs_path)!='80c61417faed19ebcb8f8f59db35ba0588d7862ff68dfa3eff58f7de4aab14ba':
        raise RuntimeError('Eligible job table changed')
    prior_path=ROOT/'tools/action_predictor/experiments/v8/priority-two-engine-audit.json'
    blob=subprocess.run(['git','show','275b717b01b2f45341de341d65b28cbe248691d1:'+prior_path.relative_to(ROOT).as_posix()],
                        cwd=ROOT,check=True,capture_output=True).stdout
    if prior_path.read_bytes()!=blob:
        raise RuntimeError('Previously committed two-game audit changed')
    prior=json.loads(blob)
    jobs=[j for j in json.loads(jobs_path.read_text()) if j['record']['raw_sha256'] in prior['games']]
    if len(jobs)!=2 or any(j['split']!='train' for j in jobs):
        raise RuntimeError('Only the two original eligible TRAIN audit games are permitted')
    bindings={str(jobs_path):digest(jobs_path),str(prior_path):digest(prior_path),
              str(Path(__file__)):digest(Path(__file__)),
              str(Path(__file__).with_name('order_availability.cjs')):digest(Path(__file__).with_name('order_availability.cjs'))}
    games=[]
    for job in jobs:
        raw=job['record']['raw_sha256']
        directory=ROOT/'.cambc/action-predictor/v8/priority'/raw
        receipt_path=directory/'receipt.json'
        expected=prior['games'][raw]
        receipt=json.loads(receipt_path.read_text())
        # Prior audit embeds this receipt's complete fields; the current bytes are
        # independently constrained by that committed report's file hashes.
        if receipt!=expected:
            raise RuntimeError('Prior per-game receipt changed')
        bindings[str(receipt_path)]=digest(receipt_path)
        for name in ('query.json','pre.jsonl.gz'):
            path=directory/name
            if digest(path)!=receipt['files'][name]:
                raise RuntimeError('Bound prior query/PRE cache changed')
            bindings[str(path)]=digest(path)
        query_path=directory/'query.json'
        query=json.loads(query_path.read_text())
        for name in ('micro_playback.cjs','playback.cjs'):
            path=Path(query['reader'])/'frozen_v1_5'/name
            bindings[str(path)]=digest(path)
        roots={root['event']:dict(actor=turn['actor'],round=turn['round'],pre=root['pre'])
               for turn in query['turns'] for root in turn['roots']}
        pre=[]
        with gzip.open(directory/'pre.jsonl.gz','rt',encoding='utf-8') as stream:
            for line in stream:
                row=json.loads(line)
                if row['record']=='priority_pre':
                    if row['event'] not in roots or row['pre']!=roots[row['event']]['pre']:
                        raise RuntimeError('Prior query/PRE alignment mismatch')
                    pre.append(row)
        pre.sort(key=lambda r:cursor(r['pre']))
        selected=set(np.linspace(0,len(pre)-1,16,dtype=int).tolist())
        for predicate in (lambda r:r['current']!=r['scheduled'],lambda r:r['current'] is not None and r['current']<0):
            found=next((i for i,r in enumerate(pre) if predicate(r)),None)
            if found is None:
                raise RuntimeError('Required signed/current-next availability fixture missing')
            selected.add(found)
        cases=[roots[pre[i]['event']] for i in sorted(selected)]
        games.append(dict(query=str(query_path),query_sha256=digest(query_path),
            expected_engine='v'+job['record']['engine_version'].replace('.','_'),cases=cases))
    local=ROOT/'.cambc/action-predictor/v23'
    local.mkdir(parents=True,exist_ok=True)
    immutable_json(OUT/'PD03-api-plan.json',dict(games=games,bindings=bindings,
        output=str(local/'order-availability.json'),raw_output=str(local/'order-availability-events.jsonl'),
        selection='16evenly-spaced existing own PRE rows per game plus first differing-current/next '
                  'and first negative-current PRE. Selection uses PRE only, no recorded target/outcome.',
        purpose='Validate actual scoped Game_API_Champion_GetPriority on engines2/3 before using '
                'other-champion fields. Check own signed/current-next values against personal '
                'snapshot as positive controls; record API availability/errors and unchanged state.',
        constraints='Restore recorded eligible TRAIN events only. No actions, branches, matches, '
                    'bot loading/modification, downloads, DEV/reserved payloads or model fits. '
                    'Unknown-unit values never retained. Raw query audit precedes validation.',
        new_fits=0,reserved_opened=0))
    print('Frozen personal getter availability check',len(cases),'cases in final game;',len(games),'games')


if __name__=='__main__':
    run()
