"""Immutable evidence inventory and actual reproduction commands for one fit."""
import json
import subprocess
import sys
from pathlib import Path
from .sequence_data import ROOT, BASE, WORK, REPORT
from ..audit import immutable_json
from ..data import digest


def run(identifier):
    info = json.loads((REPORT / f'{identifier}.json').read_text())
    directory = WORK / f'runs/{identifier}'
    checkpoint = directory / f"round-{info['selected_round']:02d}.pt"
    assert digest(checkpoint) == info['checkpoint_sha256']
    files = [*directory.glob('round-*.pt'), *directory.glob('*-predictions.npz'),
             *directory.glob('*-goals.npz'), *Path(__file__).parent.glob('*.py')]
    for name in ('policy-design.json', 'policy-input-bindings.json', 'sequence-plan.json',
                 'achieved-goal-plan.json', 'analysis-plan.json', 'preflight.json',
                 'personal-input-roundtrip.json', 'portable-original-preflight-failure.json',
                 'goal-target-support.json',
                 'known-limits-before-results.json', 'known-input-omissions-addendum.json',
                 'portable-preflight-v2.json', f'{identifier}.json', f'{identifier}-analysis.json',
                 f'{identifier}-portable-roundtrip.json', f'{identifier}-export.json',
                 f'{identifier}-actor-roundtrip.json'):
        p = REPORT / name
        if p.exists(): files.append(p)
    for suffix in ('-REPORT.md', '-matched-movement.json'):
        p = REPORT / f'{identifier}{suffix}'
        if p.exists(): files.append(p)
    # Bind the actual upstream code imported by this fit/adapter without repeating
    # the immutable 495-game extraction or running historical audit scripts.
    for name in ('reliable_model.py', 'reliable_train.py', 'priority_fit_v3.py',
                 'entity_set.py', 'priority_predictor.py', 'priority_inputs.py',
                 'priority_residual_predictor.py', 'priority_residual_modes.py',
                 'observation_data.py', 'rich_data.py', 'observation_metrics.py'):
        files.append(Path(__file__).parents[1] / name)
    files.extend([BASE.parent / 'v9/frequency/natural-mask.npy',
                  ROOT / 'sdk/python/cambc/__init__.py'])
    for split in ('train', 'validation'):
        for suffix in ('sequences', 'goals', 'public'):
            files.append(REPORT / f'{split}-{suffix}.json')
    exports = WORK / f'exports/{identifier}'
    if exports.exists(): files.extend(exports.iterdir())
    priority_export = WORK / 'exports/P05'
    if priority_export.exists(): files.extend(priority_export.iterdir())
    for name in ('P05-portable-export.json', 'P05-portable-roundtrip.json', 'P05-portable-preflight-failure.json'):
        p = REPORT / name
        if p.exists(): files.append(p)
    complexity = dict(goal_policy_nominal_parameters=info['parameters'],
                      goal_policy_declared_trainable=info['parameters'] - 258,
                      inactive_L00_retention_parameters=151 if identifier == 'L00' else 0,
                      reused_frozen_priority_component_learned_weight_scalars=298824,
                      full_exported_neural_weight_scalars=info['parameters'] + 298824,
                      qualification='Goal policy includes its unused frozen258-scalar legacy priority linear layer; L00 retains but does not use the151-scalar retention layer. Reused P05 port includes its frozen M01 context encoder plus integer-mixture linear. Dictionary buffers and feature work are additional; no small-total-model or production latency claim.')
    commands = [f'.venv-action-predictor/Scripts/python.exe -m tools.action_predictor.learned_policy.{module} {identifier}'
                for module in ('fit', 'analysis', 'matched_movement', 'export', 'portable_roundtrip', 'actor_roundtrip', 'completion')]
    immutable_json(REPORT / f'{identifier}-completion.json', dict(
        identifier=identifier, selected_round=info['selected_round'],
        selected_updates=info['selected_updates'], completed_updates=info['completed_updates'],
        actual_fit_commit=info['source_commit'],
        complexity=complexity,
        inventory_commit=subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip(),
        bindings={str(p.relative_to(ROOT)):digest(p) for p in files},
        commands_from_repo_root=commands,
        shared_prerequisites=['learned_policy.sequence_data train/validation',
                              'learned_policy.achieved_goals train/validation',
                              'learned_policy.public_inputs train/validation',
                              'learned_policy.goal_targets_diagnosis',
                              'learned_policy.input_roundtrip'],
        safety='Fit is one registered optimizer run. Reproduction fit command intentionally refuses an existing directory; do not overwrite/retrain to reproduce inference. Both reserved partitions sealed; no matches, downloads, existing bot edits or deployment.',
        timing_scope='Fit timer starts after data loading/model/optimizer initialization; includes all training rounds, DEV inference, selected TRAIN/DEV full decoding, prediction serialization and evaluation. Not pure optimization time or complete end-to-end wall cost.',
        bot_status='Causal actor dispatch and portable host math exist; native WASI/live personal-SDK bridge, draft and unavailable purchase/ambiguous target arguments remain unresolved. No closed-loop strength or complete bot certification.',
        new_fits=0, reserved_opened=0, promoted=False))


if __name__ == '__main__':
    run(sys.argv[1])
