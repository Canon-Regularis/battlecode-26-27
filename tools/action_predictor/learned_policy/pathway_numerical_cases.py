"""Double mixture MAP/NLL checks of saved worst-normalization frozen steps."""
import json
import sys
import numpy as np
import torch
from .model import SPATIAL
from .pathway_protocol import LOCAL,OUT
from .pathway_reference import load_model
from ..audit import immutable_json
from ..data import digest


@torch.no_grad()
def run(identifier):
    torch.set_num_threads(2);model,_,checkpoint=load_model(identifier)
    directory=LOCAL/f'Q01-v2/{identifier}';path=directory/'normalization-worst-cases.pt'
    ready=json.loads((OUT/f'Q01-{identifier}-ready-v2.json').read_text())
    assert digest(path)==ready['worst_cases_sha256']
    cases=torch.load(path,weights_only=False);records=[]
    for branch,scopes in cases.items():
        for scope,case in scopes.items():
            step=case['step'];geo=case['geometry'];n=len(step['context']);row=torch.arange(n)
            goal=step['logprior'].double().log_softmax(-1)
            typ=model.types(step).double().log_softmax(-1)
            type_mass=torch.logsumexp(goal[:,:,None]+typ,1)
            scores=type_mass.clone();coordinates=torch.full((n,15),-1,dtype=torch.long);joints={}
            for family in SPATIAL:
                codes=torch.full((n,),family,dtype=torch.long)
                head=model.spatial_log_probs(step,**geo,family=codes).double().log_softmax(-1)
                joint=torch.logsumexp(goal[:,:,None]+typ[:,:,family,None]+head,1)
                joints[family]=joint;scores[:,family],coordinates[:,family]=joint.max(-1)
            scores[:,9]+=case['priority_mode_logp'].double()
            prediction=scores.argmax(-1);coordinate=coordinates[row,prediction]
            primary=case['primary'];same=prediction==primary['prediction']
            spatial=torch.zeros(n,dtype=torch.bool)
            for family in SPATIAL:spatial|=prediction==family
            equal=same&(~spatial|(coordinate==primary['coordinate']))
            equal&=(prediction!=9)|(case['priority_mode']==primary['priority'])
            valid=torch.as_tensor(case['valid']);y=case['target']['y'];py=case['target']['py']
            logmass=type_mass[row,y].clone()
            for family,joint in joints.items():
                m=y==family
                if m.any():logmass[m]=joint[m][torch.arange(int(m.sum())),py[m]]
            logmass[y==9]-=case['target']['priority_parameter_nll'][y==9].double()
            difference=(-logmass-case['primary_nll'].double()).abs()
            at=case['at'];family=case['kind']
            records.append(dict(branch=branch,scope=scope,worst_sum_error=case['error'],
                original_batch_index=at,original_row=int(case['rows'][at]),at_valid=case['at_valid'],
                examined_family=family,true_family=int(y[at]),primary_predicted_family=int(primary['prediction'][at]),
                primary_type_log_probability=float(primary['type_logp'][at,int(family)]) if family!='type' else None,
                valid_decisions=int(valid.sum()),semantic_MAP_mismatches_valid=int((valid&~equal).sum()),
                semantic_MAP_mismatch_original_rows=case['rows'][(valid&~equal).numpy()].tolist(),
                max_NLL_discrepancy_valid=float(difference[valid].max()) if valid.any() else None,
                double_type_normalization_max_error=float((type_mass.exp().sum(-1)-1).abs().max()),
                meaning='Independent normalized float64 mixture over the frozen float32 component outputs/current stored causal step. No new decoder/policy or changed benchmark forecasts. Full original batch shape retained; compare only real decisions for semantic/NLL checks.'))
    immutable_json(OUT/f'Q01-{identifier}-numerical-cases.json',dict(records=records,
        cases_checked=len(records),valid_case_decisions=sum(r['valid_decisions'] for r in records),
        semantic_MAP_mismatches_valid=sum(r['semantic_MAP_mismatches_valid'] for r in records),
        max_NLL_discrepancy_valid=max(r['max_NLL_discrepancy_valid'] or 0 for r in records),
        worst_cases_sha256=digest(path),ready_sha256=digest(OUT/f'Q01-{identifier}-ready-v2.json'),
        checkpoint_sha256=digest(checkpoint),source_sha256=digest(__file__),
        qualification='Worst-case selected numerical cohort, duplicates across scopes possible; not a new random evaluation sample or complete independent causal-filter reproduction. Original2e-6 float32 conditional-normalization criterion remains failed where reported.',
        new_fits=0,reserved_opened=0))
    print('Q01 numerical cases',identifier,len(records),'MAP mismatches',sum(r['semantic_MAP_mismatches_valid'] for r in records),flush=True)


if __name__=='__main__':run(sys.argv[1])
