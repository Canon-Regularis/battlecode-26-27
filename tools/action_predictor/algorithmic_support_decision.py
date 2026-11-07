"""Bind TRAIN support gate outcome and pinned query provenance; no fits/DEV."""
import json,hashlib
from pathlib import Path
from .algorithmic.study import ROOT,WORK,REPORT,JOBS
from .audit import immutable_json
from .data import digest

def run():
    c1=json.loads((REPORT/'C01-train.json').read_text());c2=json.loads((REPORT/'C02-train.json').read_text());control=json.loads((REPORT/'C00-train.json').read_text())['libraries']['simple']['per_family'];gates={}
    for name,r,ground in [('C01',c1['libraries']['C01']['per_family'],c1['libraries']['C01']['ground_cast1']['union_with_G00']),('C02',c2['per_family'],c1['libraries']['C01']['ground_cast1']['union_with_G00'])]:
        observed={'move':r['move']['union_with_G00'],'ground_cast1':ground,'ward':r['ward']['union_with_G00'],'priority':r['priority']['union_with_G00'],'blocked':r['blocked']['union_with_G00']};minimum={'move':.90,'ground_cast1':.70,'ward':.40,'priority':.30,'blocked':.20};checks={k:dict(observed=observed[k],required=minimum[k],passes=observed[k]>=minimum[k]) for k in minimum}
        # C00's original report has only pure library coverage. Reconstruct its
        # frozen union with G00 to apply the explicitly planned no-regression gate.
        import numpy as np
        from .algorithmic.study import matches
        with np.load(ROOT/'.cambc/action-predictor/v5/combined-train.npz') as z:y=z['y'];py=z['py'];p=z['priority']
        with np.load(WORK.parent/'v9/runs/G00/train-predictions.npz') as z:b=matches(np.stack((z['prediction'],z['proposed_coordinate'],z['priority']),-1)[:,None],y,py,p).any(1)
        old=np.load(WORK/'train-candidates.npy',mmap_mode='r');covered=matches(old[:,1],y,py,p).any(1)
        for family,code in [('attack',2),('cast_0',5)]:
            baseline=float((covered|b)[y==code].mean());checks[family+'_no_regression']=dict(observed=r[family]['union_with_G00'],required=baseline,passes=r[family]['union_with_G00']>=baseline)
        gates[name]=dict(checks=checks,allocate_fit=all(v['passes'] for v in checks.values()),DEV_evaluation_allocated=False)
    assert not any(v['allocate_fit'] for v in gates.values())
    jobs=json.loads(JOBS.read_text());provenance=[];constants=json.loads((REPORT/'C01-historical-constants.json').read_text())
    for version in ('2.0.0','3.0.0'):
        job=next(j for j in jobs if j['split']=='train' and j['record']['engine_version']==version);path=Path(job['work'])/'supplement'/job['record']['raw_sha256']/'query.json';q=json.loads(path.read_text());assert q['raw_sha256']==job['record']['raw_sha256'];raw=Path(q['raw']);assert digest(raw)==q['raw_sha256'];data=raw.read_bytes();assert '.'.join(map(str,data[8:11]))==version;result=next(r for r in constants['results'] if r['engine_version']==version);assert result['raw_sha256']==q['raw_sha256'] and result['constants']['wardPlacementRange']==2
        provenance.append(dict(engine=version,raw_sha256=q['raw_sha256'],query_sha256=digest(path)))
    immutable_json(REPORT/'C01-C02-support-decision.json',dict(source_sha256=digest(__file__),original_gate_plan_sha256=digest(REPORT/'C01-plan.json'),study_bindings={name:digest(REPORT/f'{name}-train.json') for name in ('C01','C02')},roundtrip_sha256=digest(REPORT/'C01-C02-TRAIN-roundtrip.json'),gates=gates,pinned_query_source_sha256=digest(Path(__file__).with_name('algorithmic_semantics.cjs')),query_provenance=provenance,decision='No fit or DEVlibraryevaluation allocated. Retain negatives; nextdiagnosepriorityandwardobjectivestate/groundcastsemantics onTRAINbefore another frozenstudy. Noallalgorithmsexhaustedclaim.',new_fits=0,DEV_rows_evaluated=0,reserved_opened=0))
    print(json.dumps(gates,indent=2))

if __name__=='__main__':run()
