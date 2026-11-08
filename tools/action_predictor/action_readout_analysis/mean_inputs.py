"""Preserve mean correction while removing input variation, with no fitting."""
import json
import numpy as np
import torch
from pathlib import Path
from ..audit import immutable_json
from ..data import digest
from ..order_information.anchored import committed_manifest
from ..priority_broad.guard import committed_sources
from ..priority_regularized.safety import dependency_files,reject_optimized_python
from ..policy_action_readout.data import load
from ..policy_action_readout.model import ActionBeliefCorrection
from ..policy_action_readout.assessment import infer,quick
from ..policy_action_readout.protocol import ROOT,LOCAL as OLD
from ..learned_policy.analysis import paired_categories

OUT=ROOT/'tools/action_predictor/experiments/v29'
LOCAL=ROOT/'.cambc/action-predictor/v29'
ANCHOR='4241a829d5283f852822abaf8eea29801942c8e5'


def run(arm):
    reject_optimized_python()
    commit,sources=committed_sources(ROOT,dependency_files(ROOT,('tools.action_predictor.action_readout_analysis.mean_inputs',)))
    report,bindings=committed_manifest(ANCHOR,'tools/action_predictor/experiments/v28/'+arm+'.json')
    completion,more=committed_manifest(ANCHOR,'tools/action_predictor/experiments/v28/'+arm+'-completion.json');bindings.update(more)
    checkpoint=OLD/'runs'/arm/'model.pt'
    if digest(checkpoint)!=completion['checkpoint_sha256']:raise RuntimeError('Selected checkpoint changed')
    data,cohorts,_,ready=load();active=cohorts['active'];x=data['train']['features']
    mean=np.asarray(x[cohorts['fit']]).mean(0)
    # A permutation of the fit population has the same mathematical mean.
    # Own fields, flags and baseline filtering are not recomputed or fitted.
    immutable_json(OUT/(arm+'-mean-input-plan.json'),dict(source_commit=commit,sources=sources,
        checkpoint_sha256=digest(checkpoint),original_fit_report_sha256=digest(ROOT/'tools/action_predictor/experiments/v28'/f'{arm}.json'),
        reference='Mean of each complete causal input feature on243522originalcorrection-fitnaturalTRAINrows only; no label/DEVfit. Preserve Wmean, not zero pathway/bias.',
        comparison='Frozen dynamicrealinputs vs constantTRAIN-fitmean in the alreadyselected readout. Every conditional argument distribution,upstreamstate,weight,decoderandrowfixed. No replacementvariant,thresholdorcheckpointselected.',
        interpretation='Fixed-weight dependence on variation, not causal informationvalue or a retrainedfeatureablation. Fractional availability/indicator means and unusual context combinations can be out of support. No strategicintent claim.',
        metrics='Completecommands,meanobservedNLL,macroF1,percategorypairedrescues/regressionsandtargeting. FulloriginalTRAIN/DEVdenominators andwholeDEVgroups; naturalfit/excludedTRAINdiagnostics. Report all outputs even adverse. No trainingcontinuationcriterion changed.',
        current_review_scope='Later independent diagnostic outside already-runningAB00review; do not claim that review certifies this producer.',
        new_fits=0,optimizer_updates=0,reserved_opened=0))
    directory=LOCAL/(arm+'-mean-input')
    if directory.exists():raise FileExistsError('Preserve prior diagnostic')
    directory.mkdir(parents=True);np.save(directory/'fit-mean.npy',mean)
    saved=torch.load(checkpoint,map_location='cpu',weights_only=True);model=ActionBeliefCorrection(int(active.sum()))
    model.load_state_dict(saved['state']);model.eval().requires_grad_(False);torch.set_num_threads(4)
    result={};comparisons={}
    for split,d in data.items():
        artificial=dict(d,features=np.broadcast_to(mean,d['features'].shape))
        p=infer(model,artificial,active,directory,'mean-'+split)
        original=OLD/'runs'/arm/(split+'-predictions.npz');key=str(original.relative_to(ROOT))
        if digest(original)!=completion['bindings'][key]:raise RuntimeError('Original dynamic predictions changed')
        with np.load(original) as z:dynamic={k:z[k] for k in z.files}
        masks={'all':np.ones(len(p['prediction']),bool)}
        if split=='train':masks.update(natural=cohorts['natural'],natural_fit=cohorts['fit'],natural_excluded=cohorts['held'])
        result[split]={name:dict(mean_input=quick(d,p,mask),dynamic_real_input=quick(d,dynamic,mask)) for name,mask in masks.items()}
        if split=='validation':comparisons=paired_categories(d['targets'],p,dynamic,masks['all'])
        bindings[key]=digest(original)
    bindings.update(ready['files']);bindings.update(sources)
    for path in directory.iterdir():bindings[str(path.relative_to(ROOT))]=digest(path)
    immutable_json(OUT/(arm+'-mean-input.json'),dict(results=result,paired_mean_minus_dynamic=comparisons,bindings=bindings,
        mean_nonzero_feature_count=int(np.count_nonzero(mean[active])),checkpoint_unchanged=digest(checkpoint)==completion['checkpoint_sha256'],
        plan_sha256=digest(OUT/(arm+'-mean-input-plan.json')),new_fits=0,optimizer_updates=0,reserved_opened=0,
        command='python -m tools.action_predictor.action_readout_analysis.mean_inputs '+arm))
    print('Frozen mean-input diagnostic',result['validation'],comparisons['overall'],flush=True)


if __name__=='__main__':
    import sys
    run(sys.argv[1])
