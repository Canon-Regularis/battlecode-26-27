"""Consume retained causal family/argument forecasts, then separate supervision."""
from collections import defaultdict
import json
import numpy as np
import torch
from ..audit import immutable_json
from ..data import digest
from ..order_information.anchored import committed_manifest
from .protocol import ROOT,OUT,LOCAL,ROWS,SWAP_SEED,FEATURES,inputs,fold,freeze,source_gate


def features(normalized,values):
    if normalized.shape!=(len(values),39) or values.dtype!=np.int64 or values.shape!=(len(values),7):raise ValueError('Own-priority interface changed')
    both=(values[:,1]==1)&(values[:,3]==1)
    return np.column_stack((normalized,~both,both&(values[:,0]!=values[:,2]))).astype(np.float64)


def donors(groups,engine,values,history,fit,seed=SWAP_SEED):
    if values.dtype!=np.int64 or history.dtype!=np.int64:raise TypeError('Exact availability inputs required')
    available=np.column_stack((values[:,[1,3,5]],history[:,:,1]))
    if not np.isin(available,[0,1]).all():raise ValueError('Availability schema changed')
    blocks=defaultdict(list)
    for i in np.flatnonzero(fit):blocks[(int(groups[i]),int(engine[i]),tuple(available[i]))].append(int(i))
    result=np.arange(len(groups),dtype=np.int64);rng=np.random.default_rng(seed);singletons=0
    for ids in blocks.values():
        if len(ids)==1:singletons+=1;continue
        order=rng.permutation(ids);result[order]=np.roll(order,1)
    if not fit[result[fit]].all() or not np.array_equal(groups[result[fit]],groups[fit]) or not np.array_equal(engine[result[fit]],engine[fit]) or not np.array_equal(available[result[fit]],available[fit]):
        raise RuntimeError('Control donor boundary violated')
    return result,singletons


def prepare():
    source_gate();plan=freeze();bind,bindings=inputs()
    directory=LOCAL/'data'
    if directory.exists():raise FileExistsError('Preserve previous preparation')
    directory.mkdir(parents=True);results={}
    jobs=json.loads(bind('.cambc/action-predictor/v7/jobs.json').read_text())
    for split,n in ROWS.items():
        family=ROOT/f'.cambc/action-predictor/v26/family-cache/{split}'
        def array(name):return np.load(bind(str((family/(name+'.npy')).relative_to(ROOT))),mmap_mode='r')
        type_logp=np.array(array('type_logp'),dtype=np.float64)
        conditional=np.array(array('mode_joint_logp'),dtype=np.float64)-type_logp
        mode=np.load(bind(f'.cambc/action-predictor/v27/forecasts/{split}/JP02/integer.npy'))
        conditional[:,9]=np.load(bind(f'.cambc/action-predictor/v27/forecasts/{split}/JP02/mode_logp.npy'))
        coordinate=np.array(array('family_coordinate'))
        with np.load(bind(f'.cambc/action-predictor/v8/priority-{split}.npz')) as z:values,history=z['values'],z['history']
        x=features(np.array(array('own_priority_features')),values)
        # All inference inputs are formed before reading current action labels.
        for name,value in dict(type_logp=type_logp,conditional_mode_logp=conditional,family_coordinate=coordinate,priority_mode=mode,features=x).items():
            np.save(directory/f'{split}-{name}.npy',value)
        dataset='.cambc/action-predictor/v5/combined-train.npz' if split=='train' else '.cambc/action-predictor/v4/validation.npz'
        with np.load(bind(dataset)) as z:raw={key:z[key] for key in ('y','py','priority','group')}
        with np.load(bind(f'.cambc/action-predictor/v27/JP02-{split}-predictions.npz')) as z:
            param_nll=z['param_nll'];baseline={key:z[key] for key in ('prediction','proposed_coordinate','priority','coordinate','nll','type_nll')}
        if len(raw['y'])!=n or x.shape!=(n,41):raise RuntimeError('Original row denominator changed')
        np.savez_compressed(directory/f'{split}-targets.npz',**raw,param_nll=param_nll)
        engine=np.zeros(n,np.int8);seen=np.zeros(n,bool)
        for job in jobs:
            if job['split']!=split:continue
            sl=slice(job['offset'],job['offset']+job['rows'])
            if seen[sl].any() or job['record']['engine_version'] not in ('2.0.0','3.0.0'):raise RuntimeError('Canonical job identity changed')
            engine[sl]=int(job['record']['engine_version'][0]);seen[sl]=True
        if not seen.all():raise RuntimeError('Incomplete eligible jobs')
        if split=='train':
            natural=np.load(bind('.cambc/action-predictor/v9/frequency/natural-mask.npy'));fit,held,held_groups=fold(raw['group'],natural)
            donor,singletons=donors(raw['group'],engine,values,history,fit)
            active=np.any(x[fit]!=0,axis=0)
            if not active.any() or not np.array_equal(active,np.any(x[donor[fit]]!=0,axis=0)):raise RuntimeError('Active capacity differs')
            np.savez_compressed(directory/'cohorts.npz',fit=fit,held=held,natural=natural,donor=donor,active=active,held_groups=held_groups)
            results['control']=dict(singleton_fit_rows=singletons,feature_changed_fit_rows=int((x[donor[fit]]!=x[fit]).any(1).sum()),
                identical_feature_fit_rows=int((x[donor[fit]]==x[fit]).all(1).sum()),fit_rows=int(fit.sum()),held_rows=int(held.sum()),
                active_feature_names=[FEATURES[i] for i in np.flatnonzero(active)],trainable_parameters=int(active.sum())*15)
        np.save(directory/f'{split}-engine.npy',engine)
        # Initial normalized family distribution, actual joint decision, and NLL.
        shifted=type_logp-type_logp.max(1,keepdims=True);initial=shifted-np.log(np.exp(shifted).sum(1,keepdims=True))
        prediction=(initial+conditional).argmax(1);proposed=coordinate[np.arange(n),prediction]
        selected=raw['y'];loss=-initial[np.arange(n),selected]+param_nll
        checks=dict(action_mismatches=int((prediction!=baseline['prediction']).sum()),
            selected_coordinate_mismatches=int((proposed!=baseline['proposed_coordinate']).sum()),
            priority_mismatches=int((mode!=baseline['priority']).sum()),
            max_observed_NLL_difference=float(np.abs(loss-baseline['nll']).max()),
            max_family_normalization_error=float(np.abs(np.exp(initial).sum(1)-1).max()),
            max_mode_logp_above_zero=float(conditional.max()))
        immutable_json(directory/f'{split}-initial-checks.json',checks)
        if checks['action_mismatches'] or checks['selected_coordinate_mismatches'] or checks['priority_mismatches'] or checks['max_observed_NLL_difference']>2e-5 or checks['max_family_normalization_error']>1e-12 or checks['max_mode_logp_above_zero']>2e-5:
            raise RuntimeError('Prospective initial contract failed; preserve artifacts')
        results[split]=checks
    files={str(p.relative_to(ROOT)):digest(p) for p in directory.iterdir()}
    immutable_json(OUT/'AB-data-ready.json',dict(plan_sha256=digest(OUT/'AB-plan.json'),sources=plan['sources'],source_commit=plan['source_commit'],
        inputs=bindings,files=files,results=results,labels_not_in_inference_inputs=True,new_fits=0,reserved_opened=0,
        command='python -m tools.action_predictor.policy_action_readout.data'))
    print('AB data ready',results,flush=True)


