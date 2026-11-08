"""Post-fit, fixed-weight block dependence and certified-error partition."""
import json
import traceback
import numpy as np
import torch

from ..audit import immutable_json
from ..data import digest
from ..order_information.anchored import committed_manifest
from ..priority_capacity.data import head
from ..priority_broad.guard import committed_sources
from ..priority_regularized.safety import dependency_files,reject_optimized_python
from ..relational_priority.data import load
from ..relational_priority.model import SignedPointCorrection
from ..relational_priority.fit import raw_forecast,predictions
from .evaluate import ROOT,OUT,ANCHOR,paired

LOCAL=ROOT/'.cambc/action-predictor/v25/CD00'


def run():
    reject_optimized_python()
    commit,sources=committed_sources(ROOT,dependency_files(ROOT,('tools.action_predictor.priority_reference.correction_diagnosis',)))
    if LOCAL.exists():raise FileExistsError('Preserve completed or attempted dependence study')
    bank=load();bindings=dict(bank.bindings)
    info,more=committed_manifest(ANCHOR,'tools/action_predictor/experiments/v24/RC00.json');bindings.update(more)
    bound,more=committed_manifest(ANCHOR,'tools/action_predictor/experiments/v24/RC-bound.json');bindings.update(more)
    checkpoint=ROOT/'.cambc/action-predictor/v24/runs/RC00/step-2000.pt'
    raw_path=ROOT/'.cambc/action-predictor/v24/runs/RC00/actual-step-2000-raw.npy'
    pred_path=raw_path.with_name('actual-step-2000-predictions.npz')
    witnesses=ROOT/'.cambc/action-predictor/v24/bounds/witnesses.npz'
    for path,receipt in ((checkpoint,info),(raw_path,info),(pred_path,info),(witnesses,bound)):
        key=str(path.relative_to(ROOT))
        if digest(path)!=receipt['bindings'][key]:raise RuntimeError('Anchored diagnostic input changed: '+key)
        bindings[key]=digest(path)
    with np.load(witnesses) as z:proof={k:z[k] for k in z.files}
    if not np.array_equal(proof['index'],bank.broad['index'].numpy()):raise RuntimeError('Bound row order changed')
    immutable_json(OUT/'CD00-plan.json',dict(source_commit=commit,sources=sources,inputs=bindings,
        purpose='Partition remaining RC00 errors using existing sufficient witnesses and measure fixed-weight dependence',
        variants=['zero_all_weights','retain_own_only','retain_other_only','full_RC00'],
        intervention='Zero specified coordinates of the saved weight vector without retraining; all inputs real PRE',
        scope='Post-fit exploratory dependence, not randomized or retrained feature benefit. No replacement selected.',
        metrics='Conditional exact integers and NLL; paired groups against warm P05. Separate sufficient-unreachable and not-ruled-out rows.',
        guards='Raw outputs saved before measurement; full variant must exactly reproduce RC00 and zero variant warm P05; no witness row may be correct',
        new_fits=0,optimizer_updates=0,reserved_opened=0))
    LOCAL.mkdir(parents=True)
    try:
        torch.set_num_threads(4)
        base,_,_=head();model=SignedPointCorrection(base,bank.metadata['active'])
        saved=torch.load(checkpoint,map_location='cpu',weights_only=True)
        model.load_state_dict(saved['state']);model.eval().requires_grad_(False)
        original=model.weights.detach().clone()
        own=torch.from_numpy(np.flatnonzero(bank.metadata['active'])<24)
        keep={'zero_all_weights':torch.zeros_like(own),'retain_own_only':own,
              'retain_other_only':~own,'full_RC00':torch.ones_like(own)}
        ids=np.arange(len(bank.fit_mask));target=bank.broad['target'].numpy();group=bank.broad['group'].numpy()
        blocked=proof['reason']>0
        strata={'all':np.ones(len(ids),bool),'sufficient_unreachable':blocked,'not_ruled_out':~blocked,
                'zero_target_features':proof['feature_count']==0,'nonzero_target_features':proof['feature_count']>0}
        results={}
        for name,mask in keep.items():
            with torch.no_grad():model.weights.copy_(original*mask)
            raw=raw_forecast(model,bank,ids)
            np.save(LOCAL/(name+'-raw.npy'),raw)
            p=predictions(model,bank,np.load(LOCAL/(name+'-raw.npy'),mmap_mode='r'),ids)
            np.savez_compressed(LOCAL/(name+'-predictions.npz'),**p)
            results[name]={}
            # No answer is used in the forward; labels first enter measurement.
            for population,population_mask in dict(fit=bank.fit_mask,held=~bank.fit_mask).items():
                table={}
                for stratum,condition in strata.items():
                    selected=population_mask&condition;n=int(selected.sum())
                    table[stratum]=dict(rows=n,correct=int(((p['integer']==target)&selected).sum()),
                        errors=int(((p['integer']!=target)&selected).sum()),
                        mean_NLL=float(p['nll'][selected].mean()) if n else None,
                        paired_vs_warm=paired(p,bank.baseline,target,group,selected) if n else None)
                results[name][population]=table
            if ((p['integer']==target)&blocked).any():raise RuntimeError('Witness contradicted by intervention')
            if name=='full_RC00':
                if not np.array_equal(raw,np.load(raw_path)):raise RuntimeError('Full raw RC00 reproduction failed')
                with np.load(pred_path) as old:
                    if any(not np.array_equal(p[key],old[key]) for key in old.files):raise RuntimeError('Full saved-prediction reproduction failed')
            if name=='zero_all_weights':
                if not np.array_equal(raw,bank.raw):raise RuntimeError('Zero raw differs from warm core')
                for key in bank.baseline:
                    if not np.array_equal(p[key],bank.baseline[key]):raise RuntimeError('Zero output differs from warm prediction: '+key)
        for path in LOCAL.iterdir():bindings[str(path.relative_to(ROOT))]=digest(path)
        bindings.update(sources);bindings[str((OUT/'CD00-plan.json').relative_to(ROOT))]=digest(OUT/'CD00-plan.json')
        immutable_json(OUT/'CD00.json',dict(results=results,bindings=bindings,source_commit=commit,
            interpretation='Not-ruled-out is not proven reachable. Fixed-weight block removal measures dependence; it cannot predict retrained information benefit or identify Fish intent.',
            new_fits=0,optimizer_updates=0,reserved_opened=0,policy_replaced=False,
            command='python -m tools.action_predictor.priority_reference.correction_diagnosis'))
        print(json.dumps({name:{pop:table['all'] for pop,table in v.items()} for name,v in results.items()},indent=2),flush=True)
    except BaseException:
        (LOCAL/'failure.txt').write_text(traceback.format_exc(),encoding='utf-8')
        raise


if __name__=='__main__':run()
