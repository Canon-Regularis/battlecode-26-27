"""Concise immutable report and inventory from the completed saved comparison."""
import json
from pathlib import Path
import numpy as np
from ..audit import immutable_json
from ..data import digest
from ..priority_broad.guard import committed_sources
from ..priority_regularized.safety import dependency_files
from .protocol import ROOT,OUT,LOCAL,ARMS


def run():
    commit,sources=committed_sources(ROOT,dependency_files(ROOT,('tools.action_predictor.policy_priority_integration.report',)))
    result=json.loads((OUT/'JP-results.json').read_text());fields=json.loads((OUT/'JP-fields-ready.json').read_text())
    forecasts=json.loads((OUT/'JP-forecasts-ready.json').read_text());bindings=dict(result['bindings']);bindings.update(sources)
    for name in ('JP-plan.json','JP-fields-ready.json','JP-forecast-plan.json','JP-forecasts-ready.json',
                 'JP-results.json','JP-null-train.json','JP-null-validation.json'):
        path=OUT/name;bindings[str(path.relative_to(ROOT))]=digest(path)
    # Reuse the consumed-and-verified forecast hashes, rather than hashing GB twice.
    for split in ('train','validation'):
        for name,value in forecasts['results'][split]['files'].items():bindings[name]=value
        path=LOCAL/f'forecasts/{split}/preserved.json';bindings[str(path.relative_to(ROOT))]=digest(path)
    old_report_path=ROOT/'tools/action_predictor/experiments/v8/P03.json'
    old_report=json.loads(old_report_path.read_text());old_predictions=ROOT/'.cambc/action-predictor/v8/runs/P03/validation-predictions.npz'
    if digest(old_predictions)!=old_report['predictions_sha256']:raise RuntimeError('Original P03 archive changed')
    bindings[str(old_predictions.relative_to(ROOT))]=digest(old_predictions)
    with np.load(old_predictions) as z:old_integer=z['priority']
    new_integer=np.load(LOCAL/'forecasts/validation/JP03/integer.npy',mmap_mode='r')
    correction=dict(original_P03_conditional_exact=old_report['validation']['priority_strata']['all']['exact'],
        current_P03_conditional_exact=result['results']['validation']['JP03']['all']['priority']['all']['conditional_exact'],
        all_row_integer_mismatches=int((old_integer!=new_integer).sum()),
        correction='Earlier handoffs/review briefs misdescribed125/576 as retained P03 exactness. Frozen P03 report and archive give96/576;125 was P05 exploratory continuation target, explicitly29aboveP03. Original artifacts are unchanged.',
        sources=['tools/action_predictor/experiments/v8/P03.json','tools/action_predictor/priority_residual_fit.py'],
        scope='Historical description correction, not a changed checkpoint, refit or new baseline selection.')
    immutable_json(OUT/'P03-handoff-correction.json',correction)
    if correction['all_row_integer_mismatches']:raise RuntimeError('Retained P03 mode parity failed')
    for name in ('P03-handoff-correction.json',):bindings[str((OUT/name).relative_to(ROOT))]=digest(OUT/name)
    lines=['# Frozen full-policy priority comparison','',
        'The selected L02 policy, upstream filtering, family probabilities, other argument heads and joint MAP remain fixed. Only the normalized priority conditional distribution changes. These are no-fit model evaluations; bot work remains paused.','',
        '| Arm | Priority head | Complete DEV commands | Macro F1 | Observed joint NLL | Priority conditional / joint | Priority type FP |',
        '| --- | --- | ---: | ---: | ---: | ---: | ---: |']
    for arm,name in ARMS.items():
        r=result['results']['validation'][arm]['all'];o=r['overall'];p=r['priority'];pr=p['all']
        lines.append(f"| {arm} | {name} | {o['strict_correct']:,}/14,439 | {o['macro_f1']:.6f} | {o['joint_nll']:.6f} | {pr['conditional_exact']}/576 / {pr['joint_exact']}/576 | {p['false_positives']['type']} |")
    lines += ['', 'The P05 null preserves the original semantic commands and conditional modes; its measured numerical differences are retained in the null receipts. All four arms were forecast and archived before current answers were read. No softmax over family modes or type-first decoder is used.','',
        'The primary contrast is real-trained RC01 against P05 and shuffled-trained RC00. P03 is a retained comparator, not a matched-capacity treatment.']
    lines += ['', 'A historical handoff error is corrected separately: retained P03 is 96/576 conditional integers, not 125/576. Its original frozen report agrees and every current P03 integer reproduces the original archive. The number 125 was an exploratory P05 continuation target; no historical artifact is rewritten.']
    for reference in ('JP00','JP01','JP03'):
        c=result['comparisons']['JP02'][reference]['overall'];iv=c['paired95']['joint_accuracy'];lv=c['paired95']['joint_nll']
        lines += ['',f"Against {reference}, JP02 rescues **{c['rescues']}** commands and regresses **{c['regressions']}**; paired whole-group accuracy-difference interval **[{100*iv['low']:.3f}, {100*iv['high']:.3f}] percentage points**. NLL-difference interval **[{lv['low']:.6f}, {lv['high']:.6f}]**. Group net differences: `{c['group_net']}`."]
    lines += ['', '## Where conditional gains go','']
    for arm in ARMS:
        c=result['results']['validation'][arm]['priority_competition']
        lines.append(f"- {arm}: {c['conditional_mode_correct']} correct integers; {c['joint_correct']} correct complete priorities; {c['correct_integer_loses_family_competition']} correct integers lose family competition; {c['priority_unreachable_even_with_unit_conditional_mass']} true priorities cannot win even with hypothetical conditional point mass one, holding family beliefs and other heads fixed.")
    lines += ['', 'The last count is an optimistic frozen-distribution bound, not achieved accuracy or an inference rule. Family beliefs are identical across arms. Correctly typed integer errors, wrong types and false-positive priority forecasts remain separately reported. Absolute/residual/fallback target-mass shares describe probability explanations, not Fish intent.','',
        '## Category and sampling evidence','',
        '| Recorded family | Support | JP00 complete | JP01 complete | JP02 complete | JP03 complete |',
        '| --- | ---: | ---: | ---: | ---: | ---: |']
    cats={a:result['results']['validation'][a]['all']['overall']['per_category'] for a in ARMS}
    for code,row in enumerate(cats['JP00']):
        if code==0:continue
        lines.append('| '+row['action']+' | '+str(row['support'])+' | '+' | '.join(str(cats[a][code]['joint_correct']) for a in ARMS)+' |')
    lines += ['', 'The JSON report contains type PRF/confusion, joint false positives, all-true-family and correctly typed parameters, category losses, continuation/change/startup movement, partial readiness, blocked-attempt versus successful-move mask flags, and direct paired targeting comparisons. Conditional nonpriority parameter paths remain fixed; their joint counts can change when priority wins or loses family competition.','',
        '| Arm | Natural TRAIN complete | Natural TRAIN priority conditional / joint | DEV complete |',
        '| --- | ---: | ---: | ---: |']
    for arm in ARMS:
        r=result['results']['train'][arm]['natural'];p=r['priority']['all'];dev=result['results']['validation'][arm]['all']['overall']
        lines.append(f"| {arm} | {r['overall']['strict_correct']:,}/{r['overall']['rows']:,} | {p['conditional_exact']}/{p['rows']} / {p['joint_exact']}/{p['rows']} | {dev['strict_correct']:,}/14,439 |")
    lines += ['', 'Augmented TRAIN and natural membership are distinct report strata. The report further separates natural rows in correction-fit groups, correction-held groups and other groups. These groups were previously seen by the warm encoder/head and research; they are not untouched full-policy evidence. Frozen upstream state uses the original augmented traversal cadence.','',
        '## Provenance and limits','',
        f"Causal field recovery covers {fields['results']['train']['rows']:,} TRAIN and {fields['results']['validation']['rows']:,} DEV rows. It reused 6,132 exact earlier TRAIN records and newly queried every remaining eligible decision. Personally unknown other champions are not imputed; rows with no known other units remain in evaluation. Scoped values and their availability are checked against the historical-engine contract. The original priority-chain audit was reused rather than repeated.",
        '', 'The five DEV groups are repeatedly inspected development evidence. Paired 2,000 whole-group resamples (seed 20261106) describe this exploratory comparison, with null empty denominators; they do not adjust for research selection or establish three-seed robustness. No arm is promoted automatically. All original category, macro-F1, movement, likelihood and targeting targets remain binding.',
        '', 'All 43 DEV shops remain strict failures; missing purchase-argument likelihood is absent from observed loss. Sparse altar/teleport/submit categories, coordinate/entity ambiguity, full legality and global calibration remain uncertified. The observed shop bucket is not complete original API-command probability. Both reserved partitions remain sealed; no matches, simulations, replay downloads, bot/runtime changes or deployments occurred.',
        '', 'Reproduction commands are in the completion inventory. Existing immutable destinations are consumed rather than overwritten. No training or optimizer update was performed; experiment wall time and end-to-end serving latency were not instrumented.', '']
    report=OUT/'JP-REPORT.md'
    if report.exists():raise FileExistsError('Preserve existing report')
    report.write_text('\n'.join(lines),encoding='utf-8');bindings[str(report.relative_to(ROOT))]=digest(report)
    immutable_json(OUT/'JP-completion.json',dict(source_commit=commit,bindings=bindings,
        execution_commits=dict(recovery=fields['source_commit'],forecast=forecasts['source_commit'],assessment=result['source_commit']),
        recovery_receipts=fields['receipts'],raw_forecast_bytes=sum((ROOT/name).stat().st_size for split in forecasts['results'].values() for name in split['files'] if name.endswith('raw.npy')),
        commands=['python -m tools.action_predictor.policy_priority_integration.'+name for name in ('recover','forecast','evaluate','report')],
        new_fits=0,optimizer_updates=0,reserved_opened=0,model_promoted=False,
        original_success_claim=False,fresh_review_pending=True))


if __name__=='__main__':run()
