"""TRAIN-only exact-integer relation diagnostic; no fitting or policy routing."""
import json
from pathlib import Path

import numpy as np
import torch

from ..audit import immutable_json
from ..data import digest
from ..priority_capacity.data import head
from ..priority_regularized.safety import dependency_files,reject_optimized_python
from ..priority_broad.guard import committed_sources
from .data import ROOT,OUT,LOCAL
from .anchored import anchored_inputs,committed_manifest

OFFSETS=(-1,0,1)
SIGNS=(-1,1)


def proposals(row,role,time,sign,offset):
    return {sign*int(unit[time])+offset for unit in row['others']
            if unit['known'] and unit['role']==role and unit[time+'_available']
            and -(2**31)<=sign*int(unit[time])+offset<2**31}


def run():
    reject_optimized_python()
    commit,sources=committed_sources(ROOT,dependency_files(ROOT,(
        'tools.action_predictor.order_information.relations',)))
    fit,_,bindings=anchored_inputs()
    ready,more=committed_manifest(commit,'tools/action_predictor/experiments/v23/order-cache-ready.json')
    bindings.update(more)
    ids=fit['index'].numpy();target=fit['target'].numpy()
    at_by_id={int(index):at for at,index in enumerate(ids)}
    plan=dict(source_commit=commit,sources=sources,inputs=bindings,
        purpose='Diagnose whether simple exact relations to newly verified personally available '
                'other priorities propose recorded fitting integers omitted from existing P05 points. '
                'Not a fitted model or deployable command library.',
        population='Only5876broad fitting rows. No control targets or DEV outcomes assessed.',
        prespecified_relations='For each available ally/enemy current/scheduled value: sign -1/+1 '
                               'and offset -1/0/+1, signedint32 results only; union duplicates. '
                               'Also compare own current/scheduled under the same transforms.',
        interpretation='TRAIN oracle diagnostics, not achieved accuracy, Fish intent or evidence '
                       'for expanding support. No best rule chosen or routed with recorded labels. '
                       'A relation may match accidentally or on outputs already in P05 vocabulary.',
        new_fits=0,new_engine_queries=0,reserved_opened=0)
    immutable_json(OUT/'OD00-plan.json',plan)
    model,_,_=head()
    with torch.no_grad():
        raw=torch.zeros((len(target),model.linear.out_features))
        points,_=model.components(raw,fit['values'])
        valid=torch.cat((torch.ones((len(target),len(model.absolute)),dtype=torch.bool),
                         fit['values'][:,5,None].bool().expand(-1,len(model.residual))),-1)
        p05=((points==fit['target'][:,None])&valid).any(-1).numpy()
    names=[(role,time,sign,offset) for role in ('ally','enemy') for time in ('current','scheduled')
           for sign in SIGNS for offset in OFFSETS]
    matches=np.zeros((len(target),len(names)),bool)
    own=np.zeros((len(target),2*len(SIGNS)*len(OFFSETS)),bool)
    counts=np.zeros(len(target),np.int32);seen=np.zeros(len(target),bool)
    raw_bindings={}
    for payload,expected in ready['receipts'].items():
        path=LOCAL/'games'/payload/'receipt.json'
        if digest(path)!=expected:raise RuntimeError('Raw getter receipt changed')
        receipt=json.loads(path.read_text());source=path.with_name('raw.jsonl')
        if digest(source)!=receipt['raw_sha256']:raise RuntimeError('Saved getter record changed')
        raw_bindings[str(path.relative_to(ROOT))]=expected
        raw_bindings[str(source.relative_to(ROOT))]=receipt['raw_sha256']
        for line in source.open(encoding='utf-8'):
            row=json.loads(line)
            if row['record']!='order_pre' or row['row'] not in at_by_id:continue
            at=at_by_id[row['row']]
            if seen[at]:raise RuntimeError('Duplicate fitted raw row')
            seen[at]=True;union=set()
            for column,(role,time,sign,offset) in enumerate(names):
                values=proposals(row,role,time,sign,offset)
                matches[at,column]=int(target[at]) in values;union.update(values)
            counts[at]=len(union)
            for column,(time,sign,offset) in enumerate((time,sign,offset) for time in ('current','scheduled')
                                                      for sign in SIGNS for offset in OFFSETS):
                if row['own'][time+'_available']:
                    own[at,column]=int(target[at])==sign*int(row['own'][time])+offset
    if not seen.all():raise RuntimeError('Missing fitted raw rows')
    any_other=matches.any(-1);any_own=own.any(-1)
    archive=LOCAL/'OD00-relations.npz'
    if archive.exists():raise FileExistsError(archive)
    np.savez_compressed(archive,index=ids,p05_point_contains_target=p05,other_matches=matches,
                        own_matches=own,distinct_other_proposals=counts)
    result=dict(rows=len(target),existing_P05_point_support=int(p05.sum()),
        other_relation_union_matches=int(any_other.sum()),own_relation_union_matches=int(any_own.sum()),
        other_additional_to_P05=int((any_other&~p05).sum()),
        other_additional_to_own=int((any_other&~any_own).sum()),
        all_other_matching_rows_also_own=int((any_other&any_own).sum()),
        relation_counts=[dict(role=role,time=time,sign=sign,offset=offset,matches=int(matches[:,column].sum()))
                         for column,(role,time,sign,offset) in enumerate(names)],
        distinct_proposal_distribution={str(int(count)):int((counts==count).sum()) for count in np.unique(counts)},
        limitations=plan['interpretation'],bindings={**bindings,**raw_bindings,
            str(archive.relative_to(ROOT)):digest(archive),str((OUT/'OD00-plan.json').relative_to(ROOT)):digest(OUT/'OD00-plan.json')},
        source_commit=commit,sources=sources,new_fits=0,reserved_opened=0)
    immutable_json(OUT/'OD00.json',result)
    print({key:value for key,value in result.items() if key in ('rows','existing_P05_point_support',
        'other_relation_union_matches','own_relation_union_matches','other_additional_to_P05','other_additional_to_own')},flush=True)


if __name__=='__main__':run()
