"""Bounded nonzero-head parity using saved personal queries and frozen contexts."""
import argparse
import json
import traceback
import numpy as np
import torch

from ..audit import immutable_json
from ..data import digest
from ..priority_capacity.data import head
from ..priority_broad.guard import committed_sources
from ..priority_regularized.safety import dependency_files,reject_optimized_python
from ..order_information.anchored import committed_manifest
from .data import load
from .model import SignedPointCorrection
from .fit import base_fingerprint
from .protocol import ROOT,LOCAL,OUT,ARMS,V23_COMMIT


def select_cases(bank):
    m=bank.metadata;v=bank.broad['values'].numpy()
    conditions=[m['engine']==2,m['engine']==3,m['available'].any((1,2)),~m['available'].any((1,2)),
        v[:,0]<0,(v[:,0]!=v[:,2]),(v[:,5]==1)&~m['history'][:,:,1].any(-1),
        ((np.abs(m['priorities'])>1000000)&m['available']).any((1,2)),bank.fit_mask,~bank.fit_mask]
    cases=[]
    for condition in conditions:
        for i in np.flatnonzero(condition)[:2]:
            if int(i) not in cases:cases.append(int(i))
    for i in np.linspace(0,len(v)-1,64,dtype=int):
        if int(i) not in cases:cases.append(int(i))
        if len(cases)==32:break
    if len(cases)!=32:raise RuntimeError('Case selection did not retain32distinct PRE rows')
    return np.asarray(cases)


