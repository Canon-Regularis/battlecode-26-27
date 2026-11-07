"""Report every bounded fit, fixed target and measured negative result."""
import csv
import html
import json
from pathlib import Path
import sys

import numpy as np

from .more_replays import frozen,sha
from .observation_study import ROOT,WORK,REPORTS,MORE,OLD,freeze_plan,log_command
from .observation_validate import sealed_audit
from . import reliable_train as rt


def read(path):return json.loads(path.read_text(encoding='utf-8'))
def percent(value):return 'unavailable' if value is None else f'{100*value:.2f}%'
def number(value):return 'unavailable' if value is None else f'{value:.4f}'
def pp(value):return f'{100*value:+.2f} pp'
def ci(value,scale=100):
    if value['low'] is None:return 'unavailable (0 supported draws)'
    return f"[{scale*value['low']:+.2f}, {scale*value['high']:+.2f}] ({value['valid_draws']}/2000 draws)"


def write_csv(name,rows):
    if not rows:return
    fields=list(dict.fromkeys(key for row in rows for key in row))
    with (REPORTS/name).open('w',newline='',encoding='utf-8') as stream:
        writer=csv.DictWriter(stream,fieldnames=fields);writer.writeheader();writer.writerows(rows)


def report():
    freeze_plan();comparison=read(REPORTS/'validation-comparison.json');ready=read(REPORTS/'data-ready.json')
    audit=read(REPORTS/'causal-data-audit.json');roundtrip=read(REPORTS/'inference-roundtrip.json')
    lock=read(REPORTS/'execution-lock.json');plan=read(REPORTS/'plan.json')
    assert roundtrip['passed'] and audit['passed']
    for path,digest in lock['training_sources'].items():assert sha(path)==digest,path
    for path,digest in lock['preserved_checkpoints'].items():assert sha(path)==digest,path
    assert sha(MORE/'combined-train.npz')==plan['train_sha256'] and sha(OLD/'validation.npz')==plan['validation_sha256']
    frozen(REPORTS/'sealed-test-audit-after.json',sealed_audit())
    infos={identifier:read(ROOT/'tools/action_predictor/experiments/v5'/(identifier+'.json')) for identifier in ('M01','M02','M03')}
    new_ids=[identifier for pair in comparison['pairs'] for identifier in (pair['control'],pair['observations'])]
    infos.update({identifier:read(REPORTS/(identifier+'.json')) for identifier in new_ids})
    metrics=[];parameters=[];per_action=[]
    for identifier,info in infos.items():
        s=info['validation'];m=s['parameters']['move'];invalid=s['observable_invalid_commands']
        metrics.append(dict(model=identifier,seed=info['seed'],best_epoch=info['best_epoch'],parameters=info['parameters'],
            action_accuracy=s['accuracy'],action_macro_f1=s['macro_f1'],joint_accuracy=s['strict_full_command_accuracy'],
            joint_parameterized_accuracy=s['joint_parameterized_accuracy'],joint_observed_nll=s['joint_nll'],
            movement_exact=m['exact_accuracy'],movement_joint=m['joint_accuracy'],movement_top3=m['top3_accuracy'],
            movement_top5=m['top5_accuracy'],movement_joint_top3=m['joint_top3_accuracy'],
            movement_chebyshev_error=m['mean_chebyshev_error'],movement_error_coverage=m['destination_error_coverage'],
            movement_penalized_chebyshev_error=m['penalized_mean_chebyshev_error'],
            partial_illegal_rate=invalid['rate'],partial_illegal_count=invalid['invalid'],partial_legality_assessed=invalid['assessed'],
            full_engine_illegal_rate=None,training_seconds=info.get('training_seconds'),elapsed_seconds=info.get('elapsed_seconds'),
            epochs_run=len(info['history']),optimizer_steps=info.get('optimizer_steps'),
            training_seconds_per_step=info['training_seconds']/info['optimizer_steps'] if info.get('optimizer_steps') else None,
            checkpoint_sha256=info['checkpoint_sha256']))
        for family,values in s['parameters'].items():parameters.append(dict(model=identifier,action=family,**values))
        for label,values in zip(rt.LABELS,s['per_class']):per_action.append(dict(model=identifier,action=label,**values))
        matrix=s['confusion_matrix']
        write_csv(identifier+'-confusion.csv',[dict(actual=label,**dict(zip(rt.LABELS,row))) for label,row in zip(rt.LABELS,matrix)])
    write_csv('metrics.csv',metrics);write_csv('parameters.csv',parameters);write_csv('per-action.csv',per_action)
    contexts=[];regressions=[];visual_pairs=[]
    for pair in comparison['pairs']:
        rich_id,control_id=pair['observations'],pair['control'];analysis=read(REPORTS/(rich_id+'-context-comparison.json'))
        for name,result in analysis.items():
            for arm in ('observations','control'):
                values=result[arm];move=values['parameters']['move']
                contexts.append(dict(seed=pair['seed'],context=name,arm=arm,rows=values['rows'],movement_support=move['support'],
                    group_support=json.dumps(values['group_support']),movement_exact=move['exact_accuracy'],movement_joint=move['joint_accuracy'],
                    joint_observed_nll=values['joint_nll'],action_macro_f1=values['macro_f1'],joint_accuracy=values['joint_accuracy'],
                    movement_exact_delta_ci_low=result['paired_intervals']['move_exact']['low'],
                    movement_exact_delta_ci_high=result['paired_intervals']['move_exact']['high'],
                    movement_exact_supported_draws=result['paired_intervals']['move_exact']['valid_draws']))
        for reference,key in [(control_id,'regressions_vs_control'),(pair['retained_id'],'regressions_vs_retained')]:
            for family,values in pair[key].items():
                regressions.append(dict(model=rich_id,seed=pair['seed'],reference=reference,action=family,
                    support=pair['observation_score']['parameters'][family]['support'],**values))
        visual_pairs.append(dict(seed=pair['seed'],control=control_id,observations=rich_id,retained=pair['retained_id'],
            models=[dict(id=name,score=infos[name]['validation']) for name in (pair['retained_id'],control_id,rich_id)],
            intervals=pair['overall_paired_intervals']))
    write_csv('contexts.csv',contexts);write_csv('targeting-regressions.csv',regressions)
    first=comparison['pairs'][0];r,c=first['observation_score'],first['control_score'];m=r['parameters']['move'];cm=c['parameters']['move']
    decision=comparison['repeat_decision'];old_reports=ROOT/'tools/action_predictor/experiments/v4'
    refs=read(old_reports/'selection-lock.json')['references'];fixed=read(old_reports/'validation-evaluation.json')['models']
    movement_target=fixed[refs['movement']]['parameters']['move']['exact_accuracy']+.10
    historical_loss_target=.9*fixed[refs['loss']]['joint_nll']
    lines=[
        '# Personal observation-history experiment (V7)',
        '',comparison['selection'],'',
        f"**{comparison['substantive_fits']} of at most 6 substantive fits completed.** Seed26 observation history versus fresh action+gap control: exact movement {percent(m['exact_accuracy'])} versus {percent(cm['exact_accuracy'])} ({pp(m['exact_accuracy']-cm['exact_accuracy'])}); joint movement {percent(m['joint_accuracy'])} versus {percent(cm['joint_accuracy'])}; observed joint NLL {number(r['joint_nll'])} versus {number(c['joint_nll'])} ({percent(1-r['joint_nll']/c['joint_nll'])} relative reduction).",
        '',
        '## Fixed experiment and causal evidence','',
        f"The protocol in [plan.json](plan.json) was frozen before fitting. Targets and current inputs are byte-identical: 433,071 training actions from 470 games/94 whole groups; 14,439 original development-validation actions from 25 games/5 groups. Payload hashes and groups are disjoint. All 75 new validation games and all 75 final-test games remain sealed. The previously exposed old test is unused.",
        '',
        f"Recovered {ready['frames']:,} unique earlier personal PRE snapshots: {ready['cached_frames']:,} reused and {ready['additional_frames']:,} additionally recovered from eligible games only; {ready['audit_cached_frames']:,} cached snapshots independently reproduced. Missing recoverable observation frames: {ready['missing_observation_frames']}; no target rows dropped. Prefix padding is explicit. Full whitelisted personal snapshots and supplements remain as gzip evidence; neural history uses the existing 253-field M01 representation (including its existing aggregation/truncation), not an exhaustive encoding of every entity field.",
        '',
        'Each frame is the acting champion\'s own personal PRE observation paired with that earlier recorded action. Its PRE precedes its action, which precedes or equals the current prediction PRE, which precedes the target action. Full indexes preserve unsampled own roots; sampled turns are never concatenated as adjacent frames. Inputs contain no target label, future snapshot, omniscient dynamic state, raw replay cursor distance or intent label. Round gaps, ages, own-turn boundaries, frame presence and observation availability are common to both arms. Personal movement/restriction queries and public static geometry were available to the champion at that PRE.',
        '',
        'M01 current encoder, GRU hidden size64, fusion and every prediction head remain unchanged. Only history input is widened from24 to61: 24 prior-action fields, 32 projected earlier-observation fields and5 common gap fields. Control zeros normalized observation values before the same Linear(253,32)+ReLU projection. Both fresh arms have119,392 nominal parameters versus104,160 in M01 (+15,232; +14.62%). Control projection weights (8,096 parameters) cannot learn observation content; its bias can learn an availability-conditioned constant. Thus nominal capacity/computation match, while effective information and feature-dependent capacity differ. Both arms execute the same dense projection and GRU; theoretical history multiply count increases by243,200 per row relative to M01 (excluding activations/biases). Measured paired training times and steps appear below; original M01 timing was not recorded comparably.',
        '',
        'Both arms start from the same seed-preserved M01 initialization, not trained M01 weights; new GRU input columns start at zero. M01 training normalization, class weights, losses, data order/shuffle RNG, AdamW settings and minimum-validation-joint-NLL checkpoint rule are retained. Training stops at35 epochs or patience6; movement peaks never choose checkpoints.',
        '',
        '## Validation results','',
        '| Model | Seed | Action accuracy | Macro F1 | Joint action+parameter | Move exact | Joint move | Move top3 / top5 | Joint NLL |',
        '|---|---:|---:|---:|---:|---:|---:|---:|---:|']
    for row in metrics:
        lines.append(f"| {row['model']} | {row['seed']} | {percent(row['action_accuracy'])} | {percent(row['action_macro_f1'])} | {percent(row['joint_accuracy'])} | {percent(row['movement_exact'])} | {percent(row['movement_joint'])} | {percent(row['movement_top3'])} / {percent(row['movement_top5'])} | {number(row['joint_observed_nll'])} |")
    if len(comparison['pairs'])==3:
        lines += ['','Across the three paired seeds (arithmetic mean; no seed selection):']
        for label,key in [('Exact movement','exact_accuracy'),('Joint movement','joint_accuracy')]:
            rich_values=[pair['observation_score']['parameters']['move'][key] for pair in comparison['pairs']]
            control_values=[pair['control_score']['parameters']['move'][key] for pair in comparison['pairs']]
            lines.append(f"- {label}: observations {percent(float(np.mean(rich_values)))} (range {percent(min(rich_values))}–{percent(max(rich_values))}); control {percent(float(np.mean(control_values)))}; mean paired gain {pp(float(np.mean(np.array(rich_values)-control_values)))}.")
    else:lines += ['','Only one matched seed was fitted because the frozen continuation rule failed. Seed robustness is unestablished; this is not evidence that all possible observation-history encoders are ineffective.']
    lines += ['','Joint accuracy restricted to parameterized commands (coordinate, priority or shop) keeps the same fixed denominator:']
    for pair in comparison['pairs']:
        a,b=pair['observation_score'],pair['control_score']
        lines.append(f"- Seed {pair['seed']}: observations {percent(a['joint_parameterized_accuracy'])}; control {percent(b['joint_parameterized_accuracy'])}; support {a['parameterized_support']} (including {a['strict_unassessed_shop']} unassessed shops counted as failures).")
    lines += ['',
        'Move exact/top-k condition the coordinate head on the recorded action family; joint movement also requires predicting move. Overall joint accuracy follows the unchanged encoded-parameter accounting, with unassessed shops always failing strict joint correctness. Spatial targets are recorded coordinates, not reconstructed intent or guaranteed entity-ID recovery. Observed joint NLL includes only reliably encoded parameters; it is not a complete likelihood for unavailable shop arguments. High overall accuracy includes common end/utility actions; macro F1 and parameterized results must be read alongside it.',
        '',
        '| Model | Move error (Chebyshev cells) | Error coverage | Penalized error | Partial observable violations | Best epoch / epochs | Train seconds / steps |',
        '|---|---:|---:|---:|---:|---:|---:|']
    for row in metrics:
        runtime='unrecorded' if row['training_seconds'] is None else f"{row['training_seconds']:.1f} / {row['optimizer_steps']}"
        lines.append(f"| {row['model']} | {number(row['movement_chebyshev_error'])} | {row['movement_error_coverage']} | {number(row['movement_penalized_chebyshev_error'])} | {row['partial_illegal_count']}/{row['partial_legality_assessed']} ({percent(row['partial_illegal_rate'])}) | {row['best_epoch']} / {row['epochs_run']} | {runtime} |")
    lines += ['',
        'Unknown/out-of-window predicted coordinates receive the original16-cell penalty in penalized error. Full engine illegal-action rate remains **unassessed**. The unchanged partial metric checks the personal movement mask and selected readiness/resource rules; it cannot certify all target rules. No matches or action execution were used to evaluate legality.',
        '', '## Unchanged targets and repetition decision','',
        f"Original targets: macro F1 >=65%; exact movement >={percent(movement_target)} (fixed strongest simple persistence {percent(movement_target-.10)} +10pp); observed joint NLL <={number(historical_loss_target)} (10% below original strongest fixed baseline {refs['loss']}); no targeting coordinate regression >2pp against frozen family references. Strongest retained/fresh action-history baseline NLL is {number(comparison['strongest_available_baseline_joint_nll'])}, making its stronger 10%-reduction threshold {number(comparison['stronger_baseline_loss_target'])}. Historical loss-gate success alone does not establish improvement over these stronger action-history baselines. The prior frozen map candidate S01 (not retained because targeting regressed) remains intact and is not part of this matched history comparison; its previously measured joint NLL is "+number(read(ROOT/'tools/action_predictor/experiments/v6/S01.json')['validation']['joint_nll'])+'.',
        '',
        f"All original targets met across three pairs: **{comparison['original_targets_met_in_three_pairs']}**. All targets including stronger controls: **{comparison['all_targets_including_stronger_controls_met']}**. No thresholds were changed.",
        '',
        'The separately named exploratory allocation trigger was frozen as >=2% loss reduction OR >=1pp exact/joint movement gain OR >=3pp direction-change/near-obstacle exact gain with >=200 move rows, plus every guard relative to both fresh control and M01. Guards: NLL <=1.01*reference, exact/joint movement drop <=0.5pp, macro F1 drop <=1pp, attack/cast0/cast1 coordinate AND family-joint drops <=2pp. This trigger is not a success target.',
        '',f"Seed26 trigger: **{decision['exploratory_trigger']}**; all guards and trigger permit repeats: **{decision['promising']}**. Exact decision and every failed guard: [repeat-decision.json](repeat-decision.json). " + ('The paired comparison was repeated at seeds27/28 within the six-fit budget.' if decision['promising'] else 'The frozen rule stopped this study after the first pair; no replacement fits or seed searches were run.'),
        '', 'Failed seed26 regression guards: '+(', '.join(reference+'/'+guard for reference,values in decision['regression_guards'].items() for guard,passed in values.items() if not passed) or 'none')+'.',
        '', '## Whole-group paired uncertainty','',
        '95% percentile intervals use2,000 paired resamples of the same five original development groups, keeping all games/actions in each group together. These quantify group variation on this reused development benchmark, not uncertainty from an untouched test. They condition on the selected checkpoints and do not rerun training/checkpoint selection for each resample. Rare-context empty resamples are explicitly counted as unsupported; they are not assigned zero accuracy. Only five independent groups limits generalization.',
        '', '| Seed | Exact movement delta (pp) | Joint movement delta (pp) | Macro F1 delta (pp) | Joint accuracy delta (pp) | Joint loss reduction (%) |',
        '|---:|---|---|---|---|---|']
    for pair in comparison['pairs']:
        intervals=pair['overall_paired_intervals']
        lines.append(f"| {pair['seed']} | {ci(intervals['move_exact'])} | {ci(intervals['move_joint'])} | {ci(intervals['macro_f1'])} | {ci(intervals['joint_accuracy'])} | {ci(intervals['joint_loss_reduction'])} |")
    lines += ['','Remaining measured target gaps:']
    for pair in comparison['pairs']:
        s=pair['observation_score'];failed=[key for key,passed in pair['original_target_gates']['passed'].items() if not passed]
        lines.append(f"- Seed {pair['seed']}: macro F1 {percent(s['macro_f1'])} versus65%; move exact {percent(s['parameters']['move']['exact_accuracy'])} versus{percent(movement_target)}; observed joint NLL {number(s['joint_nll'])} versus stronger-baseline threshold {number(comparison['stronger_baseline_loss_target'])}. Failed original gates: {', '.join(failed) or 'none'}. Targeting deltas below identify which families trade off against movement.")
    lines += ['', '## Targeting and action support','',
        'The following coordinate and joint changes are observation history minus the matched control, and minus the retained seed-matched M01/M02/M03. All targeting families and zero-support cases remain in [parameters.csv](parameters.csv) and [targeting-regressions.csv](targeting-regressions.csv). Negative changes are regressions; sparse support is not proof of safety.',
        '', '| Seed | Family | Support | Exact change vs control / retained | Joint change vs control / retained |',
        '|---:|---|---:|---:|---:|']
    for pair in comparison['pairs']:
        for family in ('attack','cast_0','cast_1','ward','submit','altar','teleport','blocked','priority','shop'):
            a,b=pair['regressions_vs_control'][family],pair['regressions_vs_retained'][family]
            fmt=lambda metric:pp(a[metric])+' / '+pp(b[metric]) if metric in a and metric in b else 'unassessed'
            lines.append(f"| {pair['seed']} | {family} | {pair['observation_score']['parameters'][family]['support']} | {fmt('exact_accuracy')} | {fmt('joint_accuracy')} |")
    lines += ['','Paired group intervals for the primary targeting guards (pp):','',
        '| Seed | Target | Exact vs control | Joint vs control | Exact vs retained | Joint vs retained |',
        '|---:|---|---|---|---|---|']
    for pair in comparison['pairs']:
        a,b=pair['overall_paired_intervals'],pair['retained_paired_intervals']
        for family in ('attack','cast_0','cast_1'):
            lines.append(f"| {pair['seed']} | {family} | {ci(a[family+'_exact'])} | {ci(a[family+'_joint'])} | {ci(b[family+'_exact'])} | {ci(b[family+'_joint'])} |")
    lines += ['', 'Seed26 per-action precision, recall, F1 and support (all seeds and full confusion matrices are exported):','',
        '| Action | Support | Control precision / recall / F1 | Observation precision / recall / F1 |',
        '|---|---:|---:|---:|']
    for label,a,b in zip(rt.LABELS,c['per_class'],r['per_class']):
        triple=lambda v:' / '.join(percent(v[k]) for k in ('precision','recall','f1'))
        lines.append(f"| {label} | {b['support']} | {triple(a)} | {triple(b)} |")
    lines += ['', '## Available history and objective contexts','',
        'Direction change compares the recorded move direction sign with the most recent earlier successful own move. Near-obstacle means a public static blocked/out-of-bounds tile within Chebyshev distance2 at personal PRE. Visible-set change uses only personally visible entity identities. These evaluation contexts never enter labels or selection as invented intent. Context findings are exploratory diagnostics; no context is removed from aggregate evaluation.',
        '', '| Seed | Context | All-action rows / move support | Control exact / joint move | Observation exact / joint move | Exact delta interval (pp) |',
        '|---:|---|---:|---:|---:|---|']
    for pair in comparison['pairs']:
        analysis=read(REPORTS/(pair['observations']+'-context-comparison.json'))
        for name,result in analysis.items():
            if name=='overall':continue
            a,b=result['observations']['parameters']['move'],result['control']['parameters']['move']
            lines.append(f"| {pair['seed']} | {name} | {result['observations']['rows']} / {a['support']} | {percent(b['exact_accuracy'])} / {percent(b['joint_accuracy'])} | {percent(a['exact_accuracy'])} / {percent(a['joint_accuracy'])} | {ci(result['paired_intervals']['move_exact'])} |")
    lines += ['','Measured context diagnosis (exact movement changes versus the fresh matched control):']
    for pair in comparison['pairs']:
        analysis=read(REPORTS/(pair['observations']+'-context-comparison.json'));parts=[]
        for name in ('direction_change','same_direction','near_static_obstacle','away_from_static_obstacle','new_own_turn','same_own_turn','visible_set_changed'):
            context=analysis[name];a,b=context['observations']['parameters']['move'],context['control']['parameters']['move']
            if a['support']:parts.append(f"{name} {pp(a['exact_accuracy']-b['exact_accuracy'])} (n={a['support']})")
        lines.append(f"- Seed {pair['seed']}: "+'; '.join(parts)+'.')
    lines += ['',
        'Available-history support, including absent prefix frames, is recorded exactly in [causal-data-audit.json](causal-data-audit.json). Any empty history bin has no measured accuracy; unavailable values are not evidence of benefit. Per-group supports, all paired targeting intervals and joint-loss/context results are in the per-seed context JSONs and [contexts.csv](contexts.csv). Interpretation should distinguish within-turn context from new-turn context, and direction changes from repeated-direction movement.',
        '', '## Verification, provenance and retained artifacts','',
        f"Seven causal/matching/accounting tests passed before fitting. Real replay-to-offline-inference roundtrip passed on {next(iter(roundtrip['models'].values()))['cases']} fixed targets per checked model across25 original development games: all four model input tensors match bitwise, and saved batch action/parameter decoding and observed joint NLL agree. This is separate from the measured prediction results above. See [inference-roundtrip.json](inference-roundtrip.json), [causal-data-audit.json](causal-data-audit.json) and [sealed-test-audit-after.json](sealed-test-audit-after.json).",
        '',
        'Offline inference uses `ObservationPredictor` with one instance per actor/game. Call `observe` for every actual earlier own action in exact order, preserving its personal PRE snapshot; use `observation=None` for an unavailable snapshot instead of skipping the action. Call `predict` with the current personal PRE before the next action. Forecasts are never appended as if observed. The interface rejects backwards/future cursors and mixed actors/perspectives, but relies on the caller supplying the complete own-action stream; the replay preparation verifies completeness against the full recorded index. No robustness claim is made for silently missing actions or for missing observations beyond the measured prefix support.',
        '',
        f"Python {sys.version.split()[0]}, torch {lock['torch']}, numpy {lock['numpy']}; deterministic CPU training with4 threads. Every previous study file and baseline checkpoint remains unchanged. Every fit's selected/best model weights, latest resumable optimizer/RNG state, training history, failure receipts if any, evidence and command ledger are retained under `{WORK}`. Nothing was launched as a match, deployed, downloaded or submitted as a PR.",
        '', 'Exact top-level commands (additional per-game Node extraction commands and query hashes are in `v7/commands.jsonl`):','',
        '```powershell',
        '.venv-action-predictor/Scripts/python.exe -m tools.action_predictor.observation_study',
        '.venv-action-predictor/Scripts/python.exe -m tools.action_predictor.observation_data --audit',
        '.venv-action-predictor/Scripts/python.exe -m tools.action_predictor.observation_data',
        '.venv-action-predictor/Scripts/python.exe -m tools.action_predictor.observation_validate',
        '.venv-action-predictor/Scripts/python.exe -m tools.action_predictor.observation_train',
        '.venv-action-predictor/Scripts/python.exe -m tools.action_predictor.observation_roundtrip '+' '.join(new_ids),
        '.venv-action-predictor/Scripts/python.exe -m tools.action_predictor.observation_report',
        '```','',
        'Full dataset, code/configuration, snapshot, reader/WASM, checkpoint and command hashes: [execution-lock.json](execution-lock.json), [data-ready.json](data-ready.json), [report-provenance.json](report-provenance.json). Reproduction uses the frozen local replay evidence; the extraction command never downloads games. Existing frozen studies and reserved partitions must not be regenerated or inspected to improve this result.',
        '']
    (REPORTS/'RESULTS.md').write_text('\n'.join(lines),encoding='utf-8')
    draw_html(visual_pairs,comparison)
    source_hashes={str(path.relative_to(ROOT)):sha(path) for path in (ROOT/'tools/action_predictor').glob('observation*') if path.is_file()}
    snapshots=WORK/'report-provenance';snapshots.mkdir(exist_ok=True)
    for name,digest in source_hashes.items():
        source=ROOT/name;copy=snapshots/(digest+'_'+source.name)
        if not copy.exists():copy.write_bytes(source.read_bytes())
    frozen(REPORTS/'report-provenance.json',dict(sources=source_hashes,commands_sha256=sha(WORK/'commands.jsonl'),
        plan_sha256=sha(REPORTS/'plan.json'),execution_lock_sha256=sha(REPORTS/'execution-lock.json'),
        data_ready_sha256=sha(REPORTS/'data-ready.json'),roundtrip_sha256=sha(REPORTS/'inference-roundtrip.json'),
        validation_comparison_sha256=sha(REPORTS/'validation-comparison.json'),
        outputs={p.name:sha(p) for p in REPORTS.iterdir() if p.suffix in ('.csv','.md','.html')},
        all_previous_studies_and_checkpoints_unchanged=True))
    print('Observation-history measured report written:',REPORTS/'RESULTS.md',flush=True)


