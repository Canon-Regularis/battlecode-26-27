"""Describe learned state retention, without assigning Fish intent labels."""
import json
import sys
import numpy as np
from .sequence_data import BASE, WORK, REPORT
from ..audit import immutable_json
from ..data import digest
from ..movement_experts.evaluate import summary


def plan():
    immutable_json(REPORT/'memory-diagnostic-plan.json',dict(
        purpose='Determine whether the selected persistent model actually retains goal state; no extra fitting or semantic objective labels.',
        quantities='Effective gap retention, inferred per-root continuation weight and exact recurrence soft_age_i=r_i*(soft_age_previous+actual_root_gap). L00age zero by construction. Predictive-prior argmax changes are not Fish objective switches.',
        diagnostic_strata='Soft expected age0,positive<=16,16..64,>64actualownroots, using original history/target horizon scales for reporting only. No strategy thresholds or checkpoint selection.',
        interpretation='World-coordinate stability and state ages establish implementation behavior, not information usefulness or strategic intent. Per-context performance associations are descriptive; latent state indices are not identified across fits.',
        source_sha256=digest(__file__),new_fits=0,reserved_opened=0))


def run(identifier):
    plan();results={};bindings={}
    for split in ('train','validation'):
        gp=WORK/f'runs/{identifier}/{split}-goals.npz';fp=WORK/f'runs/{identifier}/{split}-predictions.npz'
        with np.load(gp) as z:retention=z['retention'];prior=z['prior'];world=z['world']
        with np.load(fp) as z:p={k:z[k] for k in z.files}
        sp=WORK/f'{split}-sequences.npz'
        with np.load(sp) as z:order=z['order'];offsets=z['offsets'];gap=z['gap']
        with np.load(WORK/f'{split}-goals.npz') as z:position=z['position'];known=z['position_known']
        n=len(prior);age=np.zeros(n,np.float64);roots=np.rint(np.expm1(gap[:,0].astype(np.float64)*8)).astype(np.int64)
        per_root=np.full(n,np.nan,np.float64);changed=[];world_delta=[];actor_delta=[]
        for a,b in zip(offsets[:-1],offsets[1:]):
            previous=None;oldage=0.
            for j in range(a,b):
                row=order[j];r=float(retention[row]);age[row]=r*(oldage+roots[j]);oldage=age[row]
                if previous is not None:
                    per_root[row]=r**(1/float(roots[j]))
                    changed.append(int(prior[row].argmax()!=prior[previous].argmax()))
                    if known[row] and known[previous]:
                        world_delta.append(float(np.abs(world[row]-world[previous]).max(-1).mean()*32))
                        actor_delta.append(float(np.abs(position[row]-position[previous]).max()*32))
                previous=row
        dataset=BASE/'combined-train.npz' if split=='train' else BASE.parent/'v4/validation.npz'
        with np.load(dataset) as z:raw={k:z[k] for k in ('y','py','priority','group')}
        direction=np.load(BASE.parent/f'v7/{split}-direction.npy');q=dict(raw=raw,direction=direction)
        def quantiles(x):
            x=np.asarray(x);x=x[np.isfinite(x)]
            return np.quantile(x,[0,.25,.5,.75,.95,1]).tolist() if len(x) else None
        masks=dict(zero=age==0,positive_through16=(age>0)&(age<=16),over16_through64=(age>16)&(age<=64),over64=age>64)
        results[split]=dict(rows=n,expected_age_root_quantiles=quantiles(age),per_root_continuation_weight_quantiles=quantiles(per_root),
            predictive_prior_argmax_change_rate=float(np.mean(changed)) if changed else None,
            mean_component_world_shift_tiles=float(np.mean(world_delta)) if world_delta else None,
            mean_actor_shift_on_same_known_origin_pairs=float(np.mean(actor_delta)) if actor_delta else None,
            age_strata={name:summary(q,p,m) for name,m in masks.items()})
        bindings.update({str(path):digest(path) for path in (gp,fp,sp)})
    immutable_json(REPORT/f'{identifier}-memory-diagnostic.json',dict(results=results,bindings=bindings,
        plan_sha256=digest(REPORT/'memory-diagnostic-plan.json'),source_sha256=digest(__file__),
        caveat='One shared retention scalar implies equal soft ages across four goal components. No ground-truth goal lifetime or entity identity is supplied. TRAIN traversal augmented; no inference-time interventions or future-state smoothing in this descriptive calculation.',
        new_fits=0,reserved_opened=0))


if __name__=='__main__':
    if sys.argv[1:]==['plan']:plan()
    else:run(sys.argv[1])
