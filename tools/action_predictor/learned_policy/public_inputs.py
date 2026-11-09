"""All cached public altars/spawn tiles; no nearest-goal policy or hidden state."""
import argparse,json,hashlib
from pathlib import Path
import numpy as np
import torch
from .sequence_data import ROOT,BASE,JOBS,WORK,REPORT
from ..audit import immutable_json
from ..data import digest

def prepare(split):
    jobs=[j for j in json.loads(JOBS.read_text()) if j['split']==split];starts=[];positions=[];kinds=[];bindings=[]
    for j in jobs:
        directory=Path(j['work'])/'supplement'/j['record']['raw_sha256'];line=next((directory/'pre.jsonl').open());r=json.loads(line);assert r['record']=='map';route=r['route'];q=json.loads((directory/'query.json').read_text());teams={t['team'] for t in q['turns']};assert len(teams)==1;team=teams.pop();points=[];labels=[]
        for a in route['altars']:points.append([a['x']/32,a['y']/32]);labels.append(0)
        for side in (0,1):
            s=route['spawns'][side]
            for y in range(s['minY'],s['maxY']):
                for x in range(s['minX'],s['maxX']):points.append([x/32,y/32]);labels.append(1 if side==team else 2)
        assert points;starts.append(j['offset']);positions.append(points);kinds.append(labels);bindings.append(dict(raw=j['record']['raw_sha256'],public_map_line_sha256=hashlib.sha256(line.encode()).hexdigest(),query_sha256=digest(directory/'query.json'),historical_supplement_receipt_sha256=digest(directory/'receipt.json')))
    value=dict(starts=starts,world=positions,kind=kinds,bindings=bindings,source_sha256=digest(__file__),meaning='Every public altar and every tile in both public spawn rectangles; own/enemy tags from recorded personal perspective. No current/future action input, dynamic hidden camp state or manually ranked goal. Relative features formed from CURRENT ownposition only. Static terrain remains in reused localgrid; no globalterrain encoder claim.',new_fits=0,reserved_opened=0);immutable_json(WORK/f'{split}-public.json',value);immutable_json(REPORT/f'{split}-public.json',dict(cache_sha256=digest(WORK/f'{split}-public.json'),games=len(jobs),bindings=bindings,source_sha256=digest(__file__),new_fits=0,reserved_opened=0));print(split,'public geometry cached',len(jobs),flush=True)

def batch(public,ids,position,known):
    games=np.searchsorted(public['starts'],ids,side='right')-1;lengths=[len(public['world'][g]) for g in games];values=np.zeros((len(ids),max(lengths),8),np.float32);mask=np.zeros(values.shape[:2],bool)
    for b,g in enumerate(games):
        n=lengths[b];mask[b,:n]=True;values[b,np.arange(n),np.asarray(public['kind'][g])]=1;delta=np.asarray(public['world'][g],np.float32)-position[b];values[b,:n,4:6]=delta*known[b];values[b,:n,6]=np.abs(delta).max(-1)*known[b];values[b,:n,7]=known[b]
    return torch.from_numpy(values),torch.from_numpy(mask)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('split',choices=['train','validation']);prepare(p.parse_args().split)
