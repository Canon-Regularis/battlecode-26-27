"""Frozen every-family joint forecasts; labels are read only after archival."""
import json
import subprocess
import traceback
from pathlib import Path

import numpy as np
import torch

from ..audit import immutable_json
from ..data import digest
from ..priority_broad.guard import committed_sources
from ..priority_regularized.safety import dependency_files,reject_optimized_python
from ..priority_modes import AbsolutePriorityModes
from ..priority_residual_modes import AnchoredPriorityModes
from ..relational_priority.model import SignedPointCorrection
from .protocol import ROOT,OUT,LOCAL,ROWS,ARMS,inputs


def choose(mode_joint,family_coordinate,integer):
    """Family modes suffice for global MAP; do not normalize mode scores."""
    prediction=mode_joint.argmax(1)
    coordinate=family_coordinate[np.arange(len(prediction)),prediction]
    return dict(prediction=prediction.astype(np.int64),proposed_coordinate=coordinate.copy(),priority=integer.copy())


def padded(offsets,priorities,available,roles,start,stop):
    lengths=np.diff(offsets[start:stop+1]);width=max(1,int(lengths.max(initial=0)))
    p=np.zeros((stop-start,width,2),np.int64);a=np.zeros_like(p,dtype=bool);r=np.full((stop-start,width),-1,np.int8)
    for i,index in enumerate(range(start,stop)):
        sl=slice(int(offsets[index]),int(offsets[index+1]));n=int(lengths[i])
        p[i,:n]=priorities[sl];a[i,:n]=available[sl];r[i,:n]=roles[sl]
    return tuple(torch.from_numpy(x) for x in (p,a,r))


def models(receipts):
    p05=torch.load(ROOT/'.cambc/action-predictor/v8/runs/P05/model.pt',map_location='cpu',weights_only=True)
    v=receipts['residual_vocabulary']
    base=AnchoredPriorityModes(torch.nn.Linear(128,2),v['absolute'],v['absolute_counts'],v['residual'],v['residual_counts'])
    base.load_state_dict(p05['head_state']);result={'JP00':base}
    for arm,name in (('JP01','RC00'),('JP02','RC01')):
        saved=torch.load(ROOT/f'.cambc/action-predictor/v24/runs/{name}/step-2000.pt',map_location='cpu',weights_only=True)
        state=saved['state'];model=SignedPointCorrection(base,active=state['active']);model.load_state_dict(state)
        if any(not torch.equal(value,base.state_dict()[key]) for key,value in model.base.state_dict().items()):
            raise RuntimeError('Correction frozen core differs from P05')
        result[arm]=model
    saved=torch.load(ROOT/'.cambc/action-predictor/v8/runs/P03/model.pt',map_location='cpu',weights_only=True)
    for key in ('extra_mean','extra_std'):
        if not torch.equal(saved[key],p05[key]):raise RuntimeError('P03/P05 input normalization differs')
    v=receipts['absolute_vocabulary']
    p03=AbsolutePriorityModes(torch.nn.Linear(128,2),v['values'],v['counts'],saved['config']['use_inputs'])
    p03.load_state_dict(saved['head_state']);result['JP03']=p03
    for model in result.values():model.eval().requires_grad_(False)
    return result


