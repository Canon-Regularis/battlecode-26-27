"""O01: verified personal action-order information against retained PC02 control."""
import json
import subprocess
import sys
import time
import traceback

import numpy as np
import torch

from .. import reliable_train as rt
from ..audit import immutable_json
from ..data import digest
from ..priority_broad.guard import committed_sources,checked_execution
from ..priority_capacity.data import head
from ..priority_capacity.measurement import measure
from ..priority_regularized.experiment import displacement_penalty
from ..priority_regularized.safety import reject_optimized_python,dependency_files,archive_then_measure
from .data import ROOT,OUT,LOCAL,load,numeric_mean_inputs
from .model import OrderHead

TEST_MODULES=('tools.action_predictor.order_information.test_entrypoint',
 'tools.action_predictor.order_information.test_model',
 'tools.action_predictor.order_information.test_asinh',
 'tools.action_predictor.order_information.test_anchored',
 'tools.action_predictor.priority_regularized.test_safety',
 'tools.action_predictor.priority_capacity.test_measurement')
TEST_COMMAND=[sys.executable,'-m','unittest',*TEST_MODULES]
STRENGTH=3.029750319831723e-5


def source_gate():
    reject_optimized_python()
    return committed_sources(ROOT,dependency_files(ROOT,
        ('tools.action_predictor.order_information.fit',*TEST_MODULES)))


def assess_cohort(model,d,directory,name,step,order=None):
    """Archive raw predictions before any diagnostic can fail."""
    order=d['order'] if order is None else order
    with torch.inference_mode():
        raw=np.concatenate([model(d['context'][s:s+256],d['features'][s:s+256],order[s:s+256]).numpy()
                            for s in range(0,len(d['target']),256)])
        def evaluate(saved):
            result={}
            for start in range(0,len(d['target']),256):
                sl=slice(start,start+256)
                output=torch.from_numpy(np.array(saved[sl],copy=True))
                values,_=measure(model,output,d['values'][sl],d['target'][sl])
                values['mode_probability']=model.log_mass(output,values['integer'],d['values'][sl]).exp()
                for key,value in values.items():result.setdefault(key,[]).append(value.numpy())
            return {key:np.concatenate(value) for key,value in result.items()}
        p=archive_then_measure(raw,directory/f'{name}-step-{step:04d}-raw.npy',evaluate)
        np.savez_compressed(directory/f'{name}-step-{step:04d}-predictions.npz',**p)
    error=np.abs(p['integer']-d['target'].numpy())
    return dict(rows=len(error),exact=int((error==0).sum()),accuracy=float((error==0).mean()),
        mean_NLL=float(p['nll'].mean()),MAE=float(error.mean()),
        mean_bounded_candidate_rank=float(p['rank'].mean()),
        mean_marginalized_explanation_shares=p['credit'].mean(0).tolist(),
        mean_mode_probability=float(p['mode_probability'].mean()))


