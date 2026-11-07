"""Additive P01-review fixes; never rewrite model or prior reporting receipts."""
import argparse,json
from .protocol import ROOT,WORK,REPORT
from ..audit import immutable_json
from ..data import digest

def run(identifier,evaluation):
    report=REPORT/f'{evaluation}-reporting-addendum.json'
    a=json.loads(report.read_text());ev=json.loads((REPORT/f'{evaluation}-evaluation.json').read_text())
    corrected=[]
    for split,decoders in a['results'].items():
        for decoder,samplings in decoders.items():
            for sampling,summary in samplings.items():
                for kind,strata in summary['contexts'].items():
                    for key,row in strata.items():
                        denominator=row['ward_support']+row['ward_type_TP']+row['ward_type_FP']
                        if denominator==0:
                            corrected.append(dict(path=['results',split,decoder,sampling,'contexts',kind,key,'ward_type_F1'],old=row['ward_type_F1'],corrected=None,reason='2TP+FP+FN is zero; F1 undefined, counts preserved'))
    references=list(a['paired_DEV']['primary']);bindings={}
    for name in references:
        p=REPORT/f'{name}-evaluation.json'
        bindings[name]=dict(report_sha256=digest(p),archives={str(p.relative_to(ROOT)):digest(p) for p in (WORK/'evaluations'/name).iterdir() if p.is_file()})
    experts={};diagnostic_commands=[];diagnostic_hashes={}
    for role,key in [('placement','placement'),('typing','typing')]:
        name=ev[key]
        if name is None:continue
        fit=json.loads((REPORT/f'{name}.json').read_text());experts[role]=dict(identifier=name,fit_report_sha256=digest(REPORT/f'{name}.json'),fit_source_commit=fit['source_commit'],checkpoint_sha256=fit['checkpoint_sha256'],artifacts={str(p.relative_to(ROOT)):digest(p) for p in (WORK/'runs'/name).iterdir() if p.is_file()})
        p=REPORT/f'{name}-placement-diagnosis.json'
        if p.exists():
            diagnostic_commands.append(f'python -m tools.action_predictor.ward_experts.diagnose {name}');diagnostic_hashes[p.name]=digest(p)
    args=f"{evaluation} {ev['placement'] or '-'} {ev['typing'] or '-'}"
    commands=[f'python -m tools.action_predictor.ward_experts.fit {v["identifier"]}' for v in experts.values()]+[f'python -m tools.action_predictor.ward_experts.evaluate {args}',f'python -m tools.action_predictor.ward_experts.roundtrip {args}']+diagnostic_commands+[f'python -m tools.action_predictor.ward_experts.reporting {evaluation} {" ".join(references)}',f'python -m tools.action_predictor.ward_experts.completion_v3 {identifier} {evaluation}']
    immutable_json(REPORT/f'{identifier}-completion-v3-{evaluation}.json',dict(experts=experts,commands=commands,comparator_bindings=bindings,diagnostic_reports=diagnostic_hashes,reporting_sha256=digest(report),evaluation_sha256=digest(REPORT/f'{evaluation}-evaluation.json'),serving_sha256=digest(REPORT/f'{evaluation}-causal-roundtrip.json'),prediction_archives={str(p.relative_to(ROOT)):digest(p) for p in (WORK/'evaluations'/evaluation).iterdir() if p.is_file()},undefined_context_F1_corrections=corrected,source_sha256=digest(__file__),fit_protocol_sha256=digest(REPORT/'protocol.json'),reporting_plan_sha256=digest(REPORT/'reporting-r2-plan.json'),qualification='Additive correction supersedes F1 only at listed paths; original counts/receipts unchanged. Comparator hashes bind the actual paired archives. Commands document reproduction, not permission to rerun existing fits. Original targets remain unmet; no promotion or seed claim. Shop arguments unavailable; sparse categories uncertified.',new_fits=0,reserved_opened=0))
    print(identifier,evaluation,'v3 manifest; undefined context F1 corrections',len(corrected),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('identifier');p.add_argument('evaluation');a=p.parse_args();run(a.identifier,a.evaluation)
