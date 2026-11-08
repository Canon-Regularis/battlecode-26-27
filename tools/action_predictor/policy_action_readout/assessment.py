"""Saved readout forecasts, complete commands, and matched category guards."""
import json
import numpy as np
import torch
from ..audit import immutable_json
from ..data import digest
from ..movement_experts.evaluate import summary,support,masks,paired
from ..learned_policy.analysis import paired_categories,readiness_flags
from ..observation_metrics import correctness
from ..order_information.anchored import committed_manifest
from .model import decode
from .data import batch
from .protocol import ROOT,OUT,LOCAL,SCIENTIFIC


@torch.no_grad()
def infer(model,d,active,directory,tag):
    model.eval();n=len(d['type_logp']);directory.mkdir(parents=True,exist_ok=True)
    raw_path=directory/(tag+'-raw.npy');lp_path=directory/(tag+'-family-logp.npy')
    if raw_path.exists() or lp_path.exists():raise FileExistsError('Preserve prior readout forecast')
    raw=np.lib.format.open_memmap(raw_path,mode='w+',dtype=np.float64,shape=(n,15))
    lp=np.lib.format.open_memmap(lp_path,mode='w+',dtype=np.float64,shape=(n,15))
    prediction=np.empty(n,np.int64);coordinate=np.empty(n,np.int64)
    for start in range(0,n,4096):
        ids=np.arange(start,min(start+4096,n));base,x=batch(d,ids,active)
        output=model.logits(base,x);raw[ids]=output.numpy();raw.flush()
        logp=output.log_softmax(-1);lp[ids]=logp.numpy()
        p=decode(logp,torch.from_numpy(np.array(d['conditional_mode_logp'][ids])),
            torch.from_numpy(np.array(d['family_coordinate'][ids])),torch.from_numpy(np.array(d['priority_mode'][ids])))
        prediction[ids]=p['prediction'].numpy();coordinate[ids]=p['proposed_coordinate'].numpy()
    raw.flush();lp.flush()
    command_path=directory/(tag+'-commands.npz')
    np.savez_compressed(command_path,prediction=prediction,proposed_coordinate=coordinate,priority=d['priority_mode'])
    immutable_json(directory/(tag+'-preserved.json'),dict(rows=n,files={p.name:digest(p) for p in (raw_path,lp_path,command_path)},
        current_answers_read_by_forecast=False))
    # Recorded-family conditional diagnostics/loss are first consulted below.
    target=d['targets'];row=np.arange(n);y=target['y']
    p={k:np.array(v) for k,v in d['baseline'].items()}
    p.update(prediction=prediction,proposed_coordinate=coordinate,priority=np.array(d['priority_mode']),
        coordinate=np.array(d['family_coordinate'][row,y]),type_nll=-np.asarray(lp)[row,y],param_nll=np.array(target['param_nll']))
    p['nll']=p['type_nll']+p['param_nll']
    path=directory/(tag+'-predictions.npz');np.savez_compressed(path,**p)
    typed=(prediction==y)&(target['py']>=0)
    if not np.array_equal(p['coordinate'][typed],coordinate[typed]):raise RuntimeError('Conditional/chosen argument parity failed')
    if np.abs(np.exp(lp).sum(1)-1).max()>1e-12:raise RuntimeError('Corrected family normalization failed')
    return p


def quick(d,p,mask=None):
    if mask is None:mask=np.ones(len(p['prediction']),bool)
    raw=d['targets'];_,joint=correctness(raw,p);m=np.bincount(raw['y'][mask]*15+p['prediction'][mask],minlength=225).reshape(15,15)
    f1=2*m.diagonal()/np.maximum(m.sum(0)+m.sum(1),1)
    return dict(rows=int(mask.sum()),strict_correct=int((joint&mask).sum()),joint_accuracy=float(joint[mask].mean()) if mask.any() else None,
        macro_F1=float(f1[1:].mean()) if mask.any() else None,joint_NLL=float(p['nll'][mask].mean()) if mask.any() else None,
        priority_joint=int((joint&mask&(raw['y']==9)).sum()),priority_type_FP=int((mask&(p['prediction']==9)&(raw['y']!=9)).sum()))


def evaluate(arm,data,cohorts,predictions,control_completion=None):
    result={};comparison={};bindings={}
    v7,more=committed_manifest(SCIENTIFIC,'tools/action_predictor/experiments/v7/data-ready.json');bindings.update(more)
    for split,d in data.items():
        path=ROOT/('.cambc/action-predictor/v5/combined-train.npz' if split=='train' else '.cambc/action-predictor/v4/validation.npz')
        # Original PRE masks/resources for final partial-legality diagnostics only.
        raw=dict(d['targets'])
        with np.load(path) as z:
            for key in ('valid','move_mask','pos_known','hp_alive','channel','flags','restrictions','ward_charges','gems','shop','ability_ready'):raw[key]=z[key]
        context=dict(raw=raw)
        for key,suffix in (('direction','direction'),('available','available'),('near','near_obstacle')):
            path=ROOT/f'.cambc/action-predictor/v7/{split}-{suffix}.npy';expected=v7['files'][path.name]
            if digest(path)!=expected:raise RuntimeError('Original diagnostic array changed')
            bindings[str(path.relative_to(ROOT))]=expected;context[key]=np.load(path)
        sampling={'all':np.ones(len(raw['y']),bool)}
        if split=='train':sampling.update(natural=cohorts['natural'],natural_fit=cohorts['fit'],natural_excluded=cohorts['held'])
        p=predictions[split];out={}
        for name,mask in sampling.items():
            overall=summary(context,p,mask)
            for code,row in enumerate(overall['per_category']):
                m=mask&(raw['y']==code);row['observed_joint_NLL']=float(p['nll'][m].mean()) if m.any() else None
            out[name]=dict(overall=overall,contexts={k:summary(context,p,mask&m) for k,m in masks(context).items() if k in ('continue','change','startup','move','blocked')})
        out['engine']={str(int(e)):quick(d,p,d['engine']==e) for e in np.unique(d['engine'])}
        out['partial_legality']=support(context,p);out['partial_readiness']=readiness_flags(raw,p)
        pc,joint=correctness(raw,p);typed=p['prediction']==raw['y'];shop=raw['y']==11
        out['failure_accounting']=dict(wrong_family=int((~typed).sum()),wrong_argument_after_correct_type=int((typed&~joint&~shop).sum()),
            typed_shop_unavailable=int((typed&shop).sum()),strict_errors=int((~joint).sum()))
        result[split]=out
        if split=='validation':
            refs={'JP02':d['baseline']}
            if arm=='AB01':
                path=LOCAL/'runs/AB00/validation-predictions.npz'
                receipt=control_completion;key=str(path.relative_to(ROOT))
                if receipt is None:raise RuntimeError('Control reference was not bound before optimization')
                if digest(path)!=receipt['bindings'][key]:raise RuntimeError('Control predictions changed')
                bindings[key]=digest(path)
                with np.load(path) as z:refs['AB00']={k:z[k] for k in z.files}
            for name,o in refs.items():
                comparison[name]=paired_categories(raw,p,o,sampling['all']);comparison[name]['movement_contexts']=paired(context,p,o)
    return result,comparison,bindings
