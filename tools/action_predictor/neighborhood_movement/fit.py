"""One bounded arm; no tuning, assessment or original-DEV loading."""
import argparse
import hashlib
import json
import time
import numpy as np
import torch
from ..gradient_routing.data import load_subset
from .engine import ARMS,update_window
from .protocol import ROOT,WORK,REPORT,SEED,preflight,build
from ..gradient_routing.assessment import evaluate,comparison
from ..gradient_routing.fit import checked_elapsed,publish_result
from ..history_horizon.data import chunks
from ..reliable_train import setup
from ..audit import immutable_json
from ..data import digest


def run(arm):
    plan,gate=preflight(arm)
    directory=WORK/'runs'/arm
    if directory.exists():raise FileExistsError('Preserve every prior fit attempt')
    setup(SEED);data=load_subset();model=build(arm);base_state={k:v.clone() for k,v in model.base_state().items()}
    directory.mkdir(parents=True);immutable_json(directory/'preflight.json',gate)
    optimizer=torch.optim.AdamW(model.trainable_parameters(),lr=.0003,weight_decay=.01)
    if optimizer.state:raise ValueError('Optimizer must start fresh')
    rng=np.random.default_rng(SEED);updates=0;trace=[];tick=time.perf_counter()
    schedules=json.loads((REPORT/'construction-probe.json').read_text())['schedules']
    def budget():
        return checked_elapsed(tick,gate['prior_seconds'])
    def save(name,epoch):
        if not all(torch.equal(v,base_state[k]) for k,v in model.base_state().items()):raise ValueError('Frozen backbone changed')
        torch.save(dict(state=model.state_dict(),optimizer=optimizer.state_dict(),round=epoch,updates=updates,
            torch_rng=torch.get_rng_state(),numpy_rng=rng.bit_generator.state,arm=arm,
            protocol_sha256=gate['protocol_sha256']),directory/name)
    save('initial.pt',0)
    initial_prediction,initial=evaluate(model,data,directory,'initial');budget()
    with np.load(ROOT/'.cambc/action-predictor/v36/runs/R00/final-predictions.npz') as z:
        reference={k:z[k] for k in z.files}
    for k,v in initial_prediction.items():
        if not np.array_equal(v,reference[k],equal_nan=True):raise ValueError('Initial predictions differ from frozen base')
    for epoch in range(1,9):
        model.train();seen=np.zeros(34720,np.uint8);schedule=hashlib.sha256();total=0.;records=[]
        for rows in chunks(data['sequences'],rng,unroll=32):
            budget();loss,steps=update_window(model,data,rows,optimizer,arm)
            updates+=len(steps);records.extend(steps);total+=loss;seen[rows[rows>=0]]+=1
            schedule.update(rows.astype('<i8').tobytes())
        if not np.all(seen==1):raise ValueError('Fitting coverage changed')
        if updates!=epoch*34:raise ValueError('Update count changed')
        expected=schedules[epoch-1]
        if schedule.hexdigest()!=expected['schedule_sha256'] or rng.bit_generator.state!=expected['numpy_rng']:
            raise ValueError('Frozen sampler or RNG changed')
        if [s['rows'] for s in records]!=expected['denominators']:raise ValueError('Optimizer denominators changed')
        if [s['movement_rows'] for s in records]!=expected['movement_rows'] or not all(s['active'] for s in records):raise ValueError('Frozen movement exposure changed')
        save(f'round-{epoch:02d}.pt',epoch)
        measurement=dict(round=epoch,updates=updates,row_presentations=34720,online_nll=total/34720,
            schedule_sha256=schedule.hexdigest(),coverage=dict(min=int(seen.min()),max=int(seen.max())),
            steps=records)
        trace.append(measurement);immutable_json(directory/f'round-{epoch:02d}.json',measurement)
        print(arm,'pass',epoch,'updates',updates,'online_NLL',total/34720,flush=True)
    budget();prediction,final=evaluate(model,data,directory,'final');budget()
    comparisons={}
    if arm=='N01':
        with np.load(WORK/'runs/N00/final-predictions.npz') as z:control={k:z[k] for k in z.files}
        comparisons['N00']=comparison(data,prediction,control)
    comparisons['frozen_R00']=comparison(data,prediction,reference)
    records=[s for row in trace for s in row['steps']]
    bindings={str(p.relative_to(ROOT)):digest(p) for p in directory.rglob('*') if p.is_file()}
    publish_result(REPORT/f'{arm}.json',dict(arm=arm,protocol_sha256=gate['protocol_sha256'],source_commit=gate['source_commit'],
        review_bindings=gate['review_bindings'],bindings=bindings,initial=initial,final=final,comparisons=comparisons,
        trace=trace,selected_round=8,completed_rounds=8,completed_updates=updates,row_presentations=34720*8,
        frozen_backbone_exact=True,trainable_parameters=5697,
        all_required_comparisons_pass=arm=='N01' and all(c['all_checks_pass'] for c in comparisons.values()),
        clipping=dict(steps=len(records),clipped=sum(s['clipped'] for s in records),fraction=float(np.mean([s['clipped'] for s in records]))),
        new_fits=1,optimizer_updates=updates,promoted=False,reserved_opened=0),tick,gate['prior_seconds'])
    print(arm,'completed; fresh independent review required',flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('arm',choices=list(ARMS));run(parser.parse_args().arm)
