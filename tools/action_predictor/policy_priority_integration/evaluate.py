"""Score preserved frozen joint forecasts, including causal-family competition."""
import json
import subprocess
import sys
import numpy as np
import torch

from ..audit import immutable_json
from ..data import digest
from ..observation_metrics import correctness
from ..learned_policy.analysis import paired_categories,readiness_flags,read
from ..movement_experts.evaluate import summary,support,masks,paired
from ..priority_broad.guard import committed_sources
from ..priority_regularized.safety import dependency_files,reject_optimized_python
from ..order_information.anchored import committed_manifest
from ..priority_capacity.measurement import target_credits
from ..priority_modes import logistic_log_mass
from .protocol import ROOT,OUT,LOCAL,ROWS,ARMS,inputs
from .forecast import models


def semantic_equal(a,b):
    """Only action-required argument slots count as semantic command changes."""
    same=a['prediction']==b['prediction'];spatial=np.isin(a['prediction'],[1,2,3,5,6,8,12,13,14])
    same&=~spatial|(a['proposed_coordinate']==b['proposed_coordinate'])
    same&=(a['prediction']!=9)|(a['priority']==b['priority'])
    return same


def category_summary(d,p,mask):
    result=summary(d,p,mask);raw=d['raw']
    for code,row in enumerate(result['per_category']):
        m=mask&(raw['y']==code)
        row['observed_joint_nll']=float(p['nll'][m].mean()) if m.any() else None
        row['type_nll']=float(p['type_nll'][m].mean()) if m.any() else None
        row['parameter_nll']=float(p['param_nll'][m].mean()) if m.any() and code!=11 else None
    return result


def priority_diagnostics(raw,p,forecast,mask,vocabulary,frequency):
    m=mask&(raw['y']==9);typed=m&(p['prediction']==9);guess=mask&(p['prediction']==9)
    correct=p['priority']==raw['priority'];error=np.abs(p['priority'].astype(np.float64)-raw['priority'].astype(np.float64))
    strata={'all':m,'absolute_seen':m&np.isin(raw['priority'],vocabulary),
        'absolute_unseen':m&~np.isin(raw['priority'],vocabulary)}
    rare_values=vocabulary[np.asarray(frequency)<=5]
    strata['absolute_frequency_at_most5']=m&np.isin(raw['priority'],rare_values)
    out={}
    for name,s in strata.items():
        t=s&(p['prediction']==9)
        out[name]=dict(rows=int(s.sum()),conditional_exact=int((s&correct).sum()),joint_exact=int((t&correct).sum()),
            typed_rows=int(t.sum()),conditional_MAE=float(error[s].mean()) if s.any() else None,
            typed_MAE=float(error[t].mean()) if t.any() else None,conditional_max_error=float(error[s].max()) if s.any() else None,
            typed_max_error=float(error[t].max()) if t.any() else None,
            mean_fallback_weight=float(forecast['fallback_weight'][s].mean()) if s.any() else None)
        if 'priority_credit' in p:
            out[name]['mean_recorded_target_mass_source_shares']=p['priority_credit'][s].mean(0).tolist() if s.any() else None
            out[name]['source_share_order']=['absolute_point','residual_point','logistic_fallback']
    out['false_positives']=dict(type=int((guess&~m).sum()),joint=int((guess&~(m&correct)).sum()),
        recorded_family_counts=np.bincount(raw['y'][guess&~m],minlength=15).tolist())
    return out


