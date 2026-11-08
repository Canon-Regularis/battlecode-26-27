"""Read saved O01 forecasts only; preserve paired comparisons and provenance."""
import json
from pathlib import Path

import numpy as np

from ..audit import immutable_json
from ..data import digest
from .data import ROOT,OUT,LOCAL,load
from .anchored import PC02_COMMIT,PC02_COMPLETION,committed_manifest


def paired(after,before,target,group,selected=None):
    selected=np.ones(len(target),bool) if selected is None else selected
    if not selected.any():return dict(rows=0,groups=0,accuracy_difference=None,mean_NLL_difference=None)
    target=target[selected];group=group[selected]
    a=after['integer'][selected]==target;b=before['integer'][selected]==target
    change=a.astype(int)-b;loss=after['nll'][selected]-before['nll'][selected]
    groups=np.unique(group);support=np.array([(group==g).sum() for g in groups])
    gains=np.array([change[group==g].sum() for g in groups])
    losses=np.array([loss[group==g].sum() for g in groups])
    rng=np.random.default_rng(20261106)
    draws=np.stack([np.bincount(rng.integers(len(groups),size=len(groups)),minlength=len(groups)) for _ in range(2000)])
    denominator=draws@support
    return dict(rows=len(target),groups=len(groups),rescues=int((a&~b).sum()),regressions=int((~a&b).sum()),
        net=int(change.sum()),accuracy_difference=float(change.mean()),mean_NLL_difference=float(loss.mean()),
        mean_bounded_rank_difference=float((after['rank'][selected]-before['rank'][selected]).mean()),
        paired_whole_group_accuracy_interval=np.quantile(draws@gains/denominator,[.025,.975]).tolist(),
        paired_whole_group_NLL_interval=np.quantile(draws@losses/denominator,[.025,.975]).tolist(),
        group_net_commands=dict(zip(map(str,groups),map(int,gains))))


def summary(p,target,mask):
    if not mask.any():return dict(rows=0,exact=0,accuracy=None,mean_NLL=None,mean_bounded_rank=None)
    correct=p['integer'][mask]==target[mask]
    return dict(rows=int(mask.sum()),exact=int(correct.sum()),accuracy=float(correct.mean()),
        mean_NLL=float(p['nll'][mask].mean()),mean_bounded_rank=float(p['rank'][mask].mean()))


