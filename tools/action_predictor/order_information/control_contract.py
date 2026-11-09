"""Validate retained PC02 as the zero-information interface control.

No control refit. Ten isolated optimizer-contract updates are archived, never
evaluated or selected as predictors. Any exact-parity failure forbids reuse.
"""
import copy
import json
from pathlib import Path

import numpy as np
import torch

from .. import reliable_train as rt
from ..audit import immutable_json
from ..data import digest
from ..priority_capacity.data import head
from ..priority_regularized.experiment import displacement_penalty
from ..priority_regularized.safety import reject_optimized_python,dependency_files
from ..priority_broad.guard import committed_sources
from .anchored import ROOT,PC02_COMMIT,PC02_COMPLETION,committed_manifest,anchored_inputs
from .model import OrderHead

LOCAL=ROOT/'.cambc/action-predictor/v23'
OUT=ROOT/'tools/action_predictor/experiments/v23'


def run():
    reject_optimized_python()
    commit,sources=committed_sources(ROOT,dependency_files(ROOT,(
        'tools.action_predictor.order_information.control_contract',
        'tools.action_predictor.order_information.test_model')))
    manifest,bindings=committed_manifest(PC02_COMMIT,PC02_COMPLETION)
    expected={name.replace('\\','/'):value for name,value in manifest['bindings'].items()}
    parent_path=ROOT/'tools/action_predictor/experiments/v22/PC02.json'
    if digest(parent_path)!=expected[parent_path.relative_to(ROOT).as_posix()]:
        raise RuntimeError('Parent control report changed')
    bindings[str(parent_path.relative_to(ROOT))]=digest(parent_path)
    parent=json.loads(parent_path.read_text())
    strength=parent['lambda_value']
    for relative in ('tools/action_predictor/experiments/v8/P05.json',
                     'tools/action_predictor/experiments/v8/priority-residual-modes-vocabulary.json'):
        _,extra=committed_manifest(PC02_COMMIT,relative);bindings.update(extra)
    initial_path=ROOT/'.cambc/action-predictor/v8/runs/P05/model.pt'
    initial_hash=expected[initial_path.relative_to(ROOT).as_posix()]
    if digest(initial_path)!=initial_hash:raise RuntimeError('Original warm checkpoint changed')
    bindings[str(initial_path.relative_to(ROOT))]=initial_hash
    fit,controls,anchored=anchored_inputs();bindings.update(anchored)
    cohorts=dict(broad_fit=fit,original_fit=controls['fit'],
                 same_fit_groups=controls['same_fit_groups'],held_groups=controls['held_groups'])
    for step in (0,100,500,1000,2000):
        required=[ROOT/f'.cambc/action-predictor/v22/runs/PC02/step-{step:04d}.pt']
        required += [ROOT/f'.cambc/action-predictor/v22/runs/PC02/{name}-step-{step:04d}-raw.npy'
                     for name in cohorts]
        for path in required:
            value=expected[path.relative_to(ROOT).as_posix()]
            if digest(path)!=value:raise RuntimeError('Retained control input changed')
            bindings[str(path.relative_to(ROOT))]=value
    plan=dict(source_commit=commit,sources=sources,inputs=bindings,
        requirement='Retain PC02 as zero-information control only if exact common readout, '
                    'gradient, clipping, parameter and optimizer-state parity passes at ALL five '
                    'predeclared checkpoints. Extra matrix must remain exactly zero.',
        rationale='Bias-free extra interface receives literal zeros in control, has zero NLL '
                  'derivative and zero warm-displacement derivative at its zero initialization. '
                  'Parameterwise AdamW plus unchanged clipping therefore preserves original core.',
        operation='Check all31300retained neural readouts, then one isolated full5876row optimizer '
                  'transition for each of PC02 steps0/100/500/1000/2000 in both reference and '
                  'expanded control. Ten contract steps, not ten candidate fits; no accuracy '
                  'assessment or selection of post-contract weights. Archive them as tests.',
        contingency='Any exact failure stops reuse; run a separately frozen necessary control '
                    'before treatment, without choosing whichever control has better scores.',
        new_fits=0,optimizer_contract_steps_planned=10,reserved_opened=0)
    immutable_json(OUT/'zero-control-plan.json',plan)
    directory=LOCAL/'control-contract'
    if directory.exists():raise FileExistsError('Preserve prior contract attempt')
    directory.mkdir(parents=True)
    rt.setup(20261120)
    warm_model,_,_=head()
    initial=torch.load(ROOT/'.cambc/action-predictor/v22/runs/PC02/step-0000.pt',
                       weights_only=True,map_location='cpu')
    for key,value in warm_model.state_dict().items():
        if not torch.equal(value,initial['head_state'][key]):raise RuntimeError('Warm reference changed')
    warm=[p.detach().clone() for p in warm_model.parameters()]
    results=[]
    for step in (0,100,500,1000,2000):
        path=ROOT/f'.cambc/action-predictor/v22/runs/PC02/step-{step:04d}.pt'
        if digest(path)!=expected[path.relative_to(ROOT).as_posix()]:raise RuntimeError('Checkpoint changed')
        checkpoint=torch.load(path,weights_only=True,map_location='cpu')
        reference=copy.deepcopy(warm_model)
        reference.load_state_dict(checkpoint['head_state'])
        expanded=OrderHead(copy.deepcopy(warm_model),False)
        expanded.base.load_state_dict(checkpoint['head_state'])
        for name,d in cohorts.items():
            raw=[]
            with torch.no_grad():
                for start in range(0,len(d['target']),256):
                    sl=slice(start,start+256)
                    # Nonzero poison input verifies that control masking is real.
                    raw.append(expanded(d['context'][sl],d['features'][sl],
                        torch.full((len(d['target'][sl]),32),17.)).numpy())
            original=ROOT/f'.cambc/action-predictor/v22/runs/PC02/{name}-step-{step:04d}-raw.npy'
            if digest(original)!=expected[original.relative_to(ROOT).as_posix()]:raise RuntimeError('Raw archive changed')
            np.testing.assert_array_equal(np.concatenate(raw),np.load(original))
            bindings[str(original.relative_to(ROOT))]=digest(original)
        old_opt=torch.optim.AdamW(reference.parameters(),lr=.003,weight_decay=0)
        new_opt=torch.optim.AdamW(expanded.parameters(),lr=.003,weight_decay=0)
        old_opt.load_state_dict(copy.deepcopy(checkpoint['optimizer']))
        augmented=copy.deepcopy(checkpoint['optimizer'])
        augmented['param_groups'][0]['params'].append(2)
        if augmented['state']:
            augmented['state'][2]={key:(value.clone() if key=='step' else torch.zeros_like(expanded.order.weight))
                                   for key,value in augmented['state'][0].items()}
        new_opt.load_state_dict(augmented)
        old_opt.zero_grad(set_to_none=True);new_opt.zero_grad(set_to_none=True)
        for start in range(0,len(fit['target']),256):
            sl=slice(start,start+256)
            old_raw=reference(fit['context'][sl],fit['features'][sl])
            new_raw=expanded(fit['context'][sl],fit['features'][sl],torch.full((len(fit['target'][sl]),32),19.))
            (-reference.log_mass(old_raw,fit['target'][sl],fit['values'][sl]).sum()/5876).backward()
            (-expanded.log_mass(new_raw,fit['target'][sl],fit['values'][sl]).sum()/5876).backward()
        displacement_penalty(list(reference.parameters()),warm,strength).backward()
        displacement_penalty(list(expanded.parameters()),warm+[torch.zeros_like(expanded.order.weight)],strength).backward()
        for a,b in zip(reference.parameters(),expanded.base.parameters()):
            torch.testing.assert_close(a.grad,b.grad,rtol=0,atol=0)
        if torch.count_nonzero(expanded.order.weight.grad):raise RuntimeError('Control received order gradient')
        old_norm=torch.nn.utils.clip_grad_norm_(reference.parameters(),5)
        new_norm=torch.nn.utils.clip_grad_norm_(expanded.parameters(),5)
        torch.testing.assert_close(old_norm,new_norm,rtol=0,atol=0)
        old_opt.step();new_opt.step()
        # Archive immediately, before assertions that might fail.
        artifact=directory/f'after-contract-{step:04d}.pt'
        torch.save(dict(reference=reference.state_dict(),expanded=expanded.state_dict(),
            reference_optimizer=old_opt.state_dict(),expanded_optimizer=new_opt.state_dict(),
            source_step=step,contract_only=True),artifact)
        for a,b in zip(reference.parameters(),expanded.base.parameters()):
            if not torch.equal(a,b):raise RuntimeError('Control core update differs')
        old_state,new_state=old_opt.state_dict(),new_opt.state_dict()
        for identifier in (0,1):
            for key,value in old_state['state'][identifier].items():
                if not torch.equal(value,new_state['state'][identifier][key]):raise RuntimeError('Control optimizer moment differs')
        if torch.count_nonzero(expanded.order.weight):raise RuntimeError('Control new weights changed')
        results.append(dict(checkpoint=step,all_cohort_raw_arrays_exact=True,
            common_gradient_clip_update_and_moments_exact=True,new_weights_remain_zero=True))
        bindings[str(path.relative_to(ROOT))]=digest(path)
        bindings[str(artifact.relative_to(ROOT))]=digest(artifact)
    immutable_json(OUT/'zero-control-equivalence.json',dict(results=results,bindings=bindings,
        plan_sha256=digest(OUT/'zero-control-plan.json'),reuse_accepted=True,
        scope='Analytic zero-input equivalence plus exact full-readout/five optimizer-transition '
              'checks. Retained PC02 control, not a newly fitted control or post-contract predictor.',
        new_fits=0,optimizer_contract_steps=10,reserved_opened=0))
    print('Retained zero-information control validated at all five checkpoints.',flush=True)


if __name__=='__main__':run()
