"""Eligible personal ward-state recovery and reuse of frozen neural inputs."""
import argparse,json,subprocess
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor
import numpy as np
import torch
from .protocol import ROOT,BASE,JOBS,WORK,REPORT
from .features import build,EXTRA,GLOBAL,INDICES
from ..proposal_data import evidence
from ..priority_fit_v3 import context_directory,load_base
from ..audit import immutable_json
from ..data import digest
from .. import reliable_train as rt

def job_run(job):
    raw=job['record']['raw_sha256'];directory=WORK/'games'/raw;directory.mkdir(parents=True,exist_ok=True);out=directory/'features.npz';rp=directory/'receipt.json';source={n:digest(Path(__file__).with_name(n)) for n in ('data.py','features.py','personal.cjs')}
    if rp.exists():
        r=json.loads(rp.read_text());assert r['sources']==source and digest(out)==r['sha256'];return r
    turns,supps,route=evidence(job);decisions=[(t,d) for t in turns for d in t['decisions']];requests=[]
    for i,(t,d) in enumerate(decisions):
        own=d['observation']['own'];s=supps[d['id']]
        if own.get('alive') and own.get('position') and s['own'].get('ward',{}).get('charges',0)>0:requests.append(dict(index=job['offset']+i,pre=d['pre_cursor'],perspective=d['observation']['perspective'],position=own['position']))
    q=dict(raw_sha256=raw,split=job['split'],original_query=str(Path(job['work'])/'supplement'/raw/'query.json'),requests=requests,output=str(directory/'personal.jsonl'));qp=directory/'query.json';immutable_json(qp,q)
    if not Path(q['output']).exists():
        run=subprocess.run(['node',str(Path(__file__).with_name('personal.cjs')),str(qp)],capture_output=True,text=True,timeout=600)
        if run.returncode:raise RuntimeError(run.stderr[-3000:])
    rows=[json.loads(x) for x in Path(q['output']).open()];assert rows[0]['source_sha256']==source['personal.cjs'] and rows[0]['query_sha256']==digest(qp);assert rows[-1]==dict(record='complete',rows=len(requests));personal={r['index']:r for r in rows if r['record']=='ward_pre'}
    with np.load(job['shard']) as z:h=z['history']
    extra=np.zeros((len(decisions),EXTRA),np.float32);tile=np.zeros((len(decisions),25,16),np.float16);mask=np.zeros((len(decisions),25),bool);champion=np.zeros(len(decisions),np.int16)
    for i,(t,d) in enumerate(decisions):extra[i],tile[i],mask[i]=build(d['observation'],supps[d['id']],route,h[i],personal.get(job['offset']+i));champion[i]=d['observation']['own']['type']
    assert len(decisions)==job['rows'] and not out.exists();np.savez_compressed(out,extra=extra,tile=tile,mask=mask,champion=champion)
    r=dict(raw=raw,split=job['split'],offset=job['offset'],rows=job['rows'],queried=len(requests),sha256=digest(out),personal_sha256=digest(q['output']),query_sha256=digest(qp),sources=source,engine=job['record']['engine_version']);immutable_json(rp,r);return r

