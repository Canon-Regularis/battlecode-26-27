"""Human-readable V4 experiment ledger and complete frozen-benchmark results."""
import csv
import html
import json
from pathlib import Path

import numpy as np

from .benchmark import REPORTS,WORK
from .reliable_train import LABELS


def pct(value):return f'{value:.2%}' if value is not None else 'unassessed'


def write():
    conclusion=json.loads((REPORTS/'conclusion.json').read_text())
    val=json.loads((REPORTS/'validation-evaluation.json').read_text())
    test=json.loads((REPORTS/'test-evaluation.json').read_text())
    lock=json.loads((REPORTS/'selection-lock.json').read_text())
    lines=['# Fish predictor: fixed-benchmark development', '',
        '**The proposed targets were not met consistently.**' if not conclusion['proposed_targets_met_consistently'] else '**The proposed validation targets were met consistently.**', '',
        'No certified untouched Fish games remain. The original whole-group test partition was preserved, sealed during this development, and evaluated only after candidate locking. It was exposed in earlier work and is not a pristine final test.', '',
        'Ten substantive fits: six development configurations and two additional seeds for each validation-selected GRU and stateless configuration. Seed results are sensitivity checks, not an ensemble. No test results select a configuration or seed.', '',
        '## Experiment log', '',
        '| Run | Configuration | Seed | Parameters | Best epoch | Validation macro F1 | Movement exact | Joint NLL |',
        '|---|---|---:|---:|---:|---:|---:|---:|']
    for path in sorted(REPORTS.glob('E[0-9][0-9].json')):
        r=json.loads(path.read_text());m=r['validation']
        lines.append(f'| {path.stem} | {r["config"]["name"]} | {r["seed"]} | {r["parameters"]} | {r["best_epoch"]} | {m["macro_f1"]:.3f} | {pct(m["parameters"]["move"]["exact_accuracy"])} | {m["joint_nll"]:.3f} |')
    lines += ['', 'Checkpoint paths: `.cambc/action-predictor/v4/runs/<run>/model.pt`. Every run retains configuration, checkpoint hash, history and validation predictions. Earlier checkpoints are unchanged.', '',
              '## Proposed targets: validation, all three GRU seeds', '',
              '| Run | Macro F1 >= .65 | Movement gain >= 10 pp | Joint loss reduction >= 10% | No targeting drop > 2 pp |',
              '|---|---:|---:|---:|---:|']
    for name,g in val['comparisons'].items():
        m=val['models'][name]
        labels=['PASS' if g['passed'][k] else 'FAIL' for k in ('macro_f1','movement','joint_loss','targeting')]
        lines.append(f'| {name} | {m["macro_f1"]:.3f}: {labels[0]} | {g["movement_gain"]*100:.2f} pp: {labels[1]} | {pct(g["joint_loss_reduction"])}: {labels[2]} | {labels[3]} |')
    lines += ['', f'Validation-selected references: `{json.dumps(lock["references"],sort_keys=True)}`.', '',
              'Group-bootstrap confidence intervals and paired differences are in `validation-evaluation.json` and `test-evaluation.json`. Resampling unit is a whole match group, with 2,000 paired resamples. Only five validation and five test groups are available; seed variation is reported separately.', '']
    for split,data in [('Validation',val),('Previously exposed final test',test)]:
        lines += [f'## {split}', '',
                  '| Run | Action accuracy | Macro F1 | Joint observable exact | Joint recorded-parameter exact, unknown shops fail | Joint NLL | Observable violations | Assessed commands |',
                  '|---|---:|---:|---:|---:|---:|---:|---:|']
        for name,m in data['models'].items():
            invalid=m['observable_invalid_commands']
            lines.append(f'| {name} | {pct(m["accuracy"])} | {m["macro_f1"]:.3f} | {pct(m["joint_observable_accuracy"])} | {pct(m["strict_full_command_accuracy"])} | {m["joint_nll"]:.3f} | {pct(invalid["rate"])} | {invalid["assessed"]} |')
        lines += ['', '| GRU run | Macro F1, 95% group CI | Movement exact, 95% group CI | Movement gain, 95% paired CI | Joint-loss reduction, 95% paired CI |',
                  '|---|---:|---:|---:|---:|']
        for name in conclusion['gru_runs']:
            ci=data['uncertainty'][name];comparison=data['comparisons'][name]
            fmt=lambda bounds:f'{bounds["low"]:.1%} to {bounds["high"]:.1%}'
            f1=ci['macro_f1']
            lines.append(f'| {name} | {f1["low"]:.3f} to {f1["high"]:.3f} | {fmt(ci["move_exact"])} | {fmt(comparison["paired_movement_uncertainty"]["movement_gain"])} | {fmt(comparison["paired_loss_uncertainty"]["joint_loss_reduction"])} |')
        lines += ['', '| Run | Family | Conditional exact | Joint exact | Top 3 | Top 5 | Mean destination error | Support |',
                  '|---|---|---:|---:|---:|---:|---:|---:|']
        for name in conclusion['gru_runs']+conclusion['stateless_runs']:
            for family in ('move','blocked','attack','cast_0','cast_1','ward','submit','altar','teleport','priority','shop'):
                m=data['models'][name]['parameters'][family]
                error=m.get('penalized_mean_chebyshev_error')
                lines.append(f'| {name} | {family} | {pct(m.get("exact_accuracy"))} | {pct(m["joint_accuracy"])} | {pct(m.get("top3_accuracy"))} | {pct(m.get("top5_accuracy"))} | {error:.3f} | {m["support"]} |' if error is not None else f'| {name} | {family} | unassessed | {pct(m["joint_accuracy"])} | - | - | - | {m["support"]} |')
        for name,m in data['models'].items():
            directory=REPORTS/'tables';directory.mkdir(exist_ok=True)
            stem=split.lower().replace(' ','-')+'-'+name
            with (directory/f'{stem}-actions.csv').open('w',newline='') as f:
                w=csv.DictWriter(f,fieldnames=['action','precision','recall','f1','support','f1_group_ci_low','f1_group_ci_high']);w.writeheader()
                for label,row in zip(LABELS,m['per_class']):
                    ci=data['uncertainty'][name]['action_f1_'+label]
                    w.writerow(dict(action=label,**row,f1_group_ci_low=ci['low'],f1_group_ci_high=ci['high']))
            with (directory/f'{stem}-confusion.csv').open('w',newline='') as f:
                w=csv.writer(f);w.writerow(['actual / predicted',*LABELS]);w.writerows([name,*row] for name,row in zip(LABELS,m['confusion_matrix']))
    chosen=conclusion['gru_runs'][0]
    lines += ['', '## Per-action detail: validation-selected GRU, final exposed test', '',
              '| Action | Precision | Recall | F1 | Support |', '|---|---:|---:|---:|---:|']
    for name,m in zip(LABELS,test['models'][chosen]['per_class']):
        lines.append(f'| {name} | {m["precision"]:.3f} | {m["recall"]:.3f} | {m["f1"]:.3f} | {m["support"]} |')
    lines += ['', '## Data quality, information boundary and remaining limits', '',
        '- Original 170 replay payloads are unique and group assignments are unchanged. Supplemental snapshots are queried at the exact personal PRE cursor; original shared fields are checked against prior evidence. History consists of strictly earlier actions by the same actor, including roots between sampled turns. Utility `(0,0)` coordinates are not treated as genuine prior locations.',
        '- Training-only augmentation adds 37,140 recorded actions in 7,669 complete rare-action turns. It retains all original sampled training actions, deduplicates action IDs and changes neither validation nor test. Shop/ward/blocked/submit/altar/teleport support improves, but selection bias in augmented training and unknown private policy state remain limitations.',
        '- The parameter head uses recorded destination/aim cells, plus a discrete logistic model of exact priority integers. Original attack/cast entity IDs are not stored. Original shop item/count can be unidentifiable; immediate inventory deltas are retained as diagnostic labels only. Joint recorded-parameter scoring counts unsupported shop arguments as failures. Full original API-command accuracy is unassessed; the legacy JSON key `strict_full_command_accuracy` names a recorded-parameter score, not proof of original ID/argument recovery.',
        '- Joint NLL is the mean partially observed action + required coordinate + required priority negative log likelihood. It is not a likelihood for missing original shop arguments. Conditional parameter accuracy uses the true family; joint accuracy additionally requires the predicted family. Outside-window/missing-position labels remain in loss and count as exact-command failures.',
        '- PRE movement and target-geometry masks are inputs/constraints, not future labels. A fixed 1e-4 full-support mixture keeps contradictory recorded labels in the likelihood instead of filtering them. Masks do not establish full engine legality.',
        '- Reported illegal-action information is an observable violation rate with an assessed denominator: exact personal movement-mask violations plus partial resource/readiness checks. **Full engine illegal-action rate is unassessed**, not zero. Predicted blocked attempts are forecasts of recorded failed actions and naturally contribute violations.',
        '- Destination error is Chebyshev error in cells, with a fixed 16-cell penalty for undecodable forecasts. Raw decoded-label error and coverage are also retained in JSON. Top-k movements include all movement rows, and joint top-3 also requires the correct action type.',
        '- These are personal-Fish-view, teacher-forced replay forecasts. Complete own history, gold and private resources are not generally available to an opposing bot. Historical engine 2/3 evidence does not establish deployment compatibility or playing strength.',
        '- No matches, alternate-action simulations, deployments or PRs were created. No strategy labels or strategy-similarity percentage are used.', '',
        'Machine-readable benchmark, design amendments, data receipts, source pins, selection locks and all metrics remain next to this report. The fixed proposed targets were not weakened.']
    (REPORTS/'RESULTS.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    # Compact chart: seed variation is separate from the wider group-bootstrap uncertainty.
    chart=[]
    grus=conclusion['gru_runs'];bases=conclusion['stateless_runs']
    movement_target=val['models'][lock['references']['movement']]['parameters']['move']['exact_accuracy']+.10
    for title,key,threshold in [('Validation action macro F1','macro_f1',.65),('Validation exact movement','movement',movement_target)]:
        chart.append(f'<h3>{title}</h3>')
        for label,names in [('GRU',grus),('Stateless',bases)]:
            values=[val['models'][n]['parameters']['move']['exact_accuracy'] if key=='movement' else val['models'][n][key] for n in names]
            mean=np.mean(values);chart.append(f'<div class="row"><span>{label}, 3 seeds</span><div class="track"><i style="width:{mean*100:.2f}%"></i><em style="left:{threshold*100:.2f}%"></em></div><b>{mean:.1%}</b></div>')
        chart.append(f'<p>Fixed target: {threshold:.1%}. Seed ranges and group uncertainty are reported separately.</p>')
    html_text='''<!doctype html><html><head><meta charset="utf-8"><style>body{margin:0;font:14px var(--font-sans,system-ui);color:var(--foreground)}h3{font-size:15px;font-weight:500;margin:14px 0}.row{display:grid;grid-template-columns:145px 1fr 55px;gap:10px;align-items:center;margin:12px 0}.track{height:18px;position:relative;background:color-mix(in srgb,currentColor 10%,transparent)}i{height:100%;display:block;background:var(--chart-1,steelblue)}em{position:absolute;top:-4px;bottom:-4px;width:2px;background:var(--foreground,currentColor)}b{font-weight:500}p{font-size:12px;opacity:.8}</style></head><body>'''+''.join(chart)+'</body></html>'
    (REPORTS/'comparison.html').write_text(html_text,encoding='utf-8')
    print('Wrote',REPORTS/'RESULTS.md')


if __name__=='__main__':write()
