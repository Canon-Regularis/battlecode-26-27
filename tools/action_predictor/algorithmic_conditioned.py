"""A01 shared candidate-conditioned scorer; same support/loss/decoder as A00."""
import json,time,sys
from pathlib import Path
import numpy as np
import torch
from torch import nn
from .algorithmic.study import ROOT,WORK,REPORT
from .algorithmic.library import NAMES
from .algorithmic_fit import load,decode,evaluate
from .audit import immutable_json
from .data import digest
from . import reliable_train as rt

DIM=44
def descriptors(c,grid):
    result=np.zeros((len(c),len(NAMES),DIM),np.float16)
    row,col=np.where((c[:,:,0]>=0)&(c[:,:,1]>=0)&(c[:,:,1]<289))
    result[row,col,:20]=grid[row,c[row,col,1]]
    row,col=np.where(c[:,:,0]>=0);result[row,col,20+c[row,col,0]]=1
    for k in range(15):result[:,k,35+k//3]=1;result[:,k,41+k%3]=1
    for k in range(15,len(NAMES)):result[:,k,40]=1
    result[c[:,:,0]<0]=0
    return result

class CandidateSelector(nn.Module):
    def __init__(self,features):
        super().__init__();self.context=nn.Linear(features,32);self.candidate=nn.Linear(DIM,32);self.dropout=nn.Dropout(.1);self.score=nn.Linear(32,1);self.fallback=nn.Linear(32,1)
        nn.init.zeros_(self.score.weight);nn.init.constant_(self.score.bias,-4);nn.init.zeros_(self.fallback.weight);nn.init.constant_(self.fallback.bias,4)
    def forward(self,x,available,desc):
        h=self.dropout(torch.tanh(self.context(x)));points=self.score(torch.tanh(h[:,None]+self.candidate(desc.float()))).squeeze(-1)
        return torch.cat((self.fallback(h),points),-1).masked_fill(~available,-1e9).log_softmax(-1)

def prepare(split,data):
    p=WORK/f'{split}-candidate-descriptors.f16.npy'
    if p.exists():raise ValueError('Existing descriptors preserved; inspect receipt rather than replace')
    path=ROOT/('.cambc/action-predictor/v5/combined-train.npz' if split=='train' else '.cambc/action-predictor/v4/validation.npz')
    with np.load(path) as z:grid=z['grid']
    out=np.lib.format.open_memmap(p,mode='w+',dtype=np.float16,shape=(len(data['c']),len(NAMES),DIM))
    for a in range(0,len(out),2048):out[a:a+2048]=descriptors(data['c'][a:a+2048],grid[a:a+2048])
    out.flush();del out,grid
    return np.load(p,mmap_mode='r')

@torch.no_grad()
def infer(model,data,mean,std):
    model.eval();scores=[];loss=[]
    for a in range(0,len(data['x']),512):
        b=a+512;x=torch.from_numpy(np.clip((data['x'][a:b]-mean)/std,-10,10));desc=torch.from_numpy(np.array(data['desc'][a:b]));lp=model(x,data['available'][a:b],desc);scores.append(lp.exp().numpy());loss.append((-torch.logsumexp(lp.double()+data['mass'][a:b].clamp_min(1e-300).log(),-1)).numpy())
    return np.concatenate(scores),np.concatenate(loss)

def run():
    rt.setup(20261107);directory=WORK/'runs/A01';assert not directory.exists(),'Existing attempted fit preserved';directory.mkdir(parents=True)
    prior=json.loads((REPORT/'A00.json').read_text());assert digest(Path(__file__).with_name('algorithmic_fit.py'))==json.loads((REPORT/'A00-plan.json').read_text())['source_sha256']
    plan=dict(id='A01',source_sha256=digest(__file__),hypothesis='Shared candidate-conditioned scoring learns command-specific relative geometry and visible target attributes, beyond A00 global slot scoring. Same frozenC00simple support, alloriginalrows, sampler,seed,optimizer,loss,history,G00fallback,harddecoder,checkpoint rule. Not a route to all-category90% under current support.',
        review_sha256=digest(REPORT/'A00-review.md'),analysis_sha256=digest(REPORT/'A00-analysis.json'),roundtrip_sha256=digest(REPORT/'A00-causal-roundtrip.json'),D00_sha256=digest(REPORT/'D00.json'),
        descriptors='44causal channels:20frozen PRE grid channels at emitted coordinate (relative offset,terrain,movementmask,visible category distances/counts/HP,altar distance,previous move);15actiononehot;6objective categories;3planner tie categories. Nonspatial grid channels0. No IDs/currentlabels/futureoutcome. No new objectives or actions. Descriptors for missing candidates zero.',
        architecture='global445->32tanh/dropout.1;candidate44->32;sharedtanh(context+candidate)->scalar;separatefallbackscalar;initialized pointbias-4,fallback4,zero output weights;fixed cached input scaling, no descriptor fit normalization',
        training=dict(seed=20261107,optimizer='AdamW',lr=.001,weight_decay=.01,batch=512,gradient_clip=5,max_rounds=35,patience=6,improvement=.0001,selection='minimum full originalDEVobservedjointNLL',loss='same A00marginalcommandlikelihood;no intent labels',rows=433071),
        decoder='A00originalhardroute held fixed regardless D00diagnostic; actionselection trainable. Boundedsupport ceiling table in A00analysis, no sparsecategory certification.',budget='Second and final pilot in originalC00budget. No repeat seeds unless original A00prospective promising trigger passes AND postfitreview supports allocation. Further support/persistence fits require separately frozen justified budget.',promotion='Original success targets binding, all43DEVshops strictfailure,altar/teleport2each uncertified. CompareG00,A00,originalsimplemovement. FreshSolxhighreview immediately after completion.')
    immutable_json(REPORT/'A01-plan.json',plan)
    data={s:load(s) for s in ('train','validation')}
    for split,d in data.items():d['desc']=prepare(split,d)
    immutable_json(REPORT/'A01-descriptors.json',dict(plan_sha256=digest(REPORT/'A01-plan.json'),files={s:digest(WORK/f'{s}-candidate-descriptors.f16.npy') for s in data},source_sha256=digest(__file__),frozen_candidate_reports={s:digest(REPORT/f'C00-{s}.json') for s in data}))
    t=data['train'];v=data['validation'];mean=t['x'].mean(0);std=np.maximum(t['x'].std(0),.01);x=torch.from_numpy(np.clip((t['x']-mean)/std,-10,10));model=CandidateSelector(x.shape[1]);opt=torch.optim.AdamW(model.parameters(),lr=.001,weight_decay=.01);rng=np.random.default_rng(20261107);best=float('inf');selected=0;trace=[];start=time.perf_counter()
    for epoch in range(1,36):
        model.train();losses=[];tick=time.perf_counter()
        for indices in np.array_split(rng.permutation(len(x)),int(np.ceil(len(x)/512))):
            idx=torch.from_numpy(indices);desc=torch.from_numpy(np.array(t['desc'][indices]));opt.zero_grad();lp=model(x[idx],t['available'][idx],desc);loss=-torch.logsumexp(lp.double()+t['mass'][idx].clamp_min(1e-300).log(),-1).mean();loss.backward();torch.nn.utils.clip_grad_norm_(model.parameters(),5);opt.step();losses.append(float(loss.detach()))
        scores,nll=infer(model,v,mean,std);value=float(nll.mean());trace.append(dict(round=epoch,training_loss=float(np.mean(losses)),dev_nll=value,seconds=time.perf_counter()-tick));torch.save(dict(state=model.state_dict(),mean=mean,std=std,epoch=epoch,optimizer=opt.state_dict(),rng=torch.get_rng_state(),numpy_rng=rng.bit_generator.state,plan_sha256=digest(REPORT/'A01-plan.json')),directory/f'round-{epoch:02d}.pt');print(trace[-1],flush=True)
        if value<best-.0001:best=value;selected=epoch
        if epoch-selected>=6:break
    model.load_state_dict(torch.load(directory/f'round-{selected:02d}.pt',weights_only=False)['state']);reports={}
    for split,d in data.items():
        scores,nll=infer(model,d,mean,std);pred,fallback=decode(scores,d);pred['nll']=nll;np.savez_compressed(directory/f'{split}-predictions.npz',**pred,fallback=fallback,selector_weights=scores);reports[split]=evaluate(d['raw'],pred,np.load(ROOT/'.cambc/action-predictor/v7'/f'{split}-direction.npy'))
    immutable_json(REPORT/'A01.json',dict(plan_sha256=digest(REPORT/'A01-plan.json'),selected_round=selected,trace=trace,reports=reports,checkpoint_sha256=digest(directory/f'round-{selected:02d}.pt'),prediction_hashes={s:digest(directory/f'{s}-predictions.npz') for s in data},parameters=sum(p.numel() for p in model.parameters()),optimizer_updates=len(trace)*int(np.ceil(433071/512)),training_seconds=time.perf_counter()-start,reserved_opened=0,three_seed_confirmed=False))
    print('CompletedA01;freshSolxhighreviewrequired',flush=True)

if __name__=='__main__':run()
