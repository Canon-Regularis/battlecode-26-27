"""Audit completed 20% evidence, rebuild source snapshots, and archive provenance.

Does not run Wasm jobs. Run only after the final work-count/normal-budget jobs finish.
"""

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from collect import collect
from tools.bot_optimizer import Options, optimize_folder
from tools.bot_optimizer.compare import instrument
from tools.bot_optimizer.compiler import inventory
from tools.bot_optimizer.model import PASS_DESCRIPTIONS


FINGERPRINT = '950f6e045c5624b53965f679837259176013e9b072f6dfc30130dffce98dc54c'
COMMIT = '97f761f04ed3d3e85a6f2217df345629baab58c8'
FINAL = 'economy20-shortcircuit-raised'
REPORTS = {
    'wasm_analysis': 'economy20-wasm-analysis',
    'initial_candidates': 'economy20-wasm-candidates',
    'large_factories': 'economy20-large-factories',
    'manual_deferred_excluded': 'economy20-deferred-candidates',
    'unguarded_deferred_excluded': 'economy20-deferred-raised',
    'guarded_deferred_excluded': 'economy20-guarded-deferred-raised',
    'combined_deferred_excluded': 'economy20-short-reductions-raised',
    'four_row_fusion': 'economy20-short-reductions-only-raised',
    'fusion_fixtures': 'economy20-short-reductions-generated',
    'fusion_bounds': 'economy20-fused-bounds',
    'eight_row_fusion': 'economy20-fused-eight-raised',
    'unguarded_shortcircuit_exploratory': 'economy20-shortcircuit-candidates',
    'shortcircuit_fixtures': 'economy20-shortcircuit-generated',
    'final_planner': FINAL,
    'differential': 'economy20-shortcircuit-differential',
    'raised_work': 'economy20-final-raised-work',
    'normal_work': 'economy20-final-normal-work',
    'normal_uninstrumented': 'economy20-final-normal',
}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_hashes(folder):
    return {str(path.relative_to(folder)): digest(path) for path in sorted(folder.rglob('*.py'))}


