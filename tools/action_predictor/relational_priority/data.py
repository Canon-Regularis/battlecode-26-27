"""Build exact all-point features without recorded-answer routing or new queries."""
from collections import defaultdict
import json
import subprocess
import sys
import traceback

import numpy as np
import torch

from ..audit import immutable_json
from ..data import digest
from ..priority_capacity.data import head
from ..priority_regularized.safety import reject_optimized_python
from ..priority_broad.guard import checked_execution
from ..order_information.anchored import anchored_inputs,committed_manifest,PC02_COMMIT,PC02_COMPLETION
from ..order_information.relation_discrimination_v3 import donors_for
from .model import SignedPointCorrection,own_features,other_features,NAMES
from .protocol import ROOT,LOCAL,OUT,V23_COMMIT,SWAP_SEED,fold,freeze,source_gate

TEST_COMMAND=[sys.executable,'-m','unittest',
    'tools.action_predictor.relational_priority.test_model',
    'tools.action_predictor.relational_priority.test_data']


class FeatureBank:
    def __init__(self,own,real,shuffled,fit_mask):
        self.own,self.real,self.shuffled=own,real,shuffled
        self.fit_mask=np.asarray(fit_mask,dtype=bool)

    def evaluation_features(self,ids):
        return torch.from_numpy(np.concatenate((self.own[ids],self.real[ids]),axis=-1))

    def training_features(self,ids,arm):
        if not self.fit_mask[np.asarray(ids)].all():raise RuntimeError('Correction-held row requested for optimization')
        if arm not in ('RC00','RC01'):raise ValueError('Unknown registered arm')
        other=self.shuffled if arm=='RC00' else self.real
        return torch.from_numpy(np.concatenate((self.own[ids],other[ids]),axis=-1))


def original_inputs():
    broad,_,bindings=anchored_inputs()
    required={'context','features','values','target','index','group'}
    if not required<=broad.keys():raise RuntimeError('Broad cohort schema missing: '+str(required-broad.keys()))
    receipt,more=committed_manifest(PC02_COMMIT,PC02_COMPLETION);bindings.update(more)
    expected={name.replace('\\','/'):value for name,value in receipt['bindings'].items()}
    paths={}
    for key,relative in (
        ('raw','.cambc/action-predictor/v22/runs/PC02/broad_fit-step-0000-raw.npy'),
        ('baseline','.cambc/action-predictor/v22/runs/PC02/broad_fit-step-0000-predictions.npz'),
        ('checkpoint','.cambc/action-predictor/v8/runs/P05/model.pt')):
        path=ROOT/relative
        if digest(path)!=expected[relative]:raise RuntimeError('Bound warm input changed: '+relative)
        bindings[relative]=expected[relative];paths[key]=path
    for relative in ('tools/action_predictor/experiments/v8/P05.json',
                     'tools/action_predictor/experiments/v8/priority-residual-modes-vocabulary.json'):
        _,more=committed_manifest(PC02_COMMIT,relative);bindings.update(more)
    with np.load(paths['baseline']) as z:
        if not {'integer','nll','rank','credit'}<=set(z.files):raise RuntimeError('Warm forecast schema changed')
        baseline={key:z[key] for key in z.files}
    if baseline['integer'].shape!=(len(broad['index']),):raise RuntimeError('Warm row count changed')
    raw=np.load(paths['raw'],mmap_mode='r')
    return broad,raw,baseline,bindings


