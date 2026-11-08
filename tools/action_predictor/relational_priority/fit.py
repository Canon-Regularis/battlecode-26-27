"""One fixed-endpoint correction fit per invocation; fresh review between arms."""
import argparse
import hashlib
import json
import sys
import time
import traceback

import numpy as np
import torch

from .. import reliable_train as rt
from ..audit import immutable_json
from ..data import digest
from ..priority_capacity.data import head
from ..priority_capacity.measurement import measure
from ..priority_broad.guard import committed_sources,checked_execution
from ..priority_regularized.safety import dependency_files,reject_optimized_python,archive_then_measure
from ..order_information.anchored import committed_manifest
from .data import load
from .model import SignedPointCorrection
from .protocol import ROOT,LOCAL,OUT,ARMS,TRAIN_SEED,STRENGTH,UPDATES,V23_COMMIT

TESTS=('tools.action_predictor.relational_priority.test_model',
       'tools.action_predictor.relational_priority.test_data',
       'tools.action_predictor.relational_priority.test_entrypoint',
       'tools.action_predictor.priority_capacity.test_measurement')
TEST_COMMAND=[sys.executable,'-m','unittest',*TESTS]


def source_gate():
    reject_optimized_python()
    return committed_sources(ROOT,dependency_files(ROOT,('tools.action_predictor.relational_priority.fit',*TESTS)))


def base_fingerprint(model):
    result=hashlib.sha256()
    for name,value in model.base.state_dict().items():
        result.update(name.encode());result.update(value.detach().cpu().numpy().tobytes())
    return result.hexdigest()


def penalty(model):return STRENGTH*model.weights.double().square().sum()


def require_control_review(arm,commit):
    bindings={}
    if arm=='RC00':return bindings
    review_path=OUT/'RC00-review.json';response_path=OUT/'RC00-review-response.json'
    if not review_path.is_file() or not response_path.is_file():
        raise RuntimeError('RC01_REQUIRES_COMPLETED_CONTROL_REVIEW')
    for path in (review_path,response_path,OUT/'RC00.json',OUT/'RC00-completion.json'):
        value,more=committed_manifest(commit,path.relative_to(ROOT).as_posix());bindings.update(more)
        if path==review_path:review=value
        elif path==response_path:response=value
        elif path.name=='RC00.json':control=value
    if review['thread']['status']!='completed' or review['thread']['model']!='gpt-6.1-sol':
        raise RuntimeError('RC00 independent review is not complete on requested model')
    if not response.get('ready_for_registered_treatment') or control['optimizer_updates']!=UPDATES:
        raise RuntimeError('RC00 review findings not resolved for registered continuation')
    checkpoint=LOCAL/'runs/RC00/step-2000.pt'
    if response.get('reviewed_checkpoint_sha256')!=digest(checkpoint):
        raise RuntimeError('Control-review checkpoint binding mismatch')
    if control['protocol_sha256']!=digest(OUT/'RC-plan.json'):
        raise RuntimeError('Control protocol differs from matched treatment')
    bindings[str(checkpoint.relative_to(ROOT))]=digest(checkpoint)
    return bindings


def raw_forecast(model,bank,ids,arm=None):
    parts=[]
    with torch.inference_mode():
        for start in range(0,len(ids),256):
            ix=ids[start:start+256]
            features=bank.evaluation_features(ix) if arm is None else bank.training_features(ix,arm)
            parts.append(model.correct_logits(torch.from_numpy(np.array(bank.raw[ix],copy=True)),features).numpy())
    return np.concatenate(parts)


def predictions(model,bank,raw,ids):
    result={}
    with torch.inference_mode():
        for start in range(0,len(ids),256):
            ix=ids[start:start+256];sl=slice(start,start+len(ix))
            output=torch.from_numpy(np.array(raw[sl],copy=True))
            p,_=measure(model,output,bank.broad['values'][ix],bank.broad['target'][ix])
            p['mode_probability']=model.log_mass(output,p['integer'],bank.broad['values'][ix]).exp()
            for name,value in p.items():result.setdefault(name,[]).append(value.numpy())
    return {name:np.concatenate(value) for name,value in result.items()}


