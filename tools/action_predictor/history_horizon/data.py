"""Fit-only normalization and explicit separation of inputs and target metadata."""
import json
import numpy as np
import torch
from ..trajectory_history.assemble import WORK, REPORT
from ..data import digest
from ..learned_policy.sequence_data import ROOT
from ..reliable_train import LABELS
from ..learned_policy.data import chunks

INPUTS=('x','history','observations','history_gaps','priority_inputs','root_gap','actor_start')
LEGACY_FILES=('v4/validation.npz','v7/observations.npy','v7/validation-sequence.npy',
              'v7/validation-gaps.npy','v7/validation-direction.npy',
              'v8/priority-validation.npz','v16/validation-sequences.npz')


def normalize(raw,mean,std):
    out={k:np.array(v,copy=True) for k,v in raw.items()}
    out['x']=(out['x']-mean)/std
    out['observations']=(out['observations']-mean)/std
    # Missing frames stay zero after normalization, including encoder bias masking.
    out['observations']*=out['history_gaps'][:,:,1:2]
    keep=np.zeros(out['history'].shape[:2],bool)
    for family in ('move','blocked','attack','cast_0','cast_1','ward','submit','altar','teleport','end'):
        keep |= out['history'][:,:,LABELS.index(family)]>0
    out['history'][:,:,16:18]*=keep[:,:,None]
    return out


def load(partition):
    manifest=json.loads((REPORT/'assembly.json').read_text())
    normalizer=WORK/'normalizer.npz'
    if digest(normalizer)!=manifest['normalizer_sha256']:raise ValueError('Normalizer changed')
    with np.load(normalizer) as z:mean,std=z['mean'],z['std']
    pieces={};sequences=[];groups=[];offset=0
    for group_index,g in enumerate(manifest['games']):
        if g['partition']!=partition:continue
        path=WORK/'games'/g['payload']/'data.npz'
        if digest(path)!=g['arrays_sha256']:raise ValueError('Data changed')
        with np.load(path) as z:raw={k:z[k] for k in z.files}
        normalized=normalize(raw,mean,std)
        for k,v in normalized.items():
            if k!='offsets':pieces.setdefault(k,[]).append(v)
        for a,b in zip(raw['offsets'][:-1],raw['offsets'][1:]):sequences.append(np.arange(a+offset,b+offset))
        groups.extend([group_index]*g['rows']);offset+=g['rows']
    if not pieces:raise ValueError('Empty partition')
    arrays={k:np.concatenate(v) for k,v in pieces.items()}
    return dict(arrays=arrays,sequences=sequences,group=np.asarray(groups))


def legacy():
    """Original DEV, diagnostic only; uses new fit-only normalization/weights."""
    base=ROOT/'.cambc/action-predictor'
    with np.load(base/LEGACY_FILES[0]) as z:raw={k:z[k] for k in z.files}
    with np.load(WORK/'normalizer.npz') as z:mean,std=z['mean'],z['std']
    with np.load(base/'v16/validation-sequences.npz') as z:
        order,offsets,gap=z['order'],z['offsets'],z['gap']
    gap_by_row=np.empty_like(gap);gap_by_row[order]=gap
    raw['root_gap']=np.expm1(gap_by_row[:,0].astype(np.float64)*8).round().astype(np.int64)
    raw['actor_start']=gap_by_row[:,2]>.5
    raw['history']=raw['history'][:,-16:]
    indices=np.load(base/'v7/validation-sequence.npy')
    raw['observations']=np.array(np.load(base/'v7/observations.npy',mmap_mode='r')[indices])
    raw['history_gaps']=np.load(base/'v7/validation-gaps.npy')
    raw['direction']=np.load(base/'v7/validation-direction.npy')
    with np.load(base/'v8/priority-validation.npz') as z:raw['priority_inputs']=z['values'].copy()
    raw['priority_inputs'][:,:4]=0
    raw['rules']=np.column_stack((raw['attack_range'],raw['ability_range'],raw['ability_mask']))
    return dict(arrays=normalize(raw,mean,std),group=raw['group'],
                sequences=[order[a:b] for a,b in zip(offsets[:-1],offsets[1:])])


def input_batch(data,ids):
    raw=data['arrays'];result={k:torch.from_numpy(raw[k][ids]) for k in INPUTS}
    for k in ('x','history','observations','history_gaps'):result[k]=result[k].float()
    return result


def geometry(data,ids):
    return {k:torch.from_numpy(data['arrays'][k][ids]).float() if k!='valid'
            else torch.from_numpy(data['arrays'][k][ids]) for k in ('grid','valid','rules')}


def targets(data,ids):
    return {k:torch.from_numpy(data['arrays'][k][ids]).long() for k in ('y','py','priority')}
