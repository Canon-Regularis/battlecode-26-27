"""C02 TRAIN-only attempted movement mechanism correction; no selector fit."""
import json
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor
from collections import Counter
import numpy as np
from .algorithmic_c01 import ROOT,WORK,REPORT,JOBS,project,encode
from .algorithmic.study import matches
from .observation_data import compact_supplement
from .rich_data import read_turns
from .audit import immutable_json,validate_decision
from .data import digest,action_name
from . import reliable_train as rt

SLOTS=[1,3,5,7,9]
NAMES=['attempt/continue1','attempt/continue2','attempt/repeat_prior_blocked_target','attempt/camp2','attempt/bank2']
BASE=None
def initialize():
    global BASE
    BASE=np.load(WORK/'C01-train-candidates.npy',mmap_mode='r')

def proposals(obs,supp,route,history):
    own=obs['own'];pos=own.get('position')
    if not pos or not own.get('alive',False) or own.get('channelType',0)!=0:return [None]*5
    p=(pos['x'],pos['y']);legal={(v['x'],v['y']) for v in supp['movement']};past=np.flatnonzero(history[:,8]>0);heading=None;blocked=None
    if len(past):
        v=np.rint(history[past[-1],18:20]*8).astype(int)
        if np.any(v):heading=(p[0]+int(v[0])*8,p[1]+int(v[1])*8)
    prior=np.flatnonzero(history[:,3]>0)
    if len(prior):
        v=np.rint(history[prior[-1],16:18]*32).astype(int);blocked=(p[0]+int(v[0]),p[1]+int(v[1]))
    camps=[e for e in obs['entities'] if e.get('known',0)&1 and e['entity']['kind']==2 and e.get('health',0)>0 and e.get('position')]
    def distance(q):return max(abs(q[0]-p[0]),abs(q[1]-p[1]))
    camp=min(((e['position']['x'],e['position']['y']) for e in camps),key=lambda q:(distance(q),q[1],q[0]),default=None);bank=min(((e['x'],e['y']) for e in route['altars']),key=lambda q:(distance(q),q[1],q[0]),default=None)
    targets=[project(p,heading,1),project(p,heading,2),blocked,project(p,camp,2),project(p,bank,2)];result=[]
    for q in targets:
        if not q or q==p or not (0<=q[0]<route['width'] and 0<=q[1]<route['height']):result.append(None)
        else:result.append(('move' if q in legal else 'blocked',q,0))
    return result

def job_run(job):
    assert job['split']=='train';record=job['record'];supplements={};route=None;bindings={}
    for suffix in ('supplement','augmentation'):
        path=Path(job['work'])/suffix/record['raw_sha256']/'pre.jsonl'
        if not path.exists():continue
        bindings[str(path)]=digest(path)
        for line in path.open():
            r=json.loads(line)
            if r['record']=='map':route=r['route']
            elif r['record']=='pre':supplements[r['id']]=compact_supplement(r)
    assert digest(job['shard'])==job['shard_sha256']
    with np.load(job['shard']) as z:history=z['history'];y=z['y']
    out=np.array(BASE[job['offset']:job['offset']+job['rows'],0]);i=0
    for turn in read_turns(job['manifest'],record):
        for d in turn['decisions']:
            validate_decision(d,turn);assert rt.LABELS[y[i]]==action_name(d['label']);s=supplements[d['id']];assert s['pre']==d['pre_cursor'];out[i,SLOTS]=[encode(c,d['observation']) for c in proposals(d['observation'],s,route,history[i])];i+=1
    assert i==len(out)
    return job['offset'],out,dict(raw=record['raw_sha256'],source=record.get('augmented_sha256',record['turns_sha256']),shard=job['shard_sha256'],supplements=bindings)

