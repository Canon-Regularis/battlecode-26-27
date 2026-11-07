"""Bind changed study caches once; reuse immutable checks when stats agree."""
import json
from pathlib import Path
from .consistent_data import ROOT,BASE,WORK,REPORT
from .data import digest
from .audit import immutable_json

def verify():
    target=REPORT/'verified-inputs.json'
    if target.exists():
        value=json.loads(target.read_text())
        for p,r in value['files'].items():
            stat=(ROOT/p).stat()
            assert stat.st_size==r['size'] and stat.st_mtime_ns==r['mtime_ns'],('Immutable input changed; verify hash before reuse',p)
        return digest(target)
    from .priority_dependencies_v3 import verify_label_schema
    verify_label_schema();expected={}
    for split in ('train','validation'):
        for kind in ('inputs','probabilities'):
            p=REPORT/f'{split}-{kind}.json';r=json.loads(p.read_text());expected[p]=digest(p)
            for name,h in r['files'].items():expected[WORK/f'{split}-{name}.npy']=h
    expected[BASE/'combined-train.npz']='39386010575ad30add064fdae750680f34cfcc732c4fd00fb657875ff4c61ffb'
    expected[BASE.parent/'v4/validation.npz']='01a15e1e10f68922334a5367bb825c8ef9bbe228ae7a9e86e92aae9609b204ed'
    expected[BASE.parent/'v9/frequency/natural-mask.npy']='09217d8fc3d5673d980c8b8a4434861aa26dddb37e506bbfa22cbaafc0e525bd'
    files={}
    for p,h in expected.items():
        assert digest(p)==h,('Study cache hash mismatch',p);stat=p.stat();files[str(p.relative_to(ROOT))]=dict(sha256=h,size=stat.st_size,mtime_ns=stat.st_mtime_ns)
    immutable_json(target,dict(files=files,source_sha256=digest(__file__),meaning='Changed V13 inputs verified once before fitting; subsequent arms require exact saved size/mtime for immutable reuse. No replay re-extraction or495-game unchanged audit.',new_fits=0,reserved_opened=0));return digest(target)
