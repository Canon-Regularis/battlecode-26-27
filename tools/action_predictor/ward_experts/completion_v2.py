"""Future manifests infer both expert identifiers from the frozen evaluation."""
import argparse,json
from pathlib import Path
from .protocol import ROOT,WORK,REPORT
from ..audit import immutable_json
from ..data import digest

def run(identifier,evaluation):
    info=json.loads((REPORT/f'{identifier}.json').read_text());ev=json.loads((REPORT/f'{evaluation}-evaluation.json').read_text());placement=ev['placement'];typing=ev['typing'];assert identifier in (placement,typing)
    args=f"{evaluation} {placement or '-'} {typing or '-'}";experts={};artifacts={}
    for role,name in (('placement',placement),('typing',typing)):
        if name is None:continue
        r=json.loads((REPORT/f'{name}.json').read_text());experts[role]=dict(identifier=name,fit_source_commit=r['source_commit'],fit_report_sha256=digest(REPORT/f'{name}.json'),checkpoint_sha256=r['checkpoint_sha256'])
        for p in (WORK/'runs'/name).iterdir():
            if p.is_file():artifacts[str(p.relative_to(ROOT))]=digest(p)
    names=['protocol.json','train-data.json','validation-data.json','architecture-diagnosis.json','placement-baselines.json','placement-baselines-correction.json','reporting-r2-plan.json','control-evaluation.json',f'{identifier}.json',f'{evaluation}-evaluation.json',f'{evaluation}-causal-roundtrip.json',f'{evaluation}-reporting-addendum.json']
    addendum=json.loads((REPORT/f'{evaluation}-reporting-addendum.json').read_text());references=list(addendum['paired_DEV']['primary'])
    for optional in (f'{identifier}-placement-diagnosis.json',f'{identifier}-classifier-diagnosis.json'):
        if (REPORT/optional).exists():names.append(optional)
    fit_commands=[f'python -m tools.action_predictor.ward_experts.fit {e["identifier"]}' for e in experts.values()]
    immutable_json(REPORT/f'{identifier}-completion-v2-{evaluation}.json',dict(experts=experts,fit_source_hashes=json.loads((REPORT/'protocol.json').read_text())['sources'],reports={n:digest(REPORT/n) for n in names},artifacts=artifacts,evaluation_artifacts={str(p.relative_to(ROOT)):digest(p) for p in (WORK/'evaluations'/evaluation).iterdir() if p.is_file()},commands=fit_commands+[f'python -m tools.action_predictor.ward_experts.evaluate {args}',f'python -m tools.action_predictor.ward_experts.roundtrip {args}',f'python -m tools.action_predictor.ward_experts.reporting {evaluation} {" ".join(references)}',f'python -m tools.action_predictor.ward_experts.completion_v2 {identifier} {evaluation}'],commands_are_reproduction_only='Existing run directories deliberately reject refits; retained prerequisites are reused.',source_sha256=digest(__file__),new_fits=0,reserved_opened=0,promoted=False,three_seed_confirmed=False,qualification='Shops43unassessedstrictfailures,missingargumentlossabsent;sparsecategoriesuncertified;ambiguousentityIDsnotrecovered;no originalreportoverwrite.'))
    print('Manifest v2',identifier,evaluation,args,flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('identifier');p.add_argument('evaluation');a=p.parse_args();run(a.identifier,a.evaluation)
