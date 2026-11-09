"""Immutable conditional transfer evidence; no full-policy improvement claim."""
import argparse
import json
from pathlib import Path
import numpy as np

from ..audit import immutable_json
from ..data import digest
from ..order_information.anchored import committed_manifest
from .data import load
from .protocol import ROOT,LOCAL,OUT,ARMS


def read(path):
    with np.load(path) as z:return {key:z[key] for key in z.files}


def paired(after,before,target,group,mask):
    if not mask.any():return dict(rows=0,groups=0,rescues=0,regressions=0,net=0,accuracy_difference=None,
                                 mean_NLL_difference=None,paired_accuracy_interval=None,paired_NLL_interval=None)
    target=target[mask];group=group[mask]
    correct=after['integer'][mask]==target;old=before['integer'][mask]==target
    change=correct.astype(int)-old;loss=after['nll'][mask]-before['nll'][mask]
    groups=np.unique(group);support=np.array([(group==g).sum() for g in groups])
    gains=np.array([change[group==g].sum() for g in groups]);losses=np.array([loss[group==g].sum() for g in groups])
    rng=np.random.default_rng(20261106)
    draws=np.stack([np.bincount(rng.integers(len(groups),size=len(groups)),minlength=len(groups)) for _ in range(2000)])
    denominator=draws@support
    return dict(rows=len(target),groups=len(groups),rescues=int((correct&~old).sum()),
        regressions=int((~correct&old).sum()),net=int(change.sum()),accuracy_difference=float(change.mean()),
        mean_NLL_difference=float(loss.mean()),mean_bounded_rank_difference=float((after['rank'][mask]-before['rank'][mask]).mean()),
        paired_accuracy_interval=np.quantile(draws@gains/denominator,[.025,.975]).tolist(),
        paired_NLL_interval=np.quantile(draws@losses/denominator,[.025,.975]).tolist(),
        positive_groups=int((gains>0).sum()),negative_groups=int((gains<0).sum()),zero_groups=int((gains==0).sum()),
        group_net_commands=dict(zip(map(str,groups),map(int,gains))))


def calibration(p,target,mask):
    confidence=p['mode_probability'][mask];correct=p['integer'][mask]==target[mask]
    if not len(confidence):return dict(rows=0,ECE=None,mode_correctness_Brier=None,bins=[])
    if not np.isfinite(confidence).all() or confidence.min()<0 or confidence.max()>1+2e-12:
        raise RuntimeError('Invalid conditional mode probabilities')
    assignment=np.minimum((confidence*10).astype(int),9)
    bins=[];ece=0.
    for i in range(10):
        selected=assignment==i;n=int(selected.sum())
        accuracy=float(correct[selected].mean()) if n else None
        mean=float(confidence[selected].mean()) if n else None
        if n:ece+=n/len(confidence)*abs(accuracy-mean)
        bins.append(dict(lower=i/10,upper=(i+1)/10,rows=n,exact=int(correct[selected].sum()),
                         accuracy=accuracy,mean_mode_probability=mean))
    return dict(rows=len(confidence),ECE=float(ece),mode_correctness_Brier=float(((confidence-correct)**2).mean()),
        observed_probability_range=[float(confidence.min()),float(confidence.max())],bins=bins,
        meaning='Conditional top-label reliability; Brier is binary mode-correctness, not full multiclass '
                'or global policy calibration. No calibration fit/threshold selection.')


def score(p,target,mask):
    if not mask.any():return dict(rows=0,exact=0,accuracy=None,mean_NLL=None,MAE=None,mean_bounded_rank=None)
    error=np.abs(p['integer'][mask]-target[mask])
    return dict(rows=len(error),exact=int((error==0).sum()),accuracy=float((error==0).mean()),
        mean_NLL=float(p['nll'][mask].mean()),MAE=float(error.mean()),max_error=int(error.max()),
        mean_bounded_rank=float(p['rank'][mask].mean()),mean_mode_probability=float(p['mode_probability'][mask].mean()),
        marginalized_target_source_shares=p['credit'][mask].mean(0).tolist())


