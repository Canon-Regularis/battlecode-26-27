"""Bounded, matched observation-history experiment. Earlier studies are read-only."""
from datetime import datetime,timezone
import json
from pathlib import Path
import sys

from .more_replays import ROOT,sha,frozen

WORK=ROOT/'.cambc/action-predictor/v7'
REPORTS=ROOT/'tools/action_predictor/experiments/v7'
OLD=ROOT/'.cambc/action-predictor/v4'
MORE=ROOT/'.cambc/action-predictor/v5'
GAP_NAMES=['frame_present','observation_available','round_gap_to_next','own_turn_boundary_to_next','round_age_to_target']


def log_command(argv,**extra):
    WORK.mkdir(parents=True,exist_ok=True)
    with (WORK/'commands.jsonl').open('a',encoding='utf-8') as stream:
        stream.write(json.dumps(dict(at=datetime.now(timezone.utc).isoformat(),cwd=str(ROOT),argv=list(map(str,argv)),**extra))+'\n')


def source_blocks():
    old=json.loads((ROOT/'.cambc/action-predictor/data/dataset.json').read_text())
    new=json.loads((MORE/'training-source.json').read_text())
    membership=json.loads((ROOT/'tools/action_predictor/experiments/v5/membership.json').read_text())
    assert {r['raw_sha256'] for r in new['recordings']}=={r['raw_sha256'] for r in membership['records'] if r['split']=='train'}
    blocks=[]
    for name,manifest,work,split,augmented in [('old_train',old,OLD,'train',True),('new_train',new,MORE,'train',True),('validation',old,OLD,'validation',False)]:
        additions=json.loads((work/'augmentation.json').read_text()) if augmented else {}
        records=[r|additions.get(r['raw_sha256'],{}) for r in manifest['recordings'] if r['split']==split]
        blocks.append(dict(name=name,manifest=manifest,work=work,records=records,
                           groups=sorted({r['group'] for r in manifest['recordings']})))
    return blocks


