"""Cache unchanged L02 family modes before labels; reuse frozen PRE state."""
import json
import traceback
from pathlib import Path

import numpy as np
import torch

from ..audit import immutable_json
from ..data import digest
from ..learned_policy.pathway_reference import load_model
from ..learned_policy.retention_gradients import fingerprint
from ..order_information.anchored import committed_manifest
from ..policy_command_cache.forecast import family_forecast
from ..priority_broad.guard import committed_sources
from ..priority_head import flatten
from ..priority_regularized.safety import dependency_files,reject_optimized_python

ROOT=Path(__file__).resolve().parents[3]
OUT=ROOT/'tools/action_predictor/experiments/v26'
LOCAL=ROOT/'.cambc/action-predictor/v26/family-cache'
ANCHOR='ac70a48'
TOLERANCE=2e-5
GEOMETRY=('grid','valid','attack_range','ability_range','ability_mask')


def run():
    reject_optimized_python()
    commit,sources=committed_sources(ROOT,dependency_files(ROOT,('tools.action_predictor.policy_family_data.prepare',)))
    if LOCAL.exists():raise FileExistsError('Preserve prior family-cache attempt')
    receipts={};bindings={}
    for name,path in (
        ('inputs','tools/action_predictor/experiments/v16/policy-input-bindings.json'),
        ('model','tools/action_predictor/experiments/v16/L02.json'),
        ('completion','tools/action_predictor/experiments/v16/L02-completion.json'),
        ('upstream','tools/action_predictor/experiments/v18/upstream-ready.json'),
        ('priority','tools/action_predictor/experiments/v8/priority-data-ready.json'),
        ('marginals','tools/action_predictor/experiments/v23/ED00.json')):
        value,more=committed_manifest(ANCHOR,path);receipts[name]=value;bindings.update(more)
    expected={k.replace('\\','/'):v for k,v in receipts['inputs']['files'].items()}
    expected.update({k.replace('\\','/'):v for k,v in receipts['completion']['bindings'].items()})
    expected.update({k.replace('\\','/'):v for k,v in receipts['marginals']['inputs_and_outputs'].items()})
    ready=receipts['upstream'];info=receipts['model']
    checkpoint=f".cambc/action-predictor/v16/runs/L02/round-{info['selected_round']:02d}.pt"
    expected[checkpoint]=info['checkpoint_sha256']
    for split in ('train','validation'):
        expected[f'.cambc/action-predictor/v16/runs/L02/{split}-predictions.npz']=info['predictions_sha256'][split]
        expected[f'.cambc/action-predictor/v8/priority-{split}.npz']=receipts['priority']['files'][split]
        for name,value in ready['results'][split]['files'].items():
            expected[f'.cambc/action-predictor/v18/upstream/{split}/{name}.npy']=value
    def bind(relative):
        if relative not in expected:raise RuntimeError('Unbound family-cache input: '+relative)
        path=ROOT/relative
        if digest(path)!=expected[relative]:raise RuntimeError('Family-cache input changed: '+relative)
        bindings[relative]=expected[relative]
        return path
    if ready['checkpoint_sha256']!=info['checkpoint_sha256'] or ready['input_receipt_sha256']!=digest(ROOT/'tools/action_predictor/experiments/v16/policy-input-bindings.json'):
        raise RuntimeError('Frozen causal upstream lineage mismatch')
    bind(checkpoint);bind('.cambc/action-predictor/v5/runs/M01/model.pt')
    p05path=bind('.cambc/action-predictor/v8/runs/P05/model.pt')
    p05=torch.load(p05path,map_location='cpu',weights_only=True)
    mean,std=p05['extra_mean'].numpy(),p05['extra_std'].numpy()
    if mean.shape!=(39,) or std.shape!=(39,) or not (std>0).all():raise RuntimeError('P05 input normalizer changed')
    immutable_json(OUT/'family-cache-plan.json',dict(source_commit=commit,sources=sources,input_manifests=bindings,
        models='Unchanged selected L02 with existing P05 priority modes; no replacement model or fitting',
        rows=dict(train=433071,validation=14439),splits='Only original eligible TRAIN/DEV; no reserved payload paths',
        inference_fields=list(GEOMETRY)+['frozen_PRE_latent','frozen_PRE_goal_features','frozen_PRE_logprior',
                                      'predicted_priority_mode','predicted_priority_mode_logp'],
        additional_features='Existing39own-priority/history channels, normalized using retained P05 TRAIN statistics; no new getter queries',
        causal_boundary='Every family is forecast before reading current labels. Frozen L02 upstream was saved before current-action assimilation; earlier actual own actions only. Baseline filter and augmented traversal cadence stay unchanged.',
        numerical='Preserve original float arithmetic. Require exact semantic baseline parity and all-row type-logp maxerror<=2e-5; type normalization and mode<=family mass tolerance2e-5. Historical tighter normalization failure remains failed.',
        retention='Flush every forecast table before target-based parity; archive file hashes before checks. Any failure preserves partial arrays, written prefix and failing PRE input block. No automatic restart or row dropping.',
        representation='Observed benchmark command representation; shop purchase arguments unavailable and entity identity ambiguous. Full engine legality unassessed.',
        future_scope='This cache does NOT supply RC01 other-unit priorities on all decisions. That separate causal recovery remains required for full-policy use of RC01. No learning protocol or fit is allocated here.',
        new_fits=0,optimizer_updates=0,new_engine_queries=0,reserved_opened=0))
    LOCAL.mkdir(parents=True)
    model,_,_=load_model('L02');model.eval().requires_grad_(False);before=fingerprint(model)
    torch.set_num_threads(4);results={}
    for split in ('train','validation'):
        directory=LOCAL/split;directory.mkdir()
        banks={};written=0;start=0;step={};geo={}
        try:
            n=ready['results'][split]['rows']
            if n!={'train':433071,'validation':14439}[split]:raise RuntimeError('Original denominator changed')
            dataset=bind('.cambc/action-predictor/v5/combined-train.npz' if split=='train' else '.cambc/action-predictor/v4/validation.npz')
            # Read an explicit PRE allowlist, without current labels, outcomes or auxiliary future targets.
            with np.load(dataset) as z:geometry={key:z[key] for key in GEOMETRY}
            cache={name:np.load(bind(f'.cambc/action-predictor/v18/upstream/{split}/{name}.npy'),mmap_mode='r')
                   for name in ('latent','features','logprior')}
            with np.load(bind(f'.cambc/action-predictor/v8/priority-{split}.npz')) as z:
                values,history=z['values'],z['history']
            if len(values)!=n or len(history)!=n or values.dtype!=np.int64 or history.dtype!=np.int64:
                raise RuntimeError('Causal own-priority row identity/schema changed')
            teacher_modes=np.load(bind(f'.cambc/action-predictor/v13/{split}-modes.npy'),mmap_mode='r')
            teacher_mode_logq=np.load(bind(f'.cambc/action-predictor/v13/{split}-mode-logq.npy'),mmap_mode='r')
            teacher_type=np.load(bind(f'.cambc/action-predictor/v14/{split}-type-logp.npy'),mmap_mode='r')
            spec=dict(type_logp=((n,15),np.float32),mode_joint_logp=((n,15),np.float32),
                family_coordinate=((n,15),np.int64),priority=((n,),np.int64),prediction=((n,),np.int64),
                proposed_coordinate=((n,),np.int64),own_priority_features=((n,39),np.float32))
            banks={key:np.lib.format.open_memmap(directory/(key+'.npy'),mode='w+',shape=shape,dtype=dtype)
                   for key,(shape,dtype) in spec.items()}
            with torch.inference_mode():
                for start in range(0,n,256):
                    stop=min(start+256,n);sl=slice(start,stop)
                    latent=torch.from_numpy(np.array(cache['latent'][sl]))
                    features=torch.from_numpy(np.array(cache['features'][sl]))
                    step=dict(context=latent+model.goal_condition(features),logprior=torch.from_numpy(np.array(cache['logprior'][sl])))
                    geo=dict(grid=torch.from_numpy(geometry['grid'][sl]).float(),valid=torch.from_numpy(geometry['valid'][sl]),
                        rules=torch.from_numpy(np.column_stack((geometry['attack_range'][sl],geometry['ability_range'][sl],geometry['ability_mask'][sl]))).float())
                    prediction=family_forecast(model,step,**geo,priority_mode=torch.from_numpy(np.array(teacher_modes[sl,9,2])),
                        priority_mode_logp=torch.from_numpy(np.array(teacher_mode_logq[sl,9]-teacher_type[sl,9])))
                    for key,value in prediction.items():banks[key][sl]=value.numpy()
                    banks['own_priority_features'][sl]=(flatten(values[sl],history[sl]).astype(np.float32)-mean)/std
                    written=stop
                    if stop==n or stop%32768==0:print('Family PRE cache',split,stop,'/',n,flush=True)
            for value in banks.values():value.flush()
            files={str(path.relative_to(ROOT)):digest(path) for path in directory.glob('*.npy')}
            immutable_json(directory/'forecasts-preserved.json',dict(rows=n,rows_written=written,files=files,labels_read=False))
            # Current answers are first accessed here, after every forecast is durable.
            with np.load(dataset) as z:y=z['y']
            baseline_path=bind(f'.cambc/action-predictor/v16/runs/L02/{split}-predictions.npz')
            with np.load(baseline_path) as z:baseline={key:z[key] for key in z.files}
            reference=np.load(bind(f'.cambc/action-predictor/v23/decoder-attribution/L02-{split}-family-logp.npy'),mmap_mode='r')
            row=np.arange(n);type_logp=np.asarray(banks['type_logp'])
            checks=dict(prediction_mismatches=int((banks['prediction']!=baseline['prediction']).sum()),
                selected_coordinate_mismatches=int((banks['proposed_coordinate']!=baseline['proposed_coordinate']).sum()),
                priority_mismatches=int((banks['priority']!=baseline['priority']).sum()),
                true_family_coordinate_mismatches=int((banks['family_coordinate'][row,y]!=baseline['coordinate']).sum()),
                max_type_logp_difference=float(np.abs(type_logp-reference).max()),
                max_true_type_NLL_difference=float(np.abs(-type_logp[row,y]-baseline['type_nll']).max()),
                max_type_normalization_error=float(np.abs(np.exp(type_logp.astype(np.float64)).sum(1)-1).max()),
                max_mode_above_family_mass=float(np.max(banks['mode_joint_logp']-type_logp)),
                finite=bool(np.isfinite(type_logp).all() and np.isfinite(banks['mode_joint_logp']).all() and np.isfinite(banks['own_priority_features']).all()))
            immutable_json(directory/'checks.json',checks)
            if any(checks[k] for k in ('prediction_mismatches','selected_coordinate_mismatches','priority_mismatches','true_family_coordinate_mismatches')):
                raise RuntimeError('Original command parity failed; preserve criterion and arrays')
            if not checks['finite'] or any(checks[k]>TOLERANCE for k in ('max_type_logp_difference','max_true_type_NLL_difference','max_type_normalization_error','max_mode_above_family_mass')):
                raise RuntimeError('Family-cache numerical contract failed; no tolerance change')
            results[split]=dict(rows=n,files=files,checks=checks)
            bindings.update(files)
            for name in ('forecasts-preserved.json','checks.json'):
                p=directory/name;bindings[str(p.relative_to(ROOT))]=digest(p)
            del geometry,cache,values,history,banks,baseline,reference
        except BaseException:
            for value in banks.values():value.flush()
            np.savez_compressed(directory/f'failure-PRE-{start}.npz',**{'step_'+k:v.numpy() for k,v in step.items()},
                                **{'geometry_'+k:v.numpy() for k,v in geo.items()})
            immutable_json(directory/'failure.json',dict(error=traceback.format_exc(),rows_written=written,last_batch_start=start))
            raise
    unchanged=fingerprint(model)==before
    if not unchanged:raise RuntimeError('Read-only model state changed')
    immutable_json(OUT/'family-cache-ready.json',dict(source_commit=commit,sources=sources,bindings=bindings,results=results,
        plan_sha256=digest(OUT/'family-cache-plan.json'),model_state_unchanged=True,
        causal_scope='Same frozen augmented-cadence filter, genuine earlier actions and gaps. No newly refiltered or natural-cadence policy; no current-answer routing.',
        numerical_scope='Original arithmetic and historical tighter failure retained; no new normalization repair or exact original API probability claim.',
        new_fits=0,optimizer_updates=0,new_engine_queries=0,reserved_opened=0,
        command='python -m tools.action_predictor.policy_family_data.prepare'))
    print('Every-family cache ready; no predictor changed or fitted.',flush=True)


if __name__=='__main__':run()