def run():
    reject_optimized_python()
    commit,sources=committed_sources(ROOT,dependency_files(ROOT,('tools.action_predictor.policy_priority_integration.forecast',
        'tools.action_predictor.policy_priority_integration.test_forecast')))
    test=subprocess.run([__import__('sys').executable,'-m','unittest','tools.action_predictor.policy_priority_integration.test_forecast','-v'],
        cwd=ROOT,capture_output=True,text=True)
    if test.returncode:raise RuntimeError('Forecast prerequisites failed: '+test.stdout+test.stderr)
    receipts,bindings=inputs();plan=json.loads((OUT/'JP-plan.json').read_text())
    ready_path=OUT/'JP-fields-ready.json';ready=json.loads(ready_path.read_text())
    if ready['plan_sha256']!=digest(OUT/'JP-plan.json'):raise RuntimeError('Recovery plan lineage differs')
    bindings[str(ready_path.relative_to(ROOT))]=digest(ready_path)
    def bind(relative,expected):
        p=Path(relative);p=p if p.is_absolute() else ROOT/p
        if digest(p)!=expected:raise RuntimeError('Consumed frozen input changed: '+str(p))
        bindings[str(p.relative_to(ROOT))]=expected
        return p
    # Only inputs actually consumed are rehashed; no unchanged whole-replay audit.
    for name,value in ready['files'].items():bind(name,value)
    family=receipts['family_cache'];family_files={}
    for split in ROWS:
        for name,value in family['results'][split]['files'].items():family_files[name.replace('\\','/')]=value
    contexts=Path(receipts['contexts']['directory'])
    for split in ROWS:bind(contexts/(split+'.npy'),receipts['contexts']['contexts'][split])
    destination=LOCAL/'forecasts'
    if destination.exists():raise FileExistsError('Preserve previous forecast attempt')
    immutable_json(OUT/'JP-forecast-plan.json',dict(source_commit=commit,sources=sources,inputs=bindings,
        recovery_plan_sha256=digest(OUT/'JP-plan.json'),arms=ARMS,batch=256,
        arithmetic='Retained normalized float64 integer mass; original frozen float32 family-mode scores promoted to float64 for priority competition. Global family order and original head integer ties retained.',
        null_contract='JP00 requires zero semantic prediction/required-argument mismatches versus retained L02 and maximum observed-NLL error<=2e-5. Save all raw outputs/forecasts before answers or checks. Failure preserves arrays and stops assessment.',
        scope='Same frozen augmented-cadence L02 filtering; no auxiliary field modifies upstream state. Exact paired other-unit fields on every row, no gold-family routing.',
        new_fits=0,optimizer_updates=0,reserved_opened=0))
    destination.mkdir(parents=True);torch.set_num_threads(4);heads=models(receipts);results={}
    for split,n in ROWS.items():
        directory=destination/split;directory.mkdir();banks={};written=0
        try:
            cache={}
            for key in ('type_logp','mode_joint_logp','family_coordinate','own_priority_features'):
                name=f'.cambc/action-predictor/v26/family-cache/{split}/{key}.npy'
                cache[key]=np.load(bind(name,family_files[name]),mmap_mode='r')
            context=np.load(contexts/(split+'.npy'),mmap_mode='r')
            with np.load(ROOT/f'.cambc/action-predictor/v8/priority-{split}.npz') as z:values,history=z['values'],z['history']
            data={key:np.load(LOCAL/f'data/{split}-{key}.npy',mmap_mode='r') for key in ('offsets','priorities','available','roles')}
            for arm,model in heads.items():
                sub=directory/arm;sub.mkdir()
                width=model.linear.out_features if arm in ('JP00','JP03') else model.base.linear.out_features
                spec=dict(raw=((n,width),np.float32),integer=((n,),np.int64),mode_logp=((n,),np.float64),
                    fallback_weight=((n,),np.float64),prediction=((n,),np.int64),proposed_coordinate=((n,),np.int64))
                banks[arm]={key:np.lib.format.open_memmap(sub/(key+'.npy'),mode='w+',shape=shape,dtype=dtype)
                    for key,(shape,dtype) in spec.items()}
            with torch.inference_mode():
                for start in range(0,n,256):
                    stop=min(start+256,n);sl=slice(start,stop);v=torch.from_numpy(values[sl]);h=torch.from_numpy(history[sl])
                    c=torch.from_numpy(np.array(context[sl]));extra=torch.from_numpy(np.array(cache['own_priority_features'][sl]))
                    raw=heads['JP00'](c,extra);points,_=heads['JP00'].components(raw,v)
                    p,a,r=padded(data['offsets'],data['priorities'],data['available'],data['roles'],start,stop)
                    features=heads['JP01'].features(points,v,h,p,a,r)
                    outputs={'JP00':raw,'JP01':heads['JP01'].correct_logits(raw,features),
                        'JP02':heads['JP02'].correct_logits(raw,features),'JP03':heads['JP03'](c,extra)}
                    for arm,output in outputs.items():banks[arm]['raw'][sl]=output.numpy()
                    # Durable raw output precedes mode/probability checks, including exceptions.
                    for arm in banks:banks[arm]['raw'].flush()
                    for arm,output in outputs.items():
                        model=heads[arm]
                        candidates,mass=model.candidate_log_masses(output) if arm=='JP03' else model.candidate_log_masses(output,v)
                        winner=mass.argmax(1);integer=candidates[torch.arange(len(v)),winner].numpy()
                        mode_logp=mass[torch.arange(len(v)),winner].numpy()
                        score=np.array(cache['mode_joint_logp'][sl],dtype=np.float64)
                        score[:,9]=cache['type_logp'][sl,9].astype(np.float64)+mode_logp
                        command=choose(score,cache['family_coordinate'][sl],integer)
                        for key in ('prediction','proposed_coordinate'):banks[arm][key][sl]=command[key]
                        banks[arm]['integer'][sl]=integer;banks[arm]['mode_logp'][sl]=mode_logp
                        mix=output[:,:-2].double().log_softmax(-1) if arm=='JP03' else model.components(output,v)[1]
                        banks[arm]['fallback_weight'][sl]=mix[:,-1].exp().numpy()
                    written=stop
                    if stop==n or stop%32768==0:print('JP frozen forecasts',split,stop,'/',n,flush=True)
            for bank in banks.values():
                for array in bank.values():array.flush()
            files={str(p.relative_to(ROOT)):digest(p) for p in directory.rglob('*.npy')}
            immutable_json(directory/'preserved.json',dict(rows=n,files=files,labels_read=False))
            results[split]=dict(rows=n,files=files)
        except BaseException:
            for bank in banks.values():
                for array in bank.values():array.flush()
            immutable_json(directory/'failure.json',dict(error=traceback.format_exc(),rows_written=written))
            raise
    immutable_json(OUT/'JP-forecasts-ready.json',dict(source_commit=commit,sources=sources,inputs=bindings,results=results,
        plan_sha256=digest(OUT/'JP-forecast-plan.json'),tests=dict(returncode=test.returncode,stdout=test.stdout,stderr=test.stderr),
        forecasts_precede_current_answers=True,new_fits=0,optimizer_updates=0,reserved_opened=0,
        command='python -m tools.action_predictor.policy_priority_integration.forecast'))


if __name__=='__main__':run()
