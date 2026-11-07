"""C03 command-generator repair: coverage only, no fit or selected predictor."""
import argparse,json
from pathlib import Path
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
import numpy as np
from .proposal_data import ROOT,BASE,WORK,REPORT,JOBS,selected_jobs,evidence,prepare_arguments,prepare_targets
from .proposal_generator import generate,encode,NAMES,SPATIAL
from .algorithmic.study import matches
from .audit import immutable_json,validate_decision
from .data import digest
from . import reliable_train as rt

def freeze():
    WORK.mkdir(parents=True,exist_ok=True);REPORT.mkdir(parents=True,exist_ok=True)
    sources=[Path(__file__).parent/n for n in ('proposal_generator.py','proposal_predictor.py','proposal_data.py','proposal_targets.cjs','proposal_study.py','proposal_roundtrip.py','test_proposal_generator.py','algorithmic/library.py','algorithmic_c01.py','algorithmic_c02.py')]
    value=dict(id='C03',purpose='Repair demonstrably incomplete command support, not another selector training experiment.',
        slots=list(NAMES),slot_count=len(NAMES),
        priority='Replace constant-zero point with the existing frozen P05 exact int64 prediction, computed for EVERY personal PRE independently of position and action argmax. Do not substitute the baseline GRU scalar. P05 can itself predict zero.',
        heads='Expose all nine existing learned conditional spatial argmaxes independently of chosen action; resolve unit targets from personal evidence, preserving ambiguity. No current recorded family supplied to inference.',
        repairs='Utilities outside position gate; ground casts both slots; historical range-two wards; five attempted-movement directions; personal-API enemy altar-lock targets. Bounded semantic proposals, no all-destination enumeration.',
        movement_outcome='One outcome per destination: blocked when outside current personal movement mask OR frozen action logit(blocked)>logit(move), else move. A causal forecast, not a proof of outcome or illegality. Preserve attempted destination. No dual-outcome library.',
        readiness='Reuse historical partial attack/cast/ward/submit readiness checks; full engine legality remains unassessed. No proposed-action simulation.',
        scope=dict(train_geometry_games=[j['record']['raw_sha256'] for j in selected_jobs('train')],train_geometry_selection='First12 canonical eligible TRAIN jobs per engine; declared24-game development cohort, not fullTRAIN geometry coverage.',train_parameter_bridge_rows=433071,dev_rows=14439,dev_games=25),
        comparisons=['frozen simple31','same31 replacing zero with P05, no added slots','unconditional nine learned coordinates plus P05 integer (representation-only diagnostic)','repaired57, plus unchanged G00 hard command'],
        interpretation='Oracle coverage only; no selector trained, no achieved-accuracy improvement claim. Existing A00 weights are incompatible and are not reused with changed slots.',
        report=['all original DEV categories and denominator','covered/uncovered and losses relative frozen support','distinct outputs/abstentions','old1301 support misses recovered','per-source support','raw PRE runtime parity of all learned arguments and proposals'],
        rules='Freeze code before DEV. Measure TRAIN cohort first. Original targets unchanged; shops unavailable strict failures; sparse categories uncertified; no reserved data, games, downloads or bot edits.',
        new_fits=0,jobs_sha256=digest(JOBS),sources={str(p.relative_to(ROOT)):digest(p) for p in sources})
    immutable_json(REPORT/'C03-plan.json',value)
    return value

def initialize(split):
    global TABLE,PRIORITY,BLOCKED
    TABLE=np.load(BASE.parent/f'v9/frequency/{split}-family-argmax.npy',mmap_mode='r')
    PRIORITY=np.load(WORK/(split+'-priority.npy'),mmap_mode='r');BLOCKED=np.load(WORK/(split+'-prefer-blocked.npy'),mmap_mode='r')

def job_run(job):
    turns,supps,route=evidence(job);raw=job['record']['raw_sha256'];targetpath=WORK/'targets'/raw/'pre.jsonl'
    targets={r['index']:r for r in map(json.loads,targetpath.open()) if r['record']=='personal_targets'}
    assert digest(job['shard'])==job['shard_sha256']
    with np.load(job['shard']) as z:history=z['history']
    out=np.full((job['rows'],len(NAMES),3),-1,np.int64);unavailable=Counter();identity=Counter();i=0
    for turn in turns:
        for d in turn['decisions']:
            validate_decision(d,turn);idx=job['offset']+i;s=supps[d['id']];assert s['pre']==d['pre_cursor']
            conditional=dict(coordinates={a:int(TABLE[idx,rt.LABELS.index(a)]) for a in SPATIAL},priority=int(PRIORITY[idx]),prefer_blocked=bool(BLOCKED[idx]))
            bundle=generate(d['observation'],s,route,history[i],conditional,targets.get(idx))
            for c in bundle['proposals']:
                value=encode(c,d['observation']['own'].get('position'),rt.LABELS)
                if value is not None:out[i,NAMES.index(c.source)]=value
                identity[c.entity_resolution]+=1
            unavailable.update(bundle['unavailable'].values());i+=1
    assert i==job['rows']
    return job['offset'],out,dict(raw=raw,rows=i,shard_sha256=job['shard_sha256'],targets_sha256=digest(targetpath),abstention_reasons=dict(unavailable),entity_resolution=dict(identity))

