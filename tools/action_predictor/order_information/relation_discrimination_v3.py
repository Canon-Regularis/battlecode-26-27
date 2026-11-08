"""No-fit exact scheduling discrimination with matched row-swapped controls."""
from collections import defaultdict
import json

import numpy as np
import torch

from ..audit import immutable_json
from ..data import digest
from ..priority_capacity.data import head
from ..priority_regularized.safety import dependency_files,reject_optimized_python
from ..priority_broad.guard import committed_sources
from .anchored import ROOT,anchored_inputs,committed_manifest,PC02_COMMIT,PC02_COMPLETION
from .data import LOCAL,OUT

RELATIONS=tuple((role,time,sign,offset,changed_only)
    for changed_only in (False,True) for role in (0,1) for time in (0,1)
    for sign in (-1,1) for offset in (-1,0,1))
NAMES=tuple(f"{'changed_' if changed else ''}{('ally','enemy')[role]}_"
    f"{('current','scheduled')[time]}_sign{sign}_offset{offset}"
    for role,time,sign,offset,changed in RELATIONS)


def relation_features(candidate,current,scheduled,available,role):
    """Exact int64 equality; unit pairing retained, IDs never used as inputs."""
    if candidate.dtype!=np.int64 or current.dtype!=np.int64 or scheduled.dtype!=np.int64:
        raise TypeError('Exact integers required')
    result=np.zeros((len(candidate),len(RELATIONS)),bool)
    changed=available[:,:,0]&available[:,:,1]&(current!=scheduled)
    for column,(kind,time,sign,offset,changed_only) in enumerate(RELATIONS):
        value=(current if time==0 else scheduled)*sign+offset
        valid=available[:,:,time]&(role==kind)&(value>=-(2**31))&(value<2**31)
        if changed_only:valid&=changed
        result[:,column]=((candidate[:,None]==value)&valid).any(-1)
    return result


def own_features(candidate,values,history):
    sources=[(values[:,i,None],values[:,i+1,None]==1) for i in (0,2,4)]
    sources.append((history[:,:,0],history[:,:,1]==1))
    return np.column_stack([((candidate[:,None]==sign*x+offset)&valid).any(-1)
                           for x,valid in sources for sign in (-1,1) for offset in (-1,0,1)])


def donors_for(blocks,n,seed):
    rng=np.random.default_rng(seed);donors=np.arange(n)
    for indices in blocks:
        if len(indices)>1:
            order=rng.permutation(indices)
            donors[order]=np.roll(order,int(rng.integers(1,len(order))))
    if not np.array_equal(np.sort(donors),np.arange(n)):raise RuntimeError('Swap is not a permutation')
    return donors