def execute(prepared,tests):
    reject_optimized_python()
    if len(tests)!=1 or tests[0]['returncode']!=0 or tests[0]['command']!=TEST_COMMAND:
        raise RuntimeError('FIT_PREREQUISITES_FAILED')
    cohorts,bindings,references,manifests=prepared
    commit,sources=source_gate()
    for relative,expected in bindings.items():
        if digest(ROOT/relative)!=expected:raise RuntimeError('Input changed after prerequisites: '+relative)
    rt.setup(20261120)
    base,_,initial_path=head()
    model=OrderHead(base,True)
    parameters=list(model.parameters())
    if [name for name,_ in model.named_parameters()]!=['base.linear.weight','base.linear.bias','order.weight']:
        raise RuntimeError('Unexpected optimizer parameter interface')
    parent_path=ROOT/'tools/action_predictor/experiments/v22/PC02.json'
    parent=json.loads(parent_path.read_text())
    if parent['lambda_value']!=STRENGTH:raise RuntimeError('Warm penalty changed')
    initial=torch.load(LOCAL.parent/'v22/runs/PC02/step-0000.pt',weights_only=True,map_location='cpu')
    for key,value in base.state_dict().items():
        if not torch.equal(value,initial['head_state'][key]):raise RuntimeError('Warm initialization changed')
    if not torch.equal(torch.get_rng_state(),initial['torch_rng']):raise RuntimeError('Initialization RNG changed')
    warm=[p.detach().clone() for p in parameters]
    fit=cohorts['broad_fit']
    plan=dict(id='O01-personal-action-order-information',source_commit=commit,sources=sources,inputs=bindings,
        treatment='Add 32 verified personal-PRE relational order fields through bias-free zero-initialized '
                  'affine matrix. Retained PC02 is the proven zero-filled expanded-interface control. '
                  'Both nominal interfaces247400parameters; zero arm has39584inactive parameters. '
                  'This tests the information treatment, not capacity-independent feature value.',
        fields=manifests['order-asinh-ready.json']['fields'],
        population='Same5876natural TRAIN priorities/55groups; original128subset; two128controls excluded. '
                   'No DEV. Controls previously seen by warm encoder/head, excluded only from this optimization.',
        unchanged='P05 context/39features/vocabulary/int64anchors/probability arithmetic/integerMAP; '
                  'same base warm initialization, seed20261120, full mean via chunks256, AdamW '
                  '.003first1000/.001last1000,WD0,clip5,2000fixed updates,CPU4threads.',
        objective=dict(command='mean normalized integer NLL',penalty='lambda*SUM squared warm displacement '
                       'of base weights+bias AND new matrix (warm zero), applied once per update',lambda_value=STRENGTH),
        selection='Fixed final2000; assessments0/100/500/1000/2000 descriptive; no threshold, '
                  'checkpoint, field, penalty or ablation selection from control outcomes.',
        diagnostic='At fixed final replace six numeric fields per available pool with fit-only '
                   'TRAIN means, preserving availability/counts/unavailable pools and learned offsets. '
                   'No replacement predictor selected; fixed-weight dependence only.',
        metrics='Conditional integer exact,NLL,MAE,bounded rank,explanation shares,confidence; '
                'paired whole-group2000resamples seed20261106 against warm and PC02; availability strata.',
        exploratory_gate=dict(broad_accuracy_gain_over_warm_at_least=.20,both_control_NLL_lower_than_warm=True,
            both_control_exact_at_least_warm=True,one_control_net_commands_over_warm_at_least=5),
        limitations='Recorded priority family supplied: no action-type or complete-policy claim. '
                    'Any policy integration needs new inputs on every row and normalized joint redecoding. '
                    'Original category/macro/movement/loss/targeting/three-seed targets unchanged.',
        continuation='Fresh GPT-6.1 Sol xhigh post-fit challenge; follow evidence, no automatic sweep/repeats.',
        safety='Independent historical control receipts; committed executable closure; actual entrypoint '
               'forgery/optimizer tripwire; raw cohort saved before measurement; preserve failures.',
        new_fits_allocated=1,reserved_opened=0)
    immutable_json(OUT/'O01-plan.json',plan)
    # Verify initial common forecasts and absence of an accidental optimizer change.
    with torch.no_grad():
        for name,d in cohorts.items():
            raw=np.concatenate([model(d['context'][s:s+256],d['features'][s:s+256],d['order'][s:s+256]).numpy()
                                for s in range(0,len(d['target']),256)])
            np.testing.assert_array_equal(raw,np.load(LOCAL.parent/f'v22/runs/PC02/{name}-step-0000-raw.npy'))
    penalty=displacement_penalty(parameters,warm,STRENGTH)
    if float(penalty.detach())!=0 or any(torch.count_nonzero(g) for g in torch.autograd.grad(penalty,parameters)):
        raise RuntimeError('Initial penalty/gradient nonzero')
    if source_gate()!=(commit,sources):raise RuntimeError('Source changed before optimization')
    for relative,expected in bindings.items():
        if digest(ROOT/relative)!=expected:raise RuntimeError('Input changed before optimization: '+relative)
    immutable_json(OUT/'O01-preflight.json',dict(passed=True,source_commit=commit,sources=sources,inputs=bindings,
        plan_sha256=digest(OUT/'O01-plan.json'),tests=tests,initial_all_raw_forecasts_exact_PC02=True,
        initial_head_RNG_and_zero_penalty_verified=True,no_optimizer_constructed_before_preflight=True))
    directory=LOCAL/'runs/O01'
    if directory.exists():raise FileExistsError('Preserve attempted fit; do not restart')
    directory.mkdir(parents=True)
    optimizer=torch.optim.AdamW(parameters,lr=.003,weight_decay=0)
    if {id(p) for p in parameters}!={id(p) for group in optimizer.param_groups for p in group['params']}:
        raise RuntimeError('Optimizer parameter coverage mismatch')
    old=initial['optimizer']['param_groups'][0]
    new=optimizer.state_dict()['param_groups'][0]
    if {k:v for k,v in old.items() if k!='params'}!={k:v for k,v in new.items() if k!='params'}:
        raise RuntimeError('Optimizer settings changed')
    trace=[];tick=time.perf_counter()
    def assess(step):
        torch.save(dict(head_state=model.state_dict(),optimizer=optimizer.state_dict(),step=step,
            torch_rng=torch.get_rng_state(),source_commit=commit,lambda_value=STRENGTH,
            plan_sha256=digest(OUT/'O01-plan.json')),directory/f'step-{step:04d}.pt')
        row=dict(step=step,seconds=time.perf_counter()-tick,cohorts={},
                 penalty=float(displacement_penalty(parameters,warm,STRENGTH).detach()))
        for name,d in cohorts.items():row['cohorts'][name]=assess_cohort(model,d,directory,name,step)
        trace.append(row)
        immutable_json(directory/f'assessment-{step:04d}.json',row)
        print('O01',step,{n:(v['exact'],v['mean_NLL']) for n,v in row['cohorts'].items()},flush=True)
    try:
        assess(0)
        for step in range(1,2001):
            if step==1001:
                for group in optimizer.param_groups:group['lr']=.001
            optimizer.zero_grad(set_to_none=True)
            for start in range(0,len(fit['target']),256):
                sl=slice(start,start+256)
                raw=model(fit['context'][sl],fit['features'][sl],fit['order'][sl])
                loss=-model.log_mass(raw,fit['target'][sl],fit['values'][sl]).sum()/5876
                if not torch.isfinite(loss):raise RuntimeError('Nonfinite command loss')
                loss.backward()
            displacement_penalty(parameters,warm,STRENGTH).backward()
            if not all(p.grad is not None and torch.isfinite(p.grad).all() for p in parameters):
                raise RuntimeError('Nonfinite/missing derivative')
            torch.nn.utils.clip_grad_norm_(parameters,5)
            optimizer.step()
            if step in (100,500,1000,2000):assess(step)
            elif step%100==0:print('O01 progress',step,round(time.perf_counter()-tick,2),flush=True)
        ablation={}
        for name,d in cohorts.items():
            order=numeric_mean_inputs(d['order'],d['order_available'],references['references'],references['available'])
            ablation[name]=assess_cohort(model,d,directory,name+'-numeric-means',2000,order)
        final,initial_metrics=trace[-1]['cohorts'],trace[0]['cohorts']
        checks=dict(broad_gain20=final['broad_fit']['accuracy']-initial_metrics['broad_fit']['accuracy']>=.20,
            both_control_NLL_lower=all(final[n]['mean_NLL']<initial_metrics[n]['mean_NLL'] for n in ('same_fit_groups','held_groups')),
            both_control_exact_not_lower=all(final[n]['exact']>=initial_metrics[n]['exact'] for n in ('same_fit_groups','held_groups')),
            some_control_gain5=any(final[n]['exact']-initial_metrics[n]['exact']>=5 for n in ('same_fit_groups','held_groups')))
        immutable_json(OUT/'O01.json',dict(source_commit=commit,sources=sources,inputs=bindings,trace=trace,
            numeric_mean_diagnostic=ablation,numeric_mean_references=references['references'].tolist(),
            lambda_value=STRENGTH,fixed_final_step=2000,optimizer_updates=2000,
            trainable_parameters=sum(p.numel() for p in parameters),seconds=time.perf_counter()-tick,
            gate=checks,exploratory_gate_passed=all(checks.values()),
            bindings={str(p.relative_to(ROOT)):digest(p) for p in directory.iterdir()},
            conditional_diagnostic_only=True,new_fits=1,reserved_opened=0,promoted=False,policy_replaced=False))
    except BaseException:
        (directory/f'failure-{time.time_ns()}.txt').write_text(traceback.format_exc())
        torch.save(dict(head_state=model.state_dict(),optimizer=optimizer.state_dict(),attempted_step=locals().get('step',0)),
                   directory/f'failure-state-{time.time_ns()}.pt')
        raise
    print('O01 complete; fresh Solxhigh review required.',flush=True)


def main():
    reject_optimized_python()
    source_gate()
    prepared=load()  # Anchor control inputs before tests or any optimizer path.
    checked_execution([TEST_COMMAND],lambda tests:execute(prepared,tests),ROOT)


if __name__=='__main__':main()