def freeze_plan():
    WORK.mkdir(parents=True,exist_ok=True);REPORTS.mkdir(parents=True,exist_ok=True)
    old_reports=ROOT/'tools/action_predictor/experiments/v4'
    benchmark=REPORTS/'benchmark.json'
    if not benchmark.exists():benchmark.write_bytes((old_reports/'benchmark.json').read_bytes())
    assert sha(benchmark)==sha(old_reports/'benchmark.json')
    saved=json.loads((ROOT/'tools/action_predictor/experiments/v5/M01.json').read_text())
    prior={}
    for version in ('v4','v5','v6'):
        directory=ROOT/'tools/action_predictor/experiments'/version
        for path in directory.rglob('*'):
            if path.is_file():prior[str(path.relative_to(ROOT))]=sha(path)
    prior[str((MORE/'commands.jsonl').relative_to(ROOT))]=sha(MORE/'commands.jsonl')
    # Preserve the first audit rather than silently updating its reference hashes.
    prior_path=REPORTS/'prior-studies-lock.json'
    if prior_path.exists():
        assert json.loads(prior_path.read_text())==prior,'A prior frozen study changed'
    else:frozen(prior_path,prior)
    frozen(REPORTS/'plan.json',dict(
        schema=7,hypothesis='Earlier personal observations may improve prediction beyond matched action history; no benefit assumed.',
        maximum_substantive_fits=6,
        fits=[dict(id=f'H{i:02d}',seed=seed,observations=observations,conditional=i>2)
              for i,seed,observations in [(1,26,False),(2,26,True),(3,27,False),(4,27,True),(5,28,False),(6,28,True)]],
        base_config=saved['config'],baseline_checkpoint_sha256=saved['checkpoint_sha256'],
        train_sha256=sha(MORE/'combined-train.npz'),validation_sha256=sha(OLD/'validation.npz'),
        benchmark_sha256=sha(benchmark),prior_studies_lock_sha256=sha(prior_path),
        target_rows=dict(train=433071,validation=14439),train_games=470,train_groups=94,validation_games=25,validation_groups=5,
        history_length=16,observation_projection=32,gap_fields=GAP_NAMES,
        representation='Retain full whitelisted personal PRE snapshots and supplements for evidence; encode earlier snapshots with the existing 253-field M01 current-observation encoder. This tests history of the existing representation, not a new observation encoder.',
        architecture='Retain M01 current encoder, GRU hidden64, fusion and every prediction head. Both arms widen only GRU input: existing 24 action fields + 32 projected observation fields + 5 common gap fields. Projection is Linear(253,32)+ReLU. Control zeros normalized observation values; same nominal parameters and executed dense computation.',
        initialization='Copy original M01 seeded initial GRU weights into first24 input columns; zero added input columns. Original other weights and shuffle RNG stream preserved. No warm-start from trained weights.',
        normalization='Use retained M01 training mean/std for current and earlier observation features; no validation-fitted statistics.',
        chronology='Use last16 actual earlier own root events from full recorded index, including unsampled turns. Observation PRE < its observed action event <= current prediction PRE < target action event. Same raw game, champion and Fish personal perspective. No current target label in inputs.',
        gaps='Only bot-observable round gaps/ages and own-turn boundaries. No raw replay cursor distances, unseen global action counts, opponent actions or omniscient dynamic state in neural inputs.',
        missing='Keep every target row. Explicit frame-present and observation-available fields; left padding is unavailable. Never concatenate sampled turns as adjacent. Stop before fitting on unexplained recovery, perspective, visibility, order or alignment failure; report missing support instead of dropping targets.',
        reuse='Reuse every required cached training/development-validation snapshot and supplement; recover only additional necessary earlier contexts from those same eligible games.',
        training=json.loads((old_reports/'benchmark.json').read_text())['training'],
        losses='Unchanged M01 weighted action CE, conditional spatial CE and discrete priority NLL; same support, class weights, gradient clip and optimizer.',
        checkpoint='Minimum original-development-validation observed joint NLL, improvement 0.0001; original35 epoch cap and patience6. Do not select peaks of movement accuracy.',
        exploratory_repeat_trigger='After seed26 pair, repeat matched pairs on27/28 if loss reduction>=2% OR exact/joint movement gain>=1pp OR direction-change/near-obstacle exact movement gain>=3pp with >=200 move rows; AND all regression guards pass. These are exploratory allocation criteria, never substitutes for original success targets.',
        exploratory_regression_guards='Relative to both fresh control and retained M01: loss <=1.01*reference; movement exact/joint no drop>0.5pp; macro F1 no drop>1pp; attack/cast_0/cast_1 coordinate AND family joint accuracy no drop>2pp. All target rows and available-history bins retained.',
        original_targets='Unchanged: macro F1>=0.65; exact movement >=strongest frozen simple baseline+10pp; joint loss>=10% below strongest baseline; no material targeting regression. Report historical frozen references and stronger matched controls separately.',
        contexts=dict(direction_change='For actual move labels, nonzero sign(dx,dy) differs from most recent earlier successful own move. Evaluation only, never an input.',
            near_obstacle='A public static blocked/out-of-bounds tile is within Chebyshev distance2 of personal PRE position.',
            visible_set_change='Current personally visible entity set differs from the most recent available earlier personal observation; unavailable is separate.',
            history_bins=['0','1-3','4-7','8-15','16']),
        uncertainty='2000 paired whole-game-group resamples; fixed group draws for both arms. Per-seed results, context supports, available-history lengths and all targeting regressions.',
        selection='Validation only. Retain M01 unless matched evidence supports a replacement without the guards failing. No seed cherry-picking; no success claim unless original targets hold across all three pairs.',
        reserved='All75 new validation and75 final-test games unopened; old exposed test not used. No downloads, matches, deployments, bot changes or PRs.',
    ))


if __name__=='__main__':
    log_command([sys.executable,'-m','tools.action_predictor.observation_study',*sys.argv[1:]],purpose='Freeze bounded observation-history protocol')
    freeze_plan()