def load():
    import subprocess
    commit=subprocess.run(['git','rev-parse','HEAD'],cwd=ROOT,check=True,capture_output=True,text=True).stdout.strip()
    plan,_=committed_manifest(commit,'tools/action_predictor/experiments/v28/AB-plan.json')
    ready,_=committed_manifest(commit,'tools/action_predictor/experiments/v28/AB-data-ready.json')
    if ready['plan_sha256']!=digest(OUT/'AB-plan.json'):raise RuntimeError('AB protocol changed')
    for p,h in ready['files'].items():
        if digest(ROOT/p)!=h:raise RuntimeError('AB cache changed: '+p)
    result={}
    for split,n in ROWS.items():
        d={key:np.load(LOCAL/f'data/{split}-{key}.npy',mmap_mode='r') for key in ('type_logp','conditional_mode_logp','family_coordinate','priority_mode','features','engine')}
        with np.load(LOCAL/f'data/{split}-targets.npz') as z:d['targets']={k:z[k] for k in z.files}
        if len(d['type_logp'])!=n:raise RuntimeError('Assessment denominator changed')
        result[split]=d
        path=ROOT/f'.cambc/action-predictor/v27/JP02-{split}-predictions.npz'
        key=str(path.relative_to(ROOT)).replace('\\','/')
        if digest(path)!=ready['inputs'][key]:raise RuntimeError('Frozen baseline command archive changed')
        with np.load(path) as z:d['baseline']={k:z[k] for k in z.files}
    with np.load(LOCAL/'data/cohorts.npz') as z:cohorts={k:z[k] for k in z.files}
    fit,held,held_groups=fold(result['train']['targets']['group'],cohorts['natural'])
    for a,b in ((fit,cohorts['fit']),(held,cohorts['held']),(held_groups,cohorts['held_groups'])):
        if not np.array_equal(a,b):raise RuntimeError('Prospective exclusion changed')
    if not np.array_equal(cohorts['fit'][cohorts['donor'][fit]],np.ones(int(fit.sum()),bool)):raise RuntimeError('Held donor introduced')
    return result,cohorts,plan,ready


def batch(d,ids,active,donor=None):
    feature_ids=np.asarray(ids) if donor is None else donor[np.asarray(ids)]
    return torch.from_numpy(np.array(d['type_logp'][ids])),torch.from_numpy(np.array(d['features'][feature_ids][:,active]))


if __name__=='__main__':prepare()
