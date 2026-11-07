"""Focused TRAIN C01/C02 history/candidate parity against earlier own roots."""
from collections import defaultdict
import json
from pathlib import Path
import numpy as np
from .algorithmic_c01 import ROOT,WORK,REPORT,JOBS,candidates,encode
from .algorithmic_c02 import proposals,SLOTS
from .rich_data import read_turns,history_vector
from .observation_data import compact_supplement
from .audit import cursor,immutable_json
from .data import digest
from . import reliable_train as rt

def run():
    jobs=json.loads(JOBS.read_text());selected=[]
    for version in ('2.0.0','3.0.0'):selected.extend([j for j in jobs if j['split']=='train' and j['record']['engine_version']==version][:2])
    c1=np.load(WORK/'C01-train-candidates.npy',mmap_mode='r');c2=np.load(WORK/'C02-train-candidates.npy',mmap_mode='r')
    with np.load(WORK.parent/'v8/priority-train.npz') as z:values=z['values']
    rows=0;cases=[]
    for job in selected:
        raw=job['record']['raw_sha256'];path=Path(job['manifest']['source'])/'extracted'/raw/'index.jsonl';events=defaultdict(list)
        indexreceipt=json.loads((path.parent/'receipt.json').read_text());assert digest(path)==indexreceipt['files']['index.jsonl']
        for line in path.open():
            turn=json.loads(line)
            if turn.get('record')=='turn':
                for root in turn['roots']:
                    s=root['header']['step'];name=root['classification'];name=f"cast_{s.get('abilitySlot')}" if name=='cast' else name
                    events[turn['actor']].append((cursor(root['event']),rt.LABELS.index(name) if name in rt.LABELS else 0,s,turn['round']))
        for stream in events.values():stream.sort(key=lambda e:e[0])
        supplements={}
        for suffix in ('supplement','augmentation'):
            p=Path(job['work'])/suffix/raw/'pre.jsonl'
            if not p.exists():continue
            for line in p.open():
                r=json.loads(line)
                if r['record']=='map':route=r['route']
                elif r['record']=='pre':supplements[r['id']]=compact_supplement(r)
        with np.load(job['shard']) as z:cached_history=z['history']
        targets=[(t,d) for t in read_turns(job['manifest'],job['record']) for d in t['decisions']]
        selection=set(range(0,len(targets),max(1,len(targets)//25)))|{len(targets)-1}
        for local in sorted(selection):
            t,d=targets[local];i=job['offset']+local;earlier=[e for e in events[t['actor']] if e[0]<=cursor(d['pre_cursor'])];h=np.zeros((32,24),np.float32)
            for k,e in enumerate(earlier[-32:],32-min(32,len(earlier))):h[k]=history_vector(e,t['round'],d['observation']['own'].get('position'),rt.LABELS)
            np.testing.assert_array_equal(h,cached_history[local]);setters=[e for e in earlier if e[2]['kind']==9]
            if setters:
                e=setters[-1];assert values[i,5]==1 and values[i,4]==e[2]['priority'] and values[i,6]==t['round']-e[3]
            else:assert values[i,5]==0
            args=(d['observation'],supplements[d['id']],route);pair=candidates(*args,values[i],h);actual=np.array([[encode(command,d['observation']) for command in library] for library in pair]);np.testing.assert_array_equal(actual,c1[i]);actual2=actual[0].copy();actual2[SLOTS]=[encode(command,d['observation']) for command in proposals(*args,h)];np.testing.assert_array_equal(actual2,c2[i]);rows+=1
        cases.append(dict(raw=raw,engine=job['record']['engine_version'],index_sha256=digest(path),cases=len(selection)))
    immutable_json(REPORT/'C01-C02-TRAIN-roundtrip.json',dict(source_sha256=digest(__file__),rows=rows,games=len(selected),cases=cases,history_and_latest_priority_rebuilt_exact=True,both_libraries_equal=True,scope='TRAINonly;everyearlierownrootthroughPREfromhashvalidfullindex,not sampledrowadjacency. Selectedindicesandallavailablehistorymasksretained. Earlierownpriorityargumentusedonlyafteritsrecordedevent. Currentanswer/futureexcluded. Noarchiveopening/simulation.',candidate_bindings={n:digest(WORK/f'{n}-train-candidates.npy') for n in ('C01','C02')},reserved_opened=0,new_fits=0,DEV_rows_evaluated=0))
    print('Supportrawhistoryroundtrip',rows,'cases',flush=True)

if __name__=='__main__':run()
