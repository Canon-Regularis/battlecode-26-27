"""Model-only post-fit inventory following the user's bot-work pause."""
import json
import subprocess
import sys
from pathlib import Path
from .sequence_data import ROOT, WORK, REPORT
from ..audit import immutable_json
from ..data import digest


def run(identifier):
    info=json.loads((REPORT/f'{identifier}.json').read_text())
    directory=WORK/f'runs/{identifier}'
    files=list(directory.glob('round-*.pt'))
    files.extend(directory.glob('*-predictions.npz'));files.extend(directory.glob('*-goals.npz'));files.extend(directory.glob('*-components.npz'))
    source_names=('model.py','data.py','inference.py','fit.py','sequence_data.py','achieved_goals.py','public_inputs.py',
                  'analysis.py','matched_movement.py','components.py','dominance_bounds.py','interventions.py',
                  'natural_evaluation.py','test_natural_evaluation.py','model_completion.py')
    source_names=source_names+('memory_analysis.py','retention_gradients.py')
    files.extend(Path(__file__).with_name(n) for n in source_names)
    common=('policy-design.json','policy-input-bindings.json','sequence-plan.json','achieved-goal-plan.json','analysis-plan.json',
            'component-execution-plan.json','L01-sensitivity-plan.json','natural-cadence-evaluation-plan.json',
            'memory-diagnostic-plan.json','memory-interpretation-addendum.json','retention-gradient-plan.json',
            'model-only-redirection.json','L00-review.json','L00-review-response.json')
    filenames=list(common)+[f'{identifier}{suffix}' for suffix in (
        '.json','-analysis.json','-matched-movement.json','-train-components.json','-validation-components.json',
        '-train-dominance-bound.json','-validation-dominance-bound.json','-natural-cadence.json',
        '-memory-diagnostic.json',
        '-retention-gradients.json','-current-mode-oracles.json',
        '-waypoint_uncertainty_projection_off.json','-persistent_goal_state_reset.json','-REPORT.md')]
    files.extend(REPORT/n for n in filenames if (REPORT/n).exists())
    for root in (WORK/f'natural-evaluation/{identifier}',WORK/f'interventions/{identifier}'):
        if root.exists():files.extend(p for p in root.rglob('*.npz') if p.is_file())
    console=WORK/f'{identifier}-console.log'
    if console.exists():files.append(console)
    if identifier=='L01':files.append(WORK/'L01-retention-gradients.json')
    for split in ('train','validation'):
        for suffix in ('sequences','goals','public'):files.append(REPORT/f'{split}-{suffix}.json')
    # Model guards bind the same historical source snapshot as L00; runtime
    # implementation files need not be executed or modified to check this.
    design=json.loads((REPORT/'policy-design.json').read_text())
    for name,expected in design['sources'].items():assert digest(Path(__file__).with_name(name))==expected,name
    immutable_json(REPORT/f'{identifier}-model-completion.json',dict(
        fit_source_commit=info['source_commit'],inventory_head=subprocess.run(['git','rev-parse','HEAD'],cwd=ROOT,capture_output=True,text=True,check=True).stdout.strip(),
        checkpoint_sha256=info['checkpoint_sha256'],selected_round=info['selected_round'],selected_updates=info['selected_updates'],completed_updates=info['completed_updates'],
        bindings={str(p.relative_to(ROOT)):digest(p) for p in files},
        commands=[f'.venv-action-predictor/Scripts/python.exe -m tools.action_predictor.learned_policy.{m} {identifier}' for m in ('fit','analysis','matched_movement','natural_evaluation')]+[
            f'.venv-action-predictor/Scripts/python.exe -m tools.action_predictor.learned_policy.memory_analysis {identifier}',
            f'.venv-action-predictor/Scripts/python.exe -m tools.action_predictor.learned_policy.components {identifier} train',
            f'.venv-action-predictor/Scripts/python.exe -m tools.action_predictor.learned_policy.components {identifier} validation',
            f'.venv-action-predictor/Scripts/python.exe -m tools.action_predictor.learned_policy.dominance_bounds {identifier} train',
            f'.venv-action-predictor/Scripts/python.exe -m tools.action_predictor.learned_policy.dominance_bounds {identifier} validation']+(
            ['.venv-action-predictor/Scripts/python.exe -m tools.action_predictor.learned_policy.interventions',
             '.venv-action-predictor/Scripts/python.exe -m tools.action_predictor.learned_policy.retention_gradients'] if identifier=='L01' else [])+[
            f'.venv-action-predictor/Scripts/python.exe -m tools.action_predictor.learned_policy.model_completion {identifier}'],
        reproduction='Fit commands intentionally refuse an existing attempt directory. Reproduce predictions/diagnostics from preserved selected checkpoints; do not overwrite or refit.',
        scope='Model training/evaluation only under explicit user redirection. Bot/runtime/native/SDK/fuel/export work paused, old prototypes preserved and excluded from this new inventory. No matches/downloads/deployment/reserved access.',
        timing_scope='Original fit timer excludes data loading and includes optimizer rounds, DEV scoring, final inference, serialization and evaluation; not pure optimization time.',
        caveats='Original benchmark retained. Secondary natural-cadence TRAIN scores remain in-sample. Component-mode unions and current-distribution dominance bounds are oracle diagnostics, not achieved accuracy or architecture ceilings. Sensitivity tests are inference-time pathway interventions, not intent recovery.',
        new_fits=0,reserved_opened=0,promoted=False))


if __name__=='__main__':run(sys.argv[1])
