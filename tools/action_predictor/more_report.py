"""Export the controlled-retrain validation results; never load test games."""
import csv
import html
import json

from .more_replays import ROOT, REPORTS, frozen, sha


def run():
    result = json.loads((REPORTS / 'validation-comparison.json').read_text())
    labels = json.loads((ROOT / '.cambc/action-predictor/data/dataset.json').read_text())['labels']
    models = [('Original E06', result['old']), ('More-data M01', result['more_data'])]
    reference_path = REPORTS.parent / 'v4/validation-evaluation.json'
    references = json.loads(reference_path.read_text())['models']
    reference_ids = ['frequency-frequency', 'frequency-persistence', 'frequency-nearest',
                     'frequency-lowest-health', 'E02', 'E05']
    fixed = {name: references[name] for name in reference_ids}
    frozen(REPORTS / 'fixed-baseline-reference.json', dict(
        source_sha256=sha(reference_path), models=fixed,
        scope='Original frozen training/validation reference results; baselines held fixed for the initial more-data comparison.',
    ))
    with (REPORTS / 'baseline-comparison.csv').open('w', newline='') as stream:
        writer = csv.writer(stream)
        writer.writerow(['model', 'macro_f1', 'action_accuracy', 'movement_exact', 'joint_nll', 'joint_recorded_accuracy'])
        for name, score in [*fixed.items(), *models]:
            writer.writerow([name, score['macro_f1'], score['accuracy'], score['parameters']['move']['exact_accuracy'],
                             score['joint_nll'], score['strict_full_command_accuracy']])
    with (REPORTS / 'per-action.csv').open('w', newline='') as stream:
        writer = csv.writer(stream)
        writer.writerow(['model', 'action', 'precision', 'recall', 'f1', 'support'])
        for name, score in models:
            for label, row in zip(labels, score['per_class']):
                writer.writerow([name, label, *[row[k] for k in ('precision', 'recall', 'f1', 'support')]])
    for name, score in models:
        identifier = 'M01' if name.startswith('More') else 'E06'
        with (REPORTS / (identifier + '-confusion.csv')).open('w', newline='') as stream:
            writer = csv.writer(stream)
            writer.writerow(['recorded / predicted', *labels])
            writer.writerows([label, *row] for label, row in zip(labels, score['confusion_matrix']))
    with (REPORTS / 'parameters.csv').open('w', newline='') as stream:
        writer = csv.writer(stream)
        fields = ['support', 'joint_accuracy', 'exact_accuracy', 'top3_accuracy', 'top5_accuracy', 'joint_top3_accuracy',
                  'penalized_mean_chebyshev_error', 'unassessable_coordinates']
        writer.writerow(['model', 'parameter_family', *fields])
        for name, score in models:
            for family, row in score['parameters'].items():
                writer.writerow([name, family, *[row.get(k) for k in fields]])

    def pct(value):
        return '\u2014' if value is None else f'{100 * value:.1f}%'

    metrics = [('Action macro F1', 'macro_f1', lambda s: s['macro_f1']),
               ('Movement exact', 'move_exact', lambda s: s['parameters']['move']['exact_accuracy']),
               ('Joint recorded accuracy', 'joint_accuracy', lambda s: s['strict_full_command_accuracy'])]
    chart = ['<svg viewBox="0 0 700 255" role="img" aria-label="Original versus more-data validation metrics" style="width:100%;height:255px">']
    for tick in (0, .25, .5, .75, 1):
        y = 215 - 175 * tick
        chart.append(f'<line x1="45" x2="690" y1="{y}" y2="{y}" stroke="var(--border)"/><text x="4" y="{y+4}" fill="var(--muted-foreground)" font-size="11">{tick:.0%}</text>')
    for j, (title, interval_key, get) in enumerate(metrics):
        center = 150 + 220 * j
        for i, (name, score) in enumerate(models):
            value = get(score); x = center - 56 + i * 64; y = 215 - 175 * value
            color = f'var(--chart-{i+1})'
            chart.append(f'<rect x="{x}" y="{y}" width="48" height="{215-y}" rx="3" fill="{color}"/><text x="{x+24}" y="{y-7}" text-anchor="middle" font-size="12" fill="var(--foreground)">{value:.1%}</text>')
            interval = result[('old' if i == 0 else 'new') + '_group_intervals'][interval_key]
            lo, hi = interval['low'], interval['high']
            if lo is not None:
                yl, yh = 215 - 175 * lo, 215 - 175 * hi
                chart.append(f'<path d="M{x+24},{yl}V{yh} M{x+17},{yl}h14 M{x+17},{yh}h14" stroke="var(--foreground)" stroke-width="1.5" fill="none"/>')
        chart.append(f'<text x="{center}" y="240" text-anchor="middle" font-size="12" fill="var(--foreground)">{title}</text>')
    chart.append('</svg>')
    rows = []
    extras = [('Action accuracy', lambda s: pct(s['accuracy'])),
              ('Observed joint NLL (lower is better)', lambda s: f'{s["joint_nll"]:.4f}'),
              ('Joint accuracy on parameterized actions', lambda s: pct(s.get('joint_parameterized_accuracy'))),
              ('Joint movement exact', lambda s: pct(s['parameters']['move']['joint_accuracy'])),
              ('Movement top 3', lambda s: pct(s['parameters']['move']['top3_accuracy'])),
              ('Movement top 5', lambda s: pct(s['parameters']['move']['top5_accuracy'])),
              ('Joint movement top 3', lambda s: pct(s['parameters']['move']['joint_top3_accuracy'])),
              ('Movement penalized Chebyshev error (cells)', lambda s: f'{s["parameters"]["move"]["penalized_mean_chebyshev_error"]:.3f}'),
              ('Attack target exact', lambda s: pct(s['parameters']['attack']['exact_accuracy'])),
              ('Ability 0 target exact', lambda s: pct(s['parameters']['cast_0']['exact_accuracy'])),
              ('Ability 1 target exact', lambda s: pct(s['parameters']['cast_1']['exact_accuracy'])),
              ('Observable-invalid rate (partial checks)', lambda s: pct(s['observable_invalid_commands']['rate']))]
    for title, get in extras:
        rows.append('<tr><td>' + title + '</td>' + ''.join('<td>' + get(score) + '</td>' for _, score in models) + '</tr>')
    action_rows = []
    for label, before, after in zip(labels, result['old']['per_class'], result['more_data']['per_class']):
        action_rows.append('<tr><td>' + html.escape(label) + f'</td><td>{after["support"]}</td>' +
                           ''.join('<td>' + pct(r[k]) + '</td>' for r in (before, after) for k in ('precision', 'recall', 'f1')) + '</tr>')
    changes = []
    for name, ci in result['paired_changes'].items():
        changes.append(f'<tr><td>{html.escape(name)}</td><td>{pct(ci["low"])} to {pct(ci["high"])}</td></tr>')
    gates = result['unchanged_target_gates']
    page = '''<!doctype html><html><head><meta charset="utf-8"><style>
    :root{font-family:var(--font-sans)}body{margin:0;color:var(--foreground)}
    p{line-height:1.5}.muted{color:var(--muted-foreground)}table{border-collapse:collapse;width:100%;font-size:13px}
    th,td{padding:9px 6px;text-align:right;border-bottom:1px solid var(--border)}th:first-child,td:first-child{text-align:left}
    .legend{display:flex;gap:24px;font-size:13px}.dot{display:inline-block;width:11px;height:11px;margin-right:6px;border-radius:2px}
    details{margin-top:18px}summary{cursor:pointer;font-weight:600}.scroll{overflow:auto}h3{font-size:16px;margin-top:24px}
    </style></head><body>'''
    page += '<p><b>Same GRU, more training data</b><br><span class="muted">Original validation only: 14,439 actions across 5 whole match groups. Seed 26; architecture and training settings unchanged.</span></p>'
    page += '<div class="legend">' + ''.join(f'<span><i class="dot" style="background:var(--chart-{i+1})"></i>{name}</span>' for i, (name, _) in enumerate(models)) + '</div>'
    page += ''.join(chart) + '<p class="muted">Whiskers: 95% whole-group bootstrap intervals. Movement scores condition on the recorded action type. Joint accuracy also requires the predicted action type to match.</p>'
    page += '<table><thead><tr><th>Validation metric</th><th>Original E06</th><th>More-data M01</th></tr></thead><tbody>' + ''.join(rows) + '</tbody></table>'
    page += '<p>Frozen development targets: ' + ', '.join(html.escape(k) + (' passed' if v else ' not met') for k, v in gates['passed'].items()) + '.</p>'
    page += '<details><summary>Unchanged benchmark baselines</summary><div class="scroll"><table><tr><th>Baseline</th><th>Macro F1</th><th>Movement exact</th><th>Joint NLL</th></tr>'
    for name, score in fixed.items():
        page += f'<tr><td>{html.escape(name)}</td><td>{pct(score["macro_f1"])}</td><td>{pct(score["parameters"]["move"]["exact_accuracy"])}</td><td>{score["joint_nll"]:.4f}</td></tr>'
    page += '</table></div><p class="muted">E02 and E05 are the existing no-history models. Frequency models use the named fixed movement/target rule. Baselines retain their original training data for this initial comparison.</p></details>'
    page += '<details><summary>Per-action precision, recall and F1</summary><div class="scroll"><table><tr><th>Action</th><th>Support</th><th>Old P</th><th>Old R</th><th>Old F1</th><th>New P</th><th>New R</th><th>New F1</th></tr>' + ''.join(action_rows) + '</table></div></details>'
    page += '<details><summary>Paired changes versus original E06: 95% group intervals</summary><table>' + ''.join(changes) + '</table></details>'
    repeated = REPORTS / 'three-seed-check.json'
    if repeated.exists():
        check = json.loads(repeated.read_text())
        page += '<h3>Predeclared three-seed check</h3><table><tr><th>Seed</th><th>Macro F1</th><th>Movement exact</th><th>Joint NLL</th><th>Targets passed</th></tr>'
        for run in check['runs']:
            score = run['validation']
            page += f'<tr><td>{run["seed"]}</td><td>{pct(score["macro_f1"])}</td><td>{pct(score["parameters"]["move"]["exact_accuracy"])}</td><td>{score["joint_nll"]:.4f}</td><td>{run["target_gates"]["passed_count"]}/4</td></tr>'
        page += '</table><p>All four frozen targets met in every seed: <b>' + ('yes' if check['all_targets_met_consistently'] else 'no') + '</b>.</p>'
    elif (REPORTS / 'repeat-decision.json').exists():
        decision = json.loads((REPORTS / 'repeat-decision.json').read_text())
        if decision['promising']:
            page += '<p>The first fit triggered the predeclared repeated-seed check. Additional fits are in progress; three-seed consistency is unestablished.</p>'
        else:
            failed = ', '.join(k for k, passed in decision['conditions'].items() if not passed)
            page += '<p>The first run did not satisfy the predeclared repeat condition (' + html.escape(failed) + '); no additional fits were run. Three-seed consistency is unestablished.</p>'
    page += '<p class="muted">350 new training games join 120 original training games. The 75 new validation and 75 final-test games remain unopened. The chart shows the matched seed 26 comparison. Observational time, engine and opponent composition can also differ; this is not an equal-compute or randomized volume comparison.</p>'
    page += '<p class="muted">Recorded parameters are partially observed: original target IDs and shop arguments are unavailable. Unknown shop commands count as failures in joint recorded accuracy. Movement error assigns a 16-cell penalty to unknown or out-of-range predictions; parameter coverage is in the CSV. Full engine illegal-action rate remains unassessed; reported violations use the existing partial checks.</p></body></html>'
    (REPORTS / 'comparison.html').write_text(page, encoding='utf-8')
    print('Exported comparison.html, per-action.csv, parameters.csv and both confusion matrices.')


if __name__ == '__main__':
    run()
