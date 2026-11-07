"""Declared posthoc constant-prior control; not a fitted or promoted treatment."""
import json
import numpy as np
import torch
from .protocol import BASE,WORK,REPORT
from .fit import load
from .evaluate import read,summarize
from .integration import type_distribution,loss_overlay,commands
from ..command_mixture import canonical
from ..audit import immutable_json
from ..data import digest

def run():
    plan=REPORT/'T00-prior-control-plan.json';assert plan.exists()
    natural=np.load(BASE.parent/'v9/frequency/natural-mask.npy');train=load('train');prior=float((train['raw']['y'][natural]==14).mean());results={}
    for split in ('train','validation'):
        d=train if split=='train' else load(split);old=torch.from_numpy(np.array(d['type-logp']));logit=torch.full((len(old),),float(np.log(prior/(1-prior))),dtype=torch.float64);types=type_distribution(old,logit);a,_=commands(types.numpy(),old.numpy(),d['modes'],d['mode_joint']);a['nll']=loss_overlay(torch.from_numpy(d['base_nll']),old,types,torch.from_numpy(d['raw']['y']).long()).numpy();a['ward_probability']=np.exp(types[:,14].numpy());p=read(WORK/f'evaluations/T00-only/{split}-primary.npz');direction=np.load(BASE.parent/f'v7/{split}-direction.npy');pack=lambda v:canonical(np.stack((v['prediction'],v['coordinate'],v['priority']),-1));same=(pack(a)==pack(p)).all(-1);masks={'all':np.ones(len(same),bool)}
        if split=='train':masks['natural']=natural
        results[split]={name:dict(summary=summarize(d['raw'],a,m,direction),semantic_commands_differ_from_T00=int((~same&m).sum()),T00_prediction_sha256=digest(WORK/f'evaluations/T00-only/{split}-primary.npz')) for name,m in masks.items()}
    immutable_json(REPORT/'T00-prior-control.json',dict(results=results,prior=prior,plan_sha256=digest(plan),source_sha256=digest(__file__),command='python -m tools.action_predictor.ward_experts.prior_control',qualification='Posthoc fixed diagnostic; no fit, tuning, checkpoint/threshold choice or promotion. Equality of hard predictions does not imply equal probabilities or learned ranking.',new_fits=0,reserved_opened=0));print('Constant-prior diagnostic complete',flush=True)

if __name__=='__main__':run()
