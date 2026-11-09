"""Actor trajectories with explicit real root gaps; no replay downloads/decoding."""
import argparse,json,hashlib
from pathlib import Path
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
import numpy as np
from ..consistent_data import ROOT,BASE,JOBS
from ..rich_data import read_turns
from ..audit import cursor,immutable_json
from ..data import digest
from .. import reliable_train as rt

WORK=ROOT/'.cambc/action-predictor/v16';REPORT=ROOT/'tools/action_predictor/experiments/v16'
ROOT_NAMES={4:'move',5:'attack',6:'cast',8:'end',9:'priority',11:'recall',12:'submit',13:'shop',14:'ward',16:'cancel',20:'altar',21:'teleport',23:'blocked'}

def plan():
    REPORT.mkdir(parents=True,exist_ok=True);WORK.mkdir(parents=True,exist_ok=True)
    value=dict(id='V16-learned-sequential-policy',direction='Learn strategic latent objective persistence AND goal-conditioned action/execution from demonstrations. No manually scored objectives, banking thresholds, greedy strategy or reconstructed Fish intent labels.',
      initial_budget=dict(fits=2,L00='matched learned latent-goal policy with belief reset at each available decision',L01='forward persistent latent-goal filter, learned retention and goal proposal',latent_goals=4,seed=20261114,extra_seeds=0),
      execution='All action choices and spatial heads trainable, warm-start M01 components; retained G00/B00/S00/X00 comparisons. P05 integer conditional remains reusable initial component with trainable priority type choice. Actor predicts using only past state and commits own actual action/result AFTER execution. No Fish future actions or backward-smoothed goals at inference.',
      sequence='All original433071TRAIN/14439DEV rows retain identity. Stream by eligible game and actor in actual event order. Full earlier own-root index determines ordinals, gaps and intervening action counts, EXCLUDING current action and previous action already consumed by posterior. Last16 actual-action/observation windows remain bounded inputs with explicit availability. Sampled targets are never declared adjacent. Unknown prefix memory explicit; latent state not claimed lossless history.',
      goal_learning='Four learned latent objective embeddings, learned current goal proposal and root-gap-aware retention. No named true-intent labels; forward marginal command/sequence likelihood trains all equivalent latent explanations. Latent states may represent tactical stages rather than strategic objectives; persistence/behavior must be measured, not assumed. No current/future label in goal proposal.',
      evaluation='Frozen original split/groups/denominators, wholeDEVjointNLL improvement.0001/patience6/max35. Exact complete commands, typePRF/confusion/FP, alltruefamily/typed parameters, continuation/change/blocked, fullsequence likelihood and persistence diagnostics; natural/augTRAIN and paired2000wholeDEVgroups seed20261106. No checkpoint selection by inferred goal stories.',
      runtime_delivery='Stateful policy actor plus SDK command dispatcher are required, followed by native/no-Torch export and a live-observation adapter. Cached scoring alone is not a bot. Current SDK4 differs from historical2/3: explicit version capability contract; no unverified equivalence. Original purchases and ambiguous entity targets remain unsupported until learned/recovered, never hand-filled. Draft policy not part of current command benchmark, so full-bot completeness cannot yet be claimed.',
      safety='Both75newval/75finaltest sealed. Only eligible470TRAIN/25originalDEV. No matches/proposed-action simulations/downloads/deployments; no existing playingbot changes. New isolated runtime components only. PR11DRAFT/open/unmerged/noautomerge/queue. Shops43 strictunassessed, missingarglikelihood absent; sparsecategories uncertified. Original90%eachsupportedcategory/macro/move/NLL/3seed goals unchanged.',
      continuation='One fit per invocation and fresh requestedGPT6.1Solxhigh review after EACH. Run the2matched fits only after causal/normalization/probability/runtime contract checks. No more expert architectures or repeats automatically; no claim learned internal Fish goals or closed-loop strength from replay agreement.',
      prior='V15S00/X00 valid negatives preserved. V14ward study user-discontinued3/4,T01unrun. Old hand-designed GoalMemory scoring is NOT the learned strategic policy.',
      sources={'sequence_data.py':digest(__file__)},jobs_sha256=digest(JOBS),new_fits=0,reserved_opened=0)
    immutable_json(REPORT/'sequence-plan.json',value);return value

