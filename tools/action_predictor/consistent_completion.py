"""Immutable postfit manifest, distinct from the fit's already frozen receipts."""
import json,sys
from pathlib import Path
from .consistent_data import ROOT,WORK,REPORT
from .audit import immutable_json
from .data import digest

def run(identifier):
    info=json.loads((REPORT/f'{identifier}.json').read_text());directory=WORK/'runs'/identifier
    reports=[REPORT/n for n in ('protocol-r3.json','verified-inputs.json','train-inputs.json','validation-inputs.json','train-probabilities.json','validation-probabilities.json','train-controls.json','validation-controls.json','train-support.json','validation-support.json',f'{identifier}.json',f'{identifier}-analysis.json',f'{identifier}-selection.json',f'{identifier}-probability-contract.json',f'{identifier}-causal-roundtrip.json')]
    immutable_json(REPORT/f'{identifier}-completion.json',dict(reports={str(p.relative_to(ROOT)):digest(p) for p in reports},artifacts={str(p.relative_to(ROOT)):digest(p) for p in directory.iterdir() if p.is_file()},source_commit='3ed62158e0a7cb2f44253b900056078a2c4a79cc',analysis_sources={str(p.relative_to(ROOT)):digest(p) for p in (Path(__file__),Path(__file__).with_name('consistent_analysis.py'),Path(__file__).with_name('consistent_selection.py'),Path(__file__).with_name('consistent_roundtrip.py'),Path(__file__).with_name('consistent_predictor.py'),Path(__file__).with_name('mixture_contract_audit.py'))},
        commands=[f'python -m tools.action_predictor.consistent_study {identifier}',f'python -m tools.action_predictor.consistent_analysis {identifier}',f'python -m tools.action_predictor.consistent_selection {identifier}',f'python -m tools.action_predictor.mixture_contract_audit {identifier}',f'python -m tools.action_predictor.consistent_roundtrip {identifier}',f'python -m tools.action_predictor.consistent_completion {identifier}'],
        cwd=str(ROOT),interpreter=str(ROOT/'.venv-action-predictor/Scripts/python.exe'),selected_optimizer_updates=info['selected_round']*846,completed_optimizer_updates=info['optimizer_updates'],three_seed_confirmed=False,promoted=False,new_fits=0,reserved_opened=0,
        qualifications='All43DEVshops unassessed strict failures, missingargumentlikelihood absent. Sparsealtar/teleport/submit uncertified. Probability is over modeled observed variables, not original fullshopAPIcommands. Entityidentity ambiguous at somecoordinates. Full enginelegality unassessed. Both75+75reserved sealed. Total predictor includes frozen G00/P05 and feature/candidate construction; selector parametercount is not totalmodelcost. No productionlatency claim.'))
    print('Completed manifest',identifier,flush=True)

if __name__=='__main__':run(sys.argv[1])
