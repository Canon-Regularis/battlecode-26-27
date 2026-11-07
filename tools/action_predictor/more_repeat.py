"""Apply the predeclared three-seed check to a promising more-data result."""
import json

import numpy as np

from .more_replays import WORK, REPORTS, frozen, sha, log_command
from .more_train import OLD, OLD_REPORTS, combined_data
from . import reliable_train as rt
from .development import gates
from .group_uncertainty import bootstrap, paired


def run():
    log_command(['.venv-action-predictor/Scripts/python.exe', '-m',
                 'tools.action_predictor.more_repeat'],
                purpose='Apply frozen repeat condition and repeated seeds, if eligible')
    plan = json.loads((REPORTS / 'repeat-plan.json').read_text())
    result = json.loads((REPORTS / 'validation-comparison.json').read_text())
    before, after = result['old'], result['more_data']
    conditions = dict(
        movement=after['parameters']['move']['exact_accuracy'] > before['parameters']['move']['exact_accuracy'],
        joint_loss=after['joint_nll'] < before['joint_nll'],
        macro_f1=after['macro_f1'] >= before['macro_f1'],
        targeting=result['unchanged_target_gates']['passed']['targeting'],
    )
    clarification = REPORTS / 'repeat-trigger-clarification.json'
    assert clarification.exists()
    all_targets = all(result['unchanged_target_gates']['passed'].values())
    promising = all(conditions.values()) or all_targets
    frozen(REPORTS / 'repeat-decision.json', dict(
        plan_sha256=sha(REPORTS / 'repeat-plan.json'), conditions=conditions,
        trigger_clarification_sha256=sha(clarification), all_four_targets_pass=all_targets,
        promising=promising, additional_fits=2 if promising else 0,
        decision='Use all predeclared criteria; no reserved data opened.',
    ))
    if not promising:
        print('M01 does not satisfy the frozen repeat condition; no additional fits.')
        return
    assert plan['additional_seeds'] == [27, 28]
    with np.load(OLD / 'validation.npz', allow_pickle=False) as archive:
        validation = {k: archive[k] for k in archive.files}
    assert sha(OLD / 'validation.npz') == json.loads((REPORTS / 'retrain-plan.json').read_text())['original_validation_sha256']
    training = combined_data()
    original = json.loads((OLD_REPORTS / 'E06.json').read_text())['config']
    references = json.loads((OLD_REPORTS / 'selection-lock.json').read_text())['references']
    baselines = json.loads((OLD_REPORTS / 'validation-evaluation.json').read_text())['models']
    rt.WORK, rt.REPORTS = WORK, REPORTS
    evidence = []
    for seed, identifier, old_id in [(26, 'M01', 'E06'), (27, 'M02', 'E07'), (28, 'M03', 'E08')]:
        path = REPORTS / (identifier + '.json')
        if not path.exists():
            config = original | dict(id=identifier, repeats='M01')
            rt.fit(config, seed, training, validation, train_source=WORK / 'combined-train.npz',
                   validation_source=OLD / 'validation.npz')
        info = json.loads(path.read_text())
        assert info['seed'] == seed and info['parameters'] == 104160
        prediction_path = WORK / 'runs' / identifier / 'validation-predictions.npz'
        old_path = OLD / 'runs' / old_id / 'validation-predictions.npz'
        old_info = json.loads((OLD_REPORTS / (old_id + '.json')).read_text())
        assert old_info['seed'] == seed
        assert sha(old_path) == old_info['predictions_sha256']
        assert sha(prediction_path) == info['predictions_sha256']
        with np.load(prediction_path, allow_pickle=False) as archive:
            prediction = {k: archive[k] for k in archive.files}
        with np.load(old_path, allow_pickle=False) as archive:
            old_prediction = {k: archive[k] for k in archive.files}
        intervals, _, _ = bootstrap(validation, prediction)
        evidence.append(dict(
            seed=seed, experiment=identifier, original_experiment=old_id,
            validation=info['validation'], original_validation=old_info['validation'],
            group_intervals=intervals, paired_changes=paired(validation, prediction, old_prediction),
            target_gates=gates(info['validation'], references, baselines),
            checkpoint_sha256=sha(WORK / 'runs' / identifier / 'model.pt'),
        ))
    metrics = dict(macro_f1=lambda s: s['macro_f1'], joint_nll=lambda s: s['joint_nll'],
                   movement_exact=lambda s: s['parameters']['move']['exact_accuracy'],
                   joint_recorded_accuracy=lambda s: s['strict_full_command_accuracy'])
    summary = {}
    for name, get in metrics.items():
        values = [get(r['validation']) for r in evidence]
        summary[name] = dict(mean=float(np.mean(values)), minimum=min(values), maximum=max(values))
    frozen(REPORTS / 'three-seed-check.json', dict(
        runs=evidence, summary=summary,
        all_targets_met_consistently=all(all(r['target_gates']['passed'].values()) for r in evidence),
        original_validation_only=True, new_validation_games_opened=0, final_test_games_opened=0,
        selection='Configuration fixed before repeated fits; no seed selected for a final test.',
    ))
    print('Three-seed check complete; reserved games remain unopened.')


if __name__ == '__main__':
    run()
