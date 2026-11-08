"""Exactly one registered readout fit; fail closed before any optimization."""
import copy
import json
import subprocess
import sys
import time
import traceback
import numpy as np
import torch
from ..audit import immutable_json
from ..data import digest
from ..order_information.anchored import committed_manifest
from .protocol import ROOT,OUT,LOCAL,ARMS,SEED,source_gate
from .data import load,batch
from .model import ActionBeliefCorrection,observed_nll
from .assessment import infer,quick,evaluate
from .review_gate import require_control_review


def run(arm):
    if arm not in ARMS:raise ValueError('Unknown prospective arm')
    commit,sources=source_gate()
    control_completion=require_control_review() if arm=='AB01' else None
    commands=[[sys.executable,'-m','unittest','tools.action_predictor.policy_action_readout.test_model',
        'tools.action_predictor.policy_action_readout.test_data','tools.action_predictor.policy_action_readout.test_review','-v']]
    tests=[]
    for command in commands:
        p=subprocess.run(command,cwd=ROOT,capture_output=True,text=True);tests.append(dict(command=command,returncode=p.returncode,stdout=p.stdout,stderr=p.stderr))
        if p.returncode:raise RuntimeError('Prerequisite failed before optimizer: '+p.stderr)
    data,cohorts,plan,ready=load();settings=plan['optimization'];directory=LOCAL/'runs'/arm
    if directory.exists():raise FileExistsError('Preserve existing/failed fit, no automatic restart')
    directory.mkdir(parents=True);torch.set_num_threads(4);torch.manual_seed(SEED)
    model=ActionBeliefCorrection(int(cohorts['active'].sum()));initial_state=copy.deepcopy(model.state_dict())
    initial={split:infer(model,d,cohorts['active'],directory,'initial-'+split) for split,d in data.items()}
    checks={}
    for split,p in initial.items():
        old=data[split]['baseline']
        checks[split]=dict(action_mismatches=int((p['prediction']!=old['prediction']).sum()),
            selected_coordinate_mismatches=int((p['proposed_coordinate']!=old['proposed_coordinate']).sum()),
            priority_mismatches=int((p['priority']!=old['priority']).sum()),max_observed_NLL_difference=float(np.abs(p['nll']-old['nll']).max()))
        if any(checks[split][k] for k in ('action_mismatches','selected_coordinate_mismatches','priority_mismatches')) or checks[split]['max_observed_NLL_difference']>2e-5:
            immutable_json(directory/'preflight-failure.json',dict(checks=checks));raise RuntimeError('Initial command contract failed; no optimizer')
    immutable_json(directory/'preflight.json',dict(source_commit=commit,sources=sources,plan_sha256=digest(OUT/'AB-plan.json'),
        data_ready_sha256=digest(OUT/'AB-data-ready.json'),checks=checks,tests=tests,trainable_parameters=sum(p.numel() for p in model.parameters()),
        optimizer_constructed=False))
    # Recheck committed executable bytes immediately before constructing Adam.
    commit,sources=source_gate()
    optimizer=torch.optim.AdamW(model.parameters(),lr=settings['lr'],weight_decay=settings['weight_decay'])
    torch.save(dict(state=initial_state,optimizer=optimizer.state_dict(),torch_rng=torch.get_rng_state()),directory/'initial-state.pt')
    ids=np.flatnonzero(cohorts['fit']);rng=np.random.default_rng(SEED);best=float('inf');best_round=0;best_state=None;trace=[];updates=0
    started=time.perf_counter()
    try:
        for round_number in range(1,settings['max_rounds']+1):
            model.train();order=rng.permutation(ids);total=0.
            for start in range(0,len(order),settings['batch']):
                ix=order[start:start+settings['batch']]
                donor=cohorts['donor'] if arm=='AB00' else None
                base,x=batch(data['train'],ix,cohorts['active'],donor);target=data['train']['targets']
                optimizer.zero_grad(set_to_none=True);lp=model(base,x)
                loss=observed_nll(lp,torch.from_numpy(target['y'][ix].astype(np.int64)),torch.from_numpy(-target['param_nll'][ix])).mean()
                penalty=settings['displacement_penalty']*sum(p.square().sum() for p in model.parameters())
                (loss+penalty).backward();torch.nn.utils.clip_grad_norm_(model.parameters(),settings['gradient_clip']);optimizer.step()
                updates+=1;total+=float(loss.detach())*len(ix)
            # Checkpoint/raw readout retained before target-based assessment.
            torch.save(dict(state=model.state_dict(),optimizer=optimizer.state_dict(),round=round_number,updates=updates,
                torch_rng=torch.get_rng_state(),numpy_rng=rng.bit_generator.state,arm=arm,source_commit=commit),directory/f'round-{round_number:02d}.pt')
            p=infer(model,data['validation'],cohorts['active'],directory,f'round-{round_number:02d}-validation');score=quick(data['validation'],p)
            improved=score['joint_NLL']<best-settings['min_improvement']
            if improved:best=score['joint_NLL'];best_round=round_number;best_state=copy.deepcopy(model.state_dict())
            trace.append(dict(round=round_number,updates=updates,training_observed_NLL=total/len(ids),validation=score,selected_improvement=improved))
            immutable_json(directory/f'round-{round_number:02d}-assessment.json',trace[-1]);print(arm,trace[-1],flush=True)
            if round_number-best_round>=settings['patience']:break
        model.load_state_dict(best_state)
        torch.save(dict(state=best_state,selected_round=best_round,arm=arm,plan_sha256=digest(OUT/'AB-plan.json'),
            data_ready_sha256=digest(OUT/'AB-data-ready.json'),source_commit=commit),directory/'model.pt')
        predictions={split:infer(model,d,cohorts['active'],directory,'selected-'+split) for split,d in data.items()}
        for split,p in predictions.items():np.savez_compressed(directory/(split+'-predictions.npz'),**p)
        result,comparison,bindings=evaluate(arm,data,cohorts,predictions,control_completion)
        for p in directory.iterdir():
            if p.is_file():bindings[str(p.relative_to(ROOT))]=digest(p)
        for name in ('AB-plan.json','AB-data-ready.json'):
            p=OUT/name;bindings[str(p.relative_to(ROOT))]=digest(p)
        bindings.update(ready['inputs']);bindings.update(ready['files']);bindings.update(sources)
        report=dict(arm=arm,source_commit=commit,sources=sources,selected_round=best_round,trace=trace,results=result,comparisons=comparison,
            bindings=bindings,checkpoint_sha256=digest(directory/'model.pt'),selected_updates=trace[best_round-1]['updates'],completed_updates=updates,
            trainable_parameters=sum(p.numel() for p in model.parameters()),measured_fit_and_final_assessment_seconds=time.perf_counter()-started,
            measured_scope='After initial preflight/optimizer setup, includes optimization, roundDEVinference, serialization and final TRAIN/DEV assessment; not pure optimization or total preparation cost.',
            original_success_targets_met=False,three_seed_confirmed=False,new_fits=1,reserved_opened=0)
        immutable_json(OUT/(arm+'.json'),report)
        immutable_json(OUT/(arm+'-completion.json'),dict(bindings={**bindings,str((OUT/(arm+'.json')).relative_to(ROOT)):digest(OUT/(arm+'.json'))},
            checkpoint_sha256=report['checkpoint_sha256'],source_commit=commit,plan_sha256=digest(OUT/'AB-plan.json'),
            commands=['python -m tools.action_predictor.policy_action_readout.data','python -m tools.action_predictor.policy_action_readout.fit '+arm],
            fresh_review_pending=True,model_promoted=False,new_fits=1,reserved_opened=0))
    except BaseException:
        torch.save(dict(state=model.state_dict(),optimizer=optimizer.state_dict(),updates=updates,trace=trace,
            torch_rng=torch.get_rng_state(),numpy_rng=rng.bit_generator.state,source_commit=commit),directory/'failure-state.pt')
        (directory/'failure.txt').write_text(traceback.format_exc(),encoding='utf-8');raise


if __name__=='__main__':run(sys.argv[1])
