"""Audit completed 30% measurements and archive reproducible source provenance.

Run after final guest, equal-work, and normal-budget validation. This does not
run matches or change the original bot, and refuses to overwrite any archive.
"""

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

from audit_twenty_percent import ROOT, FINGERPRINT, COMMIT, source_hashes, wasm_sections
from collect import collect
from normal_budget import observe_local
from tools.bot_optimizer import Options, optimize_folder, optimize_source
from tools.bot_optimizer.compare import instrument
from tools.bot_optimizer.compiler import inventory
from tools.bot_optimizer.model import PASS_DESCRIPTIONS


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('final', 'differential', 'raised-work', 'normal-work', 'normal', 'inspected-wasm', 'output', 'snapshot'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--guest', action='append', required=True, help='label=completed-results.json')
    parser.add_argument('--report', action='append', default=[], help='label=additional-completed-results.json')
    parser.add_argument('--exploratory', action='append', default=[], help='label=exploratory-results.json')
    parser.add_argument('--optimizer-tests', type=int, required=True, help='count from successful final test run')
    parser.add_argument('--bot-tests', type=int, required=True, help='count from successful final copied-bot test run')
    args = parser.parse_args()
    if args.output.exists() or args.snapshot.exists():
        parser.error('output and snapshot must both be new')
    directories = {'final': args.final, 'differential': args.differential, 'raised_work': args.raised_work,
                   'normal_work': args.normal_work, 'normal': args.normal}
    evidence = collect([*(f'{label}={path}/results.json' for label, path in directories.items()),
                        *args.guest, *args.report, *args.exploratory])
    reports = {label: row['report'] for label, row in evidence['runs'].items()}
    final = reports['final']
    maps = {'collision', 'corners', 'lanes'}
    assert final['input_sha256'] == FINGERPRINT
    assert final['target'] == 'draft_planner:DraftPlanner.build' and final['repeats'] == 2
    assert len(final['trajectory_checks']) == 6
    assert all(row.get('engine_replay_equal') and row.get('all_nonmeasurement_stdout_equal')
               for row in final['trajectory_checks'])
    assert {(r['run'], r['map'], r['side']) for r in final['comparisons']} == {
        (run, game_map, side) for run in range(2) for game_map in maps for side in ('a','b')}
    for row in final['comparisons']:
        assert row['reduction_percent'] >= 30 and row['printed_outputs_equal'], row
        assert len(row['baseline_fuel']) == len(row['optimized_fuel']) == 1
        reduction = 100 * (1 - row['optimized_fuel'][0] / row['baseline_fuel'][0])
        assert abs(reduction - row['reduction_percent']) < 1e-10
        peer, = [r for r in final['comparisons'] if r['map'] == row['map'] and r['side'] == row['side'] and r['run'] != row['run']]
        assert (row['baseline_fuel'], row['optimized_fuel']) == (peer['baseline_fuel'], peer['optimized_fuel'])
    assert reports['differential']['scenario_count'] == 240 and reports['differential']['exact_observations_equal']
    assert reports['differential']['observations_sha256'] == 'f5d3e1a8f32089ed8ec35dc15b53ebc435d3b3e3bcc6e407a5a50ce9198835f6'
    for label in ('differential', 'raised_work', 'normal_work', 'normal'):
        assert reports[label]['input_sha256'] == FINGERPRINT
        assert reports[label]['pass_counts'] == final['pass_counts'], label
    specification = 'planner:LoopPlanner.find_loops:expansion_count'
    expected = {'collision': 6020, 'corners': 20000, 'lanes': 20000}
    assert reports['raised_work']['observe_local'] == specification
    assert reports['raised_work']['fuel'] == 1_000_000_000
    for label in ('raised_work','normal_work','normal'):
        assert {r['map'] for r in reports[label]['comparisons']} == maps
    for row in reports['raised_work']['comparisons']:
        assert row['work_counts_equal'] and row['engine_replay_equal']
        for variant in ('baseline_work','optimized_work'):
            for side in ('a','b'):
                assert row[variant][side] == [[specification, expected[row['map']]]]
    assert reports['normal']['rounds'] == 3 and not reports['normal']['instrumented']
    assert reports['normal']['fuel'] == reports['normal_work']['fuel'] == 'normal engine default'
    assert reports['normal_work']['observe_local'] == specification
    for argument in args.guest:
        label, _, filename = argument.partition('=')
        report = reports[label]
        assert 'datasets' in report
        suite = report['suite']
        fixture = ROOT / 'benchmarks/bot-optimizer/src' / ('kernels.py' if suite == 'core' else f'{suite}.py')
        source = fixture.read_text()
        measured = Path(filename).parent / 'bot/src'
        assert measured.joinpath('original.py').read_text() == source
        assert report['source_sha256'] == hashlib.sha256(source.encode()).hexdigest()
        assert measured.joinpath('optimized.py').read_text() == optimize_source(source).source
    assert args.optimizer_tests > 0 and args.bot_tests > 0

    bot = ROOT / 'bots/economy-bot'
    original_files = list(inventory(bot))
    for path in original_files:
        relative = str(path.relative_to(ROOT))
        historical = subprocess.check_output(['git','show',f'{COMMIT}:{relative}'], cwd=ROOT)
        assert path.read_bytes() == historical, relative
    assert not subprocess.check_output(['git','ls-files','--','bots/economy-bot'], cwd=ROOT).strip()
    staged = subprocess.check_output(['git','diff','--cached','--name-only'], cwd=ROOT).decode().splitlines()
    subprocess.run(['git','diff','--check'], cwd=ROOT, check=True)

    args.snapshot.mkdir(parents=True)
    shutil.copytree(ROOT / 'tools/bot_optimizer', args.snapshot / 'compiler', ignore=shutil.ignore_patterns('__pycache__'))
    shutil.copytree(ROOT / 'benchmarks/bot-optimizer', args.snapshot / 'benchmark-tools',
                    ignore=shutil.ignore_patterns('__pycache__', '*.json', '*.md'))
    generated = optimize_folder(bot, args.snapshot / 'generated')
    baseline = optimize_folder(bot, args.snapshot / 'baseline', Options(disabled=frozenset(PASS_DESCRIPTIONS)))
    assert generated['input_sha256'] == baseline['input_sha256'] == FINGERPRINT
    assert generated['pass_counts'] == final['pass_counts']
    hashes = source_hashes(args.snapshot / 'generated/src')
    assert hashes == source_hashes(args.differential / 'optimized/src')
    assert hashes == source_hashes(args.normal / 'optimized/src')
    for name in ('generated','baseline'):
        measured = 'optimized' if name == 'generated' else 'baseline'
        source = args.snapshot / name
        timed = args.snapshot / f'{name}-instrumented'
        shutil.copytree(source, timed)
        instrument(timed, final['target'])
        assert source_hashes(timed / 'src') == source_hashes(args.final / measured / 'src')
        counted = args.snapshot / f'{name}-counted'
        shutil.copytree(source, counted)
        observe_local(counted, specification)
        for directory in (args.raised_work,args.normal_work):
            assert source_hashes(counted / 'src') == source_hashes(directory / measured / 'src')

    for argument in args.exploratory:
        label = argument.partition('=')[0]
        evidence['runs'][label]['acceptance'] = {'accepted_final_evidence': False,
            'reason': 'Exploratory alternatives; not proof of final compiler semantics or savings.'}
    module = wasm_sections(args.final / 'optimized/.cambc/build/bot.wasm')
    inspected = wasm_sections(args.inspected_wasm)
    same_runtime = next(s for s in module['sections'] if s['kind'] == 10) == next(s for s in inspected['sections'] if s['kind'] == 10)
    assert same_runtime
    evidence['audit'] = {
        'status': 'complete', 'objective': 'at least30% less equal-work planner fuel on every map',
        'input_sha256': FINGERPRINT, 'source_commit': COMMIT,
        'original_files_verified_byte_for_byte': len(original_files), 'original_bot_untracked': True,
        'staged_paths': staged, 'snapshot': str(args.snapshot),
        'current_emitted_sources_match_measured_sources': True,
        'current_guest_sources_match_measured_sources': True,
        'compiler_source_sha256': source_hashes(args.snapshot / 'compiler'),
        'benchmark_source_sha256': source_hashes(args.snapshot / 'benchmark-tools'),
        'generated_source_sha256': hashes, 'final_wasm': module,
        'inspected_wasm_code_section_matches_final': same_runtime,
        'fuel_reduction_percent': {game_map: {
            'minimum': min(r['reduction_percent'] for r in final['comparisons'] if r['map'] == game_map),
            'maximum': max(r['reduction_percent'] for r in final['comparisons'] if r['map'] == game_map),
        } for game_map in sorted(maps)},
        'validation': {'optimizer_tests': args.optimizer_tests, 'generated_bot_tests': args.bot_tests,
                       'exact_differential_scenarios': 240, 'raised_expansions': expected,
                       'normal_budget': reports['normal']['comparisons'],
                       'note': 'Test counts come from verified commands; guest reports and work counts are embedded.'},
    }
    (args.snapshot / 'audit.json').write_text(json.dumps(evidence['audit'], indent=2, sort_keys=True)+'\n')
    with args.output.open('x') as stream:
        stream.write(json.dumps(evidence, indent=2, sort_keys=True)+'\n')
    print(json.dumps(evidence['audit'], indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
