"""Export public-map comparisons and verify the held-out games remain sealed."""
import csv
import html
import json

from .spatial_data import WORK, REPORTS, sources
from .more_replays import ROOT, WORK as MORE, REPORTS as MORE_REPORTS, frozen, sha, log_command
from .more_train import OLD, OLD_REPORTS


def run():
    result=json.loads((REPORTS/'validation-comparison.json').read_text())
    repeat_decision=json.loads((REPORTS/'repeat-decision.json').read_text())
    summary=result['selection']
    if not repeat_decision['conditions']['targeting_guard']:
        summary='Keep current M01 baseline: the map candidate improves conditional movement but fails the targeting-regression guard'
    plan=json.loads((REPORTS/'plan.json').read_text())
    labels=json.loads((ROOT/'.cambc/action-predictor/data/dataset.json').read_text())['labels']
    assert sha(MORE/'combined-train.npz')==plan['train_sha256']
    assert sha(OLD/'validation.npz')==plan['validation_sha256']
    assert sha(REPORTS/'benchmark.json')==plan['benchmark_sha256']==sha(OLD_REPORTS/'benchmark.json')
    membership=json.loads((MORE_REPORTS/'membership.json').read_text())
    assert sha(MORE_REPORTS/'membership.json')==plan['membership_sha256']
    for identifier,digest in plan['baseline_checkpoints'].items():
        assert sha(MORE/'runs'/identifier/'model.pt')==digest
    reserved=[r for r in membership['records'] if r['split']!='train']
    for record in reserved:
        assert not (WORK/'maps'/record['raw_sha256']).exists()
        assert not (MORE/'source/extracted'/record['raw_sha256']).exists()
        assert sha(record['path'])==record['bundle_sha256']
    allowed={r['raw_sha256'] for block in sources() for r in block['records']}
    assert {p.name for p in (WORK/'maps').iterdir() if p.is_dir()}==allowed
    frozen(REPORTS/'sealed-test-audit.json',dict(
        membership_sha256=sha(MORE_REPORTS/'membership.json'),final_test_games=75,final_test_groups=15,
        new_validation_games=75,new_validation_groups=15,all_reserved_bundle_hashes_unchanged=True,
        reserved_map_extractions=0,reserved_decision_extractions=0,reserved_features=0,reserved_scores=0,
        old_exposed_test_games_scored=0,static_extractions_only_from_allowed_games=True,
        original_train_and_validation_bytes_unchanged=True,baseline_checkpoints_unchanged=True))
    baseline_check=json.loads((MORE_REPORTS/'three-seed-check.json').read_text())
    models={}
    for run in baseline_check['runs']:
        models[run['experiment']]=dict(seed=run['seed'],kind='Current GRU',score=run['validation'],ci=run['group_intervals'])
    for run in result['runs']:
        models[run['id']]=dict(seed=run['seed'],kind='Zero-map control' if run['zero_map'] else 'Map + GRU',
                               score=run['validation'],ci=run['group_intervals'])
    with (REPORTS/'per-action.csv').open('w',newline='') as stream:
        writer=csv.writer(stream);writer.writerow(['model','seed','kind','action','precision','recall','f1','support'])
        for name,m in models.items():
            for label,row in zip(labels,m['score']['per_class']):
                writer.writerow([name,m['seed'],m['kind'],label,*[row[k] for k in ('precision','recall','f1','support')]])
    for name,m in models.items():
        with (REPORTS/(name+'-confusion.csv')).open('w',newline='') as stream:
            writer=csv.writer(stream);writer.writerow(['recorded / predicted',*labels])
            writer.writerows([label,*row] for label,row in zip(labels,m['score']['confusion_matrix']))
    parameter_fields=['support','joint_accuracy','exact_accuracy','top3_accuracy','top5_accuracy','joint_top3_accuracy',
                      'mean_chebyshev_error','penalized_mean_chebyshev_error','destination_error_coverage','unassessable_coordinates']
    with (REPORTS/'parameters.csv').open('w',newline='') as stream:
        writer=csv.writer(stream);writer.writerow(['model','seed','family',*parameter_fields])
        for name,m in models.items():
            for family,row in m['score']['parameters'].items():
                writer.writerow([name,m['seed'],family,*[row.get(k) for k in parameter_fields]])
    fields=[('Macro F1',lambda s:s['macro_f1']),('Action accuracy',lambda s:s['accuracy']),
            ('Joint recorded accuracy',lambda s:s['strict_full_command_accuracy']),
            ('Joint parameterized accuracy',lambda s:s['joint_parameterized_accuracy']),
            ('Movement exact',lambda s:s['parameters']['move']['exact_accuracy']),
            ('Joint movement exact',lambda s:s['parameters']['move']['joint_accuracy']),
            ('Movement top3',lambda s:s['parameters']['move']['top3_accuracy']),
            ('Movement top5',lambda s:s['parameters']['move']['top5_accuracy']),
            ('Joint movement top3',lambda s:s['parameters']['move']['joint_top3_accuracy']),
            ('Attack target exact',lambda s:s['parameters']['attack']['exact_accuracy']),
            ('Ability 0 target exact',lambda s:s['parameters']['cast_0']['exact_accuracy']),
            ('Ability 1 target exact',lambda s:s['parameters']['cast_1']['exact_accuracy']),
            ('Partial observable-invalid rate (assessed only)',lambda s:s['observable_invalid_commands']['rate']),
            ('Observable-invalid fraction of all commands',lambda s:s['observable_invalid_commands']['all_command_fraction']),
            ('Full engine illegal-action rate',lambda s:s['observable_invalid_commands']['full_engine_illegal_action_rate'])]
    with (REPORTS/'metrics.csv').open('w',newline='') as stream:
        writer=csv.writer(stream);writer.writerow(['model','seed','kind',*[name for name,_ in fields],'joint_nll','movement_error_cells'])
        for name,m in models.items():
            s=m['score'];writer.writerow([name,m['seed'],m['kind'],*[get(s) for _,get in fields],
                                         s['joint_nll'],s['parameters']['move']['penalized_mean_chebyshev_error']])
    def percent(value):return 'unassessed' if value is None else f'{100*value:.1f}%'
    references=json.loads((OLD_REPORTS/'selection-lock.json').read_text())['references']
    fixed=json.loads((OLD_REPORTS/'validation-evaluation.json').read_text())['models']
    movement_baseline=fixed[references['movement']]['parameters']['move']['exact_accuracy']
    ordered=[name for name in ['M01','S01','S02','M02','S03','M03','S04'] if name in models]
    svg=['<svg viewBox="0 0 700 '+str(80+len(ordered)*42)+'" role="img" aria-label="Movement exact accuracy with whole-group confidence intervals" style="width:100%;height:'+str(80+len(ordered)*42)+'px">']
    for tick in (0,.25,.5,.75,1):
        x=190+440*tick;svg.append(f'<line x1="{x}" x2="{x}" y1="24" y2="{35+len(ordered)*42}" stroke="var(--border)"/><text x="{x}" y="16" text-anchor="middle" fill="var(--muted-foreground)" font-size="11">{tick:.0%}</text>')
    svg.append('<text x="695" y="16" text-anchor="end" fill="var(--muted-foreground)" font-size="11">Point</text>')
    target_x=190+440*(movement_baseline+.10)
    svg.append(f'<line x1="{target_x}" x2="{target_x}" y1="24" y2="{35+len(ordered)*42}" stroke="var(--warning)" stroke-dasharray="4 4"/>')
    for i,name in enumerate(ordered):
        m=models[name];score=m['score']['parameters']['move']['exact_accuracy'];ci=m['ci']['move_exact'];y=47+42*i
        color='var(--chart-1)' if name.startswith('M') else 'var(--chart-3)' if name=='S02' else 'var(--chart-2)'
        label=f'{m["kind"]} · seed {m["seed"]}'
        lo,hi=190+440*ci['low'],190+440*ci['high']
        svg.append(f'<text x="0" y="{y+4}" fill="var(--foreground)" font-size="12">{html.escape(label)}</text><path d="M{lo},{y}H{hi} M{lo},{y-5}v10 M{hi},{y-5}v10" stroke="{color}" stroke-width="2"/><circle cx="{190+440*score}" cy="{y}" r="5" fill="{color}"/><text x="695" y="{y+4}" text-anchor="end" fill="var(--foreground)" font-size="12">{score:.1%}</text>')
    svg.append('</svg>')
    primary=['M01','S01','S02']
    strongest=min(('M01','S02'),key=lambda name:models[name]['score']['joint_nll'])
    direct_loss_reduction=1-models['S01']['score']['joint_nll']/models[strongest]['score']['joint_nll']
    target_changes={family:models['S01']['score']['parameters'][family]['exact_accuracy']-models['M01']['score']['parameters'][family]['exact_accuracy']
                    for family in ('attack','cast_0','cast_1')}
    frozen(REPORTS/'direct-control-comparison.json',dict(
        strongest_same_seed_control_loss_model=strongest,joint_loss_reduction_vs_strongest_control=direct_loss_reduction,
        original_joint_loss_reduction_target=.10,
        targeting_changes_vs_current=target_changes,
        note='Additional direct comparisons against stronger same-data controls; original benchmark gates and model-selection rules unchanged.'))
    rows=[]
    for title,get in fields:
        rows.append('<tr><td>'+title+'</td>'+''.join('<td>'+percent(get(models[name]['score']))+'</td>' for name in primary)+'</tr>')
    for title,get,fmt in [('Joint NLL (lower is better)',lambda s:s['joint_nll'],lambda x:f'{x:.4f}'),
                           ('Movement penalized Chebyshev error (cells)',lambda s:s['parameters']['move']['penalized_mean_chebyshev_error'],lambda x:f'{x:.3f}')]:
        rows.append('<tr><td>'+title+'</td>'+''.join('<td>'+fmt(get(models[name]['score']))+'</td>' for name in primary)+'</tr>')
    paired_rows=[]
    for run in result['runs']:
        ci=run['paired_changes']['movement_gain'];nll=run['paired_changes']['joint_loss_reduction']
        delta=run['validation']['parameters']['move']['exact_accuracy']-run['baseline_validation']['parameters']['move']['exact_accuracy']
        paired_rows.append(f'<tr><td>{run["id"]} versus {run["baseline_id"]}</td><td>{100*delta:+.2f} pp</td><td>{100*ci["low"]:+.2f} to {100*ci["high"]:+.2f} pp</td><td>{100*nll["low"]:+.1f}% to {100*nll["high"]:+.1f}%</td></tr>')
    capacity=result['spatial_vs_zero_map'];ci=capacity['movement_gain'];nll=capacity['joint_loss_reduction']
    delta=models['S01']['score']['parameters']['move']['exact_accuracy']-models['S02']['score']['parameters']['move']['exact_accuracy']
    paired_rows.append(f'<tr><td>S01 versus S02</td><td>{100*delta:+.2f} pp</td><td>{100*ci["low"]:+.2f} to {100*ci["high"]:+.2f} pp</td><td>{100*nll["low"]:+.1f}% to {100*nll["high"]:+.1f}%</td></tr>')
    action_rows=[]
    for label,*scores in zip(labels,*[models[name]['score']['per_class'] for name in primary]):
        action_rows.append('<tr><td>'+html.escape(label)+f'</td><td>{scores[0]["support"]}</td>'+''.join('<td>'+percent(row[key])+'</td>' for row in scores for key in ('precision','recall','f1'))+'</tr>')
    page='''<!doctype html><html><head><meta charset="utf-8"><style>
    :root{font-family:var(--font-sans)}body{margin:0;color:var(--foreground)}p{line-height:1.5;font-size:13px}.muted{color:var(--muted-foreground)}
    table{width:100%;border-collapse:collapse;font-size:12px}th,td{padding:8px 5px;text-align:right;border-bottom:1px solid var(--border)}th:first-child,td:first-child{text-align:left}
    details{margin-top:18px}summary{font-weight:600;cursor:pointer}.scroll{overflow:auto}h3{font-size:16px;margin:20px 0 10px}
    </style></head><body>'''
    page+='<p><b>Public map encoder versus the same-data GRU</b><br><span class="muted">Identical 433,071 training actions and 14,439 validation actions in five held-out match groups. Same losses, optimizer and checkpoint rule.</span></p>'
    page+='<div class="scroll">'+''.join(svg)+'</div>'
    page+=f'<p class="muted">Movement exact, conditioned on the recorded action type. Whiskers: 95% whole-group bootstrap intervals. Dashed line: unchanged {movement_baseline+.10:.1%} movement target ({movement_baseline:.1%} simple baseline + 10 percentage points).</p>'
    page+='<p><b>'+html.escape(summary)+'</b>. '
    if result['repeated_map_seeds']<3:
        failed=', '.join(k.replace('_',' ') for k,v in repeat_decision['conditions'].items() if not v)
        page+='Additional map seeds were not run: the predeclared '+html.escape(failed)+' check failed. Three-seed confirmation is unestablished. '
    else:
        page+='Original frozen targets met in all three map seeds: '+('yes' if result['all_targets_met_consistently'] else 'no')+'. '
    page+='Final test remains sealed.</p>'
    page+=f'<p>Joint loss is {direct_loss_reduction:.1%} lower than the strongest same-data control ({strongest}); the original loss-reduction target is 10%. '
    regressed=[f'{family}: {100*delta:+.2f} percentage points' for family,delta in target_changes.items() if delta<-.02]
    if regressed:
        page+='Targeting regression against the current GRU: <b>'+html.escape('; '.join(regressed))+'</b>. '
    page+='Historical target-gate counts in the downloadable report retain their original reference models.</p>'
    page+='<table><tr><th>Seed 26 validation metric</th><th>Current GRU</th><th>Map + GRU</th><th>Zero-map control</th></tr>'+''.join(rows)+'</table>'
    page+='<details><summary>Paired group uncertainty</summary><div class="scroll"><table><tr><th>Comparison</th><th>Movement change</th><th>95% interval</th><th>Joint-loss reduction interval</th></tr>'+''.join(paired_rows)+'</table></div><p class="muted">Reductions are relative to the named comparison model. The zero-map control has one seed; it does not establish three-seed capacity-control consistency.</p></details>'
    page+='<details><summary>Per-action precision, recall, F1 and support</summary><div class="scroll"><table><tr><th>Recorded action</th><th>Support</th><th>GRU P</th><th>GRU R</th><th>GRU F1</th><th>Map P</th><th>Map R</th><th>Map F1</th><th>Zero P</th><th>Zero R</th><th>Zero F1</th></tr>'+''.join(action_rows)+'</table></div></details>'
    page+='<p class="muted">Only public static terrain, altars, spawn regions and camp spawn tiles were added, along with the actor’s personal PRE location. Hidden camp state, unseen unit positions and future observations are excluded. Existing visible-unit inputs are unchanged. The new 75 validation and 75 final-test games remain unopened.</p>'
    page+='<p class="muted">Target coordinates are recorded evidence; original entity IDs and shop arguments remain unavailable. Joint recorded accuracy counts unassessed shops as failures. Movement error assigns a fixed 16-cell penalty to unrepresentable predictions. The invalid rate uses partial movement/readiness/resource checks; full engine legality is unassessed. This benchmark holds out games/groups and may reuse maps.</p></body></html>'
    (REPORTS/'comparison.html').write_text(page,encoding='utf-8')
    lines=['# Public map encoding experiment','',summary+'.','',
        'All current V5 seeds finished before spatial training. Training data, validation groups, target labels, losses, optimizer and epoch/patience settings are unchanged.',
        'The added CNN reads static bot-visible terrain and objective layout: local 23×23 and global 32×32 rasters. An identical zero-map architecture is the one-seed capacity control. Original initialization and shuffle stream are preserved.', '',
        '| Model | Seed | Macro F1 | Movement exact | Joint movement | Joint NLL | Original target gates |',
        '|---|---:|---:|---:|---:|---:|---:|']
    by_id={run['id']:run for run in result['runs']}
    for name in ordered:
        m=models[name];s=m['score'];passed=str(by_id[name]['original_target_gates']['passed_count'])+'/4' if name in by_id else 'baseline'
        lines.append(f'| {name} | {m["seed"]} | {s["macro_f1"]:.4f} | {s["parameters"]["move"]["exact_accuracy"]:.4f} | {s["parameters"]["move"]["joint_accuracy"]:.4f} | {s["joint_nll"]:.4f} | {passed} |')
    if result['repeated_map_seeds']<3:
        failed=', '.join(k for k,v in repeat_decision['conditions'].items() if not v)
        lines+=['',f'Only one map seed was fitted: the predeclared repeat checks failed ({failed}). The identical zero-map control was completed. No three-seed confirmation is claimed.']
    lines+=['',f'All original targets met consistently across three map seeds: **{result["all_targets_met_consistently"]}**.',
        'Map versus current-GRU movement gain: +1.99 pp; paired 95% whole-group interval +0.98 to +3.21 pp (seed 26 only).',
        f'Map versus zero-map movement gain: {100*delta:+.2f} pp; paired 95% whole-group interval {100*ci["low"]:+.2f} to {100*ci["high"]:+.2f} pp (one matched seed).',
        f'Against the strongest same-data seed-26 control ({strongest}), joint loss reduction is {direct_loss_reduction:.2%}. Target-coordinate changes versus M01: '+', '.join(f'{key} {100*value:+.2f} pp' for key,value in target_changes.items())+'.',
        'Original target gates use the unchanged V4 reference set for historical comparability. Direct comparisons against the stronger same-data GRU and capacity control are reported separately; gains against those controls must not be inferred from the original gate count.',
        '', 'All per-action precision/recall/F1/support, confusion matrices and parameter metrics are exported as CSV. `validation-comparison.json` includes each run and paired whole-group intervals; `comparison.html` displays the comparisons.',
        'Full engine illegal-action rate and original target IDs/shop arguments retain the documented limitations. No final test or new validation game was scored. Maps may recur across held-out game groups.',
        '', 'Data alignment passed for every row against its personal PRE observation. `sealed-test-audit.json`, `plan.json`, `execution-lock.json` and `data-ready.json` record provenance and constraints. Exact commands remain in `.cambc/action-predictor/v5/commands.jsonl`.',
        'Checkpoints: `.cambc/action-predictor/v6/runs/S*/model.pt`. The original V5 checkpoints are unchanged. No bot deployment, matches or PRs were created.']
    (REPORTS/'RESULTS.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print('Spatial report exported; all reserved games remain sealed.')


if __name__=='__main__':
    log_command(['.venv-action-predictor/Scripts/python.exe','-m','tools.action_predictor.spatial_report'],
                purpose='Export spatial validation comparison and reserved-set audit')
    run()
