"""Produce portable per-action tables, confusion matrices and comparison charts."""
import csv
import html
import json
from pathlib import Path


def write_report(reports):
    result = json.loads((reports/'final-test.json').read_text())
    labels = result['labels']
    lines = ['# Frozen-test prediction results', '',
             'All action metrics use the same 15,604 actions from 25 games in five frozen match groups.',
             'Validation selected checkpoints. Counts and metrics weight sampled actions equally.', '',
             '| Model | Accuracy | Macro F1 |', '|---|---:|---:|']
    chart = []
    for name, m in result['actions'].items():
        lines.append(f'| {name} | {m["accuracy"]:.2%} | {m["macro_f1"]:.2%} |')
        chart.append(f'<div class="row"><span>{html.escape(name)}</span><div class="track"><div class="bar" style="width:{m["accuracy"]*100:.2f}%"></div></div><b>{m["accuracy"]:.1%}</b></div>')
        with (reports/f'{name}-per-action.csv').open('w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=['action', 'precision', 'recall', 'f1', 'support'])
            writer.writeheader()
            writer.writerows(dict(action=label, **row) for label, row in zip(labels, m['per_class']))
        with (reports/f'{name}-confusion.csv').open('w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['actual / predicted', *labels])
            writer.writerows([label, *row] for label, row in zip(labels, m['confusion_matrix']))
    for name in ('frozen_gru', 'stateless_mlp', 'most_common'):
        lines += ['', f'## {name}: per-action metrics', '',
                  '| Action | Precision | Recall | F1 | Support |', '|---|---:|---:|---:|---:|']
        for label, m in zip(labels, result['actions'][name]['per_class']):
            lines.append(f'| {label} | {m["precision"]:.3f} | {m["recall"]:.3f} | {m["f1"]:.3f} | {m["support"]} |')
    lines += ['', '## Recorded destination and target coordinates', '',
              'These scores condition on the recorded action family. They are not joint full-action accuracy.',
              'Attack and unit-cast coordinates require visible compatible occupants; ground casts use recorded aim cells.',
              'Original target entity IDs are unavailable; unique-occupant mapping is a diagnostic, not ID ground truth.', '',
              '| Model | Family | Exact coordinate | Top 3 | Mean Chebyshev error | Support | Multi-candidate exact | Multi-candidate support |',
              '|---|---|---:|---:|---:|---:|---:|---:|']
    for name, score in result['targets'].items():
        for family, m in score['per_family'].items():
            multiple = score['multiple_candidates_per_family'][family]
            fmt = lambda x: f'{x:.2%}' if x is not None else 'unassessed'
            lines.append(f'| {name} | {family} | {fmt(m["exact_accuracy"])} | {fmt(m["top3_accuracy"])} | {m["mean_chebyshev_error"]:.3f} | {m["support"]} | {fmt(multiple["exact_accuracy"])} | {multiple["support"]} |')
    lines += ['', 'Joint action-type and coordinate accuracy on the same 4,086 supported target actions:', '']
    for name, score in result['targets'].items():
        if 'joint_type_and_coordinate_accuracy' in score:
            lines.append(f'- {name}: {score["joint_type_and_coordinate_accuracy"]:.2%}.')
    coverage = json.loads((reports/'target-data.json').read_text())['coverage']['test']
    lines += ['', '## Coverage and limits', '', f'Frozen-test target evidence counts: `{json.dumps(coverage, sort_keys=True)}`.', '',
              'The fixed +/-8 coordinate window covers every supported test move/cast. Three attacks lack a visible compatible target and are excluded with an explicit reason.',
              'Self-only casts and actions with one candidate can be trivial; the multi-candidate columns expose that effect.',
              'No terrain/path legality is reconstructed. Hidden state resets at each sampled turn. This is historical engine 2/3 replay prediction, not a strategy-similarity percentage or a playing-strength result.', '',
              'Confusion matrices are in `*-confusion.csv` (actual rows, predicted columns); exact counts and every model\'s per-action metrics are also in `final-test.json`.']
    (reports/'RESULTS.md').write_text('\n'.join(lines)+'\n', encoding='utf-8')
    data = json.dumps(result).replace('<', '\\u003c')
    document = '''<!doctype html><html><head><meta charset="utf-8"><style>
:root{color-scheme:light dark;font:14px system-ui}body{margin:0;color:inherit}h2{font-size:16px;font-weight:500;margin:14px 0} .row{display:grid;grid-template-columns:150px 1fr 55px;gap:10px;align-items:center;margin:10px 0}.track{background:color-mix(in srgb,currentColor 10%,transparent);height:16px}.bar{background:#618ad4;height:100%}b{font-weight:500}select{font:inherit;padding:5px}table{border-collapse:collapse;font-size:11px}td,th{padding:5px;text-align:right}th{font-weight:500}.scroll{overflow:auto;max-height:480px}.legend{opacity:.75;margin:8px 0}
</style></head><body><h2>Next-action accuracy · frozen test</h2>''' + ''.join(chart) + '''<h2>Confusion matrix</h2><label>Model <select id="model"></select></label><p class="legend">Actual rows · predicted columns · cell shade is row proportion; numbers are counts.</p><div class="scroll" id="matrix"></div><h2>Exact destination / aim coordinate · conditional on action type</h2><div id="target"></div><script>
const result=DATA;const select=document.getElementById('model');
for(const name of Object.keys(result.actions)){const option=document.createElement('option');option.value=name;option.textContent=name;select.appendChild(option)}
function update(){const m=result.actions[select.value];let table='<table><tr><th>Actual / predicted</th>'+result.labels.map(x=>'<th>'+x+'</th>').join('')+'</tr>';m.confusion_matrix.forEach((row,i)=>{const sum=row.reduce((a,b)=>a+b,0);table+='<tr><th>'+result.labels[i]+'</th>'+row.map(n=>'<td style="background:color-mix(in srgb,#618ad4 '+(sum?100*n/sum:0)+'%,transparent)">'+n+'</td>').join('')+'</tr>'});document.getElementById('matrix').innerHTML=table+'</table>'}select.addEventListener('change',update);update();
let target='';for(const [name,score] of Object.entries(result.targets)){target+='<h2>'+name+'</h2>';for(const [family,m] of Object.entries(score.per_family)){target+='<div class="row"><span>'+family+' · n='+m.support+'</span><div class="track"><div class="bar" style="width:'+(100*m.exact_accuracy)+'%"></div></div><b>'+(100*m.exact_accuracy).toFixed(1)+'%</b></div>'}}document.getElementById('target').innerHTML=target;
</script></body></html>'''.replace('DATA', data)
    document = document.replace('#618ad4', 'var(--chart-1,steelblue)')
    # Labels include the literal <unknown> class, which must remain text in HTML.
    document = document.replace("'<th>'+x+'</th>'", "'<th>'+String(x).replaceAll('<','&lt;').replaceAll('>','&gt;')+'</th>'")
    document = document.replace("'<tr><th>'+result.labels[i]+'</th>'", "'<tr><th>'+String(result.labels[i]).replaceAll('<','&lt;').replaceAll('>','&gt;')+'</th>'")
    (reports/'comparison.html').write_text(document, encoding='utf-8')


if __name__ == '__main__':
    write_report(Path('tools/action_predictor/experiments/v3'))
