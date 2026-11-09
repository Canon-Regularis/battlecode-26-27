"""Full initial parity and bounded gradients; no actual-data optimizer steps."""
import hashlib
import json
import numpy as np
import torch
from .protocol import ROOT,WORK,REPORT,SEED,build
from ..gradient_routing.data import load_subset
from ..gradient_routing.assessment import evaluate
from ..history_horizon.data import chunks,input_batch,geometry,targets
from ..reliable_train import setup
from ..audit import immutable_json
from ..data import digest


def run():
    directory=WORK/'construction';directory.mkdir(parents=True,exist_ok=False)
    data=load_subset();rng=np.random.default_rng(SEED);schedules=[]
    for epoch in range(8):
        seen=np.zeros(34720,np.uint8);h=hashlib.sha256();den=[];moves=[]
        for rows in chunks(data['sequences'],rng,unroll=32):
            ids=rows[rows>=0];seen[ids]+=1;den.append(len(ids));moves.append(int((data['arrays']['y'][ids]==8).sum()))
            h.update(rows.astype('<i8').tobytes())
        if not np.all(seen==1) or den!=[1024]*33+[928] or min(moves)<=0:raise ValueError('Frozen window schedule changed')
        schedules.append(dict(pass_number=epoch+1,batches=34,denominators=den,movement_rows=moves,
            schedule_sha256=h.hexdigest(),numpy_rng=rng.bit_generator.state))
    with np.load(ROOT/'.cambc/action-predictor/v36/runs/R00/final-predictions.npz') as z:reference={k:z[k] for k in z.files}
    initial=None;results={}
    for arm in ('N00','N01'):
        setup(SEED);model=build(arm);sub=directory/arm;sub.mkdir()
        state={k:v.clone() for k,v in model.state_dict().items()};torch_rng=torch.get_rng_state()
        if initial is None:initial=state;initial_rng=torch_rng
        else:
            if not all(torch.equal(v,initial[k]) for k,v in state.items()) or not torch.equal(torch_rng,initial_rng):
                raise ValueError('Arm initialization differs')
        torch.save(dict(state=state,torch_rng=torch_rng),sub/'initial.pt')
        prediction,summary=evaluate(model,data,sub,'initial')
        for k,v in prediction.items():
            if not np.array_equal(v,reference[k],equal_nan=True):raise ValueError('Initial reference forecast parity failed: '+k)
        # Four complete windows, actual input ordering, no optimizer construction.
        memory=model.empty(4);losses=[]
        for ids in np.arange(128).reshape(4,32).T:
            step=model.begin(**input_batch(data,ids),state=memory,reset8=True)
            loss,memory=model.observed(step,**geometry(data,ids),**targets(data,ids));losses.append(loss.sum())
        (torch.stack(losses).sum()/128).backward()
        gradients={}
        for name,p in model.named_parameters():
            if not p.requires_grad:
                if p.grad is not None:raise ValueError('Frozen base received gradients')
            else:
                if p.grad is None or not torch.isfinite(p.grad).all():raise ValueError('Missing/nonfinite residual gradient')
                gradients[name]=p.grad.numpy().copy()
        np.savez_compressed(sub/'gradients.npz',**gradients)
        if not all(torch.equal(v,model.state_dict()[k]) for k,v in state.items()):raise ValueError('Probe changed weights')
        results[arm]=dict(initial_rows_exact=34720,gradient_rows=128,
            gradient_norms={k:float(np.linalg.norm(v)) for k,v in gradients.items()},
            base_gradients_none=True,weights_unchanged=True,summary=summary)
        print(arm,'full initial forecast parity and finite residual gradients; no optimizer updates',flush=True)
    immutable_json(REPORT/'construction-probe.json',dict(source_sha256=digest(__file__),
        identical_initial_tensors_and_rng=True,total_parameters=144989,trainable_parameters=5697,
        schedules=schedules,results=results,
        bindings={str(p.relative_to(ROOT)):digest(p) for p in directory.rglob('*') if p.is_file()},
        new_fits=0,actual_data_optimizer_updates=0))


if __name__=='__main__':run()
