"""Additive final study summary and fitting-only saved-output diagnostic."""
import json
import numpy as np
from .data import load
from .protocol import ROOT,WORK,REPORT
from ..audit import immutable_json
from ..data import digest
from ..observation_metrics import correctness


def fitting_diagnostic(result):
    # A and its primary frozen selector are chosen by design, not best result.
    epoch=result['selected']['movement'];path=WORK/'runs/A'/f'selected-{epoch:02d}-fit.npz'
    if digest(path)!=result['bindings'][str(path.relative_to(ROOT))]:raise ValueError('Control forecast changed')
    data=load('fit');raw=data['arrays']
    with np.load(path) as z:p={k:z[k] for k in z.files}
    parameter,joint=correctness(raw,p);ix=np.arange(len(raw['y']));py=raw['py'];coordinate=p['coordinate']
    tile=(py>=0)&(py<289);pred_tile=(coordinate>=0)&(coordinate<289)
    support=tile&raw['valid'][ix,py.clip(0,288)]&(raw['grid'][ix,py.clip(0,288),5]>0)
    last=raw['grid'][:,:,18].argmax(1);known=raw['grid'][:,:,18].max(1)>0
    repeats=pred_tile&known&(coordinate==last);rows={}
    for name,direction in [('change',3),('continue',2)]:
        mask=(raw['y']==8)&(raw['direction']==direction);wrong=mask&~parameter
        rows[name]=dict(rows=int(mask.sum()),gold_inside_current_move_support=int((mask&support).sum()),
            conditional_correct=int((mask&parameter).sum()),complete_correct=int((mask&joint).sum()),
            wrong_coordinate=int(wrong.sum()),correct_coordinate_wrong_family=int((mask&parameter&~joint).sum()),
            last_delta_available=int((mask&known).sum()),wrong_coordinate_repeats_last_delta=int((wrong&repeats).sum()),
            missing_all_16observations=int((mask&(raw['history_gaps'][:,:,1].sum(1)==0)).sum()),
            full_16observations=int((mask&(raw['history_gaps'][:,:,1].sum(1)==16)).sum()))
    return dict(arm='A',selector='movement',round=epoch,partition='fit',rows=rows,
        forecast_sha256=digest(path),
        limits='In-sample descriptive output analysis, not a causal history ablation or observation-sufficiency test. Current movement mask is not a full legality proof. No checkpoint or hyperparameter selection.')


