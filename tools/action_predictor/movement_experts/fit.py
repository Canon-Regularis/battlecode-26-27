"""Exactly one of two movement fits, preserving every attempted checkpoint."""
import argparse,json,subprocess,time
import numpy as np
import torch
import torch.nn.functional as F
from .protocol import ROOT,BASE,WORK,REPORT,freeze
from .data import load,verify,batch,read
from .model import MovementExpert
from .evaluate import infer,summary,paired,masks,support
from ..audit import immutable_json
from ..data import digest
from .. import reliable_train as rt

def run(identifier):
    plan=freeze();rt.setup(20261113);directory=WORK/'runs'/identifier;assert not directory.exists(),'Preserve prior attempt';directory.mkdir(parents=True);start=time.perf_counter();bindings=verify();d={s:load(s) for s in ('train','validation')};t=d['train'];v=d['validation'];natural=np.load(BASE.parent/'v9/frequency/natural-mask.npy');ids=np.flatnonzero(natural&np.isin(t['raw']['y'],[3,8]));assert len(ids)==50192
    mean=t['x'][natural].mean(0,dtype=np.float64).astype(np.float32);std=np.maximum(t['x'][natural].std(0,dtype=np.float64),.01).astype(np.float32);counts=np.stack([np.bincount(t['raw']['py'][ids[t['raw']['y'][ids]==code]],minlength=291) for code in (8,3)]);model=MovementExpert(identifier=='X00',counts);opt=torch.optim.AdamW(model.parameters(),lr=.001,weight_decay=.01);rng=np.random.default_rng(20261113);trace=[];best=float('inf');selected=0;commit=subprocess.run(['git','rev-parse','HEAD'],cwd=ROOT,text=True,capture_output=True,check=True).stdout.strip();fit_start=time.perf_counter()
    for epoch in range(1,36):
        tick=time.perf_counter();model.train();total=0
        for ix in np.array_split(rng.permutation(ids),int(np.ceil(len(ids)/256))):
            opt.zero_grad();lp,_=model(*batch(t,ix,mean,std));loss=F.nll_loss(lp,torch.from_numpy(t['raw']['py'][ix]).long());loss.backward();torch.nn.utils.clip_grad_norm_(model.parameters(),5);opt.step();total+=float(loss.detach())*len(ix)
        out,gate=infer(model,v,mean,std);nll=float(out['nll'].mean());trace.append(dict(round=epoch,train_conditional_nll=total/len(ids),dev_full_joint_nll=nll,seconds=time.perf_counter()-tick));torch.save(dict(state=model.state_dict(),optimizer=opt.state_dict(),mean=mean,std=std,counts=counts,mixture=model.mixture,epoch=epoch,rng=torch.get_rng_state(),numpy_rng=rng.bit_generator.state,protocol_sha256=digest(REPORT/'protocol.json'),source_commit=commit),directory/f'round-{epoch:02d}.pt');print(identifier,trace[-1],flush=True)
        if nll<best-.0001:best=nll;selected=epoch
        if epoch-selected>=6:break
    saved=torch.load(directory/f'round-{selected:02d}.pt',weights_only=False);model.load_state_dict(saved['state']);reports={};prediction_hashes={};gate_stats={};comparison={}
    for split,data in d.items():
        p,g=infer(model,data,mean,std);np.savez_compressed(directory/f'{split}-predictions.npz',**p);np.save(directory/f'{split}-gates.npy',g);prediction_hashes[split]=digest(directory/f'{split}-predictions.npz');reports[split]={k:summary(data,p,m) for k,m in masks(data,natural if split=='train' else None).items()};gate_stats[split]=dict(mean_weights=np.nanmean(g,0).tolist(),mean_entropy=float(np.nansum(-g*np.log(np.clip(g,1e-30,1)),1)[np.isin(data['raw']['y'],[3,8])].mean()),interpretation='Unsupervised latent mixture utilization, not Fish behavior labels.')
        reports[split]['support']=support(data,p)
        nonmovement=~np.isin(data['raw']['y'],[3,8]);np.testing.assert_array_equal(p['coordinate'][nonmovement],data['baseline']['coordinate'][nonmovement]);np.testing.assert_array_equal(p['priority'],data['baseline']['priority']);not_proposed=~np.isin(p['prediction'],[3,8]);np.testing.assert_array_equal(p['proposed_coordinate'][not_proposed],data['baseline']['proposed_coordinate'][not_proposed])
        if split=='validation':
            comparison['G00']=paired(data,p,data['baseline'])
            if identifier=='X00':comparison['S00']=paired(data,p,read(WORK/'runs/S00/validation-predictions.npz'))
    immutable_json(REPORT/f'{identifier}.json',dict(identifier=identifier,selected_round=selected,trace=trace,training_rows=len(ids),training_counts={'move':48286,'blocked':1906},parameters=sum(p.numel() for p in model.parameters()),reports=reports,comparisons=comparison,gate=gate_stats,completed_updates=len(trace)*int(np.ceil(len(ids)/256)),selected_updates=selected*int(np.ceil(len(ids)/256)),checkpoint_sha256=digest(directory/f'round-{selected:02d}.pt'),predictions_sha256=prediction_hashes,input_bindings_sha256=digest(REPORT/'input-bindings.json'),protocol_sha256=digest(REPORT/'protocol.json'),source_commit=commit,fit_interval_seconds=time.perf_counter()-fit_start,whole_command_seconds=time.perf_counter()-start,timing_scope='fit interval includes rounds, per-roundDEV inference/checkpointing and final TRAIN/DEV inference/reporting; whole command additionally includes hash verification/loading/normalization. Feature extraction not performed.',new_fits=1,reserved_opened=0,three_seed_confirmed=False,promoted=False));print('Completed',identifier,'fresh Sol xhigh post-fit review required before next fit',flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('identifier',choices=['S00','X00']);run(p.parse_args().identifier)