def game(job):
    raw=job['record']['raw_sha256'];directory=WORK/'games'/raw;directory.mkdir(parents=True,exist_ok=True);out=directory/'sequence.npz';receipt=directory/'sequence.json'
    if receipt.exists():
        r=json.loads(receipt.read_text());assert r['source_sha256']==digest(__file__) and digest(out)==r['arrays_sha256'];return r
    source=Path(job['manifest']['source'])/'extracted'/raw;index=source/'index.jsonl';body=index.read_bytes();h=hashlib.sha256(body).hexdigest();expected=json.loads((source/'receipt.json').read_text())['files']['index.jsonl'];assert h==expected
    roots=defaultdict(list)
    for line in body.splitlines():
        t=json.loads(line)
        if t.get('record')!='turn':continue
        for root in t['roots']:
            step=root['header']['step'];name=ROOT_NAMES.get(step['kind'],'<unknown>')
            if name=='cast':name=f'cast_{step["abilitySlot"]}'
            roots[t['actor']].append((cursor(root['event']),cursor(root['pre']),t['round'],rt.LABELS.index(name) if name in rt.LABELS else 0))
    selected=defaultdict(list);i=0
    for t in read_turns(job['manifest'],job['record']):
        for d in t['decisions']:
            selected[t['actor']].append((cursor(d['event_cursor']),cursor(d['pre_cursor']),t['round'],job['offset']+i));i+=1
    assert i==job['rows'];orders=[];gaps=[];offsets=[0];counts=dict(selected_rows=i,actual_own_roots=0,nonadjacent_selected=0,unavailable_prefix_streams=0)
    for actor,targets in sorted(selected.items()):
        actual=sorted(roots[actor]);assert len({x[0] for x in actual})==len(actual);lookup={r[0]:k for k,r in enumerate(actual)};prefix=np.zeros((len(actual)+1,15),np.int32)
        for k,r in enumerate(actual):prefix[k+1]=prefix[k];prefix[k+1,r[3]]+=1
        previous=None;last_round=0
        for event,pre,round_number,row in sorted(targets):
            ordinal=lookup[event];r=actual[ordinal];assert r[:3]==(event,pre,round_number) and pre<event
            if previous is None:
                delta=ordinal+1;intervening=prefix[ordinal];elapsed=0;initial=1;counts['unavailable_prefix_streams']+=int(ordinal>0)
            else:
                assert previous<ordinal and actual[previous][0]<=pre
                delta=ordinal-previous;intervening=prefix[ordinal]-prefix[previous+1];elapsed=round_number-last_round;initial=0;assert elapsed>=0;counts['nonadjacent_selected']+=int(delta>1)
            # Only past root counts; the answer at `ordinal` is not included.
            assert intervening.sum()==(ordinal if previous is None else delta-1)
            gaps.append(np.r_[np.log1p(delta)/8,np.log1p(elapsed)/8,initial,np.log1p(intervening)/8].astype(np.float32));orders.append(row);previous=ordinal;last_round=round_number
        offsets.append(len(orders));counts['actual_own_roots']+=len(actual)
    assert len(orders)==i;np.savez_compressed(out,order=np.asarray(orders,np.int32),offsets=np.asarray(offsets,np.int64),gap=np.stack(gaps))
    r=dict(raw=raw,split=job['split'],offset=job['offset'],rows=i,streams=len(offsets)-1,counts=counts,index_sha256=h,turns_sha256=job['record'].get('augmented_sha256',job['record']['turns_sha256']),arrays_sha256=digest(out),source_sha256=digest(__file__),new_fits=0,reserved_opened=0);immutable_json(receipt,r);return r

def prepare(split):
    plan();jobs=[j for j in json.loads(JOBS.read_text()) if j['split']==split];assert len(jobs)==(470 if split=='train' else 25);order=[];gap=[];offsets=[0];bindings=[]
    target=REPORT/f'{split}-sequences.json';assert not target.exists(),'Retained completed assembly; do not repeat unchanged work'
    with ProcessPoolExecutor(max_workers=2) as pool:
        for n,r in enumerate(pool.map(game,jobs),1):
            with np.load(WORK/'games'/r['raw']/'sequence.npz') as z:order.append(z['order']);gap.append(z['gap']);offsets.extend((z['offsets'][1:]+offsets[-1]).tolist())
            bindings.append(r)
            if n%10==0 or n==len(jobs):print('Learned policy streams',split,n,'/',len(jobs),flush=True)
    order=np.concatenate(order);gap=np.concatenate(gap);count=433071 if split=='train' else 14439;assert np.array_equal(np.sort(order),np.arange(count));np.savez_compressed(WORK/f'{split}-sequences.npz',order=order,offsets=np.asarray(offsets,np.int64),gap=gap)
    immutable_json(target,dict(rows=count,streams=len(offsets)-1,bindings=bindings,arrays_sha256=digest(WORK/f'{split}-sequences.npz'),plan_sha256=digest(REPORT/'sequence-plan.json'),source_sha256=digest(__file__),interpretation='Actor order and true root gaps verified. This is new policy sequence assembly from immutable recorded eligible events, not repeated engine/replay audit or new extraction. No current answer used in gap features.',new_fits=0,reserved_opened=0))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('split',choices=['train','validation']);prepare(p.parse_args().split)