def run():
    old=json.loads((REPORT/'C01-train.json').read_text());cp=WORK/'C01-train-candidates.npy';assert digest(cp)==old['candidates_sha256']
    immutable_json(REPORT/'C02-plan.json',dict(id='C02',source_sha256=digest(__file__),C01_plan_sha256=digest(REPORT/'C01-plan.json'),C01_candidates_sha256=digest(cp),jobs_sha256=digest(JOBS),slots_replaced=SLOTS,new_proposals=NAMES,nominal_slots=33,hypothesis='C01wronglyabstainswhenmaskempty;8100of10065TRAINblockedattemptshaveemptycurrentmovementmask. Replace5geometricXYtieswithsmallcausalattemptfamily;historicalmovementblockedrootkind23confirmedpinnedcodec. No currentrecordedoutcome enters proposals.',outcome='One outcome per destination:currentpersonal enginemaskmembership forecasts move elseblocked. No duplicationunderbothoutcomes. This can misforecast hidden/dynamicblocking; not an engine hypotheticalsimulation/legalityclaim.',history='Earlier actual ownsuccessfulmoveheading(last32roots),earlierblockedtargetrelativecurrentposition(last32roots). Unavailablehistory=>abstain. No currentlabel,futurestate,oraclegoal,IDs,sampledrowstitching.',comparison='C01same33slotsanditsfixedsimple33control. OtherC01slotsunchanged. No newselectorfit,noDEVoutputs,originalC01categorysupportgateunchanged. No fitsallocated.',reserved_opened=0))
    path=ROOT/'.cambc/action-predictor/v5/combined-train.npz';assert digest(path)==old['data_sha256']
    with np.load(path) as z:y=z['y'];py=z['py'];priority=z['priority'];mm=z['move_mask'];flags=z['flags']
    outpath=WORK/'C02-train-candidates.npy';assert not outpath.exists();out=np.lib.format.open_memmap(outpath,mode='w+',dtype=np.int64,shape=(len(y),33,3));bindings=[];jobs=[j for j in json.loads(JOBS.read_text()) if j['split']=='train'];assert len(jobs)==470
    with ProcessPoolExecutor(max_workers=4,initializer=initialize) as pool:
        for n,(offset,c,binding) in enumerate(pool.map(job_run,jobs),1):
            out[offset:offset+len(c)]=c;bindings.append(binding)
            if n%25==0 or n==470:print('C02TRAIN',n,'/470',flush=True)
    out.flush();gp=WORK.parent/'v9/runs/G00/train-predictions.npz';assert digest(gp)==old['G00_predictions_sha256']
    with np.load(gp) as z:baseline=np.stack((z['prediction'],z['proposed_coordinate'],z['priority']),-1)[:,None]
    b=matches(baseline,y,py,priority).any(1);match=matches(out,y,py,priority);covered=match.any(1);per={}
    for code,name in enumerate(rt.LABELS):
        mask=y==code;n=int(mask.sum());per[name]=dict(support=n,covered=int(covered[mask].sum()),coverage=float(covered[mask].mean()) if n else None,union_with_G00=float((covered|b)[mask].mean()) if n else None)
    blocked=y==3;immutable_json(REPORT/'C02-train.json',dict(plan_sha256=digest(REPORT/'C02-plan.json'),candidates_sha256=digest(outpath),rows=len(y),games=470,overall=float(covered.mean()),per_family=per,rescues_beyond_G00=int((covered&~b).sum()),new_slot_matches=dict(zip(NAMES,map(int,match[:,SLOTS].sum(0)))),distinct_outputs=dict(Counter(len({tuple(c) for c in row if c[0]>=0}) for row in out)),blocked_diagnostic=dict(rows=int(blocked.sum()),empty_mask=int((blocked&(mm.sum(1)==0)).sum()),move_flag_unavailable=int((blocked&((flags&1)==0)).sum()),attempt_destination_retained=True,no_duplicate_outcome_library=True),bindings=bindings,DEV_rows_evaluated=0,new_fits=0,reserved_opened=0))
    print(json.dumps(per,indent=2),flush=True)

if __name__=='__main__':run()