def run():
    reject_optimized_python()
    commit,sources=committed_sources(ROOT,dependency_files(ROOT,(
        'tools.action_predictor.order_information.relation_discrimination_v3',
        'tools.action_predictor.order_information.test_discrimination_v3')))
    fit,_,bindings=anchored_inputs();n=len(fit['target'])
    ready,more=committed_manifest(commit,'tools/action_predictor/experiments/v23/order-cache-ready.json');bindings.update(more)
    receipt,more=committed_manifest(PC02_COMMIT,PC02_COMPLETION);bindings.update(more)
    expected={key.replace('\\','/'):value for key,value in receipt['bindings'].items()}
    def bind(relative):
        path=ROOT/relative
        if digest(path)!=expected[relative]:raise RuntimeError('Independent baseline binding changed: '+relative)
        bindings[relative]=expected[relative];return path
    raw_path=bind('.cambc/action-predictor/v22/runs/PC02/broad_fit-step-0000-raw.npy')
    raw=np.load(raw_path)
    baseline_path=bind('.cambc/action-predictor/v22/runs/PC02/broad_fit-step-0000-predictions.npz')
    with np.load(baseline_path) as z:baseline_integer=z['integer']
    required={'context','features','values','target','index','group'}
    if not required<=fit.keys():raise RuntimeError('Cohort schema missing: '+str(required-fit.keys()))
    if baseline_integer.shape!=(n,):raise RuntimeError('Baseline row count changed')
    pri_ready,more=committed_manifest(PC02_COMMIT,'tools/action_predictor/experiments/v8/priority-data-ready.json')
    bindings.update(more)
    pri_path=ROOT/'.cambc/action-predictor/v8/priority-train.npz'
    if digest(pri_path)!=pri_ready['files']['train']:raise RuntimeError('Causal own-priority history changed')
    bindings[str(pri_path.relative_to(ROOT))]=pri_ready['files']['train']
    plan=dict(source_commit=commit,sources=sources,inputs=bindings,
        question='Do exact per-unit other-priority relations discriminate the recorded integer '
                 'from a competing existing P05 integer beyond own-history relations and frequent-value coincidences?',
        population='All5876broad fitting rows only. No control targets/DEV/reserved evaluation.',
        alternatives='For each row select highest warm-P05-mass distinct integer unequal to recording '
                     'from its existing points and logistic floor/ceil modes; ties smaller integer. '
                     'On warm errors this is the actual warm command. Recorded label selects diagnostic '
                     'pairs only; no runtime router or negative-intent label is manufactured.',
        statistics='48fixed boolean features: ally/enemy xcurrent/scheduled xsign-/+ xoffset-1/0/+1, '
                   'with/without requiring that SAME unit current!=scheduled and both available. '
                   'Exact int64 arithmetic. Own controls apply same transforms to current/scheduled/'
                   'latest argument/any of16previous argument slots with masks.',
        primary='Recorded-minus-alternative incidence of ANY24unguarded other relations; '
                'compare actual evidence against mean64availability-matched row permutations. '
                'Also report all48features without selecting a best relation.',
        swap='Within group xengine xsorted per-unit(role,current_available,scheduled_available) '
             'signature, random-permutation cyclic derangement for nonsingletons; singleton rows '
             'remain explicit. Seeds20261124..20261187. Permute complete current/scheduled unit '
             'pairs jointly, preserving raw value marginals and per-row availability/counts. '
             'Own history, targets and alternatives stay fixed. Diagnostic corruption only, '
             'never inference or a claim of exchangeable temporal data.',
        strata=['all','warm_error','neither_target_nor_alternative_matches_own_simple_relations',
                'swappable_with_available_other_information'],
        uncertainty='2000paired whole-group resamples seed20261106 of actual-minus-mean-swapped '
                    'contrasts. Exploratory in-sample TRAIN diagnostic; not untouched policy accuracy '
                    'or multiplicity-adjusted per-feature testing. Report whole-group counts.',
        allocation='Evidence for this named relation channel requires positive primary all-row '
                   'actual-minus-swap contrast with positive paired interval and positive net '
                   'contrast in a majority of informative groups, plus positive point contrast '
                   'in the own-neither stratum. This is an exploratory information gate, not '
                   'an original success target or proof of trainability. No rule/variant selected.',
        new_fits=0,new_engine_queries=0,reserved_opened=0)
    immutable_json(OUT/'OD03-plan.json',plan)
    torch.set_num_threads(4)
    model,_,_=head()
    # Explicitly bind warm head/vocabulary consumed by head().
    bind('.cambc/action-predictor/v8/runs/P05/model.pt')
    for relative in ('tools/action_predictor/experiments/v8/P05.json',
                     'tools/action_predictor/experiments/v8/priority-residual-modes-vocabulary.json'):
        _,more=committed_manifest(PC02_COMMIT,relative)
        bindings.update(more)
    directory=LOCAL/'relation-discrimination-v3'
    if directory.exists():raise FileExistsError('Preserve attempted diagnostic')
    directory.mkdir(parents=True)
    target=fit['target'].numpy();alternative=np.empty(n,np.int64);warm=np.empty(n,np.int64)
    with torch.inference_mode():
        for start in range(0,n,256):
            stop=min(n,start+256);r=torch.from_numpy(raw[start:stop])
            candidates,mass=model.candidate_log_masses(r,fit['values'][start:stop])
            warm[start:stop]=candidates.gather(1,mass.argmax(-1)[:,None])[:,0].numpy()
            mass=mass.masked_fill(candidates==fit['target'][start:stop,None],-torch.inf)
            alternative[start:stop]=candidates.gather(1,mass.argmax(-1)[:,None])[:,0].numpy()
    np.savez_compressed(directory/'candidate-pairs.npz',target=target,alternative=alternative,warm_mode=warm)
    if (alternative==target).any():raise RuntimeError('Recorded integer retained as alternative')
    np.testing.assert_array_equal(warm,baseline_integer)
    records=[None]*n;engines=[None]*n;at_by_id={int(v):i for i,v in enumerate(fit['index'].tolist())}
    for payload,expected_hash in ready['receipts'].items():
        path=LOCAL/'games'/payload/'receipt.json'
        if digest(path)!=expected_hash:raise RuntimeError('Recorded getter receipt changed')
        saved=json.loads(path.read_text());source=path.with_name('raw.jsonl')
        if digest(source)!=saved['raw_sha256']:raise RuntimeError('Recorded getter output changed')
        bindings[str(path.relative_to(ROOT))]=expected_hash;bindings[str(source.relative_to(ROOT))]=saved['raw_sha256']
        for line in source.open(encoding='utf-8'):
            row=json.loads(line)
            if row['record']!='order_pre' or row['row'] not in at_by_id:continue
            i=at_by_id[row['row']]
            if records[i] is not None:raise RuntimeError('Duplicate fitted query row')
            records[i]=sorted([u for u in row['others'] if u['known']],key=lambda u:(u['role'],u['current_available'],u['scheduled_available']))
            engines[i]=saved['engine']
    if any(row is None for row in records):raise RuntimeError('Missing fitted query row')
    width=max(map(len,records));current=np.zeros((n,width),np.int64);scheduled=current.copy()
    role=np.full((n,width),-1,np.int8);available=np.zeros((n,width,2),bool);blocks=defaultdict(list)
    group=fit['group'].numpy()
    for i,record in enumerate(records):
        signature=[]
        for j,unit in enumerate(record):
            role[i,j]=0 if unit['role']=='ally' else 1
            for t,time in enumerate(('current','scheduled')):
                available[i,j,t]=unit[time+'_available']
                if available[i,j,t]:(current if t==0 else scheduled)[i,j]=int(unit[time])
            signature.append((int(role[i,j]),*map(bool,available[i,j])))
        blocks[(int(group[i]),engines[i],tuple(signature))].append(i)
    blocks=[np.asarray(value) for value in blocks.values()]
    swappable=np.zeros(n,bool)
    for indices in blocks:
        if len(indices)>1:swappable[indices]=True
    with np.load(pri_path) as z:
        values=z['values'][fit['index'].numpy()];history=z['history'][fit['index'].numpy()]
    np.testing.assert_array_equal(values,fit['values'].numpy())
    own_target=own_features(target,values,history);own_alternative=own_features(alternative,values,history)
    actual_target=relation_features(target,current,scheduled,available,role)
    actual_alternative=relation_features(alternative,current,scheduled,available,role)
    def contrasts(a,b):
        return np.column_stack((a[:,:24].any(-1).astype(np.float64)-b[:,:24].any(-1),
                                a.astype(np.float64)-b))
    actual=contrasts(actual_target,actual_alternative)
    swapped=np.empty((64,n,49),np.float32);donor_bank=np.empty((64,n),np.int32);effective=[]
    for repeat in range(64):
        donor=donors_for(blocks,n,20261124+repeat);donor_bank[repeat]=donor
        np.testing.assert_array_equal(role[donor],role)
        np.testing.assert_array_equal(available[donor],available)
        if (donor[swappable]==np.flatnonzero(swappable)).any():raise RuntimeError('Swappable row kept itself')
        different=((current[donor]!=current)|(scheduled[donor]!=scheduled)).any(-1)
        effective.append(int(different.sum()))
        swapped[repeat]=contrasts(relation_features(target,current[donor],scheduled[donor],available,role),
                                  relation_features(alternative,current[donor],scheduled[donor],available,role))
    archive=directory/'raw-contrasts.npz'
    np.savez_compressed(archive,index=fit['index'].numpy(),target=target,alternative=alternative,warm_mode=warm,
        actual=actual,swapped=swapped,donors=donor_bank,own_target=own_target,own_alternative=own_alternative,
        actual_target_features=actual_target,actual_alternative_features=actual_alternative,
        swappable=swappable,any_other_available=available.any((1,2)),group=group)
    # Preserve raw outcomes before any reporting/uncertainty operation.
    bindings[str(archive.relative_to(ROOT))]=digest(archive)
    pair_archive=directory/'candidate-pairs.npz'
    bindings[str(pair_archive.relative_to(ROOT))]=digest(pair_archive)
    means=swapped.mean(0,dtype=np.float64);delta=actual-means
    strata=dict(all=np.ones(n,bool),warm_error=warm!=target,
        neither_target_nor_alternative_matches_own_simple_relations=~own_target.any(-1)&~own_alternative.any(-1),
        swappable_with_available_other_information=swappable&available.any((1,2)))
    results={}
    names=('ANY_unguarded_other_relation',*NAMES)
    for name,mask in strata.items():
        if not mask.any():results[name]=dict(rows=0,features=None);continue
        groups=np.unique(group[mask]);support=np.array([(mask&(group==g)).sum() for g in groups])
        sums=np.stack([delta[mask&(group==g)].sum(0) for g in groups])
        rng=np.random.default_rng(20261106)
        draws=np.stack([np.bincount(rng.integers(len(groups),size=len(groups)),minlength=len(groups)) for _ in range(2000)])
        interval=np.quantile((draws@sums)/(draws@support)[:,None],[.025,.975],axis=0)
        results[name]=dict(rows=int(mask.sum()),groups=len(groups),features={})
        for col,label in enumerate(names):
            d=delta[mask,col]
            group_mean=sums[:,col]/support
            results[name]['features'][label]=dict(actual_pair_contrast=float(actual[mask,col].mean()),
                mean_swapped_pair_contrast=float(means[mask,col].mean()),incremental_contrast=float(d.mean()),
                paired_whole_group_interval=interval[:,col].tolist(),positive_groups=int((group_mean>0).sum()),
                negative_groups=int((group_mean<0).sum()),zero_groups=int((group_mean==0).sum()),
                group_incremental_contrast=dict(zip(map(str,groups),map(float,group_mean))))
    primary=results['all']['features'][names[0]]
    own_neither=results['neither_target_nor_alternative_matches_own_simple_relations']
    own_contrast=own_neither['features'][names[0]]['incremental_contrast'] if own_neither['rows'] else None
    informative=primary['positive_groups']+primary['negative_groups']
    gate=dict(positive_primary_interval=primary['paired_whole_group_interval'][0]>0,
        majority_informative_groups_positive=primary['positive_groups']>informative/2,
        own_neither_incremental_positive=own_contrast is not None and own_contrast>0)
    immutable_json(OUT/'OD03.json',dict(results=results,inputs_and_outputs=bindings,sources=sources,
        source_commit=commit,plan_sha256=digest(OUT/'OD03-plan.json'),primary_gate=gate,
        exploratory_information_gate_passed=all(gate.values()),
        swapping=dict(repeats=64,blocks=len(blocks),singleton_rows=int((~swappable).sum()),
            swappable_rows=int(swappable.sum()),effective_changed_rows_range=[min(effective),max(effective)],
            availability_counts_and_value_marginals_preserved=True),
        own_relation_pair_contrast=(own_target.any(-1).astype(float)-own_alternative.any(-1)).mean().item(),
        new_fits=0,reserved_opened=0,policy_replaced=False))
    print('OD03 primary',primary,'gate',gate,flush=True)


if __name__=='__main__':run()