def run():
    current_path=OUT/'O01.json';current=json.loads(current_path.read_text())
    cohorts,bindings,references,manifests=load()
    control,extra=committed_manifest(PC02_COMMIT,PC02_COMPLETION);bindings.update(extra)
    control_hashes={k.replace('\\','/'):v for k,v in control['bindings'].items()}
    def archive(path,expected):
        relative=path.relative_to(ROOT).as_posix()
        if digest(path)!=expected:raise RuntimeError('Saved prediction changed: '+relative)
        bindings[relative]=expected
        with np.load(path) as z:return {key:z[key] for key in z.files}
    comparisons={};contexts={};numeric={}
    for name,d in cohorts.items():
        target=d['target'].numpy();group=d['group'].numpy()
        available=d['order_available'].numpy().any(-1)
        current_predictions={}
        for label,suffix in (('O01',name),('numeric_means',name+'-numeric-means')):
            path=LOCAL/f'runs/O01/{suffix}-step-2000-predictions.npz'
            expected=current['bindings'][str(path.relative_to(ROOT))]
            current_predictions[label]=archive(path,expected)
        for label,step in (('warm',0),('PC02',2000)):
            path=LOCAL.parent/f'v22/runs/PC02/{name}-step-{step:04d}-predictions.npz'
            current_predictions[label]=archive(path,control_hashes[path.relative_to(ROOT).as_posix()])
        after=current_predictions['O01']
        comparisons[name]={label:paired(after,current_predictions[label],target,group) for label in ('warm','PC02')}
        contexts[name]={}
        for stratum,mask in (('order_available',available),('no_order_available',~available)):
            contexts[name][stratum]=dict(rows=int(mask.sum()),groups=len(np.unique(group[mask])),
                models={label:summary(p,target,mask) for label,p in current_predictions.items()},
                comparisons={label:paired(after,current_predictions[label],target,group,mask) for label in ('warm','PC02')})
        numeric[name]=paired(after,current_predictions['numeric_means'],target,group)
        numeric[name]['semantic_changes']=int((after['integer']!=current_predictions['numeric_means']['integer']).sum())
    paths=[current_path,OUT/'O01-plan.json',OUT/'O01-preflight.json',Path(__file__)]
    bindings.update({str(p.relative_to(ROOT)):digest(p) for p in paths})
    immutable_json(OUT/'O01-analysis.json',dict(comparisons=comparisons,availability_strata=contexts,
        numeric_variation_vs_TRAIN_means=numeric,bindings=bindings,
        uncertainty='2000paired whole-group draws seed20261106. Pre-exposed repeatedly inspected TRAIN '
                    'controls, not untouched or confirmatory full-policy generalization. Fit intervals in-sample.',
        units=dict(accuracy='Difference in accuracy fraction',NLL='Mean integer NLL difference in nats'),
        numeric_diagnostic='Fixed final weights; replace numeric within-pool variability, preserving '
                           'masks/counts/unavailable cases and learned offsets. No variant selected.',
        new_fits=0,reserved_opened=0))
    before=current['trace'][0]['cohorts'];after=current['trace'][-1]['cohorts']
    lines=['# O01: verified personal action-order information','',
        'This matched information contrast adds other personally known champions\' current and '
        'scheduled priority relations to the actual retained P05 integer model. It compares with '
        'PC02 embedded in an equally sized zero-input interface; exact readout and optimizer-transition '
        'equivalence established control reuse before fitting. No control retraining was needed.','',
        '| Cohort | Rows | Warm exact | PC02 exact | O01 exact | Warm NLL | PC02 NLL | O01 NLL |',
        '| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |']
    parent=json.loads((ROOT/'tools/action_predictor/experiments/v22/PC02.json').read_text())
    for name,v in after.items():
        control_v=parent['trace'][-1]['cohorts'][name]
        lines.append(f"| {name} | {v['rows']} | {before[name]['exact']} | {control_v['exact']} | {v['exact']} | "
                     f"{before[name]['mean_NLL']:.6f} | {control_v['mean_NLL']:.6f} | {v['mean_NLL']:.6f} |")
    lines+=['',f"Named exploratory gate: **{current['exploratory_gate_passed']}**, checks `{current['gate']}`.",'',
        'The treatment uses 32 permutation-invariant ally/enemy current/scheduled statistics: '
        'availability, count, signed-asinh relative min/max/mean, and below/equal/above fractions. '
        'All known personally queryable champions contribute; no entity/game IDs or hidden priorities '
        'are model inputs. The signed transform was fixed after observing the TRAIN numeric range '
        'and before fitting. Normalization uses only the 5,876 fitting rows.','',
        'Historical engines 2 and 3 expose this read-only API. Signed own-value parity and '
        'unavailable-enemy rejection were verified before extraction. The first probe\'s endian '
        'failure remains preserved; corrected queries use explicit little-endian decoding. New '
        'fields were restored on exactly 6,132 eligible TRAIN decisions in 344 games. No DEV '
        'or reserved payload was accessed, and no hypothetical actions were executed.','',
        'Availability is explicit: 5,595/5,876 fitting, 115/128 same-group and 122/128 held-group '
        'controls have any order evidence. Rows without this information remain in every total. '
        'The numeric-mean diagnostic changes only fixed-weight readout inputs and does not select '
        'an alternative predictor. Dependence on these fields does not by itself establish useful '
        'transfer or recovery of Fish\'s rules.','',
        'The base context, original 39 fields, vocabulary, exact int64 anchors, probability '
        'arithmetic, MAP decoder, initialization, seed, full-population accumulation, learning-rate '
        'schedule and 2,000-update endpoint match PC02. The same displacement penalty includes '
        'base weights, base bias and the new matrix, whose warm value is zero. It is applied once '
        'per full-population update. Both interfaces have 247,400 nominal parameters; the control\'s '
        '39,584 new weights remain inactive. This does not isolate information from active capacity.','',
        'Both frozen encoder and warm head previously saw these controls. Their rows/groups are '
        'excluded from the new head optimization, so they test transfer from this optimization, '
        'not untouched full-policy generalization. All reported paired intervals are exploratory '
        'and conditional on this population, seed and endpoint. Bounded ranks do not rank all '
        'integers; marginalized shares do not label Fish\'s hidden intent.','',
        'This diagnostic supplies the recorded priority family. It measures no action typing, '
        'macro F1 or complete-policy improvement. Any integration must acquire the fields for '
        'every eligible decision and recompute normalized joint command probabilities and winners. '
        'The original category, movement, likelihood, targeting and three-seed targets remain '
        'unmet. Shops stay strict failures; sparse actions, entity identity, full legality and '
        'global calibration retain their limitations. No promotion follows.','',
        f"Fit commit: `{current['source_commit']}`. Sixteen prerequisite tests passed, including "
        'real-entrypoint optimized-Python/source-mismatch/coherent-control-forgery optimizer '
        'tripwires and raw-archive survival after measurement failure. Raw predictions precede '
        'assessment, and all five checkpoints are retained. Timing includes fitting, assessment '
        'and serialization after preflight; it is not pure optimization or serving cost.','',
        'Reproduce into absent destinations only: `python -m tools.action_predictor.order_information.fit`; '
        'then `python -m tools.action_predictor.order_information.results`. Never rerun this completed fit. '
        'The immutable cache/proof commands are listed in the completion inventory. Fresh Sol xhigh '
        'review follows. No bot/runtime work, matches, downloads or deployment.','']
    report=OUT/'O01-REPORT.md'
    if report.exists():raise FileExistsError(report)
    report.write_text('\n'.join(lines),encoding='utf-8')
    bindings.update(current['inputs']);bindings.update(current['sources']);bindings.update(current['bindings'])
    for path in (report,OUT/'O01-analysis.json',OUT/'zero-control-equivalence.json',OUT/'zero-control-plan.json',
                 OUT/'order-cache-plan.json',OUT/'order-cache-ready.json',OUT/'order-asinh-plan.json',OUT/'order-asinh-ready.json',
                 ROOT/'tools/action_predictor/experiments/v22/PC02-review.json',
                 ROOT/'tools/action_predictor/experiments/v22/PC02-control-input-addendum.json'):
        bindings[str(path.relative_to(ROOT))]=digest(path)
    for relative,expected in bindings.items():
        if digest(ROOT/relative)!=expected:raise RuntimeError('Completion mismatch: '+relative)
    immutable_json(OUT/'O01-completion.json',dict(bindings=bindings,fit_source_commit=current['source_commit'],
        fixed_final_step=2000,optimizer_updates=2000,supervised_presentations=5876*2000,
        conditional_diagnostic_only=True,policy_replaced=False,new_fits=1,reserved_opened=0,
        control='Retained PC02, mathematically and empirically embedded as zero-input interface. '
                'Ten isolated contract transitions are tests, not new candidate fits.',
        commands=['python -m tools.action_predictor.order_information.cache',
                  'python -m tools.action_predictor.order_information.cache_asinh',
                  'python -m tools.action_predictor.order_information.control_contract',
                  'python -m tools.action_predictor.order_information.fit',
                  'python -m tools.action_predictor.order_information.results']))
    print('Bound O01 results and',len(bindings),'artifacts.',flush=True)


if __name__=='__main__':run()
