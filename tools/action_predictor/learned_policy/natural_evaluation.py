"""Supplemental natural-cadence TRAIN replay, no fitting or checkpoint selection."""
import json
import sys
import numpy as np
import torch
from .sequence_data import BASE, WORK, REPORT
from .model import GoalPolicy
from .data import load
from .inference import infer
from ..priority_fit_v3 import load_base
from ..movement_experts.evaluate import summary
from ..audit import immutable_json
from ..data import digest


class RowView:
    def __init__(self, value, index): self.value,self.index=value,index
    def __getitem__(self, rows): return self.value[self.index[rows]]


class EntityView:
    def __init__(self, bank, index): self.bank,self.index=bank,index
    def batch(self, rows): return self.bank.batch(self.index[np.asarray(rows)])


def natural_gaps(stream, old_gap, y, rounds, selected):
    """Reconstitute only past root counts, excluding both endpoint commands."""
    delta_float=np.expm1(old_gap[:,0].astype(np.float64)*8)
    counts_float=np.expm1(old_gap[:,3:].astype(np.float64)*8)
    delta=np.rint(delta_float).astype(np.int64);counts=np.rint(counts_float).astype(np.int64)
    assert np.abs(delta_float-delta).max()<.05 and np.abs(counts_float-counts).max()<.05
    np.testing.assert_array_equal(counts.sum(1),delta-1)
    ordinal=np.cumsum(delta)-1;prefix=np.zeros_like(counts)
    for i in range(len(stream)):
        prefix[i]=counts[i]
        if i:
            prefix[i]+=prefix[i-1];prefix[i,y[stream[i-1]]]+=1
    np.testing.assert_array_equal(prefix.sum(1),ordinal)
    positions=np.flatnonzero(selected[stream]);output=[];previous=None
    for i in positions:
        if previous is None:
            gap=int(ordinal[i])+1;elapsed=0;intervening=prefix[i];initial=1
        else:
            gap=int(ordinal[i]-ordinal[previous]);elapsed=int(rounds[stream[i]]-rounds[stream[previous]])
            intervening=prefix[i]-prefix[previous];intervening[y[stream[previous]]]-=1;initial=0
        assert elapsed>=0 and intervening.min()>=0 and intervening.sum()==gap-1
        output.append(np.r_[np.log1p(gap)/8,np.log1p(elapsed)/8,initial,np.log1p(intervening)/8].astype(np.float32))
        previous=i
    return stream[positions],np.asarray(output,np.float32).reshape(-1,18)


def subset(d, keep_mask):
    keep=np.flatnonzero(keep_mask);inverse=np.full(len(keep_mask),-1,np.int64);inverse[keep]=np.arange(len(keep))
    transitions=np.zeros((len(keep),18),np.float32);sequences=[]
    for stream in d['sequences']:
        ids,gaps=natural_gaps(stream,d['transition_gap'][stream],d['raw']['y'],d['raw']['round'],keep_mask)
        if len(ids):sequences.append(inverse[ids]);transitions[inverse[ids]]=gaps
    public=dict(d['public']);public['starts']=np.searchsorted(keep,np.asarray(public['starts'])).tolist()
    result=dict(d,raw={k:d['raw'][k][keep] for k in ('y','py','priority','group')},
        inputs={k:RowView(v,keep) for k,v in d['inputs'].items()},sequences=sequences,transition_gap=transitions,
        goals={k:RowView(v,keep) for k,v in d['goals'].items()},indices=d['indices'][keep],history_gaps=d['history_gaps'][keep],
        priority_mode=d['priority_mode'][keep],priority_mode_logp=d['priority_mode_logp'][keep],
        baseline={k:v[keep] for k,v in d['baseline'].items()},entities=EntityView(d['entities'],keep),public=public)
    return result,keep


def plan():
    immutable_json(REPORT/'natural-cadence-evaluation-plan.json',dict(
        purpose='LP-06 supplemental fixed-checkpoint TRAIN evaluation with the original288801identity-verified natural rows, not an easier benchmark or another fit.',
        chronology='Retain full actual-root ordinal/count information. Dropped augmented targets become intervening earlier actual actions; current target and previous natural target excluded from gap counts. First natural target has explicit unavailable-prefix memory. Never glue nonconsecutive natural rows.',
        inputs='Current personal PRE, actual earlier16observation/action windows and frozen normalization unchanged. Recompute only selected-decision transition summaries and forward latent filter cadence. Current/future answers never enter proposal; earlier removed own actions may contribute counts after occurrence.',
        evaluation='Same selected L00/L01 checkpoint, no selection or optimizer. All original TRAIN/DEV reports remain authoritative; supplemental natural scores are in-sample, no untouched/fresh-fold or isolated group-shift evidence. Future-achieved auxiliary targets retain the original target scheme and are not a matched goal-label sampling comparison.',
        source_sha256=digest(__file__),new_fits=0,reserved_opened=0))


def run(identifier):
    plan();torch.set_num_threads(2)
    info=json.loads((REPORT/f'{identifier}.json').read_text());path=WORK/f"runs/{identifier}/round-{info['selected_round']:02d}.pt"
    assert digest(path)==info['checkpoint_sha256']
    teacher,saved=load_base();checkpoint=torch.load(path,weights_only=False)
    model=GoalPolicy(teacher,checkpoint['persistent']);model.load_state_dict(checkpoint['state']);model.eval()
    d=load('train',saved);maskpath=BASE.parent/'v9/frequency/natural-mask.npy'
    assert digest(maskpath)=='09217d8fc3d5673d980c8b8a4434861aa26dddb37e506bbfa22cbaafc0e525bd'
    natural,keep=subset(d,np.load(maskpath));assert len(keep)==288801
    forecast,goals=infer(model,natural)
    directory=WORK/f'natural-evaluation/{identifier}';assert not directory.exists();directory.mkdir(parents=True)
    np.savez_compressed(directory/'predictions.npz',original_index=keep,**forecast)
    np.savez_compressed(directory/'goals.npz',**goals)
    direction=np.load(BASE.parent/'v7/train-direction.npy')[keep]
    q=dict(raw=natural['raw'],direction=direction)
    contexts=dict(all=np.ones(len(keep),bool),move_continue=(natural['raw']['y']==8)&(direction==2),move_change=(natural['raw']['y']==8)&(direction==3))
    immutable_json(REPORT/f'{identifier}-natural-cadence.json',dict(
        scores={k:summary(q,forecast,m) for k,m in contexts.items()},
        checkpoint_sha256=digest(path),predictions_sha256=digest(directory/'predictions.npz'),goals_sha256=digest(directory/'goals.npz'),
        natural_mask_sha256=digest(maskpath),input_receipt_sha256=digest(REPORT/'policy-input-bindings.json'),
        plan_sha256=digest(REPORT/'natural-cadence-evaluation-plan.json'),source_sha256=digest(__file__),
        new_fits=0,reserved_opened=0))
    print('Natural cadence completed',identifier,len(keep),flush=True)


if __name__=='__main__':
    if sys.argv[1:] == ['plan']:plan()
    else:run(sys.argv[1])