def competition(raw,p,forecast,type_logp,mode_joint_logp):
    other=np.array(mode_joint_logp,dtype=np.float64);other[:,9]=-np.inf
    best=other.argmax(1);r=np.arange(len(best));peak=other[r,best]
    priority_type=np.asarray(type_logp[:,9],dtype=np.float64)
    # Optimistic conditional point mass ONE; a diagnostic bound, never a forecast.
    possible=(priority_type>peak)|((priority_type==peak)&(9<best))
    actual=priority_type+forecast['mode_logp'];margin=actual-peak
    true=raw['y']==9;correct=p['priority']==raw['priority'];typed=p['prediction']==9
    return dict(priority_rows=int(true.sum()),conditional_mode_correct=int((true&correct).sum()),
        joint_correct=int((true&correct&typed).sum()),correct_integer_loses_family_competition=int((true&correct&~typed).sum()),
        wrong_integer_but_priority_selected=int((true&~correct&typed).sum()),
        optimistic_fixed_type_and_other_heads_priority_joint_ceiling=int((true&possible).sum()),
        priority_unreachable_even_with_unit_conditional_mass=int((true&~possible).sum()),
        true_priority_joint_margin_quantiles=np.quantile(margin[true],[0,.25,.5,.75,1]).tolist(),
        marginal_priority_type_argmax_correct=int((true&(np.asarray(type_logp).argmax(1)==9)).sum()),
        meaning='Oracle probability upper bound with frozen family beliefs and other conditional heads, not achieved accuracy or a proposed decoder. Correct-integer mode can lose joint competition; diffuse Q is consistently discounted. No type-first replacement is selected.')


