"""Conservative per-row MAP limits with frozen core and tied point features."""
import json
import numpy as np
import torch

from ..audit import immutable_json
from ..data import digest
from ..priority_capacity.data import head
from ..priority_modes import logistic_log_mass
from ..priority_broad.guard import committed_sources
from ..priority_regularized.safety import dependency_files,reject_optimized_python
from .data import load
from .protocol import ROOT,LOCAL,OUT

MARGIN=1e-9


def find_witness(values,features,logpoint,logfallback,target_index,margin=MARGIN):
    """Return one sufficient witness; absence never proves reachability."""
    same=(features==features[target_index]).all(-1)
    same[target_index]=False
    if not features[target_index].any():
        score=np.logaddexp(logpoint,logfallback)
        blocked=same&(score>score[target_index]+margin)
        reason=1
    else:
        # Strict positive margins on BOTH coefficients avoid underflow/tie claims.
        blocked=same&(logpoint>logpoint[target_index]+margin)&(logfallback>logfallback[target_index]+margin)
        score=np.minimum(logpoint-logpoint[target_index],logfallback-logfallback[target_index])
        reason=2
    if not blocked.any():return -1,0
    return int(np.where(blocked,score,-np.inf).argmax()),reason


def run():
    reject_optimized_python()
    commit,sources=committed_sources(ROOT,dependency_files(ROOT,(
        'tools.action_predictor.relational_priority.bounds',
        'tools.action_predictor.relational_priority.test_bounds')))
    bank=load();n=len(bank.broad['index'])
    plan=dict(source_commit=commit,sources=sources,inputs=bank.bindings,
        purpose='Separate full point support from frozen-core shared-feature decision limits. '
                'No training or checkpoint selection; all5876real-input rows retained.',
        proof='For candidatev, new unnormalized mass is A_v*exp(w dot f_v)+B_v. '
              'A_v sums original available point coefficients at that integer; B_v is original '
              'fallback coefficient times logistic-bin mass. Denominator is common within row. '
              'Same-feature candidates share the multiplier. If BOTH logcoefficients of a '
              'competitor exceed the target by>1e-9, target cannot beat it for ANYw. '
              'If target features are allzero, both same-zero masses are fixed; any strictly '
              'larger original mass with margin>1e-9 is a sufficient witness.',
        scope='Frozen P05 raw distributions, point identities, actual causal feature values and '
              'current/past context. Available duplicates must have identical features and their '
              'masses are marginalized. Include old floor/ceil logistic modes as possible zero-point '
              'witnesses. No witness means unresolved, not proven reachable. Shared weights across '
              'rows and regularization may tighten the upper bound further.',
        checks='Archive all witness/coefficient/feature arrays before summary assertions. Save '
               'row-level failure inputs before raising any row-contract error. No blocked row '
               'may be correct under warm P05. Sample32Normal(0,3)weight vectors pluszero with '
               'seed20261127 to check preserved pair inequalities; these are arithmetic checks, '
               'not fitted models, optimization or policy accuracies.',
        interpretation='This configuration-specific conservative upper bound is not an architecture '
                       'or observation ceiling, candidate-coverage score, Fish intent, or achieved '
                       'accuracy. Retraining core, changing feature/state inputs or vocabulary changes it.',
        new_fits=0,optimizer_updates=0,new_engine_queries=0,reserved_opened=0)
    immutable_json(OUT/'RC-bound-plan.json',plan)
    base,_,_=head();base.eval().requires_grad_(False);torch.set_num_threads(1)
    target=bank.broad['target'].numpy();active=bank.metadata['active']
    reason=np.zeros(n,np.uint8);witness=np.zeros(n,np.int64);feature_count=np.zeros(n,np.int16)
    coefficients=np.full((n,4),-np.inf,np.float64)
    target_features=np.zeros((n,int(active.sum())),bool)
    directory=LOCAL/'bounds'
    if directory.exists():raise FileExistsError('Preserve attempted bound diagnostic')
    directory.mkdir(parents=True)
    for i in range(n):
        raw=torch.from_numpy(np.array(bank.raw[i:i+1],copy=True))
        with torch.no_grad():points,mix=base.components(raw,bank.broad['values'][i:i+1])
        point=points.numpy()[0];mix=mix.numpy()[0];available=np.isfinite(mix[:-1])
        f=bank.evaluation_features(np.array([i])).numpy()[0][:,active]
        unique,first,inverse=np.unique(point[available],return_index=True,return_inverse=True)
        point_features=f[available][first]
        if not np.array_equal(f[available],point_features[inverse]):
            np.savez_compressed(directory/f'row-failure-{i}.npz',row=i,raw=raw.numpy(),points=point,
                mix=mix,features=f,available=available,unique=unique,inverse=inverse,
                partial_reason=reason,partial_coefficients=coefficients)
            raise RuntimeError('Available duplicate point explanations have different features')
        old_center=float(raw[0,-2])*100
        candidates=np.unique(np.r_[unique,np.int64(np.floor(old_center)),np.int64(np.ceil(old_center))])
        logpoint=np.full(len(candidates),-np.inf)
        np.logaddexp.at(logpoint,np.searchsorted(candidates,point[available]),mix[:-1][available])
        features=np.zeros((len(candidates),len(active.nonzero()[0])),bool)
        features[np.searchsorted(candidates,unique)]=point_features
        with torch.no_grad():
            logfallback=mix[-1]+logistic_log_mass(raw[:,-2:],torch.from_numpy(candidates[None])).numpy()[0]
        at=int(np.searchsorted(candidates,target[i]))
        if at==len(candidates) or candidates[at]!=target[i] or not np.isfinite(logpoint[at]):
            np.savez_compressed(directory/f'row-failure-{i}.npz',row=i,raw=raw.numpy(),target=target[i],
                candidates=candidates,logpoint=logpoint,logfallback=logfallback,features=features,
                partial_reason=reason,partial_coefficients=coefficients)
            raise RuntimeError('Expected full fitting point support missing')
        target_features[i]=features[at];feature_count[i]=int(features[at].sum())
        chosen,kind=find_witness(candidates,features,logpoint,logfallback,at)
        if chosen>=0:
            reason[i]=kind;witness[i]=candidates[chosen]
            coefficients[i]=[logpoint[at],logfallback[at],logpoint[chosen],logfallback[chosen]]
        if (i+1)%2048==0 or i+1==n:print('RC bound rows',i+1,'/',n,flush=True)
    path=directory/'witnesses.npz'
    np.savez_compressed(path,index=bank.broad['index'].numpy(),reason=reason,witness=witness,
        feature_count=feature_count,target_features=target_features,coefficients=coefficients)
    blocked=reason>0
    if (bank.baseline['integer'][blocked]==target[blocked]).any():
        raise RuntimeError('Conservative witness contradicts warm exact forecast')
    weights=np.r_[np.zeros((1,int(active.sum()))),np.random.default_rng(20261127).normal(0,3,(32,int(active.sum())))]
    shift=weights@target_features[blocked].T
    a,b,c,d=coefficients[blocked].T
    difference=np.logaddexp(c[None]+shift,d[None])-np.logaddexp(a[None]+shift,b[None])
    if not (difference>0).all():raise RuntimeError('Sampled inequality contradicted witness')
    results={}
    for name,mask in (('fit',bank.fit_mask),('held',~bank.fit_mask),('all',np.ones(n,bool))):
        rows=int(mask.sum());count=int((blocked&mask).sum())
        results[name]=dict(rows=rows,point_supported=rows,zero_target_feature_rows=int(((feature_count==0)&mask).sum()),
            zero_feature_fixed_order_witnesses=int(((reason==1)&mask).sum()),
            same_feature_coefficient_witnesses=int(((reason==2)&mask).sum()),
            any_weight_unreachable_at_least=count,conditional_MAP_upper_bound=rows-count,
            upper_bound_fraction=(rows-count)/rows,warm_correct=int(((bank.baseline['integer']==target)&mask).sum()))
    bindings=dict(bank.bindings);bindings[str(path.relative_to(ROOT))]=digest(path)
    immutable_json(OUT/'RC-bound.json',dict(results=results,bindings=bindings,sources=sources,source_commit=commit,
        plan_sha256=digest(OUT/'RC-bound-plan.json'),sampled_weight_vectors=33,
        minimum_sampled_log_mass_margin=float(difference.min()) if blocked.any() else None,
        configuration_scope=plan['interpretation'],new_fits=0,optimizer_updates=0,reserved_opened=0))
    print('Conservative RC limits',results,flush=True)


if __name__=='__main__':run()
