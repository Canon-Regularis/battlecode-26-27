"""Verify actual subset parity, schedules and inference without optimizer updates."""
import hashlib
import json
import numpy as np
import torch
from .data import load_subset,REPORT,WORK
from .protocol import SEED,INITIAL
from .assessment import evaluate
from ..history_horizon.data import load,chunks
from ..history_horizon.model import Policy
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
    for epoch in range(16):
        seen=np.zeros(8192,np.uint8);hash_=hashlib.sha256();count=0
        for rows in chunks(data['sequences'],rng,unroll=32):
            if rows.shape!=(32,32) or (rows<0).any():raise ValueError('Partial batch')
            count+=1;seen[rows.flatten()]+=1;hash_.update(rows.astype('<i8').tobytes())
        if count!=8 or not np.all(seen==1):raise ValueError('Coverage changed')
        schedules.append(dict(pass_number=epoch+1,batches=count,schedule_sha256=hash_.hexdigest(),numpy_rng=rng.bit_generator.state))
    bounded=dict(arrays={k:v[:256].copy() for k,v in data['arrays'].items()},
                 sequences=data['sequences'][:8],group=data['group'][:256])
    setup(SEED);model=Policy();model.load_state_dict(torch.load(INITIAL,map_location='cpu',weights_only=False)['state'])
    directory=WORK/'construction';directory.mkdir(parents=True,exist_ok=False)
    prediction,_=evaluate(model,bounded,directory,'initial')
    if not np.isfinite(prediction['nll']).all():raise ValueError('Nonfinite live-cache inference')
    immutable_json(REPORT/'construction-probe.json',dict(source_sha256=digest(__file__),
        exact_normalized_subset_rows=8192,only_override='actor_start reset metadata at256windowstarts',
        groups=len(np.unique(data['group'])),schedules=schedules,
        projected_updates=dict(U00=128,U01=512),row_presentations_per_arm=131072,
        causal_forecast_probe_rows=256,observed_likelihood_and_conditional_modes_exact=True,
        bindings={str(p):digest(p) for p in directory.iterdir() if p.is_file()},
        new_fits=0,optimizer_updates=0))
    print('Exact8192row subset parity;16matched schedules;256row causal/likelihood probe; no optimizer updates',flush=True)


if __name__=='__main__':run()