def summary(c,y,py,priority,base):
    match=matches(c,y,py,priority);covered=match.any(1);union=covered|base
    per={}
    for k,name in enumerate(rt.LABELS):
        m=y==k;n=int(m.sum());per[name]=dict(rows=n,library_covered=int(covered[m].sum()),union_with_G00=int(union[m].sum()),union_rate=float(union[m].mean()) if n else None)
    return dict(covered=int(covered.sum()),union_with_G00=int(union.sum()),missing=int((~union).sum()),rescues_beyond_G00=int((covered&~base).sum()),per_family=per),covered,match

def run(split):
    plan=freeze();prepare_arguments()
    if split=='validation':assert (REPORT/'C03-train.json').exists()
    prepare_targets(split);jobs=selected_jobs(split)
    path=BASE/'combined-train.npz' if split=='train' else BASE.parent/'v4/validation.npz'
    expected='39386010575ad30add064fdae750680f34cfcc732c4fd00fb657875ff4c61ffb' if split=='train' else '01a15e1e10f68922334a5367bb825c8ef9bbe228ae7a9e86e92aae9609b204ed'
    assert digest(path)==expected
    with np.load(path) as z:y=z['y'];py=z['py'];priority=z['priority'];group=z['group']
    gp=BASE.parent/f'v9/runs/G00/{split}-predictions.npz'
    with np.load(gp) as z:baseline=np.stack((z['prediction'],z['proposed_coordinate'],z['priority']),-1)[:,None]
    original=np.load(BASE.parent/f'v10/{split}-candidates.npy',mmap_mode='r')[:,1]
    base=matches(baseline,y,py,priority).any(1)
    # Same-size repair and full-data bridge are kept separate from the expanded library.
    oldmatch=matches(original,y,py,priority);oldcovered=oldmatch.any(1);pv=np.load(WORK/(split+'-priority.npy'));table=np.load(BASE.parent/f'v9/frequency/{split}-family-argmax.npy',mmap_mode='r')
    replacement=oldmatch[:,:-1].any(1)|((y==9)&(pv==priority));bridge=np.full((len(y),10,3),-1,np.int64)
    for k,a in enumerate(SPATIAL):bridge[:,k,0]=rt.LABELS.index(a);bridge[:,k,1]=table[:,rt.LABELS.index(a)];bridge[:,k,2]=0
    bridge[:,-1,0]=9;bridge[:,-1,2]=pv
    bridge_summary,_,_=summary(bridge,y,py,priority,base)
    indexes=np.concatenate([np.arange(j['offset'],j['offset']+j['rows']) for j in jobs]);out=np.full((len(indexes),len(NAMES),3),-1,np.int64);cursor=0;bindings=[]
    target=WORK/(split+'-candidates.npy');assert not target.exists()
    with ProcessPoolExecutor(max_workers=2,initializer=initialize,initargs=(split,)) as pool:
        for n,(offset,rows,binding) in enumerate(pool.map(job_run,jobs),1):
            np.testing.assert_array_equal(indexes[cursor:cursor+len(rows)],np.arange(offset,offset+len(rows)))
            out[cursor:cursor+len(rows)]=rows;cursor+=len(rows);bindings.append(binding)
            if n%5==0 or n==len(jobs):print('Repaired generators',split,n,'/',len(jobs),flush=True)
    np.save(target,out);np.save(WORK/(split+'-indices.npy'),indexes)
    ix=indexes;result,covered,match=summary(out,y[ix],py[ix],priority[ix],base[ix]);oldunion=(oldcovered|base)[ix];newunion=covered|base[ix]
    result.update(rows=len(ix),groups=len(np.unique(group[ix])),old_support_missing=int((~oldunion).sum()),old_missing_recovered=int((~oldunion&newunion).sum()),old_support_lost=int((oldunion&~newunion).sum()),per_source_matches=dict(zip(NAMES,map(int,match.sum(0)))),distinct_outputs=dict(sorted(Counter(len({tuple(v) for v in row if v[0]>=0}) for row in out).items())))
    result['same31_P05_replacement_on_identical_rows']=dict(old_union=int(oldunion.sum()),new_union=int((replacement|base)[ix].sum()),priority_covered_old=int((oldcovered&(y==9))[ix].sum()),priority_covered_new=int((replacement&(y==9))[ix].sum()))
    result['full_original_split_priority_replacement']=dict(rows=len(y),old_union=int((oldcovered|base).sum()),new_union=int((replacement|base).sum()),per_family={name:dict(rows=int((y==k).sum()),old_union=int(((oldcovered|base)&(y==k)).sum()),new_union=int(((replacement|base)&(y==k)).sum())) for k,name in enumerate(rt.LABELS)})
    result['full_original_split_parameter_bridge_diagnostic']=dict(bridge_summary,meaning='Conditional-coordinate observed-representation oracle only; not all are resolved executable entity commands; utilities absent. No model chosen-family gate. No achieved accuracy claim.')
    immutable_json(REPORT/f'C03-{split}.json',dict(plan_sha256=digest(REPORT/'C03-plan.json'),arguments_sha256=digest(REPORT/'C03-arguments.json'),data_sha256=expected,candidates_sha256=digest(target),indices_sha256=digest(WORK/(split+'-indices.npy')),G00_prediction_sha256=digest(gp),result=result,bindings=bindings,new_fits=0,reserved_opened=0,shop_assessed=0,strict_entity_identity_certified=False))
    print(json.dumps({k:v for k,v in result.items() if k not in ('full_original_split_parameter_bridge_diagnostic','per_source_matches')},indent=2),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('split',choices=['train','validation']);run(p.parse_args().split)