def draw_html(pairs,comparison):
    payload=json.dumps(pairs).replace('</','<\\/')
    markup='''<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Fish personal observation history</title><style>
*{box-sizing:border-box}body{margin:0;color:var(--foreground);font:14px var(--font-sans,system-ui,sans-serif)}main{width:100%}p{color:var(--muted-foreground);line-height:1.5}select{background:var(--secondary);color:var(--foreground);border:1px solid var(--border);border-radius:var(--radius,6px);padding:8px}.legend{display:flex;gap:18px;flex-wrap:wrap;margin:20px 0}.legend span:before{content:"";display:inline-block;width:11px;height:11px;background:var(--c);margin-right:7px;border-radius:2px}.panel{background:var(--card);border:1px solid var(--border);border-radius:var(--radius,12px);padding:16px;margin:16px 0}h2{font-size:16px;margin:0 0 14px}.metric{margin:16px 0 24px}.label{margin-bottom:7px}.barrow{display:grid;grid-template-columns:48px 1fr 65px;align-items:center;gap:9px;margin:7px 0;font-variant-numeric:tabular-nums}.track{background:var(--secondary);height:13px;border-radius:3px;overflow:hidden}.bar{height:100%;background:var(--c)}table{width:100%;border-collapse:collapse;font-variant-numeric:tabular-nums}td,th{text-align:left;padding:10px 6px;border-bottom:1px solid var(--border)}.small{font-size:12px}.status{border-left:3px solid var(--warning);padding:4px 12px;color:var(--warning)}.axis{font-size:11px;color:var(--muted-foreground);display:flex;justify-content:space-between;margin-left:57px;margin-right:74px}footer{color:var(--muted-foreground);font-size:12px;line-height:1.5}
</style><main><p>Matched GRUs · original development validation only · 14,439 actions / 25 games / 5 groups</p><div class="status">STATUS</div><p><label>Matched seed <select id="seed"></select></label></p><div class="legend"><span style="--c:var(--muted-foreground,#8390a5)">Retained action GRU</span><span style="--c:var(--chart-1,#3577be)">Fresh action + gap control</span><span style="--c:var(--chart-2,#1b997c)">Personal observation history</span></div><section class="panel"><h2>Recorded action and movement prediction</h2><div id="bars"></div><div class="axis"><span>0%</span><span>50%</span><span>100%</span></div></section><section class="panel"><h2>Joint prediction loss and paired uncertainty</h2><table id="loss"></table><p id="intervals" class="small"></p></section><footer>Exact movement conditions on recorded move type; joint movement requires the predicted action type too. Whole-group paired percentile intervals use 2,000 resamples of five development groups. These are reused development results, not an untouched-test result. All 75 new validation and 75 final-test games remain sealed. Fixed movement target: 65.21%; macro F1 target: 65%. No matches, deployment or PR.</footer></main><script>
const data=PAYLOAD,colors=['var(--muted-foreground,#8390a5)','var(--chart-1,#3577be)','var(--chart-2,#1b997c)'],sel=document.querySelector('#seed');
for(const d of data){const o=document.createElement('option');o.textContent=d.seed;o.value=d.seed;sel.append(o)}
const pc=x=>(x*100).toFixed(2)+'%',rng=x=>x.low===null?'unavailable':'['+(100*x.low).toFixed(2)+', '+(100*x.high).toFixed(2)+']';
function render(){const d=data.find(x=>x.seed==sel.value);const defs=[['Exact movement',s=>s.parameters.move.exact_accuracy],['Joint action + movement',s=>s.parameters.move.joint_accuracy],['Action macro F1',s=>s.macro_f1],['Joint action + encoded parameter',s=>s.strict_full_command_accuracy]];
document.querySelector('#bars').innerHTML=defs.map(([label,get])=>'<div class="metric"><div class="label">'+label+'</div>'+d.models.map((m,i)=>'<div class="barrow"><span>'+m.id+'</span><div class="track"><div class="bar" style="--c:'+colors[i]+';width:'+get(m.score)*100+'%"></div></div><b>'+pc(get(m.score))+'</b></div>').join('')+'</div>').join('');
document.querySelector('#loss').innerHTML='<tr><th>Model</th><th>Observed joint NLL ↓</th></tr>'+d.models.map(m=>'<tr><td>'+m.id+'</td><td>'+m.score.joint_nll.toFixed(4)+'</td></tr>').join('');
const a=d.models[2].score,b=d.models[1].score;document.querySelector('#intervals').innerHTML='Observation − matched control: exact movement <b>'+((a.parameters.move.exact_accuracy-b.parameters.move.exact_accuracy)*100).toFixed(2)+' pp</b>, group interval '+rng(d.intervals.move_exact)+' pp. Joint movement interval '+rng(d.intervals.move_joint)+' pp. Relative joint-loss reduction '+pc(1-a.joint_nll/b.joint_nll)+', interval '+rng(d.intervals.joint_loss_reduction)+'%.';}
sel.addEventListener('change',render);render();</script>'''
    status=f"{comparison['substantive_fits']}/6 fits completed. "+('Fixed targets met across three pairs.' if comparison['all_targets_including_stronger_controls_met'] else 'Fixed targets not met consistently; M01 retained.')
    (REPORTS/'comparison.html').write_text(markup.replace('STATUS',html.escape(status)).replace('PAYLOAD',payload),encoding='utf-8')


if __name__=='__main__':
    log_command([sys.executable,'-m','tools.action_predictor.observation_report'],purpose='Report all bounded fits, context supports, uncertainty and unchanged targets')
    report()
