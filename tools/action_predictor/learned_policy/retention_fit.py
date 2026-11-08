"""One registered sequential-policy fit; no extra fit or deployment orchestration."""
import argparse,json,subprocess,time,copy
import numpy as np
import torch
from .sequence_data import ROOT,BASE,WORK,REPORT
from .model import GoalPolicy
from .retention_routing import backward
from .retention_protocol import freeze as route_freeze
from .fit import verify
from .data import load,chunks,causal_inputs,geometry,targets
from .inference import infer,select_state
from ..priority_fit_v3 import load_base
from ..movement_experts.evaluate import summary,paired
from ..audit import immutable_json
from ..data import digest
from .. import reliable_train as rt

def run(identifier):
    design=route_freeze();rt.setup(20261114);directory=WORK/'runs'/identifier;assert not directory.exists(),'Preserve attempted fit';directory.mkdir(parents=True);verify();teacher,saved=load_base();model=GoalPolicy(teacher,True);data={s:load(s,saved) for s in ('train','validation')};t=data['train'];v=data['validation'];opt=torch.optim.AdamW([p for p in model.parameters() if p.requires_grad],lr=.0003,weight_decay=.01);rng=np.random.default_rng(20261114);trace=[];best=float('inf');selected=0;updates=0;commit=subprocess.run(['git','rev-parse','HEAD'],cwd=ROOT,capture_output=True,text=True,check=True).stdout.strip();tick=time.perf_counter()
    for epoch in range(1,36):
        state=model.empty(32);model.train();seen=np.zeros(len(t['raw']['y']),np.uint8);total=0.;aux_total=0.;start=time.perf_counter()
        for rows in chunks(t['sequences'],rng):
            opt.zero_grad();losses=[];auxiliary=[];denominator=0
            for ids in rows:
                valid=ids>=0;ix=np.maximum(ids,0);mask=torch.from_numpy(valid);step=model.begin(**causal_inputs(t,ix),state=state);target=targets(t,ix);loss,post=model.observed(step,**geometry(t,ix),**{k:target[k] for k in ('y','py','priority_parameter_nll')});aux=model.achieved_goal_loss(step,target['achieved'],target['achievement_available']);losses.append(loss[mask].sum());auxiliary.append(aux[mask].sum());denominator+=int(valid.sum());state=select_state(state,post,mask);seen[ids[valid]]+=1
            primary=torch.stack(losses).sum()/denominator;aux=torch.stack(auxiliary).sum()/denominator;objective=primary+.05*aux;backward(model,primary,aux);torch.nn.utils.clip_grad_norm_([p for p in model.parameters() if p.requires_grad],5);opt.step();updates+=1;total+=float(primary.detach())*denominator;aux_total+=float(aux.detach())*denominator;state={k:v.detach() for k,v in state.items()}
        assert np.all(seen==1);forecast,_=infer(model,v,decode=False);nll=float(forecast['nll'].mean());trace.append(dict(round=epoch,train_command_nll=total/len(seen),train_achieved_aux_nll=aux_total/len(seen),DEV_command_nll=nll,updates=updates,seconds=time.perf_counter()-start));torch.save(dict(state=model.state_dict(),optimizer=opt.state_dict(),mean=saved['mean'],std=saved['std'],config=saved['config'],persistent=model.persistent,round=epoch,source_commit=commit,torch_rng=torch.get_rng_state(),numpy_rng=rng.bit_generator.state,design_sha256=digest(REPORT/'L02-protocol.json')),directory/f'round-{epoch:02d}.pt');print(identifier,trace[-1],flush=True)
        if nll<best-.0001:best=nll;selected=epoch
        if epoch-selected>=6:break
    selected_state=torch.load(directory/f'round-{selected:02d}.pt',weights_only=False);model.load_state_dict(selected_state['state']);results={};comparisons={};hashes={}
    for split,d in data.items():
        forecast,goals=infer(model,d,decode=True);np.savez_compressed(directory/f'{split}-predictions.npz',**forecast);np.savez_compressed(directory/f'{split}-goals.npz',**goals);hashes[split]=digest(directory/f'{split}-predictions.npz');direction=np.load(BASE.parent/f'v7/{split}-direction.npy');masks={'all':np.ones(len(d['raw']['y']),bool)}
        if split=='train':masks['natural']=np.load(BASE.parent/'v9/frequency/natural-mask.npy')
        q=dict(raw=d['raw'],direction=direction,available=np.load(BASE.parent/f'v7/{split}-available.npy'),near=np.load(BASE.parent/f'v7/{split}-near_obstacle.npy'));results[split]={k:summary(q,forecast,m) for k,m in masks.items()}
        if split=='validation':
            comparisons['G00']=paired(q,forecast,d['baseline'])
            if identifier=='L02':
                with np.load(WORK/'runs/L01/validation-predictions.npz') as z:control={k:z[k] for k in z.files}
                comparisons['L01']=paired(q,forecast,control)
    immutable_json(REPORT/f'{identifier}.json',dict(selected_round=selected,trace=trace,parameters=sum(p.numel() for p in model.parameters()),completed_updates=updates,selected_updates=trace[selected-1]['updates'],results=results,comparisons=comparisons,predictions_sha256=hashes,checkpoint_sha256=digest(directory/f'round-{selected:02d}.pt'),design_sha256=digest(REPORT/'L02-protocol.json'),source_commit=commit,seconds=time.perf_counter()-tick,new_fits=1,reserved_opened=0,promoted=False,three_seed_confirmed=False));print('Completed',identifier,'fresh Sol xhigh review required',flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('identifier',choices=['L02']);run(p.parse_args().identifier)
