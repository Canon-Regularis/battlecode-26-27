"""Immutable fixed-endpoint PC02 comparisons, report and completion inventory."""
import json
from pathlib import Path

import numpy as np

from ..audit import immutable_json
from ..data import digest
from ..priority_capacity.data import load
from .experiment import ROOT,OLD,OUT,LOCAL


def run():
    current_path=OUT/'PC02.json'
    current=json.loads(current_path.read_text())
    parent_path=ROOT/'tools/action_predictor/experiments/v21/PC01.json'
    parent=json.loads(parent_path.read_text())
    plan=json.loads((OUT/'PC02-plan.json').read_text())
    controls=load()
    with np.load(OLD/'v21/PC01-cohort.npz') as z:
        cohorts={name:np.asarray(value['group']) for name,value in controls.items()}
        cohorts['broad_fit']=z['group']
        target={name:np.asarray(value['target']) for name,value in controls.items()}
        target['broad_fit']=z['target']
    cohorts['original_fit']=cohorts.pop('fit')
    target['original_fit']=target.pop('fit')
    comparisons={}
    bindings={str(current_path.relative_to(ROOT)):digest(current_path),
              str(parent_path.relative_to(ROOT)):digest(parent_path),
              str(Path(__file__).relative_to(ROOT)):digest(Path(__file__))}
    for name,group in cohorts.items():
        paths=dict(initial=LOCAL/f'runs/PC02/{name}-step-0000-predictions.npz',
                   regularized=LOCAL/f'runs/PC02/{name}-step-2000-predictions.npz',
                   PC01=OLD/f'v21/runs/PC01/{name}-step-2000-predictions.npz')
        archives={}
        for label,path in paths.items():
            receipt=parent if label=='PC01' else current
            expected=receipt['bindings'][str(path.relative_to(ROOT))]
            if digest(path)!=expected:
                raise RuntimeError('Prediction binding mismatch: '+str(path))
            bindings[str(path.relative_to(ROOT))]=expected
            with np.load(path) as z:
                archives[label]={key:z[key] for key in z.files}
        groups=np.unique(group)
        support=np.array([(group==g).sum() for g in groups])
        rng=np.random.default_rng(20261106)
        draws=np.stack([np.bincount(rng.integers(len(groups),size=len(groups)),minlength=len(groups))
                        for _ in range(2000)])
        denominator=draws@support
        comparisons[name]=dict(rows=len(group),groups=len(groups),references={})
        after=archives['regularized']
        after_correct=after['integer']==target[name]
        for reference in ('initial','PC01'):
            before=archives[reference]
            correct=before['integer']==target[name]
            change=after_correct.astype(int)-correct
            loss=after['nll']-before['nll']
            gains=np.array([change[group==g].sum() for g in groups])
            losses=np.array([loss[group==g].sum() for g in groups])
            comparisons[name]['references'][reference]=dict(rescues=int((~correct&after_correct).sum()),
                regressions=int((correct&~after_correct).sum()),net=int(change.sum()),
                mean_NLL_difference=float(loss.mean()),mean_bounded_rank_difference=float((after['rank']-before['rank']).mean()),
                paired_whole_group_accuracy_interval=np.quantile(draws@gains/denominator,[.025,.975]).tolist(),
                paired_whole_group_NLL_interval=np.quantile(draws@losses/denominator,[.025,.975]).tolist(),
                group_net_commands=dict(zip(map(str,groups),map(int,gains))))
    immutable_json(OUT/'PC02-analysis.json',dict(cohorts=comparisons,bindings=bindings,
        uncertainty='2000paired whole-group draws seed20261106. Controls pre-exposed to warm head/encoder; '
                    'not untouched generalization or selection-adjusted full-policy evidence. Fits in-sample.',
        units=dict(accuracy='Difference in accuracy fraction',NLL='Mean integer NLL difference, nats'),
        fixed_final_step=2000,new_fits=0,reserved_opened=0))
    first,last=current['trace'][0],current['trace'][-1]
    lines=['# PC02: warm-start-regularized P05 contrast','',
        'One controlled diagnostic retains PC01’s population, architecture, inputs, initialization, '
        'seed, optimizer, full-population accumulation and fixed endpoint. It changes only the '
        'training objective by penalizing squared displacement from the warm P05 weights and bias.','',
        f"`loss = mean normalized integer NLL + {current['lambda_value']:.12g} × sum squared parameter displacement`",'',
        'The strength is .5 times PC01’s initial broad TRAIN NLL divided by its final squared '
        'parameter drift. This is one TRAIN-derived prospective allocation rule for PC02, not a '
        'control-selected strength, sweep, or universally optimal regularization setting.','',
        '| Update | Broad fit /5,876 | Original fit /128 | Same-group control /128 | Disjoint-group control /128 | Penalty |',
        '| --- | ---: | ---: | ---: | ---: | ---: |']
    for row in current['trace']:
        c=row['cohorts']
        lines.append('| '+str(row['step'])+' | '+' | '.join(str(c[n]['exact']) for n in (
            'broad_fit','original_fit','same_fit_groups','held_groups'))+f" | {row['penalty']:.6f} |")
    lines+=['','| Cohort | Warm NLL | PC01 final NLL | PC02 final NLL | PC02 mean bounded rank |',
            '| --- | ---: | ---: | ---: | ---: |']
    for name,c in last['cohorts'].items():
        lines.append(f"| {name} | {first['cohorts'][name]['mean_NLL']:.6f} | "
            f"{parent['trace'][-1]['cohorts'][name]['mean_NLL']:.6f} | {c['mean_NLL']:.6f} | "
            f"{c['mean_bounded_candidate_rank']:.3f} |")
    lines+=['',f"Named exploratory gate passed: **{current['exploratory_gate_passed']}**. Checks: `{current['gate']}`.",
        'This requires substantial fitting improvement, both control losses below warm, no control '
        'exact decline, and at least five additional exact values on one control. Merely preventing '
        'learning to recover warm scores is insufficient. The gate does not replace any original '
        'complete-command/category or three-seed target.','',
        'The full-population mean gradient is accumulated across chunks before one optimizer update. '
        'The displacement penalty is added exactly once per update. AdamW is unchanged (.003 then '
        '.001, 1,000 updates each; zero decay, clip 5); all 207,816 head parameters remain trainable. '
        'No threshold, calibration, alternative endpoint or seed is selected.','',
        'Both the frozen encoder and warm head previously saw the controls. They are excluded only '
        'from this new optimization. Results cannot establish untouched generalization, sufficient '
        'observations or a definitive cause of the original P05 failure. Rank is among distinct '
        'existing point/fallback-mode candidates, not every integer. Explanation shares marginalize '
        'equivalent outputs and are not Fish-intent labels.','',
        'The source gate binds static repository-local import closure and explicit prerequisite test '
        'modules. Optimized Python is explicitly refused. Real-entrypoint tests inject previously '
        'omitted-source mismatches and install an optimizer-construction tripwire. A separate injected '
        'measurement exception verifies that raw arrays survive. Assessments archive each complete '
        'cohort raw matrix before scoring it. These corrections are prospective; earlier incidents '
        'and frozen reports remain unchanged.','',
        f"Fit source commit: `{current['source_commit']}`. Seven focused tests passed before optimizer "
        'creation. The prior approved accumulation check and identical cohort are reused; no '
        'repeated 495-game extraction audit. Timing includes optimization, assessment and serialization '
        'after preflight; it is not pure optimization or production serving cost.','',
        'This supplies the recorded priority family for conditional evaluation. The complete policy '
        'is not replaced. Any future integrated comparison must recompute normalized joint command '
        'probabilities and winning families. No full-command improvement, promotion or robustness '
        'claim follows. Original shop/sparse-category/identity/legality qualifications remain.','',
        'Both 75-game reserved partitions remain sealed; no DEV payloads, matches, downloads, '
        'bot/runtime work or deployment. Fresh Sol xhigh review follows.','',
        'Reproduce once into absent immutable destinations: `python -m tools.action_predictor.priority_regularized.experiment`, '
        'then `python -m tools.action_predictor.priority_regularized.results`. Do not rerun completed fitting.','']
    report=OUT/'PC02-REPORT.md'
    if report.exists():
        raise FileExistsError(report)
    report.write_text('\n'.join(lines),encoding='utf-8')
    bindings.update(plan['inputs'])
    bindings.update(current['bindings'])
    paths=[report,OUT/'PC02-plan.json',OUT/'PC02-preflight.json',OUT/'PC02-analysis.json',
           ROOT/'tools/action_predictor/experiments/v21/PC01-review.json',
           ROOT/'tools/action_predictor/experiments/v21/PC01-review-response.json']
    bindings.update({str(p.relative_to(ROOT)):digest(p) for p in paths})
    bindings.update(plan['sources'])
    for relative,expected in bindings.items():
        if digest(ROOT/relative)!=expected:
            raise RuntimeError('Completion binding mismatch: '+relative)
    immutable_json(OUT/'PC02-completion.json',dict(bindings=bindings,fit_source_commit=current['source_commit'],
        fixed_final_step=2000,optimizer_updates=2000,supervised_presentations=5876*2000,
        penalty_strength=current['lambda_value'],diagnostic_only=True,policy_replaced=False,
        commands=['python -m tools.action_predictor.priority_regularized.experiment',
                  'python -m tools.action_predictor.priority_regularized.results'],
        new_fits=1,reserved_opened=0))
    print('Bound PC02 results and',len(bindings),'artifacts.')


if __name__=='__main__':
    run()
