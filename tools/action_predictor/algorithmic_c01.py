"""C01 support revision developed/scored on TRAIN only. No optimizer."""
import json,math
from pathlib import Path
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
import numpy as np
from .algorithmic.library import emit,dist,xy
from .algorithmic.study import ROOT,WORK,REPORT,JOBS,matches
from .observation_data import compact_supplement
from .rich_data import read_turns
from .audit import validate_decision,immutable_json
from .data import action_name,digest
from . import reliable_train as rt

NAMES=[f'{g}/{tie}' for g in ('camp_near','camp_hp','enemy_near','bank','home') for tie in ('greedy_yx','greedy_xy')]+['attempt/camp','attempt/bank']+[f'{a}/{r}' for a in ('attack','cast_0','cast_1') for r in ('near','hp')]+['ground1/camp','ground1/enemy','ground1/continue']+['ward/camp','ward/enemy','ward/bank','ward/continue']+['end','cancel','recall','submit/bank']+['priority/negative_last','priority/negative_last_plus2gap','priority/negative_last_minusgap','priority/zero']
assert len(NAMES)==33
PRIORITY=None
def initialize():
    global PRIORITY
    with np.load(WORK.parent/'v8/priority-train.npz') as z:PRIORITY=z['values']

def project(p,g,r):
    if g is None or dist(p,g)==0 or r<=0:return None
    scale=min(r,dist(p,g))/dist(p,g)
    def rounded(v):return int(math.copysign(math.floor(abs(v)+.5),v))
    return (p[0]+rounded((g[0]-p[0])*scale),p[1]+rounded((g[1]-p[1])*scale))

def candidates(obs,supp,route,priority,history):
    """Only allowlisted PRE, public map, exact causal priority, earlier own roots."""
    own=obs['own'];pos=own.get('position');alive=own.get('alive',False);free=alive and own.get('channelType',0)==0;flags=own.get('roundFlags',0);restr=supp['restrictions'];old=emit(obs,supp,route,simple=True)
    # Same-slot-budget baseline: original simple library plus2continuation rules.
    control=old+[None,None]
    for k,a in ((27,'end'),(28,'cancel'),(29,'recall')):control[k]=(a,None,0)
    out=[None]*len(NAMES)
    out[25]=('end',None,0);out[26]=('cancel',None,0) if own.get('channelType',0)!=0 else None;out[27]=('recall',None,0) if free else None
    if priority[5]:
        last=int(priority[4]);gap=int(priority[6]);out[29:32]=[('priority',None,-last),('priority',None,-last+2*gap),('priority',None,-last-gap)]
    out[32]=('priority',None,0)
    if not pos:return out,control
    p=xy(pos);w,h=route['width'],route['height'];visible=[e for e in obs['entities'] if e.get('known',0)&1 and e.get('position') and e.get('health',0)>0]
    def near(es):return min((xy(e['position']) for e in es),key=lambda g:(dist(p,g),g[1],g[0]),default=None)
    camp=near([e for e in visible if e['entity']['kind']==2]);enemy=near([e for e in visible if e['entity']['kind']==1 and e['team']!=own['team']]);bank=min(map(xy,route['altars']),key=lambda g:(dist(p,g),g[1],g[0]),default=None)
    past=np.flatnonzero(history[:,rt.LABELS.index('move')]>0);heading=None
    if len(past):
        delta=np.rint(history[past[-1],18:20]*8).astype(int)
        if np.any(delta):heading=(p[0]+int(delta[0])*8,p[1]+int(delta[1])*8)
    legal=set(map(xy,supp['movement']));steps=legal-{p};radius=max((dist(p,v) for v in steps),default=0)
    def attempt(g):
        q=project(p,g,radius)
        if not q or not (0<=q[0]<w and 0<=q[1]<h):return None
        return ('move' if q in legal else 'blocked',q,0)
    for k in range(5):out[2*k:2*k+2]=[old[3*k],old[3*k+2]]
    out[10:12]=[attempt(camp),attempt(bank)]
    if heading and steps:
        q=min(steps,key=lambda v:(dist(v,heading),v[1],v[0]));control[31]=('move',q,0) if dist(q,heading)<dist(p,heading) else None;control[32]=attempt(heading)
    def ready(slot):
        props=(own.get('abilityProps') or [{},{}])[slot]
        return free and flags&1024 and not restr&4 and bool(props.get('type')) and own.get('cooldowns',[1,1])[slot]==0 and (not props.get('maxCharges') or own.get('charges',[0,0])[slot]>0)
    for k,a in enumerate(('attack','cast_0','cast_1')):
        ok=free and flags&2 and not restr&2 if k==0 else ready(k-1)
        if ok:out[12+2*k:14+2*k]=old[15+3*k:17+3*k]
    props=(own.get('abilityProps') or [{},{}])[1]
    if ready(1) and props.get('target',0)&16:
        for k,g in enumerate((camp,enemy,heading)):
            q=project(p,g,int(props.get('range',0)))
            if q and 0<=q[0]<w and 0<=q[1]<h:out[18+k]=('cast_1',q,0)
    if free and supp['own'].get('ward',{}).get('charges',0)>0:
        for k,g in enumerate((camp,enemy,bank,heading)):
            q=project(p,g,2)
            if q and 0<=q[0]<w and 0<=q[1]<h:out[21+k]=('ward',q,0)
    if free and own.get('gems',0)>0 and bank and dist(p,bank)<=route['submit_range']:out[28]=('submit',bank,0)
    return out,control

