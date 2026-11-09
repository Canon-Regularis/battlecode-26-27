"""Saved-output capacity/control analysis, including microfit label coverage."""
import json
import numpy as np
from .protocol import ROOT,LOCAL,OUT
from .data import load
from ..audit import immutable_json
from ..data import digest
from ..observation_metrics import interval


def run():
    info=json.loads((OUT/'PC00.json').read_text())
    data=load();directory=LOCAL/'runs/PC00';results={};bindings={}
    fit=data['fit'];absolute=np.unique(fit['target'].numpy())
    available=fit['values'][:,5].numpy()==1
    residual=np.unique((fit['target']+fit['values'][:,4]).numpy()[available])
    for name,d in data.items():
        target=d['target'].numpy();values=d['values'].numpy();group=d['group'].numpy()
        abs_seen=np.isin(target,absolute)
        res_seen=(values[:,5]==1)&np.isin(target+values[:,4],residual)
        masks=dict(all=np.ones(len(target),bool),absolute_seen_in_new_fit=abs_seen,
                   absolute_not_seen_in_new_fit=~abs_seen,
                   some_absolute_or_residual_label_seen_in_new_fit=abs_seen|res_seen,
                   neither_point_label_seen_in_new_fit=~(abs_seen|res_seen))
        saved={}
        for step in (0,100,500,1000,2000):
            path=directory/f'{name}-step-{step:04d}-predictions.npz'
            assert digest(path)==info['bindings'][str(path.relative_to(ROOT))]
            with np.load(path) as z:saved[step]={key:z[key] for key in z.files}
            bindings[str(path.relative_to(ROOT))]=digest(path)
        results[name]={}
        for label,m in masks.items():
            n=int(m.sum());row=dict(rows=n,steps={})
            for step,p in saved.items():
                error=np.abs(p['integer']-target)
                row['steps'][str(step)]=dict(exact=int(((error==0)&m).sum()),
                    accuracy=float((error[m]==0).mean()) if n else None,
                    mean_NLL=float(p['nll'][m].mean()) if n else None,
                    mean_bounded_candidate_rank=float(p['rank'][m].mean()) if n else None,
                    mean_target_probability_source_shares=p['credit'][m].mean(0).tolist() if n else None)
            groups=np.unique(group);rng=np.random.default_rng(20261106)
            draws=np.stack([np.bincount(rng.integers(len(groups),size=len(groups)),minlength=len(groups)) for _ in range(2000)])
            denominator=np.array([(m&(group==g)).sum() for g in groups]);total=draws@denominator
            before=(saved[0]['integer']==target).astype(int);after=(saved[2000]['integer']==target).astype(int)
            correct=np.array([((after-before)[m&(group==g)]).sum() for g in groups])
            loss=np.array([(saved[2000]['nll']-saved[0]['nll'])[m&(group==g)].sum() for g in groups])
            def ratio(a):return np.divide(draws@a,total,out=np.full(2000,np.nan),where=total>0)
            row['final_minus_initial_paired_group95']=dict(accuracy=interval(ratio(correct)),NLL=interval(ratio(loss)))
            results[name][label]=row
    immutable_json(OUT/'PC00-analysis.json',dict(results=results,
        fit_absolute_values=len(absolute),fit_available_residual_values=len(residual),bindings=bindings,
        source_sha256=digest(__file__),fit_sha256=digest(OUT/'PC00.json'),
        qualification='Post-fit exploratory label-coverage strata; all original128rows per cohort '
                      'remain in all. These labels are derived from the new microfit only, not prior '
                      'P05/encoder exposure. Both encoder and warm head previously saw controls. '
                      'Fine-tuning forgetting, output-label coverage, representation and transfer '
                      'are not isolated causes. Paired group intervals conditional on fixed cohorts, '
                      'one seed and prior exposure, not untouched full-policy uncertainty. '
                      'Candidate rank is bounded, not full integer support rank.',
        new_fits=0,reserved_opened=0))
    print(json.dumps({name:{key:dict(rows=value['rows'],initial=value['steps']['0']['exact'],final=value['steps']['2000']['exact'])
                           for key,value in rows.items()} for name,rows in results.items()},indent=2))


if __name__=='__main__':run()