def prepare(tests):
    reject_optimized_python()
    source_gate()
    if len(tests)!=1 or tests[0]['returncode']!=0 or tests[0]['command']!=TEST_COMMAND:
        raise RuntimeError('CACHE_PREREQUISITES_FAILED')
    broad,raw,baseline,bindings=original_inputs()
    ready,more=committed_manifest(V23_COMMIT,'tools/action_predictor/experiments/v23/order-cache-ready.json')
    bindings.update(more)
    pri,more=committed_manifest(PC02_COMMIT,'tools/action_predictor/experiments/v8/priority-data-ready.json')
    bindings.update(more)
    path=ROOT/'.cambc/action-predictor/v8/priority-train.npz'
    if digest(path)!=pri['files']['train']:raise RuntimeError('Own causal history changed')
    bindings[str(path.relative_to(ROOT))]=pri['files']['train']
    with np.load(path) as z:
        history=np.array(z['history'][broad['index'].numpy()]);values=np.array(z['values'][broad['index'].numpy()])
    np.testing.assert_array_equal(values,broad['values'].numpy())
    n=len(values);records=[None]*n;engines=np.zeros(n,np.int8)
    at={int(index):i for i,index in enumerate(broad['index'].tolist())}
    for payload,expected in ready['receipts'].items():
        receipt_path=ROOT/'.cambc/action-predictor/v23/games'/payload/'receipt.json'
        if digest(receipt_path)!=expected:raise RuntimeError('Saved API receipt changed')
        saved=json.loads(receipt_path.read_text());source=receipt_path.with_name('raw.jsonl')
        if digest(source)!=saved['raw_sha256']:raise RuntimeError('Saved personal getter record changed')
        bindings[str(receipt_path.relative_to(ROOT))]=expected
        bindings[str(source.relative_to(ROOT))]=saved['raw_sha256']
        for line in source.open(encoding='utf-8'):
            row=json.loads(line)
            if row['record']!='order_pre' or row['row'] not in at:continue
            i=at[row['row']]
            if records[i] is not None:raise RuntimeError('Duplicate broad query row')
            units=[u for u in row['others'] if u['known']]
            for u in units:
                if u['role'] not in ('ally','enemy'):raise RuntimeError('Unknown personally available role')
                for time in ('current','scheduled'):
                    if not isinstance(u[time+'_available'],bool):raise RuntimeError('Non-Boolean API availability')
                    if not u[time+'_available'] and u[time] is not None:raise RuntimeError('Unavailable raw priority retained')
            records[i]=sorted(units,key=lambda u:(u['role'],u['current_available'],u['scheduled_available']))
            engines[i]=2 if saved['engine']=='v2_0_0' else 3 if saved['engine']=='v3_0_0' else 0
    if any(row is None for row in records) or (engines==0).any():raise RuntimeError('Missing/unsupported eligible personal evidence')
    width=max(map(len,records));priorities=np.zeros((n,width,2),np.int64)
    available=np.zeros((n,width,2),bool);roles=np.full((n,width),-1,np.int8)
    blocks=defaultdict(list);groups=broad['group'].numpy()
    for i,units in enumerate(records):
        signature=[]
        for j,u in enumerate(units):
            roles[i,j]=0 if u['role']=='ally' else 1
            for t,time in enumerate(('current','scheduled')):
                available[i,j,t]=u[time+'_available']
                if available[i,j,t]:priorities[i,j,t]=int(u[time])
            signature.append((int(roles[i,j]),*map(bool,available[i,j])))
        blocks[(int(groups[i]),int(engines[i]),tuple(signature))].append(i)
    donors=donors_for([np.asarray(indices) for indices in blocks.values()],n,SWAP_SEED)
    np.testing.assert_array_equal(roles[donors],roles)
    np.testing.assert_array_equal(available[donors],available)
    fit_mask,held=fold(groups)
    np.testing.assert_array_equal(fit_mask[donors],fit_mask)
    plan=freeze()  # Frozen field definitions/fold/optimization precede feature assessment.
    directory=LOCAL/'data'
    if directory.exists():raise FileExistsError('Preserve attempted cache; do not restart automatically')
    directory.mkdir(parents=True)
    torch.set_num_threads(4)
    base,_,_=head();base.eval().requires_grad_(False)
    points_count=len(base.absolute)+len(base.residual)
    if raw.shape!=(n,points_count+3):raise RuntimeError('Warm raw interface changed')
    arrays={
        'own':np.lib.format.open_memmap(directory/'own.npy',mode='w+',dtype=np.bool_,shape=(n,points_count,24)),
        'other-real':np.lib.format.open_memmap(directory/'other-real.npy',mode='w+',dtype=np.bool_,shape=(n,points_count,48)),
        'other-shuffled':np.lib.format.open_memmap(directory/'other-shuffled.npy',mode='w+',dtype=np.bool_,shape=(n,points_count,48)),
        'points':np.lib.format.open_memmap(directory/'points.npy',mode='w+',dtype=np.int64,shape=(n,points_count))}
    real_support=np.zeros(72,bool);control_support=np.zeros(72,bool)
    try:
        with torch.inference_mode():
            for start in range(0,n,256):
                stop=min(start+256,n);sl=slice(start,stop)
                output=base(broad['context'][sl],broad['features'][sl])
                np.testing.assert_array_equal(output.numpy(),raw[sl])
                points,_=base.components(output,broad['values'][sl])
                own=own_features(points,broad['values'][sl],torch.from_numpy(history[sl]))
                real=other_features(points,torch.from_numpy(priorities[sl]),torch.from_numpy(available[sl]),torch.from_numpy(roles[sl]))
                swap=other_features(points,torch.from_numpy(priorities[donors[sl]]),torch.from_numpy(available[sl]),torch.from_numpy(roles[sl]))
                valid=torch.cat((torch.ones((stop-start,len(base.absolute)),dtype=torch.bool),
                    broad['values'][sl,5,None].bool().expand(-1,len(base.residual))),-1)
                own&=valid[:,:,None];real&=valid[:,:,None];swap&=valid[:,:,None]
                for name,value in (('own',own),('other-real',real),('other-shuffled',swap),('points',points)):
                    arrays[name][sl]=value.numpy()
                selected=fit_mask[sl]
                if selected.any():
                    own_seen=own[selected].any((0,1)).numpy()
                    real_support|=np.r_[own_seen,real[selected].any((0,1)).numpy()]
                    control_support|=np.r_[own_seen,swap[selected].any((0,1)).numpy()]
                if stop==n or stop%2048==0:print('RC all-point cache',stop,'/',n,flush=True)
        for value in arrays.values():value.flush()
        arrays.clear()
        active=real_support&control_support
        if not active.any():raise RuntimeError('No common active relations')
        data=dict(index=broad['index'].numpy(),group=groups,fit_mask=fit_mask,held_groups=held,donors=donors,
                  active=active,priorities=priorities,available=available,roles=roles,history=history,engine=engines,
                  real_support=real_support,control_support=control_support)
        np.savez_compressed(directory/'metadata.npz',**data)
        files={str(path.relative_to(ROOT)):digest(path) for path in directory.iterdir()}
        immutable_json(OUT/'RC-data-ready.json',dict(protocol_sha256=digest(OUT/'RC-plan.json'),
            producer_commit=plan['source_commit'],producer_sources=plan['sources'],inputs=bindings,files=files,
            rows=n,points=points_count,feature_names=list(NAMES),trainable_weights=int(active.sum()),
            inactive_features=[NAMES[i] for i in np.flatnonzero(~active)],
            fit_rows=int(fit_mask.sum()),held_rows=int((~fit_mask).sum()),
            effective_corrupted_rows=int(((priorities[donors]!=priorities)&available).any((1,2)).sum()),
            tests=tests,labels_not_used_in_features_or_split=True,new_fits=0,reserved_opened=0))
        print('RC feature cache ready:',n,'rows,',int(fit_mask.sum()),'newfit,',int((~fit_mask).sum()),
              'newheld,',int(active.sum()),'common trainable weights',flush=True)
    except BaseException:
        (directory/'failure.txt').write_text(traceback.format_exc(),encoding='utf-8')
        raise