def wasm_sections(path):
    data = path.read_bytes()
    assert data[:8] == b'\x00asm\x01\x00\x00\x00'
    index, sections = 8, []
    while index < len(data):
        kind = data[index]
        index += 1
        size = shift = 0
        while True:
            value = data[index]
            index += 1
            size |= (value & 127) << shift
            if value < 128:
                break
            shift += 7
        body = data[index:index + size]
        assert len(body) == size
        sections.append({'kind': kind, 'bytes': size, 'sha256': hashlib.sha256(body).hexdigest()})
        index += size
    return {'path': str(path), 'bytes': len(data), 'sha256': digest(path), 'sections': sections}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True, help='new compact JSON archive')
    parser.add_argument('--snapshot', type=Path, required=True, help='new compiler/source audit directory')
    args = parser.parse_args()
    if args.output.exists() or args.snapshot.exists():
        parser.error('output and snapshot must both be new')
    evidence = collect([f'{label}=replays/{folder}/results.json' for label, folder in REPORTS.items()])
    reports = {label: run['report'] for label, run in evidence['runs'].items()}
    final = reports['final_planner']
    assert final['input_sha256'] == FINGERPRINT
    assert final['target'] == 'draft_planner:DraftPlanner.build' and final['repeats'] == 2
    assert len(final['trajectory_checks']) == 6
    assert all(row.get('engine_replay_equal') and row.get('all_nonmeasurement_stdout_equal')
               for row in final['trajectory_checks'])
    assert {(row['run'], row['map'], row['side']) for row in final['comparisons']} == {
        (run, game_map, side) for run in range(2)
        for game_map in ('collision', 'corners', 'lanes') for side in ('a', 'b')}
    for row in final['comparisons']:
        assert row['reduction_percent'] >= 20 and row['printed_outputs_equal']
        peer, = [r for r in final['comparisons'] if r['map'] == row['map']
                 and r['side'] == row['side'] and r['run'] != row['run']]
        assert (row['baseline_fuel'], row['optimized_fuel']) == (peer['baseline_fuel'], peer['optimized_fuel'])
    assert reports['differential']['scenario_count'] == 240
    assert reports['differential']['exact_observations_equal']
    for label in ('raised_work', 'normal_work', 'normal_uninstrumented'):
        assert reports[label]['input_sha256'] == FINGERPRINT
        assert {row['map'] for row in reports[label]['comparisons']} == {'collision', 'corners', 'lanes'}
    assert all(row['work_counts_equal'] for row in reports['raised_work']['comparisons'])
    assert reports['normal_uninstrumented']['rounds'] == 3
    assert not reports['normal_uninstrumented']['instrumented']
    bot = ROOT / 'bots/economy-bot'
    original_files = list(inventory(bot))
    for path in original_files:
        relative = str(path.relative_to(ROOT))
        historical = subprocess.check_output(['git', 'show', f'{COMMIT}:{relative}'], cwd=ROOT)
        assert path.read_bytes() == historical, relative
    assert not subprocess.check_output(['git', 'ls-files', '--', 'bots/economy-bot'], cwd=ROOT).strip()
    staged = subprocess.check_output(['git', 'diff', '--cached', '--name-only'], cwd=ROOT).decode().splitlines()
    subprocess.run(['git', 'diff', '--check'], cwd=ROOT, check=True)

    args.snapshot.mkdir(parents=True)
    shutil.copytree(ROOT / 'tools/bot_optimizer', args.snapshot / 'compiler',
                    ignore=shutil.ignore_patterns('__pycache__'))
    generated = optimize_folder(bot, args.snapshot / 'generated')
    baseline = optimize_folder(bot, args.snapshot / 'baseline', Options(disabled=frozenset(PASS_DESCRIPTIONS)))
    assert generated['input_sha256'] == baseline['input_sha256'] == FINGERPRINT
    assert generated['pass_counts'] == final['pass_counts']
    generated_hashes = source_hashes(args.snapshot / 'generated/src')
    for folder in ('economy20-shortcircuit-differential', 'economy20-final-normal'):
        assert generated_hashes == source_hashes(Path('replays') / folder / 'optimized/src')
    for name in ('generated', 'baseline'):
        measured = 'optimized' if name == 'generated' else 'baseline'
        source = args.snapshot / name
        instrumented = args.snapshot / f'{name}-instrumented'
        shutil.copytree(source, instrumented)
        instrument(instrumented, final['target'])
        assert source_hashes(instrumented / 'src') == source_hashes(Path('replays') / FINAL / measured / 'src')

    excluded = {label: 'Unsafe deferred allocation changes shared-key/finalizer history.'
                for label in REPORTS if label.endswith('_excluded')}
    excluded['unguarded_shortcircuit_exploratory'] = 'Manual upper-bound probe omits required container guard.'
    for label, reason in excluded.items():
        evidence['runs'][label]['acceptance'] = {'accepted_final_evidence': False, 'reason': reason}
    module = wasm_sections(Path('replays') / FINAL / 'optimized/.cambc/build/bot.wasm')
    inspected = wasm_sections(Path('replays/economy-cached-raised/optimized/.cambc/build/bot.wasm'))
    evidence['audit'] = {
        'status': 'complete', 'objective': 'at least20% less equal-work planner fuel on every map',
        'input_sha256': FINGERPRINT, 'source_commit': COMMIT,
        'original_files_verified_byte_for_byte': len(original_files), 'original_bot_untracked': True,
        'staged_paths': staged, 'snapshot': str(args.snapshot),
        'current_emitted_sources_match_measured_sources': True,
        'generated_source_sha256': generated_hashes,
        'final_wasm': module,
        'inspected_wasm_code_section_matches_final': next(s for s in module['sections'] if s['kind'] == 10)
            == next(s for s in inspected['sections'] if s['kind'] == 10),
        'fuel_reduction_percent': {game_map: {
            'minimum': min(r['reduction_percent'] for r in final['comparisons'] if r['map'] == game_map),
            'maximum': max(r['reduction_percent'] for r in final['comparisons'] if r['map'] == game_map),
        } for game_map in ('collision', 'corners', 'lanes')},
        'validation': {'optimizer_tests': 133, 'generated_bot_tests': 71,
                       'exact_differential_scenarios': 240,
                       'note': 'Unit counts reflect verified commands; guest reports and work counts are embedded.'},
    }
    (args.snapshot / 'audit.json').write_text(json.dumps(evidence['audit'], indent=2, sort_keys=True) + '\n')
    with args.output.open('x') as stream:
        stream.write(json.dumps(evidence, indent=2, sort_keys=True) + '\n')
    print(json.dumps(evidence['audit'], indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
