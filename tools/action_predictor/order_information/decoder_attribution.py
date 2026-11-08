"""Distinguish marginal family beliefs from complete-command MAP decisions."""
import json

import numpy as np
import torch

from ..audit import immutable_json
from ..data import digest
from .. import reliable_train as rt
from ..priority_broad.guard import committed_sources
from ..priority_regularized.safety import dependency_files,reject_optimized_python
from ..learned_policy.pathway_reference import load_model
from ..goal_readout.model import FrozenGoalReadout
from ..goal_readout.data import geometry_reference
from .anchored import ROOT,committed_manifest
from .data import LOCAL,OUT


def read(path):
    with np.load(path) as z:return {key:z[key] for key in z.files}


def run():
    reject_optimized_python()
    commit,sources=committed_sources(ROOT,dependency_files(ROOT,(
        'tools.action_predictor.order_information.decoder_attribution',)))
    receipts={};bindings={}
    for relative in ('tools/action_predictor/experiments/v18/U01-completion-v2.json',
                     'tools/action_predictor/experiments/v18/upstream-ready.json',
                     'tools/action_predictor/experiments/v16/L02-completion.json',
                     'tools/action_predictor/experiments/v8/priority-data-ready.json'):
        value,more=committed_manifest(commit,relative);receipts[relative]=value;bindings.update(more)
    expected={}
    for value in receipts.values():expected.update({k.replace('\\','/'):v for k,v in value.get('bindings',{}).items()})
    ready=receipts['tools/action_predictor/experiments/v18/upstream-ready.json']
    priority=receipts['tools/action_predictor/experiments/v8/priority-data-ready.json']
    for split,row in ready['results'].items():
        for name,value in row['files'].items():expected[f'.cambc/action-predictor/v18/upstream/{split}/{name}.npy']=value
        expected[f'.cambc/action-predictor/v8/priority-{split}.npz']=priority['files'][split]
    # These benchmark and natural-membership identities are original frozen values.
    expected['.cambc/action-predictor/v5/combined-train.npz']='39386010575ad30add064fdae750680f34cfcc732c4fd00fb657875ff4c61ffb'
    expected['.cambc/action-predictor/v4/validation.npz']='01a15e1e10f68922334a5367bb825c8ef9bbe228ae7a9e86e92aae9609b204ed'
    expected['.cambc/action-predictor/v9/frequency/natural-mask.npy']='09217d8fc3d5673d980c8b8a4434861aa26dddb37e506bbfa22cbaafc0e525bd'
    expected['.cambc/action-predictor/v5/runs/M01/model.pt']='906261a160de839a9e536462e84d6c19360b8fd9e584764d70fd0eb80f378936'
    def bind(relative):
        if relative not in expected:raise RuntimeError('Unbound diagnostic input: '+relative)
        path=ROOT/relative
        if digest(path)!=expected[relative]:raise RuntimeError('Diagnostic input changed: '+relative)
        bindings[relative]=expected[relative];return path
    plan=dict(source_commit=commit,sources=sources,
        purpose='Measure family-level suppression under normalized complete-command MAP versus '
                'marginal family argmax, using frozen causal upstream features. Distinguish this '
                'from weak type beliefs and unchanged integer-mode errors.',
        models=['L02','U01'],sampling='All original DEV rows; augmented and natural-membership TRAIN '
                    'reported separately. Same cached augmented-cadence filtering; not natural cadence.',
        outputs='Only marginal family log probabilities/type-argmax diagnostics; existing complete '
                'commands stay unchanged. No new complete-predictor variant selected or scored.',
        interpretation='Joint MAP correctly discounts uncertain conditional arguments. A difference '
                'from type argmax is not objective/decoder inconsistency. Relations to omitted own '
                'priority channels are descriptive, not causal attribution. No fitting.',
        new_fits=0,new_engine_queries=0,reserved_opened=0)
    immutable_json(OUT/'ED00-plan.json',plan)
    torch.set_num_threads(4)
    if rt.LABELS.index('priority')!=9:raise RuntimeError('Label order changed')
    for relative in ('tools/action_predictor/experiments/v18/U01.json',
                     'tools/action_predictor/experiments/v16/L02.json',
                     'tools/action_predictor/experiments/v17/Q01-L02-reference.json',
                     '.cambc/action-predictor/v5/runs/M01/model.pt'):
        bind(relative)
    upstream,_,upstream_checkpoint=load_model('L02')
    bind(upstream_checkpoint.relative_to(ROOT).as_posix())
    info=json.loads((ROOT/'tools/action_predictor/experiments/v18/U01.json').read_text())
    checkpoint=bind(f".cambc/action-predictor/v18/runs/U01/round-{info['selected_round']:02d}.pt")
    treatment=FrozenGoalReadout(upstream,geometry_reference(),True)
    treatment.load_state_dict(torch.load(checkpoint,weights_only=False,map_location='cpu')['state']);treatment.eval()
    directory=LOCAL/'decoder-attribution'
    if directory.exists():raise FileExistsError('Preserve prior attribution attempt')
    directory.mkdir(parents=True)
    results={}
    for split in ('train','validation'):
        path='.cambc/action-predictor/v5/combined-train.npz' if split=='train' else '.cambc/action-predictor/v4/validation.npz'
        raw=read(bind(path));y=raw['y'];n=len(y)
        cache={name:np.load(bind(f'.cambc/action-predictor/v18/upstream/{split}/{name}.npy'),mmap_mode='r')
               for name in ('latent','features','logprior')}
        values=read(bind(f'.cambc/action-predictor/v8/priority-{split}.npz'))['values']
        changed=(values[:,1]==1)&(values[:,3]==1)&(values[:,0]!=values[:,2])
        masks={'all':np.ones(n,bool),'current_scheduled_different':changed,'current_scheduled_equal':~changed}
        if split=='train':masks['natural']=np.load(bind('.cambc/action-predictor/v9/frequency/natural-mask.npy'))
        results[split]={}
        for name,model in (('L02',upstream),('U01',treatment)):
            logp=np.empty((n,len(rt.LABELS)),np.float32)
            with torch.inference_mode():
                for start in range(0,n,256):
                    stop=min(start+256,n)
                    latent=torch.from_numpy(np.array(cache['latent'][start:stop]))
                    features=torch.from_numpy(np.array(cache['features'][start:stop]))
                    prior=torch.from_numpy(np.array(cache['logprior'][start:stop]))
                    step=dict(context=latent+model.goal_condition(features),logprior=prior)
                    logp[start:stop]=torch.logsumexp(prior[:,:,None]+model.types(step),1).numpy()
            archive=directory/f'{name}-{split}-family-logp.npy'
            np.save(archive,logp)  # Preserve before comparison assertions.
            bindings[str(archive.relative_to(ROOT))]=digest(archive)
            prefix='v16' if name=='L02' else 'v18'
            prediction=read(bind(f'.cambc/action-predictor/{prefix}/runs/{name}/{split}-predictions.npz'))
            difference=float(np.max(np.abs(-logp[np.arange(n),y]-prediction['type_nll'])))
            if difference>2e-5:raise RuntimeError('Frozen marginal reconstruction differs from archived type loss')
            marginal=logp.argmax(-1);joint=prediction['prediction'];rows={}
            priority_correct=prediction['priority']==raw['priority']
            for stratum,mask in masks.items():
                table={}
                for code,family in enumerate(rt.LABELS):
                    true=(y==code)&mask;marginal_correct=(marginal==code)&true;joint_correct=(joint==code)&true
                    table[family]=dict(support=int(true.sum()),marginal_type_correct=int(marginal_correct.sum()),
                        joint_selected_family_correct=int(joint_correct.sum()),
                        marginal_correct_joint_other=int((marginal_correct&~joint_correct).sum()),
                        joint_correct_marginal_other=int((joint_correct&~marginal_correct).sum()),
                        marginal_false_positives=int(((marginal==code)&~true&mask).sum()),
                        joint_false_positives=int(((joint==code)&~true&mask).sum()),
                        mean_true_family_probability=float(np.exp(logp[true,code]).mean()) if true.any() else None)
                m=mask&(y==rt.LABELS.index('priority'))
                rows[stratum]=dict(rows=int(mask.sum()),families=table,
                    correct_priority_integer_support=int((m&priority_correct).sum()),
                    marginal_priority_correct_integer=int((m&priority_correct&(marginal==9)).sum()),
                    joint_priority_correct_integer=int((m&priority_correct&(joint==9)).sum()),
                    correct_integer_marginal_priority_but_joint_other=int((m&priority_correct&(marginal==9)&(joint!=9)).sum()))
            results[split][name]=dict(maximum_archived_true_type_NLL_difference=difference,strata=rows)
    immutable_json(OUT/'ED00.json',dict(results=results,inputs_and_outputs=bindings,sources=sources,
        plan_sha256=digest(OUT/'ED00-plan.json'),source_commit=commit,new_fits=0,reserved_opened=0,
        limitations=plan['interpretation'],numerical='Existing conditional-normalization qualification '
                    'unchanged. This checks marginal family probabilities, not a new raw-PRE filter audit.'))
    print({name:results['validation'][name]['strata']['all']['families']['priority'] for name in results['validation']},flush=True)


if __name__=='__main__':run()
