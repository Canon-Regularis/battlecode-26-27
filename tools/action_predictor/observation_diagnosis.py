"""Interpret already-frozen predictions; no fitting or new replay inspection."""
import json
from pathlib import Path
import sys

import numpy as np

from . import reliable_train as rt
from .more_replays import frozen,sha
from .observation_study import ROOT,WORK,REPORTS,OLD,freeze_plan,log_command


def read(path):return json.loads(path.read_text(encoding='utf-8'))


def diagnose():
    freeze_plan();comparison=read(REPORTS/'validation-comparison.json')
    assert comparison['substantive_fits']==2,'This interpretation is explicitly for the stopped first pair'
    first=read(REPORTS/'report-provenance.json')
    for name,digest in first['outputs'].items():assert sha(REPORTS/name)==digest
    with np.load(OLD/'validation.npz') as archive:y,py=archive['y'],archive['py']
    direction=np.load(WORK/'validation-direction.npy',mmap_mode='r')
    move=y==rt.LABELS.index('move');changed=move&(direction==3)
    predictions={name:np.load(WORK/'runs'/name/'validation-predictions.npz') for name in ('H01','H02')}
    correct={name:move&(pred['coordinate']==py)&(py>=0)&(py<289) for name,pred in predictions.items()}
    total_errors=int((move&~correct['H02']).sum());turn_errors=int((changed&~correct['H02']).sum())
    contexts=read(REPORTS/'H02-context-comparison.json')
    rows=[]
    for name in ('direction_change','same_direction','near_static_obstacle','away_from_static_obstacle','new_own_turn','same_own_turn','visible_set_changed'):
        context=contexts[name];a,b=context['observations']['parameters']['move'],context['control']['parameters']['move']
        rows.append(dict(context=name,support=a['support'],control=a['exact_accuracy'],observations=a['exact_accuracy'],
                         gain=a['exact_accuracy']-b['exact_accuracy'],interval=context['paired_intervals']['move_exact']))
        rows[-1]['control']=b['exact_accuracy']
    pair=comparison['pairs'][0];rich,control=pair['observation_score'],pair['control_score']
    retained=read(ROOT/'tools/action_predictor/experiments/v5/M01.json')['validation']
    pc=lambda value:f'{100*value:.2f}%'
    delta=lambda value:f'{100*value:+.2f} pp'
    interval=lambda value:f"[{100*value['low']:+.2f}, {100*value['high']:+.2f}]"
    lines=['# Observation-history findings', '',
        'Observation history produced a modest destination improvement, but failed the frozen macro-F1 and ability-targeting guards against retained M01. The study stopped after two fits; no seed search or additional experiment was substituted. M01 remains the baseline.', '',
        '| Metric | Fresh action+gap control H01 | Observation history H02 | Retained M01 |',
        '|---|---:|---:|---:|']
    for label,get in [('Action accuracy',lambda s:s['accuracy']),('Action macro F1',lambda s:s['macro_f1']),
                      ('Joint action + encoded parameter',lambda s:s['strict_full_command_accuracy']),
                      ('Exact movement destination',lambda s:s['parameters']['move']['exact_accuracy']),
                      ('Joint movement',lambda s:s['parameters']['move']['joint_accuracy'])]:
        lines.append('| '+label+' | '+' | '.join(pc(get(s)) for s in (control,rich,retained))+' |')
    lines += ['| Observed joint NLL | '+' | '.join(f"{s['joint_nll']:.4f}" for s in (control,rich,retained))+' |','',
        f"Against the matched control, exact movement gained {delta(pair['observation_score']['parameters']['move']['exact_accuracy']-control['parameters']['move']['exact_accuracy'])} (95% paired-group interval {interval(pair['overall_paired_intervals']['move_exact'])} pp). Joint movement gained only {delta(rich['parameters']['move']['joint_accuracy']-control['parameters']['move']['joint_accuracy'])}, with interval {interval(pair['overall_paired_intervals']['move_joint'])} pp spanning zero. Joint loss decreased by {pc(1-rich['joint_nll']/control['joint_nll'])}; its relative-reduction interval is {interval(pair['overall_paired_intervals']['joint_loss_reduction'])}%. These are conditional development-group intervals from five groups, not untouched-test or three-seed confirmation.", '',
        '## Where the movement gain occurs', '',
        '| Objective context | Move support | Control exact | History exact | Gain | Paired-group interval (pp) |',
        '|---|---:|---:|---:|---:|---|']
    for row in rows:lines.append(f"| {row['context']} | {row['support']} | {pc(row['control'])} | {pc(row['observations'])} | {delta(row['gain'])} | {interval(row['interval'])} |")
    lines += ['',
        f"Direction changes remain the main destination bottleneck: {turn_errors} of {total_errors} H02 destination errors ({pc(turn_errors/total_errors)}) occur on the {int(changed.sum())} recorded direction-changing moves. Exact accuracy there is only {pc(contexts['direction_change']['observations']['parameters']['move']['exact_accuracy'])}, versus {pc(contexts['same_direction']['observations']['parameters']['move']['exact_accuracy'])} when repeating the earlier direction. History corrected {int((changed&correct['H02']).sum()-(changed&correct['H01']).sum())} additional direction-changing destinations, but did not resolve that gap.", '',
        'The larger gains occur at new own-turn boundaries and after personally visible entity-set changes; the latter has only157 move examples. Near-obstacle and direction-changing gains exceed their comparison contexts. These contexts overlap, so their gains cannot be added or treated as causal explanations. They are objective evaluation strata, not invented intent labels or additional success criteria.', '',
        '## Why the study stopped', '',
        f"H02 macro F1 is {pc(rich['macro_f1'])}, versus {pc(retained['macro_f1'])} for M01 ({delta(rich['macro_f1']-retained['macro_f1'])}, exceeding the frozen1pp regression guard). Ability-slot1 coordinate targeting is {pc(rich['parameters']['cast_1']['exact_accuracy'])}, versus {pc(retained['parameters']['cast_1']['exact_accuracy'])} ({delta(rich['parameters']['cast_1']['exact_accuracy']-retained['parameters']['cast_1']['exact_accuracy'])} on243 examples, exceeding the2pp guard). The improvement trigger passed; both required guards failed. The point regression and its uncertainty are both retained in the full report.", '',
        'The original65% macro-F1 and65.21% exact-movement targets remain unmet. Passing the historical loss threshold against E02 does not establish a10% improvement over stronger current action-history baselines. No threshold or benchmark was changed to claim success.', '',
        '## Evidence and limits', '',
        '- All433,071 training rows and14,439 original development-validation rows were retained, with whole groups and payload hashes disjoint.',
        '- Recovered1,889,036 earlier personal PRE observations. Full raw whitelisted evidence is retained; neural history uses M01\'s existing253-field observation encoder and a32-field projection.',
        '- Seven causal/matching/accounting tests passed. Saved-model inference matched all four input tensors exactly and reproduced action/parameter outputs on75 real replay targets for each of H01/H02, including natural empty-history cases.',
        '- Only112 development rows have fewer than16 earlier observations (28 movement rows). No missing-history rows were dropped; startup and unavailable-observation conclusions remain limited.',
        '- Both fresh arms have119,392 nominal parameters; M01 has104,160. Measured total training time was522.7s/19 epochs for H01 and684.2s/26 epochs for H02, using the unchanged stopping rule.',
        '- All75 new validation and75 final-test games remain sealed. No further replays, matches, bot changes, deployment or PR.', '',
        'Full per-action precision/recall/F1/support, confusion matrices, targeting regressions, top-k movement, destination error, partial legality, history bins, hashes and exact commands: [RESULTS.md](RESULTS.md). Full engine illegal-action rate is unassessed; the partial observable metric is not a legality certificate.', '']
    (REPORTS/'FINDINGS.md').write_text('\n'.join(lines),encoding='utf-8')
    frozen(REPORTS/'movement-error-diagnosis.json',dict(total_movement_errors=total_errors,direction_change_errors=turn_errors,
        direction_change_error_fraction=turn_errors/total_errors,context_results=rows,postfit_interpretation_only=True,
        original_thresholds_unchanged=True,additional_fits=0))
    source=Path(__file__);copy=WORK/'provenance'/(sha(source)+'_'+source.name)
    if not copy.exists():copy.write_bytes(source.read_bytes())
    frozen(REPORTS/'findings-provenance.json',dict(source=str(source),source_sha256=sha(source),source_snapshot=str(copy),
        original_report_provenance_sha256=sha(REPORTS/'report-provenance.json'),
        frozen_validation_predictions={name:sha(WORK/'runs'/name/'validation-predictions.npz') for name in predictions},
        final_commands_sha256=sha(WORK/'commands.jsonl'),findings_sha256=sha(REPORTS/'FINDINGS.md'),
        diagnosis_sha256=sha(REPORTS/'movement-error-diagnosis.json'),no_new_fits=True))
    print('Recorded objective error diagnosis; frozen fitted study unchanged.',flush=True)


if __name__=='__main__':
    commands=WORK/'commands.jsonl';copy=WORK/'provenance'/('commands-'+sha(commands)+'.jsonl')
    if not copy.exists():copy.write_bytes(commands.read_bytes())
    log_command([sys.executable,'-m','tools.action_predictor.observation_diagnosis'],purpose='Interpret frozen context results and count direction-change destination errors; no fitting')
    diagnose()
