"""Strictly separate causal policy inputs from action/future-achievement targets."""
import json
import numpy as np
import torch
from .sequence_data import ROOT,BASE,WORK,REPORT
from .. import reliable_train as rt
from ..entity_set import EntityBank
from .public_inputs import batch as public_batch

def load(split,saved):
    with np.load(BASE/'combined-train.npz' if split=='train' else BASE.parent/'v4/validation.npz') as z:raw={k:z[k] for k in z.files}
    inputs,_=rt.model_data(raw,saved['config'],(saved['mean'],saved['std']))
    with np.load(WORK/f'{split}-sequences.npz') as z:sequence={k:z[k] for k in z.files}
    gap=np.empty_like(sequence['gap']);gap[sequence['order']]=sequence['gap'];sequences=[sequence['order'][a:b] for a,b in zip(sequence['offsets'][:-1],sequence['offsets'][1:])]
    with np.load(WORK/f'{split}-goals.npz') as z:goals={k:z[k] for k in z.files}
    with np.load(BASE.parent/f'v9/runs/G00/{split}-predictions.npz') as z:baseline={k:z[k] for k in z.files}
    oldtypes=np.load(BASE.parent/f'v14/{split}-type-logp.npy',mmap_mode='r');mode_joint=np.load(BASE.parent/f'v13/{split}-mode-logq.npy',mmap_mode='r');modes=np.load(BASE.parent/f'v13/{split}-modes.npy',mmap_mode='r')
    return dict(raw=raw,inputs=inputs,sequences=sequences,transition_gap=gap,goals=goals,observations=np.load(BASE.parent/'v7/observations.npy',mmap_mode='r'),indices=np.load(BASE.parent/f'v7/{split}-sequence.npy',mmap_mode='r'),history_gaps=np.load(BASE.parent/f'v7/{split}-gaps.npy',mmap_mode='r'),priority_mode=np.array(modes[:,9,2]),priority_mode_logp=np.array(mode_joint[:,9]-oldtypes[:,9]),baseline=baseline,mean=saved['mean'].numpy(),std=saved['std'].numpy(),entities=EntityBank(BASE.parent/'v9/entities',split,119),public=json.loads((WORK/f'{split}-public.json').read_text()))

def causal_inputs(d,ids):
    ix=np.asarray(ids);obs=np.array(d['observations'][d['indices'][ix]]);obs=(obs-d['mean'])/d['std'];inputs=d['inputs'];entities,mask=d['entities'].batch(ix);p=d['goals']['position'][ix];known=d['goals']['position_known'][ix];public,public_mask=public_batch(d['public'],ix,p,known);return dict(x=inputs['x'][ix],history=inputs['history'][ix],observations=torch.from_numpy(obs),history_gaps=torch.from_numpy(np.array(d['history_gaps'][ix])),transition_gap=torch.from_numpy(d['transition_gap'][ix]),position=torch.from_numpy(p),position_known=torch.from_numpy(known),entities=entities,entity_mask=mask,public_tokens=public,public_mask=public_mask)

def targets(d,ids):
    ix=np.asarray(ids);i=d['inputs'];return dict(y=i['y'][ix],py=i['py'][ix],priority_parameter_nll=torch.from_numpy(d['baseline']['param_nll'][ix]),achieved=torch.from_numpy(d['goals']['achieved_position'][ix]),achievement_available=torch.from_numpy(d['goals']['goal_target_available'][ix]))

def geometry(d,ids):
    i=d['inputs'];return dict(grid=i['grid'][ids].float(),valid=i['valid'][ids],rules=i['rules'][ids])

def chunks(sequences,rng=None,batch_size=32,unroll=8):
    order=np.arange(len(sequences)) if rng is None else rng.permutation(len(sequences));next_sequence=0;active=[None]*batch_size;at=np.zeros(batch_size,np.int64)
    while True:
        for b in range(batch_size):
            if active[b] is None and next_sequence<len(order):active[b]=sequences[order[next_sequence]];at[b]=0;next_sequence+=1
        if all(s is None for s in active):break
        rows=np.full((unroll,batch_size),-1,np.int64)
        for b,s in enumerate(active):
            if s is None:continue
            count=min(unroll,len(s)-at[b]);rows[:count,b]=s[at[b]:at[b]+count];at[b]+=count
            if at[b]==len(s):active[b]=None
        yield rows