def run(arm):
    current_path=OUT/f'{arm}.json';info=json.loads(current_path.read_text());bank=load()
    target=bank.broad['target'].numpy();group=bank.broad['group'].numpy()
    bindings=dict(bank.bindings)
    path=LOCAL/f'runs/{arm}/actual-step-2000-predictions.npz'
    if digest(path)!=info['bindings'][str(path.relative_to(ROOT))]:raise RuntimeError('Current prediction archive changed')
    current=read(path)
    archives={'warm':bank.baseline,arm:current}
    if arm=='RC01':
        import subprocess
        commit=subprocess.run(['git','rev-parse','HEAD'],cwd=ROOT,check=True,capture_output=True,text=True).stdout.strip()
        control,more=committed_manifest(commit,'tools/action_predictor/experiments/v24/RC00.json');bindings.update(more)
        path=LOCAL/'runs/RC00/actual-step-2000-predictions.npz'
        expected=control['bindings'][str(path.relative_to(ROOT))]
        if digest(path)!=expected:raise RuntimeError('Matched control archive changed')
        archives['RC00']=read(path);bindings[str(path.relative_to(ROOT))]=expected
    if any('mode_probability' not in p for p in archives.values()):raise RuntimeError('Missing saved conditional confidence')
    seen=np.isin(target,np.unique(target[bank.fit_mask]))
    available=bank.metadata['available'].any((1,2))
    values=bank.broad['values'].numpy();history=bank.metadata['history']
    contexts=dict(all=np.ones(len(target),bool),other_available=available,other_unavailable=~available,
        correction_fit_seen_integer=seen,correction_fit_unseen_integer=~seen,
        latest_argument_outside16=(values[:,5]==1)&~history[:,:,1].any(-1),
        current_scheduled_different=(values[:,1]==1)&(values[:,3]==1)&(values[:,0]!=values[:,2]),
        engine2=bank.metadata['engine']==2,engine3=bank.metadata['engine']==3)
    populations=dict(fit=bank.fit_mask,held=~bank.fit_mask)
    result={};comparisons={};reliability={}
    for name,population in populations.items():
        result[name]={}
        for context,condition in contexts.items():
            mask=population&condition
            result[name][context]=dict(rows=int(mask.sum()),groups=len(np.unique(group[mask])),
                models={label:score(p,target,mask) for label,p in archives.items()},
                versus={label:paired(current,p,target,group,mask) for label,p in archives.items() if label!=arm})
        comparisons[name]=result[name]['all']['versus']
        reliability[name]={label:calibration(p,target,population) for label,p in archives.items()}
    allocation=None
    if arm=='RC01':
        warm=comparisons['held']['warm'];control=comparisons['held']['RC00']
        allocation=dict(held_exact_gain2pp_over_warm=warm['accuracy_difference']>=.02,
            held_exact_gain1pp_over_control=control['accuracy_difference']>=.01,
            held_NLL_lower_than_both=warm['mean_NLL_difference']<0 and control['mean_NLL_difference']<0,
            majority_held_groups_net_positive_over_warm=warm['positive_groups']>warm['groups']/2)
    producer=Path(__file__)
    bindings[str(current_path.relative_to(ROOT))]=digest(current_path)
    bindings[str(producer.relative_to(ROOT))]=digest(producer)
    immutable_json(OUT/f'{arm}-analysis.json',dict(results=result,comparisons=comparisons,
        conditional_reliability=reliability,bindings=bindings,allocation_checks=allocation,
        exploratory_allocation_gate_passed=all(allocation.values()) if allocation is not None else None,
        allocation_status='Treatment required; no control-only allocation verdict' if allocation is None else 'Registered paired point criteria; not original success or certification',
        uncertainty='2000paired whole-group draws seed20261106. New-fit group exclusion only; warm '
                    'model/vocabulary and earlier TRAIN research exposed these groups. In-sample fit '
                    'and exploratory held diagnostics, not untouched or selection-adjusted policy evidence.',
        units=dict(accuracy='Difference in conditional integer accuracy fraction',NLL='Mean integer NLL difference in nats'),
        no_action_type_or_complete_policy_assessment=True,new_fits=0,reserved_opened=0))
    report=OUT/f'{arm}-REPORT.md'
    if report.exists():raise FileExistsError(report)
    lines=[f'# {arm}: shared signed priority correction','',
        'The P05 core is frozen. Only 72 shared signed relation weights are trained on all available '
        'point components, with original duplicate marginalization and full-support logistic fallback. '
        'Own-history features are identical between arms. RC00 uses matched shuffled other-unit '
        'information during optimization; RC01 uses real information. Both use real causal inputs '
        'for every primary assessment. No alternative decoder or recorded-label router is used.','',
        '| Update | Real-input fit exact /4,208 | Real-input held exact /1,668 | Fit NLL | Held NLL | Actual optimization-input fit NLL |',
        '| --- | ---: | ---: | ---: | ---: | ---: |']
    for row in info['trace']:
        fit=row['real_input']['fit'];held=row['real_input']['held']
        lines.append(f"| {row['step']} | {fit['exact']} | {held['exact']} | {fit['mean_NLL']:.6f} | "
                     f"{held['mean_NLL']:.6f} | {row['optimization_input_fit']['mean_NLL']:.6f} |")
    lines+=['','| Population/reference | Rescues | Regressions | Net | Mean NLL difference | Paired accuracy interval |',
            '| --- | ---: | ---: | ---: | ---: | --- |']
    for name,table in comparisons.items():
        for reference,v in table.items():
            lines.append(f"| {name} / {reference} | {v['rescues']} | {v['regressions']} | {v['net']} | "
                         f"{v['mean_NLL_difference']:.6f} | {v['paired_accuracy_interval']} |")
    lines+=['',
        'The correction fits 4,208 natural-priority decisions from 40 groups; 1,668 decisions in '
        '15 groups are excluded from this optimization. The split is fixed by group seed 20261125, '
        'not label difficulty. Every one of the original 5,876 broad rows remains in the tables. '
        'The frozen encoder/head/vocabulary previously saw these eligible TRAIN games, and prior '
        'diagnostics inspected the population. This is not a fresh full-policy test. Legacy '
        '128-row controls and DEV are not evaluated in this study.','',
        'Both arms have the same 72 supported, active trainable weights and zero initialization. '
        'No new integer vocabulary or hidden layers are introduced. Both current and scheduled '
        'per-unit values remain exact int64 with availability masks; unknown values never match. '
        'Raw fallback location, scale and component logit stay fixed, while its normalized '
        'mixture weight may change with point corrections. Own/history relations and selected '
        'alternatives from OD03 are not treated as true-intent labels.','',
        'The fixed endpoint is 2,000 full-population mean-gradient updates, accumulated through '
        '256-row chunks, AdamW .003 then .001, zero decay, clip 5, inherited lambda '
        '3.029750319831723e-5 times summed squared new weights. No group, strength, threshold, '
        'relation, seed or checkpoint is selected from held outcomes. Interim assessments are '
        'descriptive; the warm baseline is a retained comparator, not an alternative selected endpoint.','',
        'With zero correction initialization, fixed full-population order and frozen inputs, '
        'this fit is deterministic for its split and corruption. Merely changing the Torch seed '
        'would not provide independent full-policy seed consistency. No robustness or three-seed '
        'claim follows from this diagnostic.','',
        'RC00 actual optimization-input fitting and real-input TRAIN performance are distinct '
        'quantities. The control corruption stays within group/engine/availability blocks and never '
        'crosses correction fit/held membership. Neither primary evaluator requests donor information '
        'at inference. Singleton or numerically unchanged corruption rows remain included.','',
        'Context tables include unavailable other-unit information, correction-fit unseen integer '
        'values, current/scheduled differences, earlier argument availability and historical engines. '
        'Unseen refers only to this correction fit, not to the warm model vocabulary. Engine and '
        'group/context differences are confounded. Empty strata remain explicit with null metrics. '
        'Conditional confidence bins and mode-correctness Brier do not establish global calibration.','',
        'This is conditional integer prediction with the recorded priority family supplied. It '
        'does not report action-type PRF, macro F1, correctly-typed conditional parameters or '
        'complete-command accuracy. Those require predicted family choices and normalized joint '
        'redecoding with new inputs on every decision. Existing predictors remain unchanged. '
        'No policy is promoted; original category/movement/macro/NLL/targeting and three-seed '
        'requirements remain unmet. Shops, sparse actions, entity identity and full legality '
        'retain their original limitations.','',
        f"Fit source `{info['source_commit']}`; trainable weights {info['trainable_parameters']}; "
        f"completed updates {info['optimizer_updates']}; presentations {info['supervised_presentations']}. "
        'Measured time includes training, assessments and serialization after preflight, not pure '
        'optimization or serving. All initial/raw forecasts and states precede their checks. '
        'The original core fingerprint and all fallback raw fields remain unchanged.','',
        'The real-versus-shuffled allocation gate is unassessed until RC01 completes.' if allocation is None else
        f"Registered exploratory allocation checks: `{allocation}`. Passing is not original success or robustness.",
        '',f"Reproduce only into absent destinations: `python -m tools.action_predictor.relational_priority.fit {arm}`, "
        f"then `python -m tools.action_predictor.relational_priority.results {arm}`. Do not rerun completed fitting. "
        'A fresh Sol xhigh post-fit challenge follows each arm before another substantive fit. '
        'No matches, downloads, new replay queries, reserved accesses, bot/runtime work or deployment.','']
    supplemental=[]
    bound_path=OUT/'RC-bound.json'
    if bound_path.exists():
        bound=json.loads(bound_path.read_text());v=bound['results']['held']
        lines+=['','Additional frozen-configuration diagnostic: all held integers have point '
            f"support, but at least {v['any_weight_unreachable_at_least']}/{v['rows']} cannot become "
            'MAP under any shared correction weights with these base distributions and feature '
            f"values fixed. The conservative conditional upper bound is {v['conditional_MAP_upper_bound']}/{v['rows']}. "
            'Most witnesses are same-zero-feature candidates whose existing ordering cannot change. '
            'This is not an observation or architecture ceiling; retraining the core or changing '
            'features/context invalidates it. It does not select a replacement configuration.','']
        bindings.update(bound['bindings']);bindings.update(bound['sources'])
        supplemental.extend([bound_path,OUT/'RC-bound-plan.json'])
    parity_path=OUT/f'{arm}-roundtrip.json'
    if parity_path.exists():
        parity=json.loads(parity_path.read_text())
        lines+=['',f"Bounded nonzero-head input parity: passed `{parity['passed']}` on32distinct "
            'personal-API input cases, with batch256padding and separate batch1 checks. Exact '
            'other-unit fields are rebuilt from saved getter records; own history and M01 contexts '
            'reuse validated caches. This is not full raw-observation encoder/filter or native '
            'serving certification. Original numerical criteria and any failures remain preserved.','']
        bindings.update(parity['bindings']);bindings.update(parity['sources'])
        supplemental.extend([parity_path,OUT/f'{arm}-roundtrip-plan.json'])
    report.write_text('\n'.join(lines),encoding='utf-8')
    bindings.update(info['inputs']);bindings.update(info['sources']);bindings.update(info['bindings'])
    for p in (report,OUT/f'{arm}-analysis.json',OUT/f'{arm}-execution-plan.json',OUT/f'{arm}-preflight.json',
              OUT/'RC-plan.json',OUT/'RC-data-ready.json',*supplemental):
        bindings[str(p.relative_to(ROOT))]=digest(p)
    for relative,expected in bindings.items():
        if digest(ROOT/relative)!=expected:raise RuntimeError('Completion binding mismatch: '+relative)
    immutable_json(OUT/f'{arm}-completion.json',dict(bindings=bindings,fit_source_commit=info['source_commit'],
        fixed_final_step=2000,optimizer_updates=info['optimizer_updates'],supervised_presentations=info['supervised_presentations'],
        trainable_parameters=info['trainable_parameters'],new_fits=1,reserved_opened=0,
        direct_input_scope='Consumed old cohort/model/raw forecast and immutable all-point caches. '
                           'Original getter evidence is transitively bound by committed RC-data-ready input lineage, '
                           'already validated during cache preparation; no repeat engine extraction.',
        conditional_diagnostic_only=True,policy_replaced=False,
        commands=['python -m tools.action_predictor.relational_priority.data',
                  f'python -m tools.action_predictor.relational_priority.fit {arm}',
                  f'python -m tools.action_predictor.relational_priority.results {arm}']))
    print(arm,'reports complete with',len(bindings),'direct artifact/source bindings.',flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('arm',choices=ARMS);run(parser.parse_args().arm)
