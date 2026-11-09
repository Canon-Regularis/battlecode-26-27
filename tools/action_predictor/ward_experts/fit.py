"""One of exactly four prespecified ward fits per invocation."""
import argparse,json,subprocess,time
from pathlib import Path
import numpy as np
import torch
import torch.nn.functional as F
from .protocol import ROOT,BASE,WORK,REPORT,FITS,freeze
from .model import Placement,Typing,target_local,placement_target,placement_modes
from .integration import type_distribution,loss_overlay,commands
from ..audit import immutable_json
from ..data import digest
from .. import reliable_train as rt

def load(split):
    d={k:np.load(WORK/f'{split}-{k}.npy',mmap_mode='r') for k in ('global','tile','mask','type-logp','ward-local-logp','ward-mode','ward-mode-logp','ward-target-logp','champion')}
    path=BASE/'combined-train.npz' if split=='train' else BASE.parent/'v4/validation.npz'
    with np.load(path) as z:d['raw']={k:z[k] for k in ('y','py','priority','group')}
    d['base_nll']=-np.load(BASE.parent/f'v13/{split}-target-logq.npy');d['modes']=np.load(BASE.parent/f'v13/{split}-modes.npy',mmap_mode='r');d['mode_joint']=np.load(BASE.parent/f'v13/{split}-mode-logq.npy',mmap_mode='r');return d

def inputs(d,ids,mean,std,identifier):
    x=np.clip((np.array(d['global'][ids])-mean)/std,-10,10);tile=np.array(d['tile'][ids],dtype=np.float32)
    if identifier=='P00':x[:,128:]=0;tile[:,:,20:]=0
    if identifier=='T00':x[:,573:]=0
    return torch.from_numpy(x),torch.from_numpy(tile),torch.from_numpy(np.array(d['mask'][ids]))

@torch.no_grad()
def infer(model,d,mean,std,identifier):
    model.eval();result={k:[] for k in ('coordinate','parameter_lp','logit','nll')}
    for a in range(0,len(d['global']),512):
        ids=slice(a,a+512);x,tile,mask=inputs(d,ids,mean,std,identifier);oldtype=torch.from_numpy(np.array(d['type-logp'][ids]));y=torch.from_numpy(d['raw']['y'][ids]).long();base=torch.from_numpy(d['base_nll'][ids])
        if identifier.startswith('P'):
            lp=model(x,tile,mask);coordinate,parameter_lp=placement_modes(lp,mask,torch.from_numpy(np.array(d['ward-local-logp'][ids])),torch.from_numpy(np.array(d['ward-mode'][ids])).long(),torch.from_numpy(np.array(d['ward-mode-logp'][ids])));target=placement_target(lp,mask,d['raw']['py'][ids],torch.from_numpy(np.nan_to_num(np.array(d['ward-target-logp'][ids]))));nll=loss_overlay(base,oldtype,oldtype,y,torch.from_numpy(np.nan_to_num(np.array(d['ward-target-logp'][ids]))),target);logit=np.zeros(len(x))
        else:
            raw=model(x);nll=loss_overlay(base,oldtype,type_distribution(oldtype,raw),y);logit=raw.numpy();coordinate=torch.from_numpy(np.array(d['ward-mode'][ids]));parameter_lp=torch.from_numpy(np.array(d['ward-mode-logp'][ids]))
        for k,v in dict(coordinate=coordinate.numpy(),parameter_lp=parameter_lp.numpy(),logit=logit,nll=nll.numpy()).items():result[k].append(v)
    return {k:np.concatenate(v) for k,v in result.items()}

