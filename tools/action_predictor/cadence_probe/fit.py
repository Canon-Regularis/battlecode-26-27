"""One bounded arm; no tuning, assessment or original-DEV loading."""
import argparse
import hashlib
import json
import time
import numpy as np
import torch
from .data import ROOT,WORK,REPORT,load_subset
from .engine import ARMS,update_window
from .protocol import SEED,INITIAL,preflight
from .assessment import evaluate,comparison
from ..history_horizon.model import Policy
from ..history_horizon.data import chunks
from ..reliable_train import setup
from ..audit import immutable_json
from ..data import digest


def run(arm):
    plan,gate=preflight(arm)
    directory=WORK/'runs'/arm
    if directory.exists():raise FileExistsError('Preserve every prior fit attempt')
    setup(SEED);data=load_subset();model=Policy()
    model.load_state_dict(torch.load(INITIAL,map_location='cpu',weights_only=False)['state'])
    directory.mkdir(parents=True);immutable_json(directory/'preflight.json',gate)
    optimizer=torch.optim.AdamW(model.parameters(),lr=.0003,weight_decay=.01)
    if optimizer.state:raise ValueError('Optimizer must start fresh')
    rng=np.random.default_rng(SEED);updates=0;trace=[];tick=time.perf_counter()
    def budget():
        if time.perf_counter()-tick+gate['prior_seconds']>=7200:
            raise RuntimeError('Two-hour paired budget exhausted; preserve attempt, no restart/extension')
    def save(name,epoch):
        torch.save(dict(state=model.state_dict(),optimizer=optimizer.state_dict(),round=epoch,updates=updates,
            torch_rng=torch.get_rng_state(),numpy_rng=rng.bit_generator.state,arm=arm,
            protocol_sha256=gate['protocol_sha256']),directory/name)
    save('initial.pt',0)
    _,initial=evaluate(model,data,directory,'initial');budget()
    for epoch in range(1,17):
        model.train();seen=np.zeros(8192,np.uint8);schedule=hashlib.sha256();total=0.;records=[]
        for rows in chunks(data['sequences'],rng,unroll=32):
            budget();loss,steps=update_window(model,data,rows,optimizer,arm)
            updates+=len(steps);records.extend(steps);total+=loss;seen[rows.flatten()]+=1
            schedule.update(rows.astype('<i8').tobytes())
        if not np.all(seen==1):raise ValueError('Fitting coverage changed')
        if updates!=epoch*(8 if arm=='U00' else 32):raise ValueError('Update cadence changed')
        save(f'round-{epoch:02d}.pt',epoch)
        measurement=dict(round=epoch,updates=updates,row_presentations=8192,online_nll=total/8192,
            schedule_sha256=schedule.hexdigest(),coverage=dict(min=int(seen.min()),max=int(seen.max())),
            steps=records)
        trace.append(measurement);immutable_json(directory/f'round-{epoch:02d}.json',measurement)
        print(arm,'pass',epoch,'updates',updates,'online_NLL',total/8192,flush=True)
    budget();prediction,final=evaluate(model,data,directory,'final');budget()
    comparisons={}
    if arm=='U01':
        with np.load(WORK/'runs/U00/final-predictions.npz') as z:control={k:z[k] for k in z.files}
        comparisons['U00']=comparison(data,prediction,control)
    records=[s for row in trace for s in row['steps']]
    bindings={str(p.relative_to(ROOT)):digest(p) for p in directory.rglob('*') if p.is_file()}
    immutable_json(REPORT/f'{arm}.json',dict(arm=arm,protocol_sha256=gate['protocol_sha256'],source_commit=gate['source_commit'],
        review_bindings=gate['review_bindings'],bindings=bindings,initial=initial,final=final,comparisons=comparisons,
        trace=trace,selected_round=16,completed_rounds=16,completed_updates=updates,row_presentations=8192*16,
        clipping=dict(steps=len(records),clipped=sum(s['clipped'] for s in records),fraction=float(np.mean([s['clipped'] for s in records]))),
        seconds=time.perf_counter()-tick,new_fits=1,optimizer_updates=updates,promoted=False,reserved_opened=0))
    print(arm,'completed; fresh independent review required',flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('arm',choices=list(ARMS));run(parser.parse_args().arm)