@torch.no_grad()
def prepare(split):
    from .protocol import freeze
    freeze();rt.setup(20261112);target=REPORT/f'{split}-data.json'
    if target.exists():return json.loads(target.read_text())
    if split=='validation':assert (REPORT/'train-data.json').exists()
    jobs=[j for j in json.loads(JOBS.read_text()) if j['split']==split];n=sum(j['rows'] for j in jobs);arrays={name:np.lib.format.open_memmap(WORK/f'{split}-{name}.npy',mode='w+',dtype=dtype,shape=shape) for name,dtype,shape in [('global',np.float32,(n,GLOBAL)),('tile',np.float16,(n,25,36)),('mask',np.bool_,(n,25)),('champion',np.int16,(n,))]};bindings=[];base=np.load(BASE.parent/f'v13/{split}-x.npy',mmap_mode='r');context=np.load(context_directory()/f'{split}.npy',mmap_mode='r');arrays['global'][:,:128]=context;arrays['global'][:,128:573]=base[:,:445]
    with ProcessPoolExecutor(max_workers=2) as pool:
        for number,r in enumerate(pool.map(job_run,jobs),1):
            a=r['offset'];b=a+r['rows']
            with np.load(WORK/'games'/r['raw']/'features.npz') as z:arrays['global'][a:b,573:]=z['extra'];arrays['tile'][a:b,:,20:]=z['tile'];arrays['mask'][a:b]=z['mask'];arrays['champion'][a:b]=z['champion']
            bindings.append(r)
            if number%20==0 or number==len(jobs):print('Ward personal PRE',split,number,'/',len(jobs),flush=True)
    rawpath=BASE/'combined-train.npz' if split=='train' else BASE.parent/'v4/validation.npz'
    with np.load(rawpath) as z:grid=z['grid'];valid=z['valid'];rules=np.column_stack((z['attack_range'],z['ability_range'],z['ability_mask']));y=z['y'];py=z['py']
    arrays['tile'][:,:,:20]=grid[:,INDICES];teacher,_=load_base();teacher.eval();outputs={name:np.lib.format.open_memmap(WORK/f'{split}-{name}.npy',mode='w+',dtype=dtype,shape=shape) for name,dtype,shape in [('type-logp',np.float64,(n,15)),('ward-local-logp',np.float64,(n,25)),('ward-mode',np.int16,(n,)),('ward-mode-logp',np.float64,(n,)),('ward-target-logp',np.float64,(n,))]};outputs['ward-target-logp'][:]=np.nan
    for a in range(0,n,512):
        b=min(n,a+512);ctx=torch.from_numpy(np.array(context[a:b]));outputs['type-logp'][a:b]=teacher.action(ctx).double().log_softmax(-1).numpy();lp=teacher.parameter_logits(ctx,torch.from_numpy(grid[a:b]).float(),torch.from_numpy(valid[a:b]),torch.full((b-a,),14,dtype=torch.int64),torch.from_numpy(rules[a:b]).float()).double().log_softmax(-1);mode=lp.argmax(-1);outputs['ward-local-logp'][a:b]=lp[:,INDICES].numpy();outputs['ward-mode'][a:b]=mode.numpy();outputs['ward-mode-logp'][a:b]=lp[torch.arange(b-a),mode].numpy();ward=np.flatnonzero(y[a:b]==14)
        if len(ward):outputs['ward-target-logp'][a+ward]=lp[ward,py[a+ward]].numpy()
    for v in [*arrays.values(),*outputs.values()]:v.flush()
    with np.load(BASE.parent/f'v9/runs/G00/{split}-predictions.npz') as z:old=z['coordinate'];oldpred=z['prediction']
    np.testing.assert_array_equal(outputs['type-logp'].argmax(-1),oldpred);np.testing.assert_array_equal(outputs['ward-mode'][y==14],old[y==14]);codes=np.full(n,-1,np.int16);local=(py//17-8+2)*5+(py%17-8+2);inrange=(np.abs(py%17-8)<=2)&(np.abs(py//17-8)<=2)&(py>=0)&(py<289);codes[inrange]=local[inrange];support=(y==14);covered=np.zeros(n,bool);ids=np.flatnonzero(support&inrange);covered[ids]=arrays['mask'][ids,codes[ids]]
    result=dict(rows=n,games=len(jobs),files={name:digest(WORK/f'{split}-{name}.npy') for name in [*arrays,*outputs]},ward_rows=int(support.sum()),ward_in_historical_range=int((support&inrange).sum()),ward_in_candidate_mask=int(covered.sum()),uncovered_ward_rows=int((support&~covered).sum()),all_G00_type_and_trueward_mode_parity=True,bindings=bindings,protocol_sha256=digest(REPORT/'protocol.json'),source_sha256=digest(__file__),new_fits=0,reserved_opened=0);immutable_json(target,result);print(split,{k:result[k] for k in ('rows','ward_rows','ward_in_historical_range','ward_in_candidate_mask','uncovered_ward_rows')},flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('split',choices=['train','validation']);prepare(p.parse_args().split)
