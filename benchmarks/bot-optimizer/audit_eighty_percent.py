"""Audit final 80% equal-work fuel savings and archive reproducible provenance.

Run after the economy80-final-* validation batch completes. This performs no
guest jobs; it checks measured reports/replays and regenerates source snapshots.
"""

import argparse
import ast
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import unittest

from audit_forty_percent import signatures
from audit_twenty_percent import ROOT, FINGERPRINT, COMMIT, source_hashes, wasm_sections
from collect import collect
from normal_budget import observe_local, trajectory, work_counts
from tools.bot_optimizer import Options, optimize_folder, optimize_source
from tools.bot_optimizer.compare import instrument, observations
from tools.bot_optimizer.benchmark import summarize
from tools.bot_optimizer.compiler import inventory
from tools.bot_optimizer.model import PASS_DESCRIPTIONS
from tools.bot_optimizer.runtime import check_logs, replay_logs
from tools.bot_optimizer.test_runner import flatten


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--snapshot', type=Path, required=True)
    args = parser.parse_args()
    assert not args.output.exists() and not args.snapshot.exists()
    labels = ('fuel', 'public', 'fast', 'rich', 'semantics', 'total-blocks', 'edge-blocks',
              'guest-prefix', 'guest-losing', 'guest-eighty', 'raised-work', 'normal-work', 'normal', 'validation')
    folders = {label: ROOT/'replays'/f'economy80-final-{label}' for label in labels}
    evidence = collect([f'{label}={folder}/results.json' for label, folder in folders.items()])
    reports = {label: data['report'] for label, data in evidence['runs'].items()}
    final, maps = reports['fuel'], {'collision', 'corners', 'lanes'}
    map_order = list(dict.fromkeys(row['map'] for row in final['comparisons']))
    assert final['input_sha256'] == FINGERPRINT
    assert final['target'] == 'draft_planner:DraftPlanner.build' and final['repeats'] == 2
    assert final['fuel_quantum_argument'] == 1_000_000_000 and final['rounds'] == 1
    assert final['output_prefix'] == 'SQUAD_LOOPS_DATA '
    assert len(final['trajectory_checks']) == 6
    assert all(row['engine_replay_equal'] and row['all_nonmeasurement_stdout_equal']
               for row in final['trajectory_checks'])
    assert {(row['run'], row['map'], row['side']) for row in final['comparisons']} == {
        (run, game_map, side) for run in range(2) for game_map in maps for side in ('a', 'b')}
    for row in final['comparisons']:
        assert row['printed_outputs_equal'] and row['reduction_percent'] >= 80, row
        assert len(row['baseline_fuel']) == len(row['optimized_fuel']) == 1
        assert abs(100*(1-row['optimized_fuel'][0]/row['baseline_fuel'][0])-row['reduction_percent']) < 1e-10
        peer, = [other for other in final['comparisons'] if other['map'] == row['map']
                 and other['side'] == row['side'] and other['run'] != row['run']]
        assert (row['baseline_fuel'], row['optimized_fuel']) == (peer['baseline_fuel'], peer['optimized_fuel'])
        measured = {}
        for variant in ('baseline', 'optimized'):
            replay, = (folders['fuel']/f'run-{row["run"]}-map-{map_order.index(row["map"])}-{variant}').glob('*.repl26a')
            measured[variant] = observations(replay, final['output_prefix'])[row['side']]
            assert measured[variant]['samples'] == row[f'{variant}_fuel']
        assert measured['baseline']['outputs'] == measured['optimized']['outputs']
    assert reports['public']['scenario_count'] == 240 and reports['public']['exact_observations_equal']
    assert reports['public']['observations_sha256'] == 'f5d3e1a8f32089ed8ec35dc15b53ebc435d3b3e3bcc6e407a5a50ce9198835f6'
    fast = reports['fast']
    assert fast['contexts'] == fast['scenarios'] == 240
    assert fast['direct_evaluations'] == fast['direct_fast_evaluations'] == 1152
    assert fast['consumer_numeric_calls'] == 3586 and fast['exact_records_and_stop_counts_equal']
    assert fast['compensated_cache_hits'] == 815 and fast['scalar_group_hits'] == 1249
    assert fast['observations_sha256'] == '70054bb9f8d57d311cc23367af6f9ef9c6c3365251c5784194566e7538229960'
    assert not fast['mutable_alias_retention']
    assert reports['rich']['scenarios'] == 96 and reports['rich']['exact_records_stable_ties_callbacks_errors_and_mutation_equal']
    assert reports['semantics']['fixture_observations'] == 10 and reports['semantics']['explicit_fast_contexts'] == 18
    assert reports['semantics']['callback_stops_throws_and_mutation_equal']
    assert reports['total-blocks']['cases'] == 66000 and reports['total-blocks']['errors'] == 29352
    assert reports['total-blocks']['exact_outputs_partial_errors_and_final_loop_locals_equal']
    assert reports['edge-blocks']['cases'] == 189918
    assert reports['edge-blocks']['exact_integer_edges_totals_and_final_loop_locals_equal']
    planner_hash = hashlib.sha256((folders['public']/'optimized/src/planner.py').read_bytes()).hexdigest()
    assert fast['planner_sha256'] == reports['total-blocks']['candidate_sha256'] == reports['edge-blocks']['candidate_sha256'] == planner_hash
    for label in ('public', 'raised-work', 'normal-work', 'normal'):
        assert reports[label]['input_sha256'] == FINGERPRINT
        assert reports[label]['pass_counts'] == final['pass_counts']
    spec = 'planner:LoopPlanner.find_loops:expansion_count'
    expansions = {'collision': 6020, 'corners': 20000, 'lanes': 20000}
    for label in ('raised-work', 'normal-work', 'normal'):
        report = reports[label]
        assert len(report['comparisons']) == 3 and {row['map'] for row in report['comparisons']} == maps
        for index, row in enumerate(report['comparisons']):
            paths = []
            for variant in ('baseline', 'optimized'):
                replay, = (folders[label]/f'run-0-map-{index}-{variant}').glob('*.repl26a')
                paths.append(replay)
                if label != 'normal':
                    assert json.loads(json.dumps(work_counts(replay))) == row[f'{variant}_work']
            assert all(row[key] == value for key, value in trajectory(*paths).items())
            assert row['engine_replay_equal']
        if label != 'normal':
            assert report['observe_local'] == spec and report['instrumented']
            assert report['observation_targets']['baseline'] == ['find_loops']
            assert 'find_loops' in report['observation_targets']['optimized']
            assert any(name.startswith('_bcopt_region_consumer_') for name in report['observation_targets']['optimized'])
            for row in report['comparisons']:
                for variant in ('baseline_work', 'optimized_work'):
                    for side in ('a', 'b'):
                        records = row[variant][side]
                        assert len(records) == 1 and records[0][0] == spec
                        assert type(records[0][1]) is int and 0 <= records[0][1] <= 20000
    assert reports['raised-work']['fuel'] == 1_000_000_000
    for row in reports['raised-work']['comparisons']:
        assert row['work_counts_equal'] and row['engine_replay_equal']
        assert all(row[variant][side] == [[spec, expansions[row['map']]]]
                   for variant in ('baseline_work', 'optimized_work') for side in ('a', 'b'))
    assert reports['normal']['rounds'] == 3 and not reports['normal']['instrumented']
    assert reports['normal']['fuel'] == reports['normal-work']['fuel'] == 'normal engine default'
    for label in ('guest-prefix', 'guest-losing', 'guest-eighty'):
        report = reports[label]
        source = (ROOT/'benchmarks/bot-optimizer/src'/('eighty.py' if report['suite'] == 'prefix' else f"{report['suite']}.py")).read_text()
        if report['suite'] == 'prefix':
            source = source.replace('score = reward + rounded',
                'score = matrix[0][route[0]] * self.weights[route[0]]\n'
                '        score += matrix[0][route[-1]] * self.weights[route[-1]]')
        assert report['source_sha256'] == hashlib.sha256(source.encode()).hexdigest()
        assert report['baseline_source_sha256'] == report['source_sha256']
        assert (folders[label]/'bot/src/original.py').read_text() == source
        assert (folders[label]/'bot/src/optimized.py').read_text() == optimize_source(source).source
        assert all(len(data['pairs']) == 10 for data in report['datasets'])
        assert all('3.13.7' in meta['python'] for data in report['datasets'] for meta in data['metadata'])
        for index, data in enumerate(report['datasets']):
            replay, = (folders[label]/f'replays-{index}').glob('*.repl26a')
            observed = summarize(replay, list(data['pairs']))
            assert all(data[key] == value for key, value in observed.items())
    for folder in folders.values():
        for replay in folder.glob('run-*/*.repl26a'):
            check_logs(replay_logs(replay))
    compiler_path = ROOT/'replays/economy80-final-compiler/results.json'
    compiler = json.loads(compiler_path.read_text())
    assert compiler['status'] == 'passed' and not compiler['failed_modules']
    loader = unittest.TestLoader()
    suite = loader.discover(str(ROOT/'tools/bot_optimizer/tests'), top_level_dir=str(ROOT))
    expected_tests = {test.id() for test in flatten(suite)}
    assert not loader.errors and compiler['tests'] == len(expected_tests)
    assert {name for row in compiler['results'] for name in row['tests']} == expected_tests
    for row in compiler['results']:
        log = (ROOT/row['log']).read_text()
        assert row['returncode'] == 0 and log.rstrip().endswith('OK')
        assert re.search(rf'Ran {len(row["tests"])} tests? in ', log)
    copied_log = (folders['validation']/'copied-bot.stderr').read_text()
    assert reports['validation']['copied_bot_returncode'] == 0
    assert reports['validation']['steps'] == 14
    for index in range(14):
        assert json.loads((folders['validation']/f'step-{index:02}.json').read_text())['returncode'] == 0
    assert 'Ran 71 tests' in copied_log and copied_log.rstrip().endswith('OK')
    bot = ROOT/'bots/economy-bot'
    original_files = list(inventory(bot))
    for path in original_files:
        relative = str(path.relative_to(ROOT))
        assert path.read_bytes() == subprocess.check_output(['git', 'show', f'{COMMIT}:{relative}'], cwd=ROOT)
    subprocess.run(['git', 'diff', '--check'], cwd=ROOT, check=True)
    for name in ('base_integer_totals', 'cancelled_products', 'losing_stores', 'retained_integer_edges',
                 'dead_primitive_slots', 'reduction_initializers', 'base_edge_scalars', 'base_prefix_scalars'):
        tree = ast.parse((ROOT/f'tools/bot_optimizer/{name}.py').read_text())
        assert not any(isinstance(n, ast.Constant) and n.value in (
            'LoopPlanner', 'DraftPlanner', 'evaluate_loop', 'camp_insertions', 'risk_tolerance', 'FUEL_RESERVE')
            for n in ast.walk(tree))
    args.snapshot.mkdir(parents=True)
    shutil.copytree(compiler_path.parent, args.snapshot/'compiler-test-evidence')
    shutil.copytree(folders['validation'], args.snapshot/'validation-evidence')
    shutil.copytree(ROOT/'tools/bot_optimizer', args.snapshot/'compiler', ignore=shutil.ignore_patterns('__pycache__'))
    shutil.copytree(ROOT/'benchmarks/bot-optimizer', args.snapshot/'benchmark-tools',
                    ignore=shutil.ignore_patterns('__pycache__', '*.json', '*.md'))
    generated = optimize_folder(bot, args.snapshot/'generated')
    baseline = optimize_folder(bot, args.snapshot/'baseline', Options(disabled=frozenset(PASS_DESCRIPTIONS)))
    assert generated['input_sha256'] == baseline['input_sha256'] == FINGERPRINT
    assert generated['pass_counts'] == final['pass_counts']
    hashes = source_hashes(args.snapshot/'generated/src')
    assert hashes == source_hashes(folders['public']/'optimized/src') == source_hashes(folders['normal']/'optimized/src')
    originals, emitted = signatures(bot/'src'), signatures(args.snapshot/'generated/src')
    assert all(emitted[name] == signature for name, signature in originals.items())
    for label, variant in (('generated', 'optimized'), ('baseline', 'baseline')):
        timed = args.snapshot/f'{label}-instrumented'
        shutil.copytree(args.snapshot/label, timed)
        instrument(timed, final['target'])
        assert source_hashes(timed/'src') == source_hashes(folders['fuel']/variant/'src')
        counted = args.snapshot/f'{label}-counted'
        shutil.copytree(args.snapshot/label, counted)
        observe_local(counted, spec)
        for directory in ('raised-work', 'normal-work'):
            assert source_hashes(counted/'src') == source_hashes(folders[directory]/variant/'src')
    before = wasm_sections(folders['fuel']/'baseline/.cambc/build/bot.wasm')
    after = wasm_sections(folders['fuel']/'optimized/.cambc/build/bot.wasm')
    for kind in (2, 10):
        assert [s for s in before['sections'] if s['kind'] == kind] == [s for s in after['sections'] if s['kind'] == kind]
    audit = dict(status='complete', objective='at least80% lower equal-work DraftPlanner.build fuel on all three maps',
        input_sha256=FINGERPRINT, source_commit=COMMIT, original_files_verified_byte_for_byte=len(original_files),
        public_signatures_unchanged=True, runtime_code_and_import_sections_unchanged=True,
        current_sources_match_measured_sources=True, snapshot=str(args.snapshot),
        compiler_source_sha256=source_hashes(args.snapshot/'compiler'),
        benchmark_source_sha256=source_hashes(args.snapshot/'benchmark-tools'), generated_source_sha256=hashes,
        baseline_wasm=before, final_wasm=after, compiler_tests=compiler, copied_bot_tests=71,
        compiler_results_sha256=hashlib.sha256(compiler_path.read_bytes()).hexdigest(),
        raised_expansions=expansions, normal_budget=reports['normal']['comparisons'], normal_work=reports['normal-work']['comparisons'],
        fuel_reduction_percent={game_map: {
            'minimum': min(row['reduction_percent'] for row in final['comparisons'] if row['map'] == game_map),
            'maximum': max(row['reduction_percent'] for row in final['comparisons'] if row['map'] == game_map)} for game_map in sorted(maps)})
    evidence['audit'] = audit
    (args.snapshot/'audit.json').write_text(json.dumps(audit, indent=2, sort_keys=True)+'\n')
    args.output.write_text(json.dumps(evidence, indent=2, sort_keys=True)+'\n')
    print(json.dumps(audit['fuel_reduction_percent'], indent=2))


if __name__ == '__main__':
    main()
