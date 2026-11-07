"""Freeze V4 development protocol before any new training."""
import json
from pathlib import Path

from .audit import immutable_json
from .data import digest

REPORTS = Path('tools/action_predictor/experiments/v4')
WORK = Path('.cambc/action-predictor/v4')


def freeze():
    old = Path('tools/action_predictor/experiments/v3')
    lock = json.loads((old/'split-lock.json').read_text())
    manifest = json.loads(Path('.cambc/action-predictor/data/dataset.json').read_text())
    history = Path(manifest['source']).parents[0]/'evaluation-partition-history.json'
    # source points to micro-expanded-v1.5, whose parent is replay-evaluation.
    history = Path(manifest['source']).parent/'evaluation-partition-history.json'
    protocol = dict(schema=4, split_lock_sha256=digest(old/'split-lock.json'),
        original_dataset_sha256=digest('.cambc/action-predictor/data/dataset.json'),
        source_partition_history_sha256=digest(history),
        untouched_fish_games=0, untouched_status='None certified. Original expert reservation previously inspected; remaining unopened reservation is candidate cohort. Later Fish studies already evaluated.',
        splits={s:dict(groups=sorted({r['group'] for r in lock['recordings'] if r['split']==s}),
                       matches=[r['match'] for r in lock['recordings'] if r['split']==s]) for s in ('train','validation','test')},
        test_policy='Same previously exposed test games; sealed during V4 development. Evaluate locked three-seed winner once at the end. No pristine external performance claim.',
        duplicates='Verify actual unzipped payload SHA256; fail on any cross-group or cross-split duplicate. Preserve original whole groups.',
        targets=dict(action_macro_f1=.65, movement_gain_absolute=.10, joint_loss_reduction_relative=.10,
                     maximum_attack_or_cast_exact_regression=.02),
        consistency='All three seeds must meet all point targets on validation. Report group bootstrap 95% CIs; consistent gain additionally requires improvement CI above zero. A seed or targeting-family failure is a failure, not averaged away.',
        task='Predict each recorded root action and its observable parameters from personal PRE plus strictly earlier own recorded actions. No intent/strategy annotations.',
        labels=dict(action='Existing 15-class vocabulary; unknown support is retained.',
                    coordinate_actions=['move','blocked','attack','cast_0','cast_1','ward','submit','altar','teleport'],
                    coordinate_domain='17x17 relative offsets plus explicit outside-window/missing-observation labels. Every action remains in benchmark; unsupported exact parameters count as joint errors.',
                    priority='Exact recorded signed integer priority; discrete logistic probability mass.',
                    shop='Immediate recorded net inventory/consumable/gold change vector is retained as label. Original item/count can be unidentifiable; do not claim original transaction reconstruction.'),
        loss='Mean per-action observed joint NLL = action categorical NLL + required coordinate categorical NLL + required discrete-logistic priority NLL. Missing original shop arguments are unobserved, not fabricated. Shop net-change prediction is diagnostic. This partially observed likelihood cannot certify full API-command reconstruction.',
        metrics=['action accuracy, macro F1, per-class precision/recall/F1/support and confusion matrix',
                 'joint action+all-assessable-parameter exact accuracy over ALL actions; shops/unobservable params count as unassessed failures for strict full-command accuracy',
                 'conditional and joint movement exact/top3/top5 and mean Chebyshev destination error; failed/blocked attempts separate',
                 'attack/cast exact and top-k with single-candidate and multi-candidate support',
                 'observable invalid-command rate with assessed denominator; full engine legality explicitly unassessed where evidence is insufficient',
                 '2000 bootstrap resamples of whole groups, paired for model-baseline differences; seed variability separate'],
        baselines=['smoothed action frequency','smoothed previous-action transitions',
                   'most-common valid movement offset','last recorded own movement offset (persistence)',
                   'nearest visible camp / nearest altar with gems: legal candidate reducing distance',
                   'nearest compatible target','lowest-health compatible target','self for self-only abilities',
                   'comparable stateless learned models, including rich-observation variant'],
        baseline_choice='Strongest baseline selected using validation only. Movement strongest means greatest exact accuracy; loss baseline means smallest observed joint NLL; targeting reference means best exact per family. Freeze choices before final scoring.',
        observation_boundary='Supplemental gold, stats, ward state, map and movement masks must be queried at the exact personal PRE cursor. POST transaction deltas are labels only. No outcome, future event, actor ID, map ID or replay ID in model inputs.',
        illegal_rate='Movement mask is an exact read-only personal query. Other checks use current restrictions/readiness/visible geometry and are partial. No action simulation, alternate timelines or matches.',
        selection='Checkpoint by validation observed joint NLL except explicitly balanced runs may use declared macro-F1 checkpoint criterion. Rank configurations by number of proposed point targets met, then lowest validation joint NLL. Freeze winner before additional seeds and final test.',
        experiment_budget=10, seed_schedule=[26,27,28],
        experiments=[
            dict(id='E01',name='stateless-basic',history=0,rich=False,spatial=False,balance=0.),
            dict(id='E02',name='gru-basic-history4',history=4,rich=False,spatial=False,balance=0.),
            dict(id='E03',name='stateless-rich-spatial',history=0,rich=True,spatial=True,balance=0.),
            dict(id='E04',name='gru-rich-history4',history=4,rich=True,spatial=True,balance=0.),
            dict(id='E05',name='gru-rich-history16',history=16,rich=True,spatial=True,balance=0.),
            dict(id='E06',name='gru-rich-balanced',history=16,rich=True,spatial=True,balance=.5),
            dict(id='E07',name='gru-rich-history32-balanced',history=32,rich=True,spatial=True,balance=.5),
            dict(id='E08',name='gru-rich-focal',history=16,rich=True,spatial=True,balance=.5,focal=1.),
            dict(id='E09',name='validation-winner-seed27',repeat_winner=True),
            dict(id='E10',name='validation-winner-seed28',repeat_winner=True)],
        training=dict(max_epochs=35,patience=6,batch_size=256,lr=.001,weight_decay=.0001,hidden=128,history_hidden=64,gradient_clip=1.,threads=4),
        stop='Stop early only if targets met consistently across three seeds; otherwise finish up to 10 experiments and report bottlenecks without relaxing criteria.')
    immutable_json(REPORTS/'benchmark.json',protocol)
    immutable_json(REPORTS/'split-lock.json',lock)
    immutable_json(REPORTS/'partition-provenance.json',json.loads(history.read_text()))
    print('Frozen benchmark:',digest(REPORTS/'benchmark.json'))


if __name__ == '__main__':
    freeze()
