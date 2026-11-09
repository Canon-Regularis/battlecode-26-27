"""Produce immutable PC01 report and completion inventory after fixed endpoint."""
import json
from pathlib import Path

from ..audit import immutable_json
from ..data import digest
from .experiment import ROOT, LOCAL, OUT, source_paths


def run():
    result = json.loads((OUT / 'PC01.json').read_text())
    plan = json.loads((OUT / 'PC01-plan.json').read_text())
    preflight = json.loads((OUT / 'PC01-preflight.json').read_text())
    analysis = json.loads((OUT / 'PC01-analysis.json').read_text())
    old = json.loads((ROOT / 'tools/action_predictor/experiments/v19/PC00.json').read_text())
    assert preflight['passed'] and result['fixed_final_step'] == 2000
    assert result['protocol_sha256'] == digest(OUT / 'PC01-plan.json')
    assert result['preflight_sha256'] == digest(OUT / 'PC01-preflight.json')
    for relative, expected in result['bindings'].items():
        assert digest(ROOT / relative) == expected, relative
    lines = ['# PC01: broader P05 population, unchanged head and controls', '',
        'One diagnostic changes PC00’s fitting population from 128 examples to all 5,876 natural '
        'priority rows in its actual 55 fit groups, excluding both unchanged control cohorts. '
        'The original 128 fit rows are included. No row is selected by current model error.', '',
        '| Update | Broad fit /5,876 | Original fit /128 | Same-fit-group control /128 | Disjoint-group control /128 |',
        '| --- | ---: | ---: | ---: | ---: |']
    for row in result['trace']:
        c = row['cohorts']
        lines.append('| '+str(row['step'])+' | '+' | '.join(str(c[n]['exact']) for n in (
            'broad_fit','original_fit','same_fit_groups','held_groups'))+' |')
    lines += ['', '| Cohort | Initial NLL | PC01 final NLL | PC00 final NLL |',
              '| --- | ---: | ---: | ---: |']
    initial, final = result['trace'][0]['cohorts'], result['trace'][-1]['cohorts']
    for name in initial:
        previous = 'fit' if name == 'original_fit' else name
        oldloss = old['trace'][-1]['cohorts'].get(previous,{}).get('mean_NLL')
        lines.append(f"| {name} | {initial[name]['mean_NLL']:.6f} | {final[name]['mean_NLL']:.6f} | "
                     +(f'{oldloss:.6f}' if oldloss is not None else 'unassessed')+' |')
    lines += ['', 'All 430 absolute and 560 available-residual training labels are empirical labels from '
        'the broader population. The existing P05 vocabulary remains unchanged; every control target '
        'has an absolute or available-residual explanation represented in this population. This is '
        'oracle support, not achieved accuracy or a true-intent assignment.', '',
        'The same step-zero warm P05 head, frozen M01 contexts, 39 normalized causal priority channels, '
        'exact int64 anchors, normalized probability arithmetic and integer MAP are retained. '
        'Optimization remains AdamW, .003 for 1,000 updates then .001 for 1,000, zero decay, clip 5, '
        'seed 20261120. Each update accumulates the full-population mean gradient through chunks '
        'before one optimizer step. The population treatment therefore increases total row presentations; '
        'it is not an equal-compute comparison. No new architecture, sampler, decoder or loss is introduced.', '',
        f"The accumulated-versus-full128gradient check differs by at most {preflight['accumulation_gradient_max_difference']:.3g}. "
        f"Initial modes reproduce G00/P05 exactly; maximum NLL discrepancy {preflight['initial_NLL_max_difference']:.3g}. "
        f"Input affine ranks are {preflight['original128fit_input_rank']}/128 for PC00’s sample and "
        f"{preflight['broader_input_rank']}/5,876 for the broader population. This removes unrestricted "
        '128-row interpolation; rank alone is not a policy recoverability or classification-capacity bound.', '',
        'Both controls were previously seen by the frozen encoder AND warm P05 head, vocabulary and '
        'normalization. They are excluded only from new optimization. Their results cannot be called '
        'untouched full-policy/group generalization. Coverage, diversity, forgetting and representation '
        'are not separately isolated. Broad fitting gains alone do not prove reusable rules or '
        'sufficient observations. All rows and negative results are retained.', '',
        'Paired whole-group intervals, rescues/regressions and NLL changes are in PC01-analysis.json. '
        'They are conditional diagnostic comparisons on pre-exposed TRAIN cohorts; no overall policy '
        'accuracy or original success certification follows. Fixed final update 2,000 is retained '
        'regardless of intermediate scores; no replacement checkpoint, threshold or seed is selected.', '',
        f"Execution source commit: `{result['source_commit']}`. Every declared source byte was checked "
        'against HEAD before prerequisites and again before optimizer creation. One checked command '
        'sequence runs the five focused tests, preparation and preflight before reaching optimization. '
        'The negative-path receipt confirms the normal entrypoint refuses uncommitted source. '
        'PC00’s historical uncommitted execution remains disclosed and unchanged.', '',
        'This is conditional integer training/evaluation only. The complete policy remains unchanged. '
        'Any future integrated comparison must recompute normalized joint command probabilities and '
        'winning action families. Shops remain unassessed strict failures; sparse categories cannot '
        'certify reliability. Original category, macro, movement, NLL, targeting and three-seed targets '
        'remain binding. No DEV payloads or reserved partitions are opened, and no matches, downloads, '
        'bot/runtime work or deployment occur. Fresh Sol xhigh review follows this fit.', '',
        'Reproduce once into absent immutable destinations: `python -m tools.action_predictor.priority_broad.experiment`; '
        'then `python -m tools.action_predictor.priority_broad.analyze` and '
        '`python -m tools.action_predictor.priority_broad.report`. Do not rerun completed fitting.', '']
    report_path = OUT / 'PC01-REPORT.md'
    assert not report_path.exists()
    report_path.write_text('\n'.join(lines), encoding='utf-8')
    bindings = {**plan['inputs'], **result['bindings'], **analysis['bindings'],
                str((LOCAL/'PC01-cohort.npz').relative_to(ROOT)):result['cohort_sha256']}
    paths = source_paths() + [Path(__file__), Path(__file__).with_name('analyze.py'), report_path,
        OUT/'PC01-plan.json',OUT/'PC01-preflight.json',OUT/'PC01.json',OUT/'PC01-analysis.json',
        OUT/'PC01-uncommitted-source-rejection.json',
        ROOT/'tools/action_predictor/experiments/v19/PC00-review.json',
        ROOT/'tools/action_predictor/experiments/v19/PC00-review-response.json']
    bindings.update({str(p.relative_to(ROOT)):digest(p) for p in paths})
    for relative, expected in bindings.items():
        assert digest(ROOT / relative) == expected, relative
    immutable_json(OUT/'PC01-completion.json',dict(bindings=bindings,
        fit_source_commit=result['source_commit'], fixed_final_step=2000,
        commands=['python -m tools.action_predictor.priority_broad.experiment',
                  'python -m tools.action_predictor.priority_broad.analyze',
                  'python -m tools.action_predictor.priority_broad.report'],
        optimizer_updates=2000, supervised_presentations=5876*2000, new_fits=1,
        exposure=plan['exposure'], diagnostic_only=True, promoted=False,reserved_opened=0))
    print('PC01 report/inventory bound',len(bindings),'artifacts.')


if __name__ == '__main__':
    run()
