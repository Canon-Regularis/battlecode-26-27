"""Score retained P03 on the existing broad TRAIN rows without fitting."""
import json
import traceback
from pathlib import Path

import numpy as np
import torch

from ..audit import immutable_json
from ..data import digest
from ..order_information.anchored import committed_manifest
from ..priority_broad.guard import committed_sources
from ..priority_modes import AbsolutePriorityModes
from ..priority_regularized.safety import dependency_files,reject_optimized_python
from ..relational_priority.data import original_inputs
from ..relational_priority.protocol import fold

ROOT=Path(__file__).resolve().parents[3]
OUT=ROOT/'tools/action_predictor/experiments/v25'
LOCAL=ROOT/'.cambc/action-predictor/v25/PR00'
ANCHOR='1d9fb6b3b715cab36b3db2ff4e8acad6a616fe6f'


def paired(new,old,target,group,mask):
    group=group[mask];correct=new['integer'][mask]==target[mask];before=old['integer'][mask]==target[mask]
    change=correct.astype(int)-before;loss=new['nll'][mask]-old['nll'][mask]
    groups=np.unique(group);support=np.array([(group==g).sum() for g in groups])
    gains=np.array([change[group==g].sum() for g in groups]);losses=np.array([loss[group==g].sum() for g in groups])
    rng=np.random.default_rng(20261106)
    draws=np.stack([np.bincount(rng.integers(len(groups),size=len(groups)),minlength=len(groups)) for _ in range(2000)])
    return dict(rows=len(group),groups=len(groups),rescues=int((correct&~before).sum()),regressions=int((~correct&before).sum()),
        net=int(change.sum()),mean_NLL_difference=float(loss.mean()),
        accuracy_difference=float(change.mean()),accuracy_interval=np.quantile(draws@gains/(draws@support),[.025,.975]).tolist(),
        NLL_interval=np.quantile(draws@losses/(draws@support),[.025,.975]).tolist(),
        group_net=dict(zip(map(str,groups),map(int,gains))))


def independent(raw,values,target):
    """NumPy arithmetic; preserve historical vocabulary-first tie order."""
    logits=raw[:,:-2].astype(np.float64)
    maximum=logits.max(1,keepdims=True)
    mix=logits-maximum-np.log(np.exp(logits-maximum).sum(1,keepdims=True))
    mean=raw[:,-2].astype(np.float64);scale=np.exp(np.clip(raw[:,-1].astype(np.float64),-6,5))
    center=np.rint(mean*100).astype(np.int64)
    candidates=np.concatenate([np.broadcast_to(values,(len(raw),len(values))),center[:,None]],1)
    def fallback(v):
        shape=(len(raw),)+(1,)*(v.ndim-1)
        hi=(v/100+.005-mean.reshape(shape))/scale.reshape(shape)
        lo=(v/100-.005-mean.reshape(shape))/scale.reshape(shape)
        return -np.logaddexp(0,-hi)-np.logaddexp(0,lo)+np.log(-np.expm1(-.01/scale)).reshape(shape)
    point=np.full_like(candidates,-np.inf,dtype=np.float64);point[:,:len(values)]=mix[:,:-1]
    at=np.searchsorted(values,center);safe=np.minimum(at,len(values)-1)
    present=(at<len(values))&(values[safe]==center)
    point[:,-1]=np.where(present,mix[np.arange(len(raw)),safe],-np.inf)
    masses=np.logaddexp(point,mix[:,-1,None]+fallback(candidates))
    mode=candidates[np.arange(len(raw)),masses.argmax(1)]
    at=np.searchsorted(values,target);safe=np.minimum(at,len(values)-1)
    present=(at<len(values))&(values[safe]==target)
    target_point=np.where(present,mix[np.arange(len(raw)),safe],-np.inf)
    nll=-np.logaddexp(target_point,mix[:,-1]+fallback(target))
    return mode,nll