def run():
    reject_optimized_python();torch.set_num_threads(4)
    commit,sources=committed_sources(ROOT,dependency_files(ROOT,('tools.action_predictor.policy_priority_integration.evaluate',
        'tools.action_predictor.policy_priority_integration.test_evaluate')))
    test=subprocess.run([sys.executable,'-m','unittest','tools.action_predictor.policy_priority_integration.test_evaluate','-v'],
        cwd=ROOT,capture_output=True,text=True)
    if test.returncode:raise RuntimeError('Assessment prerequisite failed: '+test.stdout+test.stderr)
    receipts,bindings=inputs();heads=models(receipts)
    ready_path=OUT/'JP-forecasts-ready.json';ready=json.loads(ready_path.read_text())
    if ready['plan_sha256']!=digest(OUT/'JP-forecast-plan.json'):raise RuntimeError('Forecast plan changed')
    bindings[str(ready_path.relative_to(ROOT))]=digest(ready_path)
    for split in ROWS:
        for name,value in ready['results'][split]['files'].items():
            if digest(ROOT/name)!=value:raise RuntimeError('Archived forecast changed: '+name)
            bindings[name]=value
    baseline_receipt=json.loads((ROOT/'tools/action_predictor/experiments/v16/L02.json').read_text())
    family=receipts['family_cache'];consumed={};datasets={};predictions={};forecasts={};null_checks={}
    for split,n in ROWS.items():
        dataset=ROOT/('.cambc/action-predictor/v5/combined-train.npz' if split=='train' else '.cambc/action-predictor/v4/validation.npz')
        expected='39386010575ad30add064fdae750680f34cfcc732c4fd00fb657875ff4c61ffb' if split=='train' else '01a15e1e10f68922334a5367bb825c8ef9bbe228ae7a9e86e92aae9609b204ed'
        if digest(dataset)!=expected:raise RuntimeError('Original benchmark changed')
        bindings[str(dataset.relative_to(ROOT))]=expected;raw=read(dataset);datasets[split]=raw
        baseline_path=ROOT/f'.cambc/action-predictor/v16/runs/L02/{split}-predictions.npz'
        if digest(baseline_path)!=baseline_receipt['predictions_sha256'][split]:raise RuntimeError('Baseline predictions changed')
        bindings[str(baseline_path.relative_to(ROOT))]=digest(baseline_path);old=read(baseline_path)
        family_arrays={}
        for field in ('family_coordinate','type_logp','mode_joint_logp'):
            fc=ROOT/f'.cambc/action-predictor/v26/family-cache/{split}/{field}.npy'
            key=str(fc.relative_to(ROOT));expected=family['results'][split]['files'][key]
            if digest(fc)!=expected:raise RuntimeError('All-family cache changed')
            bindings[key]=expected;family_arrays[field]=np.load(fc,mmap_mode='r')
        consumed[split]=family_arrays
        coordinate=family_arrays['family_coordinate'][np.arange(n),raw['y']]
        with np.load(ROOT/f'.cambc/action-predictor/v8/priority-{split}.npz') as z:values=z['values']
        predictions[split]={};forecasts[split]={}
        for arm,model in heads.items():
            directory=LOCAL/f'forecasts/{split}/{arm}'
            saved={k:np.load(directory/(k+'.npy'),mmap_mode='r') for k in
                ('raw','integer','mode_logp','fallback_weight','prediction','proposed_coordinate')}
            p={k:np.array(v) for k,v in old.items()};p['coordinate']=np.array(coordinate)
            for key in ('prediction','proposed_coordinate'):p[key]=np.array(saved[key])
            p['priority']=np.array(saved['integer']);p['nll']=old['nll'].astype(np.float64);p['param_nll']=old['param_nll'].astype(np.float64)
            p['priority_credit']=np.full((n,3),np.nan,np.float64)
            ix=np.flatnonzero(raw['y']==9)
            with torch.inference_mode():
                for start in range(0,len(ix),256):
                    ids=ix[start:start+256];output=torch.from_numpy(np.array(saved['raw'][ids]));target=torch.from_numpy(raw['priority'][ids].astype(np.int64))
                    lp=model.log_mass(output,target) if arm=='JP03' else model.log_mass(output,target,torch.from_numpy(values[ids]))
                    if arm=='JP03':
                        mix=output[:,:-2].double().log_softmax(-1)
                        at=torch.searchsorted(model.values,target);safe=at.clamp(max=len(model.values)-1)
                        present=(at<len(model.values))&(model.values[safe]==target)
                        absolute=mix.gather(1,safe[:,None])[:,0].masked_fill(~present,-torch.inf)
                        fallback=mix[:,-1]+logistic_log_mass(output[:,-2:],target)
                        credit=(torch.stack((absolute,torch.full_like(absolute,-torch.inf),fallback),-1)-lp[:,None]).exp()
                    else:
                        _,credit=target_credits(model,output,torch.from_numpy(values[ids]),target)
                    p['priority_credit'][ids]=credit.numpy()
                    p['param_nll'][ids]=-lp.numpy();p['nll'][ids]=p['type_nll'][ids]+p['param_nll'][ids]
            path=LOCAL/f'{arm}-{split}-predictions.npz'
            if path.exists():raise FileExistsError('Preserve prior assessment attempt')
            np.savez_compressed(path,**p);bindings[str(path.relative_to(ROOT))]=digest(path)
            predictions[split][arm]=p;forecasts[split][arm]=saved
        null=predictions[split]['JP00']
        checks=dict(semantic_command_mismatches=int((~semantic_equal(null,old)).sum()),
            conditional_coordinate_mismatches=int((null['coordinate']!=old['coordinate']).sum()),
            priority_mode_mismatches=int((null['priority']!=old['priority']).sum()),
            max_observed_NLL_difference=float(np.abs(null['nll']-old['nll']).max()),
            unchanged_nonpriority_loss=bool(np.array_equal(null['nll'][raw['y']!=9],old['nll'][raw['y']!=9])))
        immutable_json(OUT/f'JP-null-{split}.json',checks);null_checks[split]=checks
        if any(checks[k] for k in ('semantic_command_mismatches','conditional_coordinate_mismatches','priority_mode_mismatches')) or checks['max_observed_NLL_difference']>2e-5 or not checks['unchanged_nonpriority_loss']:
            raise RuntimeError('Frozen null parity failed; outputs preserved, assessment stopped')
    results={};comparisons={};refs={}
    natural_path=ROOT/'.cambc/action-predictor/v9/frequency/natural-mask.npy'
    expected='09217d8fc3d5673d980c8b8a4434861aa26dddb37e506bbfa22cbaafc0e525bd'
    if digest(natural_path)!=expected:raise RuntimeError('Natural membership changed')
    bindings[str(natural_path.relative_to(ROOT))]=expected;natural=np.load(natural_path)
    for split,raw in datasets.items():
        receipt,more=committed_manifest('bcfc9949271de9baf9f1d10b815658e1e8eb423d','tools/action_predictor/experiments/v7/data-ready.json')
        bindings.update(more);d=dict(raw=raw)
        for key,suffix in (('direction','direction'),('available','available'),('near','near_obstacle')):
            path=ROOT/f'.cambc/action-predictor/v7/{split}-{suffix}.npy';value=receipt['files'][path.name]
            if digest(path)!=value:raise RuntimeError('Original V7 diagnostic changed')
            bindings[str(path.relative_to(ROOT))]=value;d[key]=np.load(path)
        sampling={'all':np.ones(len(raw['y']),bool)}
        if split=='train':
            sampling['natural']=natural;population=receipts['RC_protocol']['population']
            fit=np.isin(raw['group'],population['fit_groups']);held=np.isin(raw['group'],population['held_groups'])
            sampling.update(natural_correction_fit_groups=natural&fit,natural_correction_held_groups=natural&held,
                natural_other_groups=natural&~(fit|held))
        results[split]={}
        for arm,p in predictions[split].items():
            row={}
            for name,mask in sampling.items():
                row[name]=dict(overall=category_summary(d,p,mask),
                    contexts={k:category_summary(d,p,mask&m) for k,m in masks(d).items() if k in ('move','blocked','continue','change','startup','zero_displacement')},
                    priority=priority_diagnostics(raw,p,forecasts[split][arm],mask,
                        np.array(receipts['absolute_vocabulary']['values']),receipts['absolute_vocabulary']['counts']))
            row['partial_legality']=support(d,p);row['partial_readiness']=readiness_flags(raw,p)
            row['priority_competition']=competition(raw,p,forecasts[split][arm],consumed[split]['type_logp'],consumed[split]['mode_joint_logp'])
            results[split][arm]=row
        if split=='validation':
            for arm in ARMS:
                comparisons[arm]={}
                for reference in ('JP00','JP01','JP03'):
                    if reference==arm:continue
                    p,o=predictions[split][arm],predictions[split][reference]
                    comparison=paired_categories(raw,p,o,sampling['all']);comparison['movement_contexts']=paired(d,p,o)
                    changed=~semantic_equal(p,o);type_changed=p['prediction']!=o['prediction']
                    comparison['command_changes']=dict(semantic=int(changed.sum()),type=int(type_changed.sum()),
                        arguments_same_type=int((changed&~type_changed).sum()),nonpriority_type_changes=int((type_changed&(p['prediction']!=9)&(o['prediction']!=9)).sum()))
                    comparisons[arm][reference]=comparison
            for name,path in dict(G00='v9/runs/G00',B00='v13/runs/B00',L02='v16/runs/L02').items():
                full=ROOT/f'.cambc/action-predictor/{path}/validation-predictions.npz';o=read(full)
                if 'family_commands' in o:
                    o['coordinate']=o['family_commands'][np.arange(len(raw['y'])),raw['y'],1];o['priority']=o['family_commands'][:,9,2]
                bindings[str(full.relative_to(ROOT))]=digest(full)
                refs[name]={arm:paired_categories(raw,p,o,sampling['all']) for arm,p in predictions[split].items()}
    immutable_json(OUT/'JP-results.json',dict(source_commit=commit,sources=sources,bindings=bindings,results=results,
        comparisons=comparisons,retained_comparisons=refs,null_checks=null_checks,
        tests=dict(returncode=test.returncode,stdout=test.stdout,stderr=test.stderr),
        limitations='Exploratory reused DEV5groups, one fitted correction per arm, no untouched/three-seed claim. TRAIN natural membership uses frozen augmented-cadence filter, not natural-cadence inference. Shop arguments unavailable/strict failures and absent from observed loss; coordinate identity ambiguity and sparse-category uncertainty remain. Full legality/global calibration unassessed.',
        new_fits=0,optimizer_updates=0,reserved_opened=0,command='python -m tools.action_predictor.policy_priority_integration.evaluate'))
    print('Frozen full-policy comparison complete', {a:results['validation'][a]['all']['overall']['strict_correct'] for a in ARMS},flush=True)


if __name__=='__main__':run()