def summary(p,target,mask):
    error=np.abs(p['integer'][mask]-target[mask])
    return dict(rows=len(error),exact=int((error==0).sum()),accuracy=float((error==0).mean()),
        mean_NLL=float(p['nll'][mask].mean()),MAE=float(error.mean()),max_error=int(error.max()),
        mean_bounded_candidate_rank=float(p['rank'][mask].mean()),
        mean_mode_probability=float(p['mode_probability'][mask].mean()),
        marginalized_target_source_shares=p['credit'][mask].mean(0).tolist())


def gradient_contract(model,bank,arm):
    ids=bank.fit_ids[:64]
    if len(ids)!=64:raise RuntimeError('Insufficient preflight fitting rows')
    def differentiate(chunk):
        model.zero_grad(set_to_none=True)
        for start in range(0,len(ids),chunk):
            ix=ids[start:start+chunk]
            output=model.correct_logits(torch.from_numpy(np.array(bank.raw[ix],copy=True)),bank.training_features(ix,arm))
            (-model.log_mass(output,bank.broad['target'][ix],bank.broad['values'][ix]).sum()/len(ids)).backward()
        return model.weights.grad.detach().clone()
    full=differentiate(64);chunked=differentiate(17)
    maximum=float((full-chunked).abs().max())
    if maximum>2e-6 or not bool(torch.isfinite(full).all()) or not torch.count_nonzero(full):
        raise RuntimeError('New shared-weight accumulation contract failed')
    if any(p.grad is not None for p in model.base.parameters()):raise RuntimeError('Frozen core received a gradient')
    model.zero_grad(set_to_none=True)
    return dict(rows=64,global_indices=bank.broad['index'][ids].tolist(),full_mean_gradient=full.tolist(),
                chunked_mean_gradient=chunked.tolist(),maximum_absolute_difference=maximum,tolerance=2e-6,
                optimizer_updates=0)


