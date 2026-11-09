"""Input/sampler/gradient parity only; no actual-data optimizer updates."""
import hashlib
import json
import copy
import numpy as np
import torch
from .data import ROOT,load_subset,REPORT,WORK
from .protocol import SEED
from .assessment import evaluate
from .engine import gradients,combine
from ..history_horizon.data import load,chunks
from ..history_horizon.model import Policy
from ..history_horizon.engine import train_window
from ..reliable_train import setup
from ..audit import immutable_json
from ..data import digest


def run():
    original=load('fit');data=load_subset();ids=data['source_ids']
    for name,value in data['arrays'].items():
        expected=original['arrays'][name][ids].copy()
        if name=='actor_start':expected[::32]=True
        np.testing.assert_array_equal(value,expected)
    np.testing.assert_array_equal(data['group'],original['group'][ids]);del original
    rng=np.random.default_rng(SEED);schedules=[]
    for epoch in range(8):
        seen=np.zeros(34720,np.uint8);hash_=hashlib.sha256();denominators=[]
        for rows in chunks(data['sequences'],rng,unroll=32):
            actual=rows[rows>=0];denominators.append(len(actual));seen[actual]+=1
            hash_.update(rows.astype('<i8').tobytes())
        if denominators!=[1024]*33+[928] or not np.all(seen==1):raise ValueError('Coverage changed')
        schedules.append(dict(pass_number=epoch+1,batches=34,denominators=denominators,
            schedule_sha256=hash_.hexdigest(),numpy_rng=rng.bit_generator.state))
    bounded=dict(arrays={k:v[:256].copy() for k,v in data['arrays'].items()},
        sequences=data['sequences'][:8],group=data['group'][:256])
    setup(SEED);model=Policy();reference=copy.deepcopy(model)
    directory=WORK/'construction';directory.mkdir(parents=True,exist_ok=False)
    torch.save(dict(state=model.state_dict(),torch_rng=torch.get_rng_state()),directory/'initial.pt')
    prediction,_=evaluate(model,bounded,directory,'initial')
    rows=np.arange(128).reshape(4,32).T
    vectors,used,total,parts=gradients(model,bounded,rows)
    ordinary,stats=combine(vectors,False);routed,_=combine(vectors,True)
    _,expected,n=train_window(reference,bounded,rows,reference.empty(4),'A')
    expected_gradient=torch.cat([torch.zeros_like(p).flatten() if p.grad is None else p.grad.flatten() for p in reference.parameters()])
    torch.testing.assert_close(ordinary,expected_gradient,rtol=1e-4,atol=2e-7)
    if used!=[p.grad is not None for p in reference.parameters()]:raise ValueError('Unused parameter mismatch')
    if abs(total-expected)>1e-8:raise ValueError('Original likelihood mismatch')
    np.savez_compressed(directory/'gradients.npz',change=vectors[0].numpy(),continuation=vectors[1].numpy(),
        rest=vectors[2].numpy(),ordinary=ordinary.numpy(),reference=expected_gradient.numpy(),routed=routed.numpy())
    immutable_json(REPORT/'construction-probe.json',dict(source_sha256=digest(__file__),
        exact_normalized_subset_rows=34720,only_override='actor_start reset metadata at 1085 existing aligned window starts',
        groups=len(np.unique(data['group'])),schedules=schedules,parameters=sum(p.numel() for p in model.parameters()),
        projected_updates=dict(R00=272,R01=272),row_presentations_per_arm=277760,
        causal_forecast_probe_rows=256,observed_likelihood_and_conditional_modes_exact=True,
        gradient_parity=dict(rows=n,loss_sum=total,partition_sums=parts,
            max_absolute_error=float((ordinary-expected_gradient).abs().max()),atol=2e-7,rtol=1e-4,
            exact_unused_parameter_parity=True,initial_conflict_statistics=stats),
        bindings={str(p.relative_to(ROOT)):digest(p) for p in directory.iterdir() if p.is_file()},
        new_fits=0,optimizer_updates=0))
    print('Exact 34720-row parity; eight schedules; 256 causal rows and 128-row gradient parity; zero optimizer updates',flush=True)


if __name__=='__main__':run()
