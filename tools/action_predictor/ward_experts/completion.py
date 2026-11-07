"""Immutable per-fit experiment manifest using the actual execution commit."""
import json,sys
from pathlib import Path
from .protocol import ROOT,WORK,REPORT
from ..audit import immutable_json
from ..data import digest

def run(identifier,evaluation):
    r=json.loads((REPORT/f'{identifier}.json').read_text());directory=WORK/'runs'/identifier;names=['protocol.json','train-data.json','validation-data.json','architecture-diagnosis.json','placement-baselines.json','control-evaluation.json',f'{identifier}.json',f'{evaluation}-evaluation.json',f'{evaluation}-causal-roundtrip.json']
    if (REPORT/f'{identifier}-placement-diagnosis.json').exists():names.append(f'{identifier}-placement-diagnosis.json')
    immutable_json(REPORT/f'{identifier}-completion.json',dict(fit_source_commit=r['source_commit'],fit_source_hashes=json.loads((REPORT/'protocol.json').read_text())['sources'],reports={name:digest(REPORT/name) for name in names},artifacts={str(p.relative_to(ROOT)):digest(p) for p in directory.iterdir() if p.is_file()},evaluation_artifacts={str(p.relative_to(ROOT)):digest(p) for p in (WORK/'evaluations'/evaluation).iterdir() if p.is_file()},commands=[f'python -m tools.action_predictor.ward_experts.fit {identifier}',f'python -m tools.action_predictor.ward_experts.evaluate {evaluation} {identifier}',f'python -m tools.action_predictor.ward_experts.roundtrip {evaluation} {identifier}'],source_sha256=digest(__file__),new_fits=0,reserved_opened=0,shops='all43DEVunassessedstrictfailures;purchaseargumentlikelihoodabsent',promoted=False,three_seed_confirmed=False))
    print('Manifest',identifier,flush=True)

if __name__=='__main__':run(sys.argv[1],sys.argv[2])
