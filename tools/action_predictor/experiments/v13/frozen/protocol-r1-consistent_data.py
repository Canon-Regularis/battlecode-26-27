"""V13 changed probability/goal inputs; reuse immutable eligible replay evidence."""
import argparse,gzip,json
from pathlib import Path
from collections import defaultdict,Counter
from concurrent.futures import ProcessPoolExecutor
import numpy as np
import torch
from .proposal_data import ROOT,BASE,JOBS,evidence,target_job,prepare_arguments
from .proposal_generator import generate,encode,NAMES,SPATIAL
from .goal_memory import GoalMemory,current_descriptors
from .command_mixture import FallbackDistribution,target_commands,agreement
from .audit import cursor,validate_decision,immutable_json
from .data import digest
from . import reliable_train as rt

WORK=ROOT/'.cambc/action-predictor/v13';REPORT=ROOT/'tools/action_predictor/experiments/v13'
GLOBAL_DIM=506;DESC_DIM=60

def base_features(x,h):
    h=np.array(h[-8:],copy=True);spatial=np.isin(h[:,:15].argmax(-1),[rt.LABELS.index(a) for a in (*SPATIAL,'end')])&(h[:,:15].sum(-1)>0)
    h[:,16:18]*=spatial[:,None]
    return np.r_[x,h.reshape(-1)].astype(np.float32)