def run(arm):
    reject_optimized_python()
    commit,sources=committed_sources(ROOT,dependency_files(ROOT,('tools.action_predictor.relational_priority.roundtrip',)))
    bank=load();cases=select_cases(bank);rows=bank.broad['index'][cases].numpy()
    info_path=OUT/f'{arm}.json';info=json.loads(info_path.read_text())
    checkpoint=LOCAL/f'runs/{arm}/step-2000.pt'
    if digest(checkpoint)!=info['bindings'][str(checkpoint.relative_to(ROOT))]:raise RuntimeError('Selected fixed endpoint changed')
    bindings=dict(bank.bindings)
    for path in (info_path,checkpoint):bindings[str(path.relative_to(ROOT))]=digest(path)
    ready,more=committed_manifest(V23_COMMIT,'tools/action_predictor/experiments/v23/order-cache-ready.json')
    bindings.update(more)
    plan=dict(source_commit=commit,sources=sources,arm=arm,rows=rows.tolist(),local_indices=cases.tolist(),
        selection='First2available PRE cases per engine,otheravailability,negative own,own current/next '
                  'difference,latestargumentoutside16,largeotherpriorities,newfit/held; fill evenly '
                  'spaced to32distinct. No recorded action/integer/forecast selects a case.',
        scope='Rebuild other-unit values/masks/roles directly from preserved personal API records, '
              'keeping original unit order. Reuse validated exact own history and frozen M01 contexts. '
              'This is input-to-head parity, not full raw-observation encoder/filter reconstruction '
              'or production/native serving. No new engine queries.',
        criteria=dict(primary_batch=256,secondary_batch=1,exact_integer_modes=True,
            exact_rebuilt_all_point_features=True,max_abs_raw=2e-5,max_abs_target_NLL=2e-5,
            policy='Preserve original criteria if failed; no tolerance/checkpoint replacement.'),
        checkpoint_sha256=digest(checkpoint),new_fits=0,optimizer_updates=0,reserved_opened=0)
    immutable_json(OUT/f'{arm}-roundtrip-plan.json',plan)
    selected=set(map(int,rows));records={}
    for payload,expected in ready['receipts'].items():
        path=ROOT/'.cambc/action-predictor/v23/games'/payload/'receipt.json'
        saved=json.loads(path.read_text())
        if not selected.intersection(saved['row_indices']):continue
        if digest(path)!=expected:raise RuntimeError('Consumed personal API receipt changed')
        source=path.with_name('raw.jsonl')
        if digest(source)!=saved['raw_sha256']:raise RuntimeError('Consumed personal getter record changed')
        bindings[str(path.relative_to(ROOT))]=expected;bindings[str(source.relative_to(ROOT))]=saved['raw_sha256']
        for line in source.open(encoding='utf-8'):
            value=json.loads(line)
            if value['record']=='order_pre' and value['row'] in selected:
                if value['row'] in records:raise RuntimeError('Duplicate selected personal row')
                records[value['row']]=value
    if set(records)!=selected:raise RuntimeError('Selected personal API rows missing')
    width=max(len(records[int(i)]['others']) for i in rows)
    priorities=np.zeros((32,width,2),np.int64);available=np.zeros((32,width,2),bool);roles=np.full((32,width),-1,np.int8)
    own_agreement=[]
    for i,index in enumerate(rows):
        row=records[int(index)]
        own_agreement.append(row['own']['current']==int(bank.broad['values'][cases[i],0]) and
                             row['own']['scheduled']==int(bank.broad['values'][cases[i],2]))
        for j,unit in enumerate(row['others']):
            if not unit['known']:continue
            if unit['role'] not in ('ally','enemy'):raise RuntimeError('Unexpected personal role')
            roles[i,j]=0 if unit['role']=='ally' else 1
            for t,time in enumerate(('current','scheduled')):
                available[i,j,t]=unit[time+'_available']
                if available[i,j,t]:priorities[i,j,t]=int(unit[time])
    directory=LOCAL/f'roundtrip/{arm}'
    if directory.exists():raise FileExistsError('Preserve attempted nonzero-head parity')
    directory.mkdir(parents=True)
    np.savez_compressed(directory/'inputs.npz',index=rows,priorities=priorities,available=available,roles=roles,
                        values=bank.broad['values'][cases].numpy(),history=bank.metadata['history'][cases],
                        context=bank.broad['context'][cases].numpy(),extra=bank.broad['features'][cases].numpy())
    base,_,_=head();model=SignedPointCorrection(base,bank.metadata['active'])
    model.load_state_dict(torch.load(checkpoint,weights_only=False,map_location='cpu')['state']);model.eval()
    torch.set_num_threads(4)
    padded=np.arange(256)%32;ids=cases[padded]
    args=dict(context=bank.broad['context'][ids],extra=bank.broad['features'][ids],values=bank.broad['values'][ids],
        history=torch.from_numpy(bank.metadata['history'][ids]),priorities=torch.from_numpy(priorities[padded]),
        available=torch.from_numpy(available[padded]),roles=torch.from_numpy(roles[padded]))
    try:
        with torch.inference_mode():
            raw=model(**args)
            reference=model.correct_logits(torch.from_numpy(np.array(bank.raw[ids],copy=True)),bank.evaluation_features(ids))
            points,_=model.components(model.base(args['context'],args['extra']),args['values'])
            rebuilt=model.features(points,args['values'],args['history'],args['priorities'],args['available'],args['roles'])
            mismatch=int((rebuilt!=bank.evaluation_features(ids)).sum())
            singleton=torch.cat([model(**{key:value[i:i+1] for key,value in args.items()}) for i in range(32)])
            mode=model.integer(raw,args['values']);reference_mode=model.integer(reference,args['values'])
            singleton_mode=model.integer(singleton,args['values'][:32])
            # Recorded labels first enter after all forecasts and modes exist.
            target=bank.broad['target'][ids]
            nll=-model.log_mass(raw,target,args['values']);ref_nll=-model.log_mass(reference,target,args['values'])
            singleton_nll=-model.log_mass(singleton,target[:32],args['values'][:32])
        np.savez_compressed(directory/'forecasts.npz',raw=raw.numpy(),reference_raw=reference.numpy(),
            singleton_raw=singleton.numpy(),integer=mode.numpy(),reference_integer=reference_mode.numpy(),
            singleton_integer=singleton_mode.numpy(),nll=nll.numpy(),reference_nll=ref_nll.numpy(),
            singleton_nll=singleton_nll.numpy(),feature_mismatches=mismatch)
        primary=dict(max_abs_raw=float((raw-reference).abs().max()),max_abs_NLL=float((nll-ref_nll).abs().max()),
                     integer_mismatches=int((mode!=reference_mode).sum()))
        secondary=dict(max_abs_raw=float((singleton-reference[:32]).abs().max()),
            max_abs_NLL=float((singleton_nll-ref_nll[:32]).abs().max()),integer_mismatches=int((singleton_mode!=reference_mode[:32]).sum()))
        checks=dict(exact_features=mismatch==0,own_PRE_values_match=all(own_agreement),
            core_unchanged=base_fingerprint(model)==info['core_sha256'],
            primary=primary['max_abs_raw']<=2e-5 and primary['max_abs_NLL']<=2e-5 and primary['integer_mismatches']==0,
            secondary=secondary['max_abs_raw']<=2e-5 and secondary['max_abs_NLL']<=2e-5 and secondary['integer_mismatches']==0)
        for path in directory.iterdir():bindings[str(path.relative_to(ROOT))]=digest(path)
        immutable_json(OUT/f'{arm}-roundtrip.json',dict(source_commit=commit,sources=sources,bindings=bindings,
            plan_sha256=digest(OUT/f'{arm}-roundtrip-plan.json'),cases=32,primary_padded_rows=256,
            primary=primary,secondary=secondary,checks=checks,passed=all(checks.values()),
            scope=plan['scope'],engines={str(i):int((bank.metadata['engine'][cases]==i).sum()) for i in (2,3)},
            new_fits=0,optimizer_updates=0,new_engine_queries=0,reserved_opened=0))
        print(arm,'input-to-head parity',checks,primary,secondary,flush=True)
        if not all(checks.values()):raise RuntimeError('Declared nonzero-head parity criterion failed; outputs preserved')
    except BaseException:
        (directory/'failure.txt').write_text(traceback.format_exc(),encoding='utf-8')
        raise


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('arm',choices=ARMS);run(parser.parse_args().arm)