def run():
    results={name:json.loads((REPORT/f'{name}.json').read_text()) for name in ('A','B','C')}
    bindings={str((REPORT/f'{name}.json').relative_to(ROOT)):digest(REPORT/f'{name}.json') for name in results}
    protocol=REPORT/'protocol.json';bindings[str(protocol.relative_to(ROOT))]=digest(protocol)
    for result in results.values():
        if result['protocol_sha256']!=digest(protocol):raise ValueError('Protocol changed')
        for key,expected in result['bindings'].items():
            if digest(ROOT/key)!=expected:raise ValueError('Saved run changed: '+key)
    selected={name:{selector:dict(round=epoch,results=result['results'][str(epoch)])
                     for selector,epoch in result['selected'].items()} for name,result in results.items()}
    comparisons={}
    for name,reference in [('B','A'),('C','B'),('C','A')]:
        comparisons[name+'-'+reference]=results[name]['comparisons'][reference]
    diagnostic=fitting_diagnostic(results['A'])
    value=dict(bindings=bindings,source_sha256=digest(__file__),selected=selected,comparisons=comparisons,
        fitting_diagnostic=diagnostic,completed_fits=3,completed_rounds=36,completed_updates=2691,
        completed_fit_row_presentations=65465*12*3,recorded_fit_and_assessment_seconds=sum(r['seconds'] for r in results.values()),
        verdict='Negative movement experiment: neither extra recurrent carry nor32step gradients meets all frozen criteria. No strategy or playing-strength claim. No promotion or repeated horizon fits.',
        next='Review completed C and this report. Then use the fitting-only destination-error evidence to design a bounded execution/optimization diagnostic before any separately reviewed new fit. The failed horizon study does not establish that useful long-term information is absent.',
        new_fits=0,reserved_opened=0)
    immutable_json(REPORT/'summary.json',value)
    lines=['# Restored-history horizon study: negative movement result','',
        'All three frozen arms completed 12 rounds and 897 optimizer updates each. A resets',
        'extra recurrent memory every eight roots; B carries memory with eight-step',
        'gradients; C carries memory with 32-step gradients. Initial tensors, rows,',
        'sampler schedules, update counts and checkpoint opportunities matched. All arms',
        'retain explicit 16-root command/observation history. No existing predictor is replaced.','',
        '## Primary selection: assessment groups','',
        'The primary tuning rule selects round 12 for every arm. Counts below use the',
        'same 16,389 assessment rows. Complete moves include the action family and destination.','',
        '| Arm | Complete commands | Moves / 2,672 | Changes / 1,370 | Continuations / 1,298 | Balanced move NLL | Full modeled NLL | Macro-F1 |',
        '|---|---:|---:|---:|---:|---:|---:|---:|']
    for name,result in results.items():
        m=result['results'][str(result['selected']['movement'])]['assessment'];c=m['categories']
        lines.append(f"| {name} | {c['all']['complete']} | {c['move']['complete']} | {c['change']['complete']} | {c['continue']['complete']} | {m['selectors']['movement']:.6f} | {m['selectors']['full']:.6f} | {m['macro_F1']:.6f} |")
    lines+=['','B minus A gains nine moves but loses five changes and 28 complete commands.',
        'It fails movement, change, balanced-NLL, full-NLL, macro-F1 and submit guards.',
        'C minus B loses 24 moves and 23 continuations, with no change gain. Its full NLL',
        'improves, but movement, change, continuation and balanced-movement NLL guards fail.',
        'C minus A loses 15 moves, five changes and nine continuations. No matched contrast',
        'passes the frozen allocation gate. Both memory-carry arms have ten fully correct',
        '32-root assessment windows, the same as A, out of 280. These windows are teacher-forced.','',
        '## Secondary selection and historical regressions','',
        'The full-NLL tuning rule selects round 11 for A/B and round 12 for C. C gains',
        '41 moves over A and 51 over B under this separate rule, but loses 19 and 15',
        'direction changes respectively. Its change guard fails both comparisons.',
        'This is not grounds to switch selectors. The full artifacts retain every category,',
        'false positive, targeting guard, bootstrap interval and leave-one-group-out result.','',
        'On the original 14,439-row DEV, primary A/B/C have 1,177/1,194/1,169 complete',
        'moves. All remain below L02 (1,365) and JP02 (1,364). The fresh models have different',
        'training exposure and initialization from those references; this comparison is a',
        'regression panel, not an isolated causal effect. Priorities, casts and wards remain',
        'weak. Missing shop arguments keep every shop a strict complete-command failure.','',
        '## Fitting-only diagnostic for the next iteration','',
        'The frozen primary A checkpoint gets only 356 of 5,032 fitting direction changes',
        'fully correct; 410 have the correct destination conditional on the true family.',
        'Of 4,676 complete-change failures, 4,622 have a wrong conditional destination;',
        'only 54 have a correct destination with a wrong family. In 3,331 of those 4,622',
        'destination errors, the conditional mode repeats the previous movement vector.',
        'All 5,032 recorded change destinations lie inside the current movement mask.',
        '3,751 change rows have all 16 earlier observations; 63 have none.','',
        'These are descriptive fitting-set facts, not proof that history causes the error',
        'or that observations are sufficient. Weak fitting performance and still-improving',
        'late training loss leave execution representation and optimization as live hypotheses.',
        'The next step is a bounded fitting-only audit of destination ranking, continuation',
        'probability and optimization evidence. Do not repeat the horizon study or launch',
        'another architecture solely because this result is negative. Any new fit needs its',
        'own concrete hypothesis, frozen comparison and review.','',
        '## Evidence and limits','',
        'The parent verified all C run bindings, matching initial weights/RNG, all twelve',
        'sampling schedules and RNG states, identical updates/coverage, both selector choices,',
        'nine finite gradient snapshots and changes in every selected floating tensor.',
        'A/B already have independent approvals. C and this additive report await review.',
        'The immutable `summary.json` binds the three result manifests and this producer.',
        'It includes both selection rules, paired reports and the fitting-only diagnostic.','',
        'One seed, previously exposed availability-enriched research groups, actual past',
        'commands, ambiguous entity targets, incomplete legality/new POST validation and',
        'missing shop arguments limit the conclusions. No reserved games, matches, downloads,',
        'runtime changes, extra fits or model promotions occurred in this reporting step.','']
    target=REPORT/'REPORT.md'
    with target.open('x',encoding='utf-8') as stream:stream.write('\n'.join(lines))
    print(json.dumps(dict(summary_sha256=digest(REPORT/'summary.json'),report_sha256=digest(target),diagnostic=diagnostic),indent=2))


if __name__=='__main__':run()
