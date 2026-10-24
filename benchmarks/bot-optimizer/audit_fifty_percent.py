"""Audit repeated 50% fuel savings, behavior, and reproducible source provenance."""

import argparse
import ast
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

from audit_forty_percent import signatures
from audit_twenty_percent import ROOT, FINGERPRINT, COMMIT, source_hashes, wasm_sections
from collect import collect
from normal_budget import observe_local
from tools.bot_optimizer import Options, optimize_folder, optimize_source
from tools.bot_optimizer.compare import instrument
from tools.bot_optimizer.compiler import inventory
from tools.bot_optimizer.model import PASS_DESCRIPTIONS
from tools.bot_optimizer.runtime import check_logs, replay_logs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--snapshot', type=Path, required=True)
    args = parser.parse_args()
    assert not args.output.exists() and not args.snapshot.exists()
    locations = {
        'final': 'economy50-derived-v2', 'differential': 'economy50-final-host',
        'fast': 'economy50-final-fast', 'raised_work': 'economy50-final-raised-work',
        'normal_work': 'economy50-final-normal-work', 'normal': 'economy50-final-normal',
        'guest_forty': 'economy50-final-guest-forty', 'guest_regions': 'economy50-final-guest-regions',
        'guest_fifty': 'economy50-final-guest-fifty', 'host': 'economy50-final-host-checks',
        'wasm': 'economy50-final-wasm-analysis', 'profile': 'economy50-functions-profile',
    }
    directories = {name: ROOT/'replays'/folder for name, folder in locations.items()}
    evidence = collect([f'{name}={folder}/results.json' for name, folder in directories.items()])
    reports = {name: value['report'] for name, value in evidence['runs'].items()}
    final, maps = reports['final'], {'collision', 'corners', 'lanes'}
    assert final['input_sha256'] == FINGERPRINT
    assert final['target'] == 'draft_planner:DraftPlanner.build' and final['repeats'] == 2
    assert len(final['trajectory_checks']) == 6
    assert all(row['engine_replay_equal'] and row['all_nonmeasurement_stdout_equal'] for row in final['trajectory_checks'])
    assert {(row['run'], row['map'], row['side']) for row in final['comparisons']} == {
        (run, game_map, side) for run in range(2) for game_map in maps for side in ('a', 'b')}
    for row in final['comparisons']:
        assert row['printed_outputs_equal'] and row['reduction_percent'] >= 50
        assert len(row['baseline_fuel']) == len(row['optimized_fuel']) == 1
        reduction = 100*(1-row['optimized_fuel'][0]/row['baseline_fuel'][0])
        assert abs(reduction-row['reduction_percent']) < 1e-10
        peer, = [value for value in final['comparisons'] if value['map'] == row['map']
                 and value['side'] == row['side'] and value['run'] != row['run']]
        assert (row['baseline_fuel'], row['optimized_fuel']) == (peer['baseline_fuel'], peer['optimized_fuel'])
    assert reports['differential']['scenario_count'] == 240
    assert reports['differential']['observations_sha256'] == 'f5d3e1a8f32089ed8ec35dc15b53ebc435d3b3e3bcc6e407a5a50ce9198835f6'
    fast = reports['fast']
    assert fast['contexts'] == fast['scenarios'] == 240
    assert fast['direct_evaluations'] == fast['direct_fast_evaluations'] == 1152
    assert fast['consumer_numeric_calls'] == 3586 and fast['exact_records_and_stop_counts_equal']
    assert not fast['mutable_alias_retention']
    assert fast['planner_sha256'] == hashlib.sha256((directories['differential']/'optimized/src/planner.py').read_bytes()).hexdigest()
    spec = 'planner:LoopPlanner.find_loops:expansion_count'
    expansions = {'collision': 6020, 'corners': 20000, 'lanes': 20000}
    for name in ('differential', 'raised_work', 'normal_work', 'normal'):
        assert reports[name]['input_sha256'] == FINGERPRINT
        assert reports[name]['pass_counts'] == final['pass_counts'], name
    for name in ('raised_work', 'normal_work', 'normal'):
        report = reports[name]
        assert {row['map'] for row in report['comparisons']} == maps
        for replay in directories[name].glob('run-*/*.repl26a'):
            check_logs(replay_logs(replay))
    for name in ('raised_work', 'normal_work'):
        report = reports[name]
        assert report['observe_local'] == spec
        assert report['observation_targets']['baseline'] == ['find_loops']
        assert 'find_loops' in report['observation_targets']['optimized']
        assert any(name.startswith('_bcopt_region_consumer_') for name in report['observation_targets']['optimized'])
        for row in report['comparisons']:
            for variant in ('baseline_work', 'optimized_work'):
                for side in ('a', 'b'):
                    records = row[variant][side]
                    assert len(records) == 1 and records[0][0] == spec
                    assert type(records[0][1]) is int and 0 <= records[0][1] <= 20000
    assert reports['raised_work']['fuel'] == 1_000_000_000
    for row in reports['raised_work']['comparisons']:
        assert row['work_counts_equal'] and row['engine_replay_equal']
        assert all(row[variant][side] == [[spec, expansions[row['map']]]]
                   for variant in ('baseline_work', 'optimized_work') for side in ('a', 'b'))
    assert reports['normal']['rounds'] == 3 and not reports['normal']['instrumented']
    assert reports['normal']['fuel'] == reports['normal_work']['fuel'] == 'normal engine default'
    for name, count in (('guest_forty', 16), ('guest_regions', 10), ('guest_fifty', 10)):
        report = reports[name]
        source = (ROOT/'benchmarks/bot-optimizer/src'/f"{report['suite']}.py").read_text()
        assert report['source_sha256'] == hashlib.sha256(source.encode()).hexdigest()
        assert (directories[name]/'bot/src/original.py').read_text() == source
        emitted = optimize_source(source).source
        assert (directories[name]/'bot/src/optimized.py').read_text() == emitted
        assert all(len(dataset['pairs']) == count for dataset in report['datasets'])
        assert all('3.13.7' in meta['python'] for dataset in report['datasets'] for meta in dataset['metadata'])
        if name == 'guest_fifty':
            assert report['pass_counts']['numeric-consumer-regions'] == 2
            assert report['pass_counts']['numeric-region-operations'] == 2
            assert '_bcopt_region_derive_' in emitted
    counts = {}
    for check in reports['host']['checks']:
        log = (directories['host']/f"{check['label']}.stderr").read_text()
        assert check['returncode'] == 0 and f"Ran {check['tests']} tests" in log and log.rstrip().endswith('OK')
        counts[check['label']] = check['tests']
    assert counts['compiler'] >= 227 and counts['copied-bot'] == 71
    bot = ROOT/'bots/economy-bot'
    original_files = list(inventory(bot))
    for path in original_files:
        relative = str(path.relative_to(ROOT))
        assert path.read_bytes() == subprocess.check_output(['git', 'show', f'{COMMIT}:{relative}'], cwd=ROOT), relative
    assert not subprocess.check_output(['git', 'ls-files', '--', 'bots/economy-bot'], cwd=ROOT).strip()
    subprocess.run(['git', 'diff', '--check'], cwd=ROOT, check=True)
    for name in ('effects', 'region_types', 'numeric_regions', 'consumer_regions', 'regions', 'numeric_ops', 'derived_tables'):
        tree = ast.parse((ROOT/f'tools/bot_optimizer/{name}.py').read_text())
        assert not any(isinstance(node, ast.Constant) and node.value in (
            'LoopPlanner', 'DraftPlanner', 'evaluate_loop', 'camp_insertions', 'risk_tolerance', 'FUEL_RESERVE')
            for node in ast.walk(tree))
    args.snapshot.mkdir(parents=True)
    shutil.copytree(ROOT/'tools/bot_optimizer', args.snapshot/'compiler', ignore=shutil.ignore_patterns('__pycache__'))
    shutil.copytree(ROOT/'benchmarks/bot-optimizer', args.snapshot/'benchmark-tools',
                    ignore=shutil.ignore_patterns('__pycache__', '*.json', '*.md'))
    generated = optimize_folder(bot, args.snapshot/'generated')
    baseline = optimize_folder(bot, args.snapshot/'baseline', Options(disabled=frozenset(PASS_DESCRIPTIONS)))
    assert generated['input_sha256'] == baseline['input_sha256'] == FINGERPRINT
    assert generated['pass_counts'] == final['pass_counts']
    hashes = source_hashes(args.snapshot/'generated/src')
    assert hashes == source_hashes(directories['differential']/'optimized/src')
    assert hashes == source_hashes(directories['normal']/'optimized/src')
    original_signatures, generated_signatures = signatures(bot/'src'), signatures(args.snapshot/'generated/src')
    assert all(generated_signatures[name] == signature for name, signature in original_signatures.items())
    for name in ('generated', 'baseline'):
        variant = 'optimized' if name == 'generated' else 'baseline'
        timed = args.snapshot/f'{name}-instrumented'
        shutil.copytree(args.snapshot/name, timed)
        instrument(timed, final['target'])
        assert source_hashes(timed/'src') == source_hashes(directories['final']/variant/'src')
        counted = args.snapshot/f'{name}-counted'
        shutil.copytree(args.snapshot/name, counted)
        observe_local(counted, spec)
        for directory in ('raised_work', 'normal_work'):
            assert source_hashes(counted/'src') == source_hashes(directories[directory]/variant/'src')
    module = wasm_sections(directories['final']/'optimized/.cambc/build/bot.wasm')
    before = wasm_sections(directories['final']/'baseline/.cambc/build/bot.wasm')
    assert reports['wasm']['wasm_sha256'] == module['sha256'] and len(reports['wasm']['functions']) == 31
    assert next(s for s in module['sections'] if s['kind'] == 10) == next(s for s in before['sections'] if s['kind'] == 10)
    evidence['audit'] = {
        'status': 'complete', 'objective': 'at least50% less equal-work planner fuel on every map',
        'input_sha256': FINGERPRINT, 'source_commit': COMMIT,
        'original_files_verified_byte_for_byte': len(original_files), 'original_bot_untracked': True,
        'public_signatures_unchanged': True, 'snapshot': str(args.snapshot),
        'compiler_source_sha256': source_hashes(args.snapshot/'compiler'),
        'benchmark_source_sha256': source_hashes(args.snapshot/'benchmark-tools'),
        'generated_source_sha256': hashes, 'final_wasm': module, 'runtime_code_section_unchanged': True,
        'current_sources_match_measured_sources': True,
        'fuel_reduction_percent': {game_map: {
            'minimum': min(row['reduction_percent'] for row in final['comparisons'] if row['map'] == game_map),
            'maximum': max(row['reduction_percent'] for row in final['comparisons'] if row['map'] == game_map)} for game_map in sorted(maps)},
        'validation': {'host_tests': counts, 'exact_planner_scenarios': 240, 'fast_path_scenarios': fast,
                       'raised_expansions': expansions, 'guest_fixtures': 36,
                       'normal_budget': reports['normal']['comparisons'], 'normal_work': reports['normal_work']['comparisons']},
    }
    (args.snapshot/'audit.json').write_text(json.dumps(evidence['audit'], indent=2, sort_keys=True)+'\n')
    args.output.write_text(json.dumps(evidence, indent=2, sort_keys=True)+'\n')
    print(json.dumps(evidence['audit']['fuel_reduction_percent'], indent=2))


if __name__ == '__main__':
    main()
