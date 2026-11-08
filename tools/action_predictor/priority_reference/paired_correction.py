"""Saved-output RC01 comparisons, retained P03 and certified error strata."""
import json
import numpy as np
from ..audit import immutable_json
from ..data import digest
from ..order_information.anchored import committed_manifest
from ..priority_broad.guard import committed_sources
from ..priority_regularized.safety import dependency_files,reject_optimized_python
from ..relational_priority.data import original_inputs
from ..relational_priority.protocol import fold
from .evaluate import ROOT,OUT,paired

LOCAL=ROOT/'.cambc/action-predictor/v25/CC00'


def run():
    reject_optimized_python()
    commit,sources=committed_sources(ROOT,dependency_files(ROOT,('tools.action_predictor.priority_reference.paired_correction',)))
    if LOCAL.exists():raise FileExistsError('Preserve paired assessment')
    broad,_,warm,bindings=original_inputs();models={'warm_P05':warm};receipts={}
    for name,relative in (('RC00','tools/action_predictor/experiments/v24/RC00.json'),
                          ('RC01','tools/action_predictor/experiments/v24/RC01.json'),
                          ('P03','tools/action_predictor/experiments/v25/PR00.json'),
                          ('bound','tools/action_predictor/experiments/v24/RC-bound.json')):
        receipt,more=committed_manifest(commit,relative);receipts[name]=receipt;bindings.update(more)
    for name in ('RC00','RC01','P03'):
        path=ROOT/(f'.cambc/action-predictor/v24/runs/{name}/actual-step-2000-predictions.npz'
                   if name!='P03' else '.cambc/action-predictor/v25/PR00/predictions.npz')
        key=str(path.relative_to(ROOT))
        if digest(path)!=receipts[name]['bindings'][key]:raise RuntimeError('Saved comparator changed: '+name)
        bindings[key]=digest(path)
        with np.load(path) as z:models[name]={k:z[k] for k in z.files}
    witness=ROOT/'.cambc/action-predictor/v24/bounds/witnesses.npz';key=str(witness.relative_to(ROOT))
    if digest(witness)!=receipts['bound']['bindings'][key]:raise RuntimeError('Saved bound changed')
    bindings[key]=digest(witness)
    with np.load(witness) as z:proof={k:z[k] for k in z.files}
    target=broad['target'].numpy();group=broad['group'].numpy();index=broad['index'].numpy()
    if not np.array_equal(proof['index'],index) or not np.array_equal(models['P03']['index'],index):
        raise RuntimeError('Saved row identity changed')
    if receipts['RC00']['core_sha256']!=receipts['RC01']['core_sha256'] or receipts['RC00']['protocol_sha256']!=receipts['RC01']['protocol_sha256']:
        raise RuntimeError('Matched frozen core/protocol changed')
    fit,held=fold(group);features=proof['target_features'];own=features[:,:24].any(-1);other=features[:,24:].any(-1)
    strata=dict(all=np.ones(len(target),bool),zero_target_features=~features.any(-1),
        nonzero_target_features=features.any(-1),certified_unreachable=proof['reason']>0,
        no_certificate_found=proof['reason']==0,own_only_target_relation=own&~other,
        other_only_target_relation=other&~own,both_target_relations=own&other,
        neither_target_relation=~own&~other)
    immutable_json(OUT/'CC00-plan.json',dict(source_commit=commit,sources=sources,inputs=bindings,
        scope='Post-fit saved-output diagnostic; conditional family supplied. Adds retained P03 comparator and all predeclared target-relation strata without selecting any predictor.',
        comparisons='RC01 against warm P05, RC00 and P03, on identical full/fit/held natural broad rows; all rows retained',
        interpretation='Target-relative strata are evaluation only, never inference routing. No certificate does not prove reachability. P03 original DEV advantage does not make it best on this TRAIN cohort.',
        gate='Original RC allocation unchanged; no new threshold, checkpoint or training selection.',
        new_fits=0,optimizer_updates=0,reserved_opened=0))
    LOCAL.mkdir(parents=True)
    # Preserve the entire compared evidence table before summaries or bound checks.
    np.savez_compressed(LOCAL/'rows.npz',index=index,target=target,group=group,fit_mask=fit,reason=proof['reason'],
        target_features=features,model_names=np.array(list(models)),
        integers=np.stack([p['integer'] for p in models.values()]),nll=np.stack([p['nll'] for p in models.values()]))
    for name in ('RC00','RC01'):
        if ((models[name]['integer']==target)&(proof['reason']>0)).any():raise RuntimeError('Certificate contradicted by '+name)
    results={}
    for population,population_mask in (('fit',fit),('held',~fit),('all',np.ones(len(fit),bool))):
        table={}
        for name,condition in strata.items():
            mask=population_mask&condition;n=int(mask.sum())
            table[name]=dict(rows=n,groups=int(len(np.unique(group[mask]))),
                models={label:dict(exact=int(((p['integer']==target)&mask).sum()),errors=int(((p['integer']!=target)&mask).sum()),
                    mean_NLL=float(p['nll'][mask].mean()) if n else None) for label,p in models.items()},
                RC01_versus={label:paired(models['RC01'],p,target,group,mask) if n else None for label,p in models.items() if label!='RC01'})
        results[population]=table
    bindings[str((LOCAL/'rows.npz').relative_to(ROOT))]=digest(LOCAL/'rows.npz')
    bindings[str((OUT/'CC00-plan.json').relative_to(ROOT))]=digest(OUT/'CC00-plan.json');bindings.update(sources)
    immutable_json(OUT/'CC00.json',dict(results=results,bindings=bindings,source_commit=commit,
        uncertainty='2000 paired whole-group draws seed20261106, exploratory previously exposed TRAIN groups. Not untouched full-policy or selection-adjusted evidence.',
        conditional_priority_only=True,policy_promoted=False,new_fits=0,optimizer_updates=0,reserved_opened=0,
        command='python -m tools.action_predictor.priority_reference.paired_correction'))
    print('Held',results['held']['all']['models'],
          'RC01 certified errors',results['held']['certified_unreachable']['models']['RC01']['errors'],
          'RC01 unresolved errors',results['held']['no_certificate_found']['models']['RC01']['errors'],flush=True)


if __name__=='__main__':run()
