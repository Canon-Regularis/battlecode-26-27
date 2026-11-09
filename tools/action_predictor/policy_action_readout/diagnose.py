"""Fixed-checkpoint actual-fitting-input diagnostic and concise fit report."""
import json
import sys
import numpy as np
import torch
from ..audit import immutable_json
from ..data import digest
from ..order_information.anchored import committed_manifest
from ..priority_broad.guard import committed_sources
from ..priority_regularized.safety import dependency_files
from .protocol import ROOT,OUT,LOCAL
from .data import load
from .model import ActionBeliefCorrection
from .assessment import infer,quick


def run(arm):
    commit,sources=committed_sources(ROOT,dependency_files(ROOT,('tools.action_predictor.policy_action_readout.diagnose',)))
    report,bindings=committed_manifest(commit,'tools/action_predictor/experiments/v28/'+arm+'.json')
    _,more=committed_manifest(commit,'tools/action_predictor/experiments/v28/'+arm+'-completion.json');bindings.update(more)
    checkpoint=LOCAL/'runs'/arm/'model.pt'
    if digest(checkpoint)!=report['checkpoint_sha256']:raise RuntimeError('Selected readout changed')
    data,cohorts,plan,ready=load();saved=torch.load(checkpoint,map_location='cpu',weights_only=True)
    model=ActionBeliefCorrection(int(cohorts['active'].sum()));model.load_state_dict(saved['state']);model.eval().requires_grad_(False)
    torch.set_num_threads(4);directory=LOCAL/'diagnostics'/arm
    if directory.exists():raise FileExistsError('Preserve prior diagnostic')
    directory.mkdir(parents=True);d=dict(data['train'])
    if arm=='AB00':
        x=np.array(d['features']);ix=np.flatnonzero(cohorts['fit']);x[ix]=d['features'][cohorts['donor'][ix]];d['features']=x
    actual=infer(model,d,cohorts['active'],directory,'selected-fitting-input')
    summary=quick(d,actual,cohorts['fit'])
    baseline=quick(data['train'],data['train']['baseline'],cohorts['fit'])
    primary=report['results']['train']['natural_fit']['overall']
    diagnostic=dict(actual_fitting_input=summary,baseline_same_rows=baseline,
        primary_real_input=dict(strict_correct=primary['strict_correct'],joint_NLL=primary['joint_nll'],rows=primary['rows']),
        interpretation='AB00actualfittinginputsarethefixedshuffledtrainingblock,notcausaldeploymentforecasts. Primaryassessmentusesrealinputs. AB01realfitinputscoincidewithprimary. No newweights,lossselectionorcheckpointselection.',
        checkpoint_sha256=digest(checkpoint),source_commit=commit,new_fits=0,reserved_opened=0)
    for path in directory.iterdir():bindings[str(path.relative_to(ROOT))]=digest(path)
    bindings.update(sources);bindings.update(ready['files'])
    immutable_json(OUT/(arm+'-fitting-diagnosis.json'),dict(diagnostic,bindings=bindings,
        command='python -m tools.action_predictor.policy_action_readout.diagnose '+arm))
    dev=report['results']['validation']['all']['overall'];comparison=report['comparisons']['JP02']['overall'];ci=comparison['paired95']
    lines=[f'# {arm}: marginal action-belief input experiment','',
        f"Selected round **{report['selected_round']} of {len(report['trace'])}**, using the original full-DEV observed-NLL rule. Selected/completed updates: {report['selected_updates']:,}/{report['completed_updates']:,}. Trainable correction: {report['trainable_parameters']} weights. Argument distributions and upstream filtering remain frozen.",'',
        f"DEV complete commands: **{dev['strict_correct']:,}/14,439**; macro F1 **{dev['macro_f1']:.6f}**; observed joint NLL **{dev['joint_nll']:.6f}**. Against JP02: **{comparison['rescues']} rescues / {comparison['regressions']} regressions**. Paired accuracy interval: `{ci['joint_accuracy']}`. Paired NLL interval: `{ci['joint_nll']}`.",'',
        'These are exploratory results on five reused DEV groups, not untouched or three-seed certification. The control retains group/context and availability structure and sometimes identical features. Any benefit cannot be attributed to correctly associated scheduling information before the matched real-input contrast.','',
        '| Recorded family | Support | Complete correct | Type FP |', '| --- | ---: | ---: | ---: |']
    for row in dev['per_category']:
        if row['action']=='<unknown>':continue
        lines.append(f"| {row['action']} | {row['support']} | {row['joint_correct']} | {row['type_FP']} |")
    lines += ['',f"Actual selected-checkpoint fitting-input scores: {summary['strict_correct']:,}/{summary['rows']:,} complete, NLL {summary['joint_NLL']:.6f}. On the same correction-fit rows with real inputs, the primary scores are {primary['strict_correct']:,} complete and NLL {primary['joint_nll']:.6f}. These input conditions must not be confused when interpreting control trainability.",'',
        'The JSON report preserves all original TRAIN rows, natural fit/excluded groups, category losses, type and joint errors, conditional and correctly typed parameters, movement continuation/change/blocked, engine context, partial legality and paired targeting evidence. Held TRAIN groups were excluded only from this correction optimization; warm components and earlier research already saw them. Natural membership retains the frozen augmented-cadence upstream state.','',
        'All 43 DEV shops remain strict failures with absent purchase-argument likelihood. Sparse categories, entity identity, full legality and global calibration remain uncertified. Frozen argument modes impose category ceilings; this action-only experiment cannot achieve the original movement or 90%-per-category targets. The original macro, likelihood, targeting and three-seed requirements remain binding.','',
        'No promotion or repeat seeds are justified from the control alone. The registered next arm requires a completed fresh Sol xhigh review and addressed correctness findings. Both reserved partitions remain sealed. No match, replay download, engine query, bot/runtime or deployment work was performed.','',
        f"Fit source: `{report['source_commit']}`. Selected checkpoint SHA256: `{report['checkpoint_sha256']}`. The measured {report['measured_fit_and_final_assessment_seconds']:.3f}s interval includes optimization, round DEV inference, serialization and final assessment after preflight; it is not pure optimization or end-to-end cost.",'',
        f'Reproduce diagnosis: `python -m tools.action_predictor.policy_action_readout.diagnose {arm}`; consume existing immutable archives rather than overwriting them.','']
    path=OUT/(arm+'-REPORT.md')
    if path.exists():raise FileExistsError('Preserve existing report')
    path.write_text('\n'.join(lines),encoding='utf-8');bindings[str(path.relative_to(ROOT))]=digest(path)
    path=OUT/(arm+'-fitting-diagnosis.json');bindings[str(path.relative_to(ROOT))]=digest(path)
    immutable_json(OUT/(arm+'-completion-supplement.json'),dict(bindings=bindings,source_commit=commit,
        original_completion_sha256=digest(OUT/(arm+'-completion.json')),checkpoint_sha256=report['checkpoint_sha256'],
        commands=['python -m tools.action_predictor.policy_action_readout.diagnose '+arm],new_fits=0,reserved_opened=0))
    print(arm,'selected fitting-input diagnostic',diagnostic,flush=True)


if __name__=='__main__':run(sys.argv[1])
