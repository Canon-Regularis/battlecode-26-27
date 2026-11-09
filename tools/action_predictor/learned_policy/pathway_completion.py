"""Reproduction inventory for completed Q00 preparation/Q01 attribution."""
import json
import subprocess
from pathlib import Path
from .sequence_data import ROOT,WORK,REPORT
from .pathway_protocol import LOCAL,OUT
from ..audit import immutable_json
from ..data import digest


def run():
    source=Path(__file__).parent
    plan=json.loads((OUT/'Q01-plan.json').read_text())
    for name,value in plan['sources'].items():assert digest(source/name)==value,name
    for name,value in plan['core_model_sources'].items():assert digest(source/name)==value,name
    recovery=json.loads((OUT/'Q01-numerics-recovery-plan.json').read_text())
    for name,value in recovery['sources'].items():assert digest(source/name)==value,name
    files=list(OUT.glob('Q00*'))+list(OUT.glob('Q01*'))
    files=[p for p in files if p.name!='Q01-completion.json']
    files+=list(source.glob('pathway_*.py'))+list(source.glob('test_pathway_*.py'))
    files+=[LOCAL/'Q00-plan.json',LOCAL/'Q00-result.json',LOCAL/'Q00-records.json',LOCAL/'Q00-pathway-probe.py']
    files+=list((LOCAL/'Q01/references').glob('*.npz'))
    for identifier in ('L01','L02'):
        files+=list((LOCAL/f'Q01-v2/{identifier}').glob('*.npz'))
        files+=list((LOCAL/f'Q01-v2/{identifier}').glob('*.pt'))
        info=json.loads((REPORT/f'{identifier}.json').read_text())
        files+=[WORK/f"runs/{identifier}/round-{info['selected_round']:02d}.pt",WORK/f'runs/{identifier}/validation-predictions.npz',REPORT/f'{identifier}.json']
    files += [REPORT/name for name in ('policy-design.json','policy-input-bindings.json','L02-review-response.json','L02-reporting-corrections.json','continuation-authority.json')]
    files += [source/name for name in ('model.py','data.py','inference.py','analysis.py')]
    commands=['-m unittest tools.action_predictor.learned_policy.test_pathway_inputs tools.action_predictor.learned_policy.test_pathway_numerics',
        '-m tools.action_predictor.learned_policy.pathway_protocol',
        '-m tools.action_predictor.learned_policy.pathway_reference',
        '-m tools.action_predictor.learned_policy.pathway_study_v2 L01',
        '-m tools.action_predictor.learned_policy.pathway_study_v2 L02',
        '-m tools.action_predictor.learned_policy.pathway_contracts',
        '-m tools.action_predictor.learned_policy.pathway_numerical_cases L01',
        '-m tools.action_predictor.learned_policy.pathway_numerical_cases L02',
        '-m tools.action_predictor.learned_policy.pathway_evaluate_v2',
        '-m tools.action_predictor.learned_policy.pathway_report',
        '-m tools.action_predictor.learned_policy.pathway_completion']
    immutable_json(OUT/'Q01-completion.json',dict(
        inventory_head=subprocess.run(['git','rev-parse','HEAD'],cwd=ROOT,capture_output=True,text=True,check=True).stdout.strip(),
        protocol_sha256=digest(OUT/'Q01-plan.json'),recovery_plan_sha256=digest(OUT/'Q01-numerics-recovery-plan.json'),
        bindings={str(p.relative_to(ROOT)):digest(p) for p in sorted(set(files))},
        commands=['.venv-action-predictor/Scripts/python.exe '+c for c in commands],
        reproduction='All models frozen; no training commands. Producers preserve existing attempts/results and refuse overwriting. Q00 canonical source is byte-identical to the original successful runpy producer. Original Q01 normalization-check failures remain failures; versioned v2 archives before checks and adds independent arithmetic, not a changed primary decoder. Reuse original TRAIN references.',
        evidence_limits='Fixed-state shadows do not propagate altered posteriors. Refiltered branches use earlier recorded own actions after prediction and unchanged Fish observations; no autonomous matches. Five reused DEV groups/selected weights; no replacement variant or robustness certification. No full counterfactual TRAIN generalization scores.',
        safety='Both75-game reservations sealed. No optimizer/matches/downloads/bot/native/runtime/SDK/export/deployment work. Shop arguments unavailable strict failures, identity/sparse-category/full-legality/calibration limitations retained. PR11 DRAFT/open/unmerged/no-auto-merge/queue.',
        new_fits=0,reserved_opened=0,promoted=False))


if __name__=='__main__':run()