def run(identifier):
    freeze();rt.setup(20261112);directory=WORK/'runs'/identifier;assert not directory.exists(),'Preserve attemptedfit';directory.mkdir(parents=True)
    # Changed ward inputs only; original immutable upstream audits are reused.
    for split in ('train','validation'):
        ready=json.loads((REPORT/f'{split}-data.json').read_text());assert ready['uncovered_ward_rows']<=.01*ready['ward_rows'] if split=='train' else True
        for name,h in ready['files'].items():assert digest(WORK/f'{split}-{name}.npy')==h
    data={s:load(s) for s in ('train','validation')};t=data['train'];v=data['validation'];natural=np.load(BASE.parent/'v9/frequency/natural-mask.npy');mean=np.array(t['global'][natural]).mean(0);std=np.maximum(np.array(t['global'][natural]).std(0),.01);y=t['raw']['y'];ward=y==14;prior=float(ward[natural].mean());aug=float(ward.mean());weights=np.where(ward,prior/aug,(1-prior)/(1-aug)).astype(np.float64);local,valid=target_local(t['raw']['py']);counts=np.bincount(local[ward&valid],minlength=25);placement=identifier.startswith('P');model=Placement(counts) if placement else Typing(prior);opt=torch.optim.AdamW(model.parameters(),lr=.001,weight_decay=.01);rng=np.random.default_rng(20261112);trainids=np.flatnonzero(ward) if placement else np.arange(len(y));batch=128 if placement else 512;trace=[];best=float('inf');selected=0;tick=time.perf_counter();commit=subprocess.run(['git','rev-parse','HEAD'],cwd=ROOT,capture_output=True,text=True,check=True).stdout.strip()
    for epoch in range(1,36):
        model.train();losses=[];start=time.perf_counter()
        for ids in np.array_split(rng.permutation(trainids),int(np.ceil(len(trainids)/batch))):
            x,tile,mask=inputs(t,ids,mean,std,identifier);opt.zero_grad()
            if placement:loss=-placement_target(model(x,tile,mask),mask,t['raw']['py'][ids],torch.from_numpy(np.array(t['ward-target-logp'][ids]))).mean()
            else:
                loss_raw=F.binary_cross_entropy_with_logits(model(x).double(),torch.from_numpy(ward[ids].astype(np.float64)),reduction='none');w=torch.from_numpy(weights[ids]);loss=(loss_raw*w).sum()/w.sum()
            loss.backward();torch.nn.utils.clip_grad_norm_(model.parameters(),5);opt.step();losses.append(float(loss.detach()))
        out=infer(model,v,mean,std,identifier);value=float(out['nll'].mean());trace.append(dict(round=epoch,train_loss=float(np.mean(losses)),dev_joint_nll=value,seconds=time.perf_counter()-start));torch.save(dict(state=model.state_dict(),mean=mean,std=std,identifier=identifier,epoch=epoch,counts=counts,prior=prior,optimizer=opt.state_dict(),rng=torch.get_rng_state(),numpy_rng=rng.bit_generator.state,protocol_sha256=digest(REPORT/'protocol.json'),source_commit=commit),directory/f'round-{epoch:02d}.pt');print(identifier,trace[-1],flush=True)
        if value<best-.0001:best=value;selected=epoch
        if epoch-selected>=6:break
    model.load_state_dict(torch.load(directory/f'round-{selected:02d}.pt',weights_only=False)['state']);stats={}
    for split,d in data.items():
        out=infer(model,d,mean,std,identifier);np.savez_compressed(directory/f'{split}-outputs.npz',**out);w=d['raw']['y']==14;stats[split]=dict(rows=len(w),ward_rows=int(w.sum()),conditional_exact=int((out['coordinate'][w]==d['raw']['py'][w]).sum()),observed_joint_nll=float(out['nll'].mean()))
    immutable_json(REPORT/f'{identifier}.json',dict(selected_round=selected,trace=trace,stats=stats,training_rows=len(trainids),natural_ward_prior=prior,augmented_ward_prior=aug,positive_weight=prior/aug,negative_weight=(1-prior)/(1-aug),parameters=sum(p.numel() for p in model.parameters()),checkpoint_sha256=digest(directory/f'round-{selected:02d}.pt'),outputs={s:digest(directory/f'{s}-outputs.npz') for s in data},source_commit=commit,protocol_sha256=digest(REPORT/'protocol.json'),completed_updates=len(trace)*int(np.ceil(len(trainids)/batch)),measured_interval_seconds=time.perf_counter()-tick,new_fits=1,reserved_opened=0));print('Completed',identifier,'freshSolxhighreviewrequired',flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('identifier',choices=FITS);run(p.parse_args().identifier)
