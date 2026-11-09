"""Current generator evidence preparation; frozen artifacts are read only."""
import json,subprocess
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import numpy as np
import torch
from .priority_fit_v3 import ROOT,BASE,context_directory,load_base
from .data import digest
from .audit import immutable_json
from .rich_data import read_turns
from .observation_data import compact_supplement
from . import reliable_train as rt

WORK=ROOT/'.cambc/action-predictor/v12';REPORT=ROOT/'tools/action_predictor/experiments/v12';JOBS=BASE.parent/'v7/jobs.json'

def selected_jobs(split):
    jobs=json.loads(JOBS.read_text());jobs=[j for j in jobs if j['split']==split]
    if split=='validation':return jobs
    # Bound changed-input recovery to a declared development TRAIN cohort; the
    # conditional-head bridge itself is measured on the entire original TRAIN.
    return [j for version in ('2.0.0','3.0.0')
            for j in [j for j in jobs if j['record']['engine_version']==version][:12]]

def evidence(job):
    r=job['record'];supps={};route=None
    for suffix in ('supplement','augmentation'):
        p=Path(job['work'])/suffix/r['raw_sha256']/'pre.jsonl'
        if not p.exists():continue
        for line in p.open():
            x=json.loads(line)
            if x['record']=='map':
                if route is not None:assert route==x['route']
                route=x['route']
            elif x['record']=='pre':supps[x['id']]=compact_supplement(x)
    return read_turns(job['manifest'],r),supps,route

def target_job(job):
    turns,supps,route=evidence(job);raw=job['record']['raw_sha256'];directory=WORK/'targets'/raw;directory.mkdir(parents=True,exist_ok=True);output=directory/'pre.jsonl';requests=[];i=0
    for t in turns:
        for d in t['decisions']:
            own=d['observation']['own'];p=own.get('position');near=bool(p) and own.get('alive',False) and any(max(abs(a['x']-p['x']),abs(a['y']-p['y']))<=own.get('attackRange',0) for a in route['altars'])
            if near:requests.append(dict(index=job['offset']+i,pre=d['pre_cursor'],perspective=d['observation']['perspective']))
            i+=1
    assert i==job['rows']
    query=dict(raw_sha256=raw,split=job['split'],original_query=str(Path(job['work'])/'supplement'/raw/'query.json'),requests=requests,output=str(output));qpath=directory/'query.json';immutable_json(qpath,query)
    if not output.exists():
        result=subprocess.run(['node',str(Path(__file__).with_name('proposal_targets.cjs')),str(qpath)],capture_output=True,text=True,timeout=180)
        if result.returncode:raise RuntimeError(result.stderr[-3000:])
    rows=[json.loads(line) for line in output.open()];assert rows[-1]==dict(record='complete',rows=len(requests));assert rows[0]['query_sha256']==digest(qpath) and rows[0]['source_sha256']==digest(Path(__file__).with_name('proposal_targets.cjs'))
    assert len(rows)==len(requests)+2
    return dict(raw=raw,split=job['split'],selected_rows=i,queried_personal_PREs=len(requests),sha256=digest(output),query_sha256=digest(qpath))

def prepare_targets(split):
    report=REPORT/f'C03-{split}-targets.json'
    if report.exists():
        r=json.loads(report.read_text())
        for b in r['games']:assert digest(WORK/'targets'/b['raw']/'pre.jsonl')==b['sha256']
        return r
    jobs=selected_jobs(split)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results=[]
        for n,r in enumerate(pool.map(target_job,jobs),1):
            results.append(r)
            if n%5==0 or n==len(jobs):print('Personal targets',split,n,'/',len(jobs),flush=True)
    value=dict(games=results,selection='All PREs with alive personal actor within ownattackRange of anypublicaltar,regardlesscurrentrecordedaction. Outsideeligibility means unavailable,not knownempty. Onlyexisting24TRAINdevelopmentgames/all25originalDEVgames;no reserved.',source_sha256=digest(__file__),query_source_sha256=digest(Path(__file__).with_name('proposal_targets.cjs')),new_fits=0,reserved_opened=0);immutable_json(report,value);return value

@torch.no_grad()
def prepare_arguments():
    WORK.mkdir(parents=True,exist_ok=True);REPORT.mkdir(parents=True,exist_ok=True);target=REPORT/'C03-arguments.json'
    if target.exists():
        value=json.loads(target.read_text())
        for split,r in value['splits'].items():
            assert digest(ROOT/r['table_path'])==r['table_sha256']
            assert digest(WORK/(split+'-priority.npy'))==r['priority_sha256']
            assert digest(WORK/(split+'-prefer-blocked.npy'))==r['outcome_preference_sha256']
        return value
    # Consume existing immutable tables without importing or modifying unfinished
    # frequency-study code. Only the hashes needed here and row parities checked.
    old=ROOT/'tools/action_predictor/experiments/v9';ready=json.loads((old/'frequency-arguments-ready.json').read_text());teacher,_=load_base();teacher.eval();rt.setup(26);result={}
    for split,path in [('train',BASE/'combined-train.npz'),('validation',BASE.parent/'v4/validation.npz')]:
        tablepath=BASE.parent/f'v9/frequency/{split}-family-argmax.npy';assert digest(tablepath)==ready['files'][tablepath.name];table=np.load(tablepath,mmap_mode='r')
        with np.load(path) as z:y=z['y']
        refpath=BASE.parent/f'v9/runs/G00/{split}-predictions.npz'
        with np.load(refpath) as z:reference={k:z[k] for k in ('coordinate','prediction','proposed_coordinate','priority')}
        np.testing.assert_array_equal(table[np.arange(len(y)),y],reference['coordinate']);np.testing.assert_array_equal(table[np.arange(len(y)),reference['prediction']],reference['proposed_coordinate'])
        values=reference['priority'];assert np.isfinite(values).all() and np.equal(values,np.rint(values)).all() and (np.abs(values)<2**24).all();priority=values.astype(np.int64)
        context=np.load(context_directory()/(split+'.npy'),mmap_mode='r');prefer=[];classes=[]
        for a in range(0,len(context),4096):
            logits=teacher.action(torch.from_numpy(np.array(context[a:a+4096])));prefer.append((logits[:,3]>logits[:,8]).numpy());classes.append(logits.argmax(-1).numpy())
        np.testing.assert_array_equal(np.concatenate(classes),reference['prediction']);pp=WORK/(split+'-priority.npy');bp=WORK/(split+'-prefer-blocked.npy');assert not pp.exists() and not bp.exists();np.save(pp,priority);np.save(bp,np.concatenate(prefer))
        result[split]=dict(rows=len(y),table_path=str(tablepath.relative_to(ROOT)),table_sha256=digest(tablepath),priority_sha256=digest(pp),outcome_preference_sha256=digest(bp),G00_prediction_sha256=digest(refpath),all_original_true_and_predicted_family_coordinates_equal=True,priority_all_rows_integer=True)
    value=dict(splits=result,P05_checkpoint_sha256=digest(BASE.parent/'v8/runs/P05/model.pt'),G00_checkpoint_sha256=digest(BASE.parent/'v9/runs/G00/model.pt'),cache_producer_receipt_sha256=digest(old/'frequency-arguments-ready.json'),source_sha256=digest(__file__),meaning='All9familyargs/P05priority available independently of chosen or recordedaction. Truefamilyusedonlyforcacheparity,neverproposalconstruction.',new_fits=0,reserved_opened=0);immutable_json(target,value);return value