def static_descriptors(c,grid):
    out=np.zeros((len(c),44),np.float32)
    for j,v in enumerate(c):
        if v[0]<0:continue
        if 0<=v[1]<289:out[j,:20]=grid[v[1]]
        out[j,20+v[0]]=1
        if j<15:out[j,35+j//3]=1
        else:out[j,40]=1
        out[j,41+(0 if j<31 else 1 if j<40 else 2)]=1
    return out

def initialize(split):
    global TABLE,PRIORITY,BLOCKED
    TABLE=np.load(BASE.parent/f'v9/frequency/{split}-family-argmax.npy',mmap_mode='r');PRIORITY=np.load(BASE.parent/f'v12/{split}-priority.npy',mmap_mode='r');BLOCKED=np.load(BASE.parent/f'v12/{split}-prefer-blocked.npy',mmap_mode='r')

def game_job(job):
    raw=job['record']['raw_sha256'];directory=WORK/'games'/raw;directory.mkdir(parents=True,exist_ok=True);outpath=directory/'inputs.npz';receipt=directory/'receipt.json'
    sources={p:digest(Path(__file__).with_name(p)) for p in ('consistent_data.py','goal_memory.py','proposal_generator.py')}
    if receipt.exists():
        r=json.loads(receipt.read_text());assert r['sources']==sources and digest(outpath)==r['sha256'];return r
    target_binding=target_job(job)
    targets={r['index']:r for r in map(json.loads,(BASE.parent/'v12/targets'/raw/'pre.jsonl').open()) if r['record']=='personal_targets'}
    turns,supps,route=evidence(job);decisions=[(t,d) for t in turns for d in t['decisions']]
    index=Path(job['manifest']['source'])/'extracted'/raw/'index.jsonl';events=defaultdict(list)
    for line in index.open():
        t=json.loads(line)
        if t.get('record')=='turn':
            for r in t['roots']:events[t['actor']].append((r,t['round']))
    for roots in events.values():roots.sort(key=lambda r:cursor(r[0]['event']))
    frames={};fp=BASE.parent/'v7/games'/raw/'frames.jsonl.gz'
    with gzip.open(fp,'rt',encoding='utf-8') as f:
        for line in f:
            r=json.loads(line);frames[r['event']]=r
    for t,d in decisions:frames[d['event_cursor']]=dict(actor=t['actor'],pre=d['pre_cursor'],observation=d['observation'])
    with np.load(job['shard']) as z:x=z['x'];h=z['history'];grid=z['grid']
    n=job['rows'];commands=np.full((n,len(NAMES),3),-1,np.int64);features=np.zeros((n,GLOBAL_DIM),np.float32);desc=np.zeros((n,len(NAMES),DESC_DIM),np.float16);counts=Counter();memories={};pointers=Counter()
    for i,(turn,d) in enumerate(decisions):
        validate_decision(d,turn);idx=job['offset']+i;actor=turn['actor'];obs=d['observation']
        memory=memories.setdefault(actor,GoalMemory());roots=events[actor]
        while pointers[actor]<len(roots):
            root,rnd=roots[pointers[actor]]
            if cursor(root['event'])>cursor(d['pre_cursor']):break
            f=frames.get(root['event'])
            if f is not None:assert f['actor']==actor and f['pre']==root['pre']
            memory.observe(root['event'],root['header']['step'],rnd,f['observation'] if f is not None else None,route);pointers[actor]+=1
            counts['earlier_actual_roots']+=1;counts['root_PRE_available']+=int(f is not None)
        conditional=dict(coordinates={a:int(TABLE[idx,rt.LABELS.index(a)]) for a in SPATIAL},priority=int(PRIORITY[idx]),prefer_blocked=bool(BLOCKED[idx]))
        bundle=generate(obs,supps[d['id']],route,h[i],conditional,targets.get(idx))
        for c in bundle['proposals']:
            value=encode(c,obs['own'].get('position'),rt.LABELS)
            if value is not None:commands[i,NAMES.index(c.source)]=value
        current,point,gs=current_descriptors(obs,route,commands[i]);past,belief,bestprogress=memory.descriptors(gs,turn['round'],d['pre_cursor'],obs['own'].get('position'),commands[i]);features[i]=np.r_[base_features(x[i],h[i]),current,past]
        desc[i,:,:44]=static_descriptors(commands[i],grid[i]);desc[i,:,44:54]=point;desc[i,:,54:59]=point[:,:5]*belief[None];desc[i,:,59]=bestprogress
        counts['targets']+=1;counts['memory_nonempty']+=int(memory.roots>0);counts['memory_current_goal_known']+=int(belief.any())
    assert len(decisions)==n;assert not outpath.exists();np.savez_compressed(outpath,c=commands,x=features,desc=desc)
    r=dict(raw=raw,split=job['split'],offset=job['offset'],rows=n,sha256=digest(outpath),sources=sources,index_sha256=digest(index),historical_frames_sha256=digest(fp),shard_sha256=job['shard_sha256'],targets=target_binding,causal_counts=dict(counts));immutable_json(receipt,r);return r

def geometry(split):
    from .consistent_study import freeze
    freeze();prepare_arguments();jobs=[j for j in json.loads(JOBS.read_text()) if j['split']==split];assert len(jobs)==(470 if split=='train' else 25)
    target=REPORT/f'{split}-inputs.json'
    if target.exists():return json.loads(target.read_text())
    n=sum(j['rows'] for j in jobs);WORK.mkdir(parents=True,exist_ok=True)
    arrays={name:np.lib.format.open_memmap(WORK/f'{split}-{name}.npy',mode='w+',dtype=dtype,shape=shape) for name,dtype,shape in [('c',np.int64,(n,len(NAMES),3)),('x',np.float32,(n,GLOBAL_DIM)),('desc',np.float16,(n,len(NAMES),DESC_DIM))]};bindings=[]
    with ProcessPoolExecutor(max_workers=2,initializer=initialize,initargs=(split,)) as pool:
        for number,r in enumerate(pool.map(game_job,jobs),1):
            a=r['offset'];b=a+r['rows']
            with np.load(WORK/'games'/r['raw']/'inputs.npz') as z:
                for key,array in arrays.items():array[a:b]=z[key]
            bindings.append(r)
            if number%10==0 or number==len(jobs):print('Causal goal inputs',split,number,'/',len(jobs),flush=True)
    for a in arrays.values():a.flush()
    result=dict(rows=n,games=len(jobs),files={k:digest(WORK/f'{split}-{k}.npy') for k in arrays},bindings=bindings,new_fits=0,reserved_opened=0);immutable_json(target,result);return result

@torch.no_grad()
def probabilities(split):
    from .proposal_predictor import load_proposal_predictor
    from .priority_head import flatten
    rt.setup(20261110);geometry(split);target=REPORT/f'{split}-probabilities.json'
    if target.exists():return json.loads(target.read_text())
    p=load_proposal_predictor().frozen;path=BASE/'combined-train.npz' if split=='train' else BASE.parent/'v4/validation.npz'
    with np.load(path) as z:raw={k:z[k] for k in z.files}
    data,_=rt.model_data(raw,p.config,(p.mean,p.std));n=len(raw['y']);c=np.load(WORK/f'{split}-c.npy',mmap_mode='r');observed=target_commands(raw['y'],raw['py'],raw['priority'])
    with np.load(BASE.parent/f'v8/priority-{split}.npz') as z:values=torch.from_numpy(z['values']);extra=torch.from_numpy((flatten(z['values'],z['history']).astype(np.float32)-p.extra_mean.numpy())/p.extra_std.numpy())
    outputs={name:np.lib.format.open_memmap(WORK/f'{split}-{name}.npy',mode='w+',dtype=dtype,shape=shape) for name,dtype,shape in [('point-logq',np.float64,(n,len(NAMES))),('mode-logq',np.float64,(n,15)),('modes',np.int64,(n,15,3)),('target-logq',np.float64,(n,)),('matches',np.bool_,(n,len(NAMES)))]}
    maxdiff=0
    with np.load(BASE.parent/f'v9/runs/G00/{split}-predictions.npz') as z:oldnll=z['nll']
    for a in range(0,n,256):
        b=min(n,a+256);inputs={k:data[k][a:b] for k in ('x','history','valid','rules')};inputs.update(grid=data['grid'][a:b].float(),priority_values=values[a:b],extra=extra[a:b]);q=FallbackDistribution(p,inputs)
        modes,logq=q.modes();outputs['modes'][a:b]=modes;outputs['mode-logq'][a:b]=logq;outputs['point-logq'][a:b]=q.log_prob(c[a:b]);outputs['target-logq'][a:b]=q.log_prob(observed[a:b,None])[:,0];outputs['matches'][a:b]=agreement(c[a:b],observed[a:b]);maxdiff=max(maxdiff,float(np.max(np.abs(outputs['target-logq'][a:b]+oldnll[a:b]))))
        if a%25600==0:print('Shared Q probabilities',split,a,'/',n,flush=True)
    for x in outputs.values():x.flush()
    assert maxdiff<.0001,('Changed fallback representation',maxdiff)
    value=dict(rows=n,files={k:digest(WORK/f'{split}-{k}.npy') for k in outputs},max_G00_observed_nll_difference=maxdiff,contract='One FallbackDistribution.log_prob used for target likelihood, every point command, and every family mode. No current answer used for modes or proposals.',source_sha256=digest(__file__),mixture_source_sha256=digest(Path(__file__).with_name('command_mixture.py')),new_fits=0,reserved_opened=0);immutable_json(target,value);return value

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('split',choices=['train','validation']);p.add_argument('--probabilities',action='store_true');a=p.parse_args();probabilities(a.split) if a.probabilities else geometry(a.split)