def execute(arm,bank,tests,prior_bindings):
    if len(tests)!=1 or tests[0]['returncode']!=0 or tests[0]['command']!=TEST_COMMAND:
        raise RuntimeError('FIT_PREREQUISITES_FAILED')
    commit,sources=source_gate()
    rt.setup(TRAIN_SEED)
    base,_,_=head();model=SignedPointCorrection(base,bank.metadata['active'])
    if [name for name,p in model.named_parameters() if p.requires_grad]!=['weights']:
        raise RuntimeError('Unexpected trainable parameter boundary')
    if model.weights.numel()!=bank.ready['trainable_weights'] or torch.count_nonzero(model.weights):
        raise RuntimeError('Correction initialization/active capacity changed')
    core=base_fingerprint(model);rng=torch.get_rng_state().clone()
    bindings=dict(bank.bindings);bindings.update(prior_bindings)
    for relative in ('tools/action_predictor/experiments/v23/OD03-review.json',
                     'tools/action_predictor/experiments/v23/OD03-review-response.json'):
        _,more=committed_manifest(V23_COMMIT,relative);bindings.update(more)
    all_ids=np.arange(5876)
    initial_raw=raw_forecast(model,bank,all_ids)
    np.testing.assert_array_equal(initial_raw,bank.raw)
    initial=predictions(model,bank,initial_raw,all_ids)
    for name in ('integer','rank','nll','credit'):
        np.testing.assert_array_equal(initial[name],bank.baseline[name])
    points=np.load(LOCAL/'data/points.npy',mmap_mode='r')
    with torch.no_grad():
        for start in range(0,5876,256):
            sl=slice(start,min(start+256,5876))
            generated,_=model.components(torch.from_numpy(np.array(bank.raw[sl],copy=True)),bank.broad['values'][sl])
            np.testing.assert_array_equal(generated.numpy(),points[sl])
    gradients=gradient_contract(model,bank,arm)
    if base_fingerprint(model)!=core or not torch.equal(torch.get_rng_state(),rng) or torch.count_nonzero(model.weights):
        raise RuntimeError('Preflight changed weights/core/RNG')
    if float(penalty(model).detach())!=0:raise RuntimeError('Initial displacement penalty not zero')
    if source_gate()!=(commit,sources):raise RuntimeError('Source changed after prerequisites')
    # Cache and old input hashes were verified by load; bind the exact committed manifests.
    if digest(OUT/'RC-plan.json')!=bank.ready['protocol_sha256']:raise RuntimeError('Protocol changed before optimizer')
    for relative,value in bank.ready['files'].items():
        if digest(ROOT/relative)!=value:raise RuntimeError('Feature cache changed during preflight: '+relative)
    immutable_json(OUT/f'{arm}-execution-plan.json',dict(arm=arm,source_commit=commit,sources=sources,inputs=bindings,
        protocol_sha256=digest(OUT/'RC-plan.json'),data_ready_sha256=digest(OUT/'RC-data-ready.json'),
        same_registered_training=bank.plan['optimization'],new_fit_rows=len(bank.fit_ids),new_held_rows=len(bank.held_ids),
        same_initial_function=True,only_correction_trainable=True,
        evaluation='Both arms use real personal evidence at primary inference; RC00 corrupts TRAIN inputs only.',
        no_DEV_or_reserved=True,new_fits_planned_here=1))
    immutable_json(OUT/f'{arm}-preflight.json',dict(passed=True,source_commit=commit,sources=sources,inputs=bindings,
        tests=tests,gradient_contract=gradients,all5876initial_raw_integer_rank_NLL_and_credits_exact_warm=True,
        all_point_identities_match_cache=True,core_sha256=core,initial_rng_sha256=hashlib.sha256(rng.numpy().tobytes()).hexdigest(),
        no_optimizer_constructed_before_preflight=True,trainable_parameters=model.weights.numel(),
        protocol_sha256=digest(OUT/'RC-plan.json')))
    directory=LOCAL/f'runs/{arm}'
    if directory.exists():raise FileExistsError('Preserve attempted correction fit')
    directory.mkdir(parents=True)
    optimizer=torch.optim.AdamW([model.weights],lr=.003,weight_decay=0)
    if {id(p) for group in optimizer.param_groups for p in group['params']}!={id(model.weights)}:
        raise RuntimeError('Optimizer parameter inclusion failed')
    trace=[];tick=time.perf_counter();target=bank.broad['target'].numpy()
    masks=dict(fit=bank.fit_mask,held=~bank.fit_mask)
    def assess(step):
        torch.save(dict(state=model.state_dict(),optimizer=optimizer.state_dict(),step=step,arm=arm,
            source_commit=commit,torch_rng=torch.get_rng_state(),core_sha256=core,
            protocol_sha256=digest(OUT/'RC-plan.json'),data_ready_sha256=digest(OUT/'RC-data-ready.json')),
            directory/f'step-{step:04d}.pt')
        raw=raw_forecast(model,bank,all_ids)
        p=archive_then_measure(raw,directory/f'actual-step-{step:04d}-raw.npy',
                              lambda saved:predictions(model,bank,saved,all_ids))
        np.savez_compressed(directory/f'actual-step-{step:04d}-predictions.npz',**p)
        fitting_raw=raw_forecast(model,bank,bank.fit_ids,arm)
        fitting=archive_then_measure(fitting_raw,directory/f'optimization-input-step-{step:04d}-raw.npy',
                                    lambda saved:predictions(model,bank,saved,bank.fit_ids))
        np.savez_compressed(directory/f'optimization-input-step-{step:04d}-predictions.npz',**fitting)
        # All predictions survive before consistency checks or summaries.
        np.testing.assert_array_equal(raw[:,model.point_count:],bank.raw[:,model.point_count:])
        if base_fingerprint(model)!=core:raise RuntimeError('Frozen P05 core changed')
        if step and int(optimizer.state[model.weights]['step'])!=step:raise RuntimeError('Optimizer counter mismatch')
        row=dict(step=step,seconds=time.perf_counter()-tick,penalty=float(penalty(model).detach()),
            real_input={name:summary(p,target,mask) for name,mask in masks.items()},
            optimization_input_fit=summary(fitting,target[bank.fit_ids],np.ones(len(bank.fit_ids),bool)))
        trace.append(row);immutable_json(directory/f'assessment-{step:04d}.json',row)
        print(arm,step,{name:(v['exact'],v['mean_NLL']) for name,v in row['real_input'].items()},
              'optimization_NLL',row['optimization_input_fit']['mean_NLL'],flush=True)
    try:
        assess(0)
        for step in range(1,UPDATES+1):
            if step==1001:
                for group in optimizer.param_groups:group['lr']=.001
            optimizer.zero_grad(set_to_none=True)
            for start in range(0,len(bank.fit_ids),256):
                ix=bank.fit_ids[start:start+256]
                output=model.correct_logits(torch.from_numpy(np.array(bank.raw[ix],copy=True)),bank.training_features(ix,arm))
                loss=-model.log_mass(output,bank.broad['target'][ix],bank.broad['values'][ix]).sum()/len(bank.fit_ids)
                if not torch.isfinite(loss):raise RuntimeError('Nonfinite correction loss')
                loss.backward()
            penalty(model).backward()
            if model.weights.grad is None or not bool(torch.isfinite(model.weights.grad).all()):
                raise RuntimeError('Missing/nonfinite signed-weight gradient')
            if any(p.grad is not None for p in model.base.parameters()):raise RuntimeError('Frozen-core gradient detected')
            torch.nn.utils.clip_grad_norm_([model.weights],5)
            optimizer.step()
            if step in (100,500,1000,2000):assess(step)
            elif step%100==0:print(arm,'progress',step,'seconds',round(time.perf_counter()-tick,2),flush=True)
        if int(optimizer.state[model.weights]['step'])!=UPDATES:raise RuntimeError('Incomplete fixed endpoint')
        immutable_json(OUT/f'{arm}.json',dict(arm=arm,source_commit=commit,sources=sources,inputs=bindings,
            trace=trace,fixed_final_step=UPDATES,optimizer_updates=UPDATES,
            supervised_presentations=len(bank.fit_ids)*UPDATES,trainable_parameters=model.weights.numel(),
            resident_parameters=sum(p.numel() for p in model.parameters()),core_unchanged=True,core_sha256=core,
            protocol_sha256=digest(OUT/'RC-plan.json'),data_ready_sha256=digest(OUT/'RC-data-ready.json'),
            bindings={str(p.relative_to(ROOT)):digest(p) for p in directory.iterdir()},
            seconds=time.perf_counter()-tick,timing_scope='After preflight through training, assessment and serialization',
            conditional_diagnostic_only=True,new_fits=1,reserved_opened=0,policy_replaced=False,promoted=False))
    except BaseException:
        (directory/f'failure-{time.time_ns()}.txt').write_text(traceback.format_exc(),encoding='utf-8')
        torch.save(dict(state=model.state_dict(),optimizer=optimizer.state_dict(),attempted_step=locals().get('step',0)),
                   directory/f'failure-state-{time.time_ns()}.pt')
        raise
    print(arm,'complete; fresh Solxhigh review required before another substantive fit.',flush=True)


def main():
    reject_optimized_python()
    parser=argparse.ArgumentParser();parser.add_argument('arm',choices=ARMS);arm=parser.parse_args().arm
    commit,_=source_gate()
    if (LOCAL/f'runs/{arm}').exists():raise FileExistsError('Preserve attempted correction fit')
    prior=require_control_review(arm,commit)
    bank=load()  # Committed data manifests and independent historical input anchors first.
    checked_execution([TEST_COMMAND],lambda tests:execute(arm,bank,tests,prior),ROOT)


if __name__=='__main__':main()
