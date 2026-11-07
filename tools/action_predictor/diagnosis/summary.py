"""Compact reviewable evidence index; preserve large immutable audit locally."""
import json
from .saved import ROOT,OLD,WORK,REPORT,read
from ..data import digest
from ..audit import immutable_json

def run():
    r=read(REPORT/'R00-saved.json');out={k:v for k,v in r.items() if k!='models'};out['full_evidence_sha256']=digest(REPORT/'R00-saved.json');out['full_evidence_location']='Local tools/action_predictor/experiments/v11/R00-saved.json;6.5MB exhaustive group/confusion export intentionally excluded from git, preserved and reproducible by diagnosis.saved';out['models']={}
    for name,model in r['models'].items():
        out['models'][name]={}
        for split,sets in model.items():
            out['models'][name][split]={k:v for k,v in sets.items() if k!='groups'}
            out['models'][name][split]['groups']={g:{k:v[k] for k in ('rows','strict','macro_f1','observed_nll')} for g,v in sets['groups'].items()}
    immutable_json(REPORT/'R00-summary.json',out)
    sources={str(p.relative_to(ROOT)):digest(p) for p in (ROOT/'tools/action_predictor/diagnosis').glob('*.py')}
    files={str(p.relative_to(ROOT)):digest(p) for p in (REPORT/'R00-plan.json',REPORT/'R00-saved.json',REPORT/'R00-summary.json',REPORT/'R01-movement.json',REPORT/'R02-plan.json',REPORT/'R02-capacity.json',REPORT/'R02-review.md',REPORT/'R02-review-addendum.json')}
    immutable_json(REPORT/'completion.json',dict(sources=sources,files=files,local_files={str(p.relative_to(ROOT)):digest(p) for p in (WORK/'R01-row-diagnostics.jsonl',WORK/'R02-capacity/final.pt',WORK/'R02-capacity/row-indices.npz',*(WORK/'R02-capacity').glob('*-predictions.npz'))},commands=['.venv-action-predictor/Scripts/python.exe -m tools.action_predictor.diagnosis.'+name for name in ('saved','movement','capacity','addendum','summary')],capacity_fit_count=1,capacity_updates=2000,production_fits=0,reserved_opened=0,notes='Do not rerun completedcapacityfit or unchangedaudits;immutableproducer guards preserve outputs. Freshpostfitreview reproduced finalpredictions;reportingcorrections additive. No model promotion.'))
    print('Compactsummary', (REPORT/'R00-summary.json').stat().st_size,flush=True)

if __name__=='__main__':run()
