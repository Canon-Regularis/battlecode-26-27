"""PC02: same PC01 population/optimization plus one TRAIN-derived warm penalty."""
import json
import subprocess
import sys
import time
import traceback
from pathlib import Path

import numpy as np
import torch

from .. import reliable_train as rt
from ..audit import immutable_json
from ..data import digest
from ..priority_broad.guard import checked_execution
from ..priority_capacity.data import head,load
from ..priority_capacity.measurement import measure
from .safety import committed_closure,reject_optimized_python,archive_then_measure

ROOT=Path(__file__).resolve().parents[3]
OLD=ROOT/'.cambc/action-predictor'
OUT=ROOT/'tools/action_predictor/experiments/v22'
LOCAL=OLD/'v22'
TEST_COMMAND=[sys.executable,'-m','unittest',
    'tools.action_predictor.priority_regularized.test_safety',
    'tools.action_predictor.priority_capacity.test_measurement']


def displacement_penalty(parameters,warm,strength):
    return strength*sum((p.double()-base.double()).square().sum() for p,base in zip(parameters,warm))


def execute(tests):
    reject_optimized_python()
    if len(tests)!=1 or tests[0]['returncode']!=0 or tests[0]['command']!=TEST_COMMAND:
        raise RuntimeError('FIT_PREREQUISITES_FAILED')
    commit,sources=committed_closure()
    rt.setup(20261120)
    model,_,initial_path=head()
    parameters=list(model.parameters())
    names=[name for name,_ in model.named_parameters()]
    if names!=['linear.weight','linear.bias'] or not all(p.requires_grad for p in parameters):
        raise RuntimeError('Unexpected trainable parameter schema')
    warm=[p.detach().clone() for p in parameters]
    parent_path=ROOT/'tools/action_predictor/experiments/v21/PC01.json'
    parent=json.loads(parent_path.read_text())
    parent_preflight_path=ROOT/'tools/action_predictor/experiments/v21/PC01-preflight.json'
    parent_preflight=json.loads(parent_preflight_path.read_text())
    cohort_path=OLD/'v21/PC01-cohort.npz'
    if digest(cohort_path)!=parent['cohort_sha256'] or not parent_preflight['passed']:
        raise RuntimeError('Prior cohort/preflight binding failed')
    with np.load(cohort_path) as z:
        fit={key:torch.from_numpy(z[key]) for key in z.files}
    if len(fit['target'])!=5876:
        raise RuntimeError('Changed fitting denominator')
    controls=load()
    for name in ('same_fit_groups','held_groups'):
        if np.isin(controls[name]['index'].numpy(),fit['index'].numpy()).any():
            raise RuntimeError('Control row entered optimization population')
    parent_directory=OLD/'v21/runs/PC01'
    parent_states={}
    bindings={str(parent_path.relative_to(ROOT)):digest(parent_path),
              str(parent_preflight_path.relative_to(ROOT)):digest(parent_preflight_path),
              str(cohort_path.relative_to(ROOT)):digest(cohort_path),
              str(initial_path.relative_to(ROOT)):digest(initial_path)}
    for step in (0,2000):
        path=parent_directory/f'step-{step:04d}.pt'
        if digest(path)!=parent['bindings'][str(path.relative_to(ROOT))]:
            raise RuntimeError('Parent checkpoint binding failed')
        bindings[str(path.relative_to(ROOT))]=digest(path)
        parent_states[step]=torch.load(path,weights_only=True,map_location='cpu')
    for key,value in model.state_dict().items():
        if not torch.equal(value,parent_states[0]['head_state'][key]):
            raise RuntimeError('Warm initialization differs from PC01')
    if not torch.equal(torch.get_rng_state(),parent_states[0]['torch_rng']):
        raise RuntimeError('Initialization RNG differs from PC01')
    # Strength uses TRAIN quantities only. No control metric enters this formula.
    drift=sum(float((parent_states[2000]['head_state'][name].double()-base.double()).square().sum())
              for name,base in zip(names,warm))
    initial_train_NLL=parent['trace'][0]['cohorts']['broad_fit']['mean_NLL']
    if drift<=0:
        raise RuntimeError('Invalid parent drift scale')
    strength=.5*initial_train_NLL/drift
    plan=dict(id='PC02-warm-start-regularization',source_commit=commit,sources=sources,inputs=bindings,
        treatment='Change only objective: original PC01 full-population mean normalized integer NLL '
                  '+lambda*SUM squared displacement of all linear weights AND bias from warm P05. '
                  'No mean-over-parameters normalization; no omitted parameter block.',
        penalty=dict(lambda_value=strength,rule='.5*PC01 initial broad TRAIN NLL / PC01 final squared '
                    'parameter displacement. TRAIN-derived allocation rule fixed before PC02; no '
                    'control tuning or sweep. At PC01 endpoint the penalty equals half initial TRAIN NLL.',
                    initial_TRAIN_NLL=initial_train_NLL,parent_squared_displacement=drift,
                    ratio=.5,parameter_names=names),
        population='Exactly PC01 cohort5876natural TRAIN priority rows/55groups, same controls excluded.',
        unchanged='Warm head/inputs/normalization/int64 anchors/vocabulary/probability arithmetic/MAP, '
                  'seed20261120,2000updates,fullpopulation mean accumulated via chunks256, '
                  'AdamW .003 first1000/.001last1000,WD0,clip5,CPU4threads.',
        endpoint='Fixed2000; assessments0,100,500,1000,2000 descriptive. No DEV payloads, '
                 'threshold/calibration/checkpoint/penalty selection or policy replacement.',
        exposure='Warm head AND frozen encoder/vocabulary/normalizer previously saw controls. '
                 'Excluded only from new optimization; not untouched full-policy generalization.',
        metrics='All four PC01 cohorts: conditional integer exact,NLL,MAE,bounded candidate rank, '
                'marginalized explanation shares,mode confidence. Paired whole-group comparisons '
                'versus warm P05 and PC01 fixedfinal, original benchmark separate.',
        exploratory_gate=dict(broad_accuracy_gain_over_warm_at_least=.20,
            both_control_NLL_lower_than_warm=True,both_control_exact_at_least_warm=True,
            one_control_net_commands_over_warm_at_least=5,
            meaning='Named pilot allocation criterion, not original success or robustness. '
                    'Merely suppressing learning to recover warm scores is insufficient.'),
        safety='Reject optimized Python; bind static repository-local import closure and explicit '
               'test roots against HEAD; real-entrypoint optimizer-tripwire failure tests. '
               'Save each entire raw cohort before any measurement callback.',
        continuation='Fresh Solxhigh review after fit; follow evidence, no automatic larger model/repeats. '
                     'Original complete-command/category/macro/movement/loss/targeting/three-seed goals '
                     'remain binding. Any future integration re-decodes normalized joint probabilities.',
        constraints='TRAINonly,no matches/downloads/bot/runtime/deployment; both75game reservations sealed.',
        new_fits_allocated=1,new_fits=0,reserved_opened=0)
    immutable_json(OUT/'PC02-plan.json',plan)
    # The penalty is zero, with zero derivatives, at the shared initialization.
    penalty=displacement_penalty(parameters,warm,strength)
    if float(penalty.detach())!=0:
        raise RuntimeError('Nonzero warm displacement at initialization')
    gradients=torch.autograd.grad(penalty,parameters)
    if any(torch.count_nonzero(g) for g in gradients):
        raise RuntimeError('Penalty changes initial command gradient')
    current_commit,current_sources=committed_closure()
    if current_commit!=commit or current_sources!=sources:
        raise RuntimeError('Source changed after preflight')
    immutable_json(OUT/'PC02-preflight.json',dict(passed=True,source_commit=commit,sources=sources,
        protocol_sha256=digest(OUT/'PC02-plan.json'),cohort_sha256=digest(cohort_path),
        initial_head_and_RNG_exact_PC01=True,initial_penalty_and_derivatives_zero=True,
        prior_accumulation_preflight_sha256=digest(parent_preflight_path),test_receipts=tests,
        no_optimizer_constructed_before_preflight=True,new_fits=0,reserved_opened=0))
    directory=LOCAL/'runs/PC02'
    if directory.exists():
        raise FileExistsError('Preserve prior attempted fit; never restart automatically')
    directory.mkdir(parents=True)
    optimizer=torch.optim.AdamW(parameters,lr=.003,weight_decay=0)
    if optimizer.state_dict()!=parent_states[0]['optimizer']:
        raise RuntimeError('Optimizer initialization differs from PC01')
    if {id(p) for p in parameters}!={id(p) for g in optimizer.param_groups for p in g['params']}:
        raise RuntimeError('Optimizer parameter membership mismatch')
    cohorts=dict(broad_fit=fit,original_fit=controls['fit'],
                 same_fit_groups=controls['same_fit_groups'],held_groups=controls['held_groups'])
    trace=[]
    tick=time.perf_counter()

    def assess(step):
        torch.save(dict(head_state=model.state_dict(),optimizer=optimizer.state_dict(),step=step,
            torch_rng=torch.get_rng_state(),source_commit=commit,lambda_value=strength,
            protocol_sha256=digest(OUT/'PC02-plan.json'),preflight_sha256=digest(OUT/'PC02-preflight.json')),
            directory/f'step-{step:04d}.pt')
        row=dict(step=step,seconds=time.perf_counter()-tick,cohorts={},
                 penalty=float(displacement_penalty(parameters,warm,strength).detach()))
        with torch.inference_mode():
            for name,d in cohorts.items():
                raw=np.concatenate([model(d['context'][s:s+256],d['features'][s:s+256]).numpy()
                                    for s in range(0,len(d['target']),256)])
                def evaluate(saved_raw):
                    predictions={}
                    for start in range(0,len(d['target']),256):
                        sl=slice(start,start+256)
                        output=torch.from_numpy(np.array(saved_raw[sl],copy=True))
                        p,_=measure(model,output,d['values'][sl],d['target'][sl])
                        p['mode_probability']=model.log_mass(output,p['integer'],d['values'][sl]).exp()
                        for key,value in p.items():
                            predictions.setdefault(key,[]).append(value.numpy())
                    return {key:np.concatenate(value) for key,value in predictions.items()}
                p=archive_then_measure(raw,directory/f'{name}-step-{step:04d}-raw.npy',evaluate)
                np.savez_compressed(directory/f'{name}-step-{step:04d}-predictions.npz',**p)
                error=np.abs(p['integer']-d['target'].numpy())
                row['cohorts'][name]=dict(rows=len(error),exact=int((error==0).sum()),
                    accuracy=float((error==0).mean()),mean_NLL=float(p['nll'].mean()),MAE=float(error.mean()),
                    mean_bounded_candidate_rank=float(p['rank'].mean()),
                    mean_marginalized_explanation_shares=p['credit'].mean(0).tolist(),
                    mean_mode_probability=float(p['mode_probability'].mean()))
        trace.append(row)
        print('PC02',step,{name:(v['exact'],v['mean_NLL']) for name,v in row['cohorts'].items()},
              'penalty',row['penalty'],flush=True)

    assess(0)
    try:
        for step in range(1,2001):
            if step==1001:
                for group in optimizer.param_groups:
                    group['lr']=.001
            optimizer.zero_grad(set_to_none=True)
            for start in range(0,len(fit['target']),256):
                sl=slice(start,start+256)
                raw=model(fit['context'][sl],fit['features'][sl])
                loss=-model.log_mass(raw,fit['target'][sl],fit['values'][sl]).sum()/len(fit['target'])
                if not torch.isfinite(loss):
                    raise RuntimeError('Nonfinite command objective')
                loss.backward()
            # Exactly once per full-population update, not once per chunk.
            displacement_penalty(parameters,warm,strength).backward()
            if not all(p.grad is not None and torch.isfinite(p.grad).all() for p in parameters):
                raise RuntimeError('Nonfinite/missing parameter derivative')
            torch.nn.utils.clip_grad_norm_(parameters,5)
            optimizer.step()
            if step in (100,500,1000,2000):
                assess(step)
            elif step%100==0:
                print('PC02 progress',step,'seconds',round(time.perf_counter()-tick,2),flush=True)
    except BaseException:
        (directory/f'failure-{time.time_ns()}.txt').write_text(traceback.format_exc())
        raise
    final,initial=trace[-1]['cohorts'],trace[0]['cohorts']
    checks=dict(broad_fit_gain=final['broad_fit']['accuracy']-initial['broad_fit']['accuracy']>=.20,
        both_control_NLL_lower=all(final[n]['mean_NLL']<initial[n]['mean_NLL'] for n in ('same_fit_groups','held_groups')),
        both_control_exact_not_lower=all(final[n]['exact']>=initial[n]['exact'] for n in ('same_fit_groups','held_groups')),
        some_control_gain5=any(final[n]['exact']-initial[n]['exact']>=5 for n in ('same_fit_groups','held_groups')))
    immutable_json(OUT/'PC02.json',dict(source_commit=commit,sources=sources,trace=trace,lambda_value=strength,
        protocol_sha256=digest(OUT/'PC02-plan.json'),preflight_sha256=digest(OUT/'PC02-preflight.json'),
        bindings={str(p.relative_to(ROOT)):digest(p) for p in directory.iterdir()},
        cohort_sha256=digest(cohort_path),fixed_final_step=2000,optimizer_updates=2000,
        trainable_parameters=sum(p.numel() for p in parameters),seconds=time.perf_counter()-tick,
        gate=checks,exploratory_gate_passed=all(checks.values()),new_fits=1,reserved_opened=0,
        conditional_diagnostic_only=True,policy_replaced=False,promoted=False,three_seed_confirmed=False))
    print('PC02 complete; fresh Solxhigh review required.',flush=True)


def main():
    reject_optimized_python()
    committed_closure()
    checked_execution([TEST_COMMAND],execute,ROOT)


if __name__=='__main__':
    main()