def run():
    reject_optimized_python()
    commit,sources=committed_sources(ROOT,dependency_files(ROOT,('tools.action_predictor.priority_reference.evaluate',)))
    if LOCAL.exists():raise FileExistsError('Preserve retained-reference attempt')
    broad,_,warm,bindings=original_inputs()
    report,more=committed_manifest(ANCHOR,'tools/action_predictor/experiments/v8/P03.json');bindings.update(more)
    vocab,more=committed_manifest(ANCHOR,'tools/action_predictor/experiments/v8/priority-absolute-modes-vocabulary.json');bindings.update(more)
    checkpoint=ROOT/'.cambc/action-predictor/v8/runs/P03/model.pt'
    if digest(checkpoint)!=report['checkpoint_sha256']:raise RuntimeError('Retained P03 changed')
    bindings[str(checkpoint.relative_to(ROOT))]=digest(checkpoint)
    saved=torch.load(checkpoint,map_location='cpu',weights_only=True)
    p05=torch.load(ROOT/'.cambc/action-predictor/v8/runs/P05/model.pt',map_location='cpu',weights_only=True)
    if saved['architecture']!='frozen-M01-priority-absolute-modes-v1':raise RuntimeError('Wrong retained head')
    if saved['baseline_sha256']!=p05['baseline_sha256']:raise RuntimeError('Different frozen context source')
    for name in ('extra_mean','extra_std'):
        if not torch.equal(saved[name],p05[name]):raise RuntimeError('P03 normalization differs from consumed features')
    fit,held=fold(broad['group'].numpy())
    immutable_json(OUT/'PR00-plan.json',dict(source_commit=commit,sources=sources,inputs=bindings,
        checkpoint='Retained selected P03 model.pt, not epoch or checkpoint reselection',rows=5876,
        rows_scope='All existing broad natural TRAIN rows; identical RC correction-fit/held grouping',
        held_groups=held.tolist(),new_fits=0,optimizer_updates=0,
        hypothesis='Establish a relevant retained integer comparator, not select a new treatment or tune RC',
        metrics='Exact conditional integers, NLL and paired whole-group differences against warm P05; 2000 draws seed20261106',
        independent_check='All-row NumPy probability/mode reconstruction; mode equality and NLL tolerance2e-8',
        exposure='Both retained heads and encoder saw these TRAIN games; not untouched generalization',
        prohibited='No DEV or reserved payloads, fitting, queries, matches, bot/runtime work or deployment'))
    LOCAL.mkdir(parents=True)
    try:
        torch.set_num_threads(4)
        with torch.random.fork_rng():
            model=AbsolutePriorityModes(torch.nn.Linear(128,2),vocab['values'],vocab['counts'],saved['config']['use_inputs'])
        model.load_state_dict(saved['head_state']);model.eval().requires_grad_(False)
        outputs=[]
        with torch.inference_mode():
            for start in range(0,len(fit),256):
                outputs.append(model(broad['context'][start:start+256],broad['features'][start:start+256]).numpy())
        raw=np.concatenate(outputs);np.save(LOCAL/'raw.npy',raw)
        # Forecasts are preserved before any measurement or numerical checks.
        with torch.inference_mode():
            tensor=torch.from_numpy(raw)
            mode=model.integer(tensor).numpy()
        np.savez_compressed(LOCAL/'forecast.npz',integer=mode,index=broad['index'].numpy())
        target=broad['target'].numpy();group=broad['group'].numpy()
        with torch.inference_mode():nll=-model.log_mass(tensor,broad['target']).numpy()
        np.savez_compressed(LOCAL/'predictions.npz',integer=mode,nll=nll,index=broad['index'].numpy())
        independent_mode,independent_nll=independent(raw,model.values.numpy(),target)
        checks=dict(mode_mismatches=int((mode!=independent_mode).sum()),max_NLL_difference=float(np.abs(nll-independent_nll).max()))
        immutable_json(LOCAL/'arithmetic.json',checks)
        if checks['mode_mismatches'] or checks['max_NLL_difference']>2e-8:raise RuntimeError('Independent reconstruction failed')
        prediction=dict(integer=mode,nll=nll);results={}
        for label,mask in dict(all=np.ones(len(fit),bool),correction_fit=fit,correction_held=~fit).items():
            results[label]=dict(rows=int(mask.sum()),P03_exact=int((mode[mask]==target[mask]).sum()),
                P05_exact=int((warm['integer'][mask]==target[mask]).sum()),P03_NLL=float(nll[mask].mean()),
                P05_NLL=float(warm['nll'][mask].mean()),paired=paired(prediction,warm,target,group,mask))
        for path in LOCAL.iterdir():bindings[str(path.relative_to(ROOT))]=digest(path)
        bindings.update(sources);bindings[str((OUT/'PR00-plan.json').relative_to(ROOT))]=digest(OUT/'PR00-plan.json')
        immutable_json(OUT/'PR00.json',dict(results=results,independent_arithmetic=checks,bindings=bindings,
            source_commit=commit,conditional_priority_only=True,new_fits=0,optimizer_updates=0,reserved_opened=0,
            exposure='Both retained models previously saw all rows. No new group-exclusion claim for either retained head.',
            inference='Historical P03 mode and normalized integer likelihood unchanged. Original M01 contexts and causal39 fields.',
            limitations='No type selection, complete-command improvement, global calibration, strategy recovery or promotion.',
            command='python -m tools.action_predictor.priority_reference.evaluate'))
        print(json.dumps(results,indent=2),flush=True)
    except BaseException:
        (LOCAL/'failure.txt').write_text(traceback.format_exc(),encoding='utf-8')
        raise


if __name__=='__main__':run()