def encode(command,obs):
    if command is None:return [-1,-1,-1]
    action,pos,value=command;coord=-1
    if pos is not None:
        p=obs['own']['position'];dx,dy=pos[0]-p['x'],pos[1]-p['y']
        if max(abs(dx),abs(dy))>8:return [-1,-1,-1]
        coord=(dy+8)*17+dx+8
    return [rt.LABELS.index(action),coord,value]

def job_run(job):
    assert job['split']=='train';record=job['record'];supplements={};route=None;bindings={}
    for suffix in ('supplement','augmentation'):
        path=Path(job['work'])/suffix/record['raw_sha256']/'pre.jsonl'
        if not path.exists():continue
        bindings[str(path)]=digest(path)
        for line in path.open():
            row=json.loads(line)
            if row['record']=='map':
                if route is not None:assert route==row['route']
                route=row['route']
            elif row['record']=='pre':supplements[row['id']]=compact_supplement(row)
    assert digest(job['shard'])==job['shard_sha256']
    with np.load(job['shard']) as z:y=z['y'];history=z['history']
    result=np.full((len(y),2,len(NAMES),3),-1,np.int64);i=0
    for turn in read_turns(job['manifest'],record):
        for d in turn['decisions']:
            validate_decision(d,turn);assert action_name(d['label'])==rt.LABELS[y[i]];supp=supplements[d['id']];assert supp['pre']==d['pre_cursor']
            pair=candidates(d['observation'],supp,route,PRIORITY[job['offset']+i],history[i])
            for mode,commands in enumerate(pair):result[i,mode]=[encode(c,d['observation']) for c in commands]
            i+=1
    assert i==job['rows']
    return job['offset'],result,dict(raw=record['raw_sha256'],turns=record.get('augmented_sha256',record['turns_sha256']),shard=job['shard_sha256'],supplements=bindings)

