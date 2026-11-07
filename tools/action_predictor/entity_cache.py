"""One-pass causal encoding over existing eligible TRAIN/development snapshots."""
from pathlib import Path
import json,sys
import numpy as np
from .fundamental_audit import WORK,REPORTS,dependencies,log
from .priority_fit_v3 import BASE,VAL,read
from .more_replays import frozen,sha
from .rich_data import read_turns
from .audit import validate_decision
from .data import action_name
from .entity_set import encode_entities
from . import reliable_train as rt

DIRECTORY=WORK/'entities'

def build():
    binding=dependencies();jobs_path=BASE.parent/'v7/jobs.json';jobs=read(jobs_path)
    assert sha(jobs_path)==read(ROOT_REPORTS/'priority-extraction-plan.json')['jobs_sha256']
    DIRECTORY.mkdir(exist_ok=True);plan=dict(source_hashes={str(Path(__file__)):sha(__file__),str(Path(__file__).with_name('entity_set.py')):sha(Path(__file__).with_name('entity_set.py'))},jobs_sha256=sha(jobs_path),dependencies=binding,
        inputs='Own token and EVERY known-bit1 personally visible champion/camp; no IDs; no nearest-k cap; no target label or POST fields. Buffs aggregated by observable type/timer/magnitude; ability identity/props/cooldowns retained. Float16 cached inputs, float32 model inputs; same inference quantization.',
        membership='433071TRAIN and14439originaldevelopment rows in frozen job order, no new games or reserved contents',missing='Unknown fields have explicit presence bits; own token always retained; dead entities included when personally known. No unavailable-history or unsupported-label rows dropped.')
    frozen(REPORTS/'entity-cache-plan.json',plan)
    target=REPORTS/'entity-cache-ready.json'
    if target.exists():
        ready=read(target);assert ready['plan_sha256']==sha(REPORTS/'entity-cache-plan.json')
        for name,digest in ready['files'].items():assert sha(DIRECTORY/name)==digest
        return ready
    results={};bindings=[];dimension=None
    for split,source in [('train',BASE/'combined-train.npz'),('validation',VAL)]:
        with np.load(source) as z:y=z['y']
        path=DIRECTORY/(split+'-entities.f16');assert not path.exists(),'Partial encoding preserved; use a new revision after investigating'
        offsets=[0];position=0;max_entities=0
        with path.open('xb') as stream:
            selected=[j for j in jobs if j['split']==split]
            for number,job in enumerate(selected,1):
                assert job['offset']==position
                turns=read_turns(job['manifest'],job['record']);count=0
                for turn in turns:
                    for decision in turn['decisions']:
                        validate_decision(decision,turn)
                        label=action_name(decision['label']);assert rt.LABELS[int(y[position])]==label
                        encoded=encode_entities(decision['observation'])
                        if dimension is None:dimension=encoded.shape[1]
                        assert encoded.shape[1]==dimension
                        stream.write(encoded.tobytes());offsets.append(offsets[-1]+len(encoded));max_entities=max(max_entities,len(encoded));position+=1;count+=1
                assert count==job['rows'];bindings.append(dict(split=split,raw=job['record']['raw_sha256'],offset=job['offset'],rows=count,source_sha256=job['record'].get('augmented_sha256',job['record']['turns_sha256'])))
                if number%25==0 or number==len(selected):print('Entity PRE encoding',split,number,'/',len(selected),flush=True)
        assert position==len(y);np.save(DIRECTORY/(split+'-offsets.npy'),np.asarray(offsets,np.int64))
        results[split]=dict(rows=position,tokens=offsets[-1],maximum_tokens_per_row=max_entities)
    ready=dict(plan_sha256=sha(REPORTS/'entity-cache-plan.json'),dimension=dimension,splits=results,bindings=bindings,files={p.name:sha(p) for p in DIRECTORY.iterdir() if p.is_file()},reserved_opened=0,all_rows_retained=True)
    frozen(target,ready);return ready

ROOT_REPORTS=REPORTS.parent/'v8'
if __name__=='__main__':log([sys.executable,'-m','tools.action_predictor.entity_cache']);print(build()['splits'])
