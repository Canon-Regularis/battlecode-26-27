"""Exactly one arm; tuning-only selection, then archived assessment predictions."""
import argparse
import hashlib
import json
import time
import numpy as np
import torch
from .model import Policy
from .data import load,legacy,chunks
from .engine import ARMS,train_window,infer,selectors
from .assessment import summarize,paired
from .protocol import ROOT,WORK,REPORT,SEED,preflight
from ..reliable_train import setup
from ..audit import immutable_json
from ..data import digest


def gradients(model,update):
    result={}
    for name,p in model.named_parameters():
        g=p.grad
        result[name]=None if g is None else dict(finite=bool(torch.isfinite(g).all()),
            nonzero=int(torch.count_nonzero(g)),L2=float(g.detach().double().norm()))
    return dict(update=update,pre_clipping=True,parameters=result)


def run(arm):
    plan,gate=preflight(arm)  # Must finish before optimizer construction/output.
    directory=WORK/'runs'/arm
    if directory.exists():raise FileExistsError('Preserve prior attempt: '+str(directory))
    setup(SEED);model=Policy();trainable=list(model.parameters())
    if sum(p.numel() for p in trainable)!=plan['parameters']:raise ValueError('Capacity changed')
    data={s:load(s) for s in ('fit','tuning')}
    if [len(data[s]['arrays']['y']) for s in data]!=[65465,15298]:raise ValueError('Rows changed')
    directory.mkdir(parents=True);immutable_json(directory/'preflight.json',gate)
    opt=torch.optim.AdamW(trainable,lr=.0003,weight_decay=.01)
    rng=np.random.default_rng(SEED);updates=0;trace=[];start=time.perf_counter()
    def save(path,epoch):
        torch.save(dict(state=model.state_dict(),optimizer=opt.state_dict(),round=epoch,
            updates=updates,arm=arm,torch_rng=torch.get_rng_state(),numpy_rng=rng.bit_generator.state,
            protocol_sha256=gate['protocol_sha256']),path)
    save(directory/'initial.pt',0)
    for epoch in range(1,13):
        model.train();state=model.empty(32);seen=np.zeros(65465,np.uint8);total=0.;schedule=hashlib.sha256()
        for rows in chunks(data['fit']['sequences'],rng,unroll=32):
            if time.perf_counter()-start+gate['prior_seconds']>=86400:
                raise RuntimeError('Study compute budget exhausted; preserve partial attempt, no automatic repeat')
            opt.zero_grad(set_to_none=True)
            state,loss,denominator=train_window(model,data['fit'],rows,state,arm)
            if denominator<=0:raise ValueError('Empty optimizer window')
            ids=rows[rows>=0];seen[ids]+=1;schedule.update(rows.astype('<i8').tobytes())
            if updates==0 or (updates+1)%100==0:
                immutable_json(directory/f'gradient-{updates+1:06d}.json',gradients(model,updates+1))
            torch.nn.utils.clip_grad_norm_(trainable,5,error_if_nonfinite=True)
            opt.step();updates+=1;total+=loss
            if updates%100==0:print(arm,'round',epoch,'update',updates,'seconds',round(time.perf_counter()-start,1),flush=True)
        if not np.all(seen==1):raise ValueError('Row coverage changed')
        checkpoint=directory/f'round-{epoch:02d}.pt';save(checkpoint,epoch)
        forecast=infer(model,data['tuning'],arm)
        np.savez_compressed(directory/f'round-{epoch:02d}-tuning.npz',**forecast)
        row=dict(round=epoch,updates=updates,train_online_nll=total/len(seen),
            tuning=selectors(data['tuning'],forecast),checkpoint_sha256=digest(checkpoint),
            schedule_sha256=schedule.hexdigest(),coverage=dict(rows=len(seen),min=int(seen.min()),max=int(seen.max())))
        trace.append(row);immutable_json(directory/f'round-{epoch:02d}-measurement.json',row)
        print(arm,row,flush=True)
    selected={key:min(trace,key=lambda r:(r['tuning'][key],r['round']))['round'] for key in ('movement','full')}
    # Freeze both choices before assessment/legacy data enter the process.
    immutable_json(directory/'selection.json',dict(selected=selected,trace=trace))
    data['assessment']=load('assessment');data['legacy']=legacy()
    results={};forecasts={}
    for epoch in sorted(set(selected.values())):
        checkpoint=torch.load(directory/f'round-{epoch:02d}.pt',map_location='cpu',weights_only=False)
        model.load_state_dict(checkpoint['state']);results[epoch]={};forecasts[epoch]={}
        for split,d in data.items():
            forecast=infer(model,d,arm,decode=True);forecasts[epoch][split]=forecast
            np.savez_compressed(directory/f'selected-{epoch:02d}-{split}.npz',**forecast)
            results[epoch][split]=summarize(d,forecast)
    comparisons={}
    historical={}
    for name,reference in plan['references'].items():
        with np.load(ROOT/reference['path']) as z:control={k:z[k] for k in z.files}
        historical[name]={selector:paired(data['legacy'],forecasts[epoch]['legacy'],control)
                          for selector,epoch in selected.items()}
    for reference in {'A':[],'B':['A'],'C':['A','B']}[arm]:
        r=json.loads((REPORT/f'{reference}.json').read_text());comparisons[reference]={}
        for selector,epoch in selected.items():
            re=r['selected'][selector];comparisons[reference][selector]={}
            for split in ('assessment','legacy'):
                with np.load(WORK/'runs'/reference/f'selected-{re:02d}-{split}.npz') as z:control={k:z[k] for k in z.files}
                comparisons[reference][selector][split]=paired(data[split],forecasts[epoch][split],control)
    bindings={str(p.relative_to(ROOT)):digest(p) for p in directory.rglob('*') if p.is_file()}
    immutable_json(REPORT/f'{arm}.json',dict(arm=arm,selected=selected,trace=trace,results=results,
        comparisons=comparisons,historical=historical,completed_rounds=12,completed_updates=updates,
        source_commit=gate['source_commit'],protocol_sha256=gate['protocol_sha256'],bindings=bindings,
        review_bindings=gate['review_bindings'],seconds=time.perf_counter()-start,
        new_fits=1,promoted=False,reserved_opened=0))
    print(arm,'completed; fresh independent postfit review required',flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('arm',choices=list(ARMS));run(parser.parse_args().arm)