def run():
    plan=dict(id='C01',slots=NAMES,slot_count=33,source_sha256=digest(__file__),semantics_sha256=digest(REPORT/'C01-historical-constants.json'),prior_library_sha256=digest(Path(__file__).parent/'algorithmic/library.py'),jobs_sha256=digest(JOBS),priority_sha256=digest(WORK.parent/'v8/priority-train.npz'),
        direction='TRAIN-only support development. NoDEVcandidategeneration/evaluation and nofit allocated. C00/A00/A01/D00frozen.0newmatches/downloads/playingbotchanges.',
        changes='10geometricmovement +2single-outcome directattempts;6entitytargetranks;3groundcast1directions;4wardrange2directions;3utilitiesindependentofposition;1submit;4causalpriorityformulas. Noall-cell/all-outcomesenumeration. Attempt destination gets exactly one predictedoutcome by currentpersonal enginemask; unknown blockers can remain unexplained. Does not certify hypotheticalsuccessfulmovement.',
        priority='negative latest actual argument,negative latest+2roundgap,negative latest-roundgap,zero. Latest/gapavailability from approved integer causal cache. Proposals are hypotheses,notFishrules. Noanswer/future/oracle. TRAINnegative2gap84matchesomitted; nofinalDEVtuning.',
        control='33slots:C00simple31,utilityend/cancel/recallmadeposition-independent,pluslegalcontinuationanddirectcontinuationattemptwithsinglemaskforecast. Nominalsizecomparison,notisolationbecausecomponents/diversitydiffer.',
        history='Last earlier successful move within32actualownroots from frozen causal shard. If unavailable explicitly abstain; do notstitch sampleddecisions. PRE-only supplement allowlist. NoIDs/maproutes/hiddenentitypositions/placedwardcoverageassumptions.',
        category_support_gate='No furtherfit from thisstudy unless TRAINunion-withG00 move>=.90,groundcast1>=.70,ward>=.40,priority>=.30,blocked>=.20 and attack/cast0 unionnotlowerthanC00. This is exploratoryallocation,not90%everycategorysuccess. Ifmiss,diagnosemissingmechanismsbeforefitting.',
        future='OnlyafterTRAINassessmentmayfreezeDEVlibrarycriterion/budgetseparately;originalsuccessrulesunchanged. Both75+75reservedsealed;everyoriginalDEVrowretainedwhenlaterevaluated.')
    immutable_json(REPORT/'C01-plan.json',plan);jobs=[j for j in json.loads(JOBS.read_text()) if j['split']=='train'];assert len(jobs)==470
    path=ROOT/'.cambc/action-predictor/v5/combined-train.npz';assert digest(path)=='39386010575ad30add064fdae750680f34cfcc732c4fd00fb657875ff4c61ffb'
    with np.load(path) as z:y=z['y'];py=z['py'];priority=z['priority'];group=z['group'];ability_mask=z['ability_mask']
    target=WORK/'C01-train-candidates.npy';assert not target.exists(),'Preserve attemptedoutputs';out=np.lib.format.open_memmap(target,mode='w+',dtype=np.int64,shape=(len(y),2,33,3));bindings=[]
    with ProcessPoolExecutor(max_workers=4,initializer=initialize) as pool:
        for n,(offset,c,binding) in enumerate(pool.map(job_run,jobs),1):
            out[offset:offset+len(c)]=c;bindings.append(binding)
            if n%25==0 or n==470:print('C01TRAIN',n,'/470',flush=True)
    out.flush();gpath=WORK.parent/'v9/runs/G00/train-predictions.npz';ginfo=json.loads((REPORT.parent/'v9/G00.json').read_text());assert digest(gpath)==ginfo['train_predictions_sha256']
    with np.load(gpath) as z:g00=np.stack((z['prediction'],z['proposed_coordinate'],z['priority']),-1)[:,None]
    b=matches(g00,y,py,priority).any(1);reports={}
    for mode,name in enumerate(('C01','simple33')):
        match=matches(out[:,mode],y,py,priority);covered=match.any(1);families={}
        for code,label in enumerate(rt.LABELS):
            mask=y==code;n=int(mask.sum());families[label]=dict(support=n,covered=int(covered[mask].sum()),coverage=float(covered[mask].mean()) if n else None,union_with_G00=float((covered|b)[mask].mean()) if n else None,unexplained=int((~covered[mask]).sum()))
        ground=(y==rt.LABELS.index('cast_1'))&((ability_mask[:,1].astype(int)&16)>0)
        reports[name]=dict(overall=float(covered.mean()),per_family=families,ground_cast1=dict(rows=int(ground.sum()),covered=int(covered[ground].sum()),coverage=float(covered[ground].mean()),union_with_G00=float((covered|b)[ground].mean())),rescues_beyond_G00=int((covered&~b).sum()),distinct_outputs=dict(Counter(len({tuple(c) for c in row if c[0]>=0}) for row in out[:,mode])),per_slot_matches=match.sum(0).tolist())
    immutable_json(REPORT/'C01-train.json',dict(plan_sha256=digest(REPORT/'C01-plan.json'),data_sha256=digest(path),candidates_sha256=digest(target),G00_predictions_sha256=digest(gpath),rows=len(y),games=470,groups=len(np.unique(group)),libraries=reports,bindings=bindings,reserved_opened=0,DEV_rows_evaluated=0,new_fits=0))
    print(json.dumps(reports,indent=2),flush=True)

if __name__=='__main__':run()