def load():
    reject_optimized_python()
    commit=subprocess.run(['git','rev-parse','HEAD'],cwd=ROOT,check=True,capture_output=True,text=True).stdout.strip()
    plan,bindings=committed_manifest(commit,'tools/action_predictor/experiments/v24/RC-plan.json')
    ready,more=committed_manifest(commit,'tools/action_predictor/experiments/v24/RC-data-ready.json');bindings.update(more)
    if digest(OUT/'RC-plan.json')!=ready['protocol_sha256']:raise RuntimeError('RC protocol changed')
    for name,value in ready['producer_sources'].items():
        if digest(ROOT/name)!=value:raise RuntimeError('RC producer source changed: '+name)
        bindings[name]=value
    for name,value in ready['files'].items():
        if digest(ROOT/name)!=value:raise RuntimeError('RC cache changed: '+name)
        bindings[name]=value
    broad,raw,baseline,more=original_inputs();bindings.update(more)
    with np.load(LOCAL/'data/metadata.npz') as z:metadata={key:z[key] for key in z.files}
    np.testing.assert_array_equal(metadata['index'],broad['index'].numpy())
    np.testing.assert_array_equal(metadata['group'],broad['group'].numpy())
    mask,held=fold(metadata['group'])
    np.testing.assert_array_equal(mask,metadata['fit_mask']);np.testing.assert_array_equal(held,metadata['held_groups'])
    np.testing.assert_array_equal(mask[metadata['donors']],mask)
    if ready['feature_names']!=list(NAMES) or len(mask)!=5876 or ready['trainable_weights']!=int(metadata['active'].sum()):
        raise RuntimeError('RC schema/population changed')
    bank=FeatureBank(*(np.load(LOCAL/f'data/{name}.npy',mmap_mode='r') for name in ('own','other-real','other-shuffled')),mask)
    for value,width in ((bank.own,24),(bank.real,48),(bank.shuffled,48)):
        if value.dtype!=np.bool_ or value.shape!=(5876,ready['points'],width):raise RuntimeError('RC feature shape/dtype changed')
    bank.broad,bank.raw,bank.baseline,bank.metadata,bank.bindings,bank.plan,bank.ready=broad,raw,baseline,metadata,bindings,plan,ready
    bank.fit_ids=np.flatnonzero(mask);bank.held_ids=np.flatnonzero(~mask)
    return bank


def main():
    reject_optimized_python()
    source_gate()
    checked_execution([TEST_COMMAND],prepare,ROOT)


if __name__=='__main__':main()
