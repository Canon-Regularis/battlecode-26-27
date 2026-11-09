"""One actual-P05 small-set capacity fit; final step fixed before optimization."""
import json
import subprocess
import time
import numpy as np
import torch
from .protocol import ROOT,LOCAL,OUT,SEED,freeze
from .data import head,load
from .measurement import measure
from .. import reliable_train as rt
from ..audit import immutable_json
from ..data import digest


def run():
    plan=freeze();rt.setup(SEED)
    directory=LOCAL/'runs/PC00'
    assert not directory.exists(),'Preserve attempted fit'
    directory.mkdir(parents=True)
    model,_,initial=head()
    cohorts=load()
    optimizer=torch.optim.AdamW(model.parameters(),lr=.003,weight_decay=0)
    parameters=list(model.parameters())
    assert len(parameters)==2 and all(p.requires_grad for p in parameters)
    assert {id(p) for p in parameters}=={id(p) for g in optimizer.param_groups for p in g['params']}
    commit=subprocess.run(['git','rev-parse','HEAD'],cwd=ROOT,capture_output=True,text=True,check=True).stdout.strip()
    trace=[];tick=time.perf_counter();gradient_receipt=None

    def assess(step):
        # Preserve model/optimizer first, even if a measurement later fails.
        torch.save(dict(head_state=model.state_dict(),optimizer=optimizer.state_dict(),step=step,
                        torch_rng=torch.get_rng_state(),source_commit=commit,
                        protocol_sha256=digest(OUT/'PC00-plan.json')),
                   directory/f'step-{step:04d}.pt')
        row=dict(step=step,seconds=time.perf_counter()-tick,cohorts={})
        model.eval()
        with torch.no_grad():
            for name,d in cohorts.items():
                raw=model(d['context'],d['features'])
                np.save(directory/f'{name}-step-{step:04d}-raw.npy',raw.numpy())
                prediction,metrics=measure(model,raw,d['values'],d['target'])
                np.savez_compressed(directory/f'{name}-step-{step:04d}-predictions.npz',
                    **{key:value.numpy() for key,value in prediction.items()})
                row['cohorts'][name]=metrics
        trace.append(row)
        print('PC00',step,{name:(value['exact'],value['mean_NLL']) for name,value in row['cohorts'].items()},flush=True)

    assess(0)
    fit=cohorts['fit']
    for step in range(1,2001):
        if step==1001:
            for group in optimizer.param_groups:group['lr']=.001
        model.train();optimizer.zero_grad(set_to_none=True)
        raw=model(fit['context'],fit['features'])
        if step==1:raw.retain_grad()
        loss=-model.log_mass(raw,fit['target'],fit['values']).mean()
        assert torch.isfinite(loss)
        loss.backward()
        if step==1:
            a=len(model.absolute)
            gradient_receipt=dict(parameter_names=[name for name,_ in model.named_parameters()],
                optimizer_inclusion_exact=True,
                parameter_gradient_norms={name:float(p.grad.norm()) for name,p in model.named_parameters()},
                output_gradient_norms=dict(absolute=float(raw.grad[:,:a].norm()),
                    residual=float(raw.grad[:,a:-3].norm()),fallback_gate=float(raw.grad[:,-3].norm()),
                    fallback_parameters=float(raw.grad[:,-2:].norm())))
        torch.nn.utils.clip_grad_norm_(parameters,5)
        optimizer.step()
        if step in plan['assessment_steps']:
            assess(step)
    final=trace[-1]['cohorts']['fit']
    fitted=final['accuracy']>=.95 and final['mean_NLL']<=.25
    files=list(directory.glob('*'))
    immutable_json(OUT/'PC00.json',dict(source_commit=commit,trace=trace,
        gradient_receipt=gradient_receipt,diagnostic_fit_gate_passed=fitted,
        fixed_final_step=2000,optimizer_updates=2000,trainable_parameters=sum(p.numel() for p in parameters),
        initial_checkpoint_sha256=digest(initial),final_checkpoint_sha256=digest(directory/'step-2000.pt'),
        protocol_sha256=digest(OUT/'PC00-plan.json'),data_ready_sha256=digest(OUT/'PC00-data-ready.json'),
        bindings={str(p.relative_to(ROOT)):digest(p) for p in files},seconds=time.perf_counter()-tick,
        timing_scope='After loading through all optimization/assessments/serialization; not pure optimization.',
        exposure=plan['exposure'],production_model=False,full_policy_comparison=False,
        original_benchmark_unchanged=True,new_fits=1,reserved_opened=0,promoted=False,three_seed_confirmed=False))
    print('Completed PC00; fresh Solxhigh review required',flush=True)


if __name__=='__main__':
    run()
