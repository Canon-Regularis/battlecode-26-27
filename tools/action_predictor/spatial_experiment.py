"""Predeclared public-map encoding experiment on the unchanged replay benchmark."""
import json
import sys

from .spatial_data import WORK, REPORTS, CHANNELS
from .more_replays import ROOT, WORK as MORE, REPORTS as MORE_REPORTS, frozen, sha, log_command


def freeze():
    assert (MORE_REPORTS / 'three-seed-check.json').exists(), 'Finish current seeds first'
    WORK.mkdir(parents=True, exist_ok=True); REPORTS.mkdir(parents=True, exist_ok=True)
    original = ROOT / 'tools/action_predictor/experiments/v4/benchmark.json'
    target = REPORTS / 'benchmark.json'
    if not target.exists():
        target.write_bytes(original.read_bytes())
    assert sha(target) == sha(original)
    config = json.loads((MORE_REPORTS / 'M01.json').read_text())['config']
    baseline = {name: json.loads((MORE_REPORTS / (name+'.json')).read_text())['checkpoint_sha256']
                for name in ('M01', 'M02', 'M03')}
    frozen(REPORTS / 'plan.json', dict(
        schema=6, purpose='Does public terrain/objective encoding improve movement beyond the same-data GRU?',
        benchmark_sha256=sha(target), membership_sha256=sha(MORE_REPORTS / 'membership.json'),
        train_sha256=sha(MORE / 'combined-train.npz'),
        validation_sha256=sha(ROOT / '.cambc/action-predictor/v4/validation.npz'),
        baseline_checkpoints=baseline, base_config=config,
        channels=CHANNELS, local_size=23, global_size=32,
        global_actor_marker='Own personal PRE location only; no marker when unknown.',
        map_model='Two depthwise CNN streams: local 23x23 -> candidate-aligned 17x17 features, global 32x32 -> layout context. Fuse with the existing GRU context and candidate ranker.',
        visibility='Static walls/holes/bushes, altars, both public spawn areas and static camp spawn tiles. No dynamic hidden camps, enemies, wards, outcomes or future state.',
        availability_sources=['sdk/python/cambc/game_map.py', 'sdk/python/cambc/__init__.py:Camp.spawn_position',
                              'Hash-pinned official viewer static map getters and campSpawns'],
        public_extractor_sha256=sha(ROOT / 'tools/action_predictor/public_map.cjs'),
        model_source_sha256=sha(ROOT / 'tools/action_predictor/map_model.py'),
        training='Same 433071 rows, input normalization, losses, class balancing, AdamW settings, batch 256, deterministic CPU4, 35 epochs/patience6 and validation joint-NLL checkpoint selection as V5.',
        initialization='Original GRU/head initialization and shuffle RNG stream preserved per seed. Added residual context and candidate projections start at zero.',
        fits=[dict(id='S01', seed=26, zero_map=False), dict(id='S02', seed=26, zero_map=True),
              dict(id='S03', seed=27, zero_map=False, conditional=True), dict(id='S04', seed=28, zero_map=False, conditional=True)],
        zero_map='Identical added architecture and parameter count; zero all map channels including actor marker. Capacity control, one seed; not a three-seed control claim.',
        repeat_condition='Repeat map model if all original targets pass OR movement exact exceeds both M01 and S02, joint movement accuracy does not regress versus M01, joint NLL <=1.02*M01, macro F1 >=M01-0.02, and unchanged targeting gate passes with no >0.02 target drop versus M01.',
        final_selection='Validation only. Keep current baseline unless map movement improves in every matched seed without the declared regressions; report all results. No seed cherry-picking.',
        original_targets_unchanged=True, final_test='75 new test games SEALED; new validation75 also unopened. Old exposed test not scored.',
        maximum_fits=4,
    ))


def run():
    freeze()
    from .spatial_train import run_experiment
    run_experiment()


if __name__ == '__main__':
    log_command(['.venv-action-predictor/Scripts/python.exe', '-m', 'tools.action_predictor.spatial_experiment', *sys.argv[1:]],
                purpose='Frozen terrain/objective CNN experiment; unchanged validation; final test sealed')
    freeze() if '--freeze-only' in sys.argv else run()
