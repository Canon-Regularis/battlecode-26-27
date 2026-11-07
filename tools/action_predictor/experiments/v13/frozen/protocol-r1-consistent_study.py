"""Prospective V13 matched selection study; no implicit fits or repeat seeds."""
import argparse,json,time
from pathlib import Path
import numpy as np
import torch
from torch import nn
from .consistent_data import ROOT,BASE,WORK,REPORT,JOBS,GLOBAL_DIM,DESC_DIM
from .proposal_generator import NAMES
from .command_mixture import log_mass,decode
from .algorithmic_fit import evaluate
from .audit import immutable_json
from .data import digest
from . import reliable_train as rt

VARIANTS={'B00':'baseline','B01':'current_goals','B02':'current_goals_and_causal_memory'}

def freeze():
    WORK.mkdir(parents=True,exist_ok=True);REPORT.mkdir(parents=True,exist_ok=True)
    sources={str(p.relative_to(ROOT)):digest(p) for p in [Path(__file__).with_name(n) for n in ('command_mixture.py','goal_memory.py','consistent_data.py','consistent_study.py','test_command_mixture.py','test_goal_memory.py','proposal_generator.py','proposal_predictor.py','proposal_targets.cjs')]}
    plan=dict(id='V13',question='Does consistent joint-probability decoding repair the fallback mismatch, and do current goal information or bounded causal persistent goal evidence improve selection?',
        first='Resolve the probability contract before fitting: exact modeled observed-representation MAP over all point commands plus one global conditional mode per fallback family. Same Q for observed likelihood and candidate probability; sum duplicate explanations. No opaque fallback-weight veto.',
        qualifications='Shop remains a marginalized observed bucket with unavailable arguments and strict failures. Coordinate/entity identity ambiguity and outside/missing coordinate buckets remain explicit. This is not exact probability over complete original shop API commands or engine-legality certification.',
        variants=VARIANTS,features=dict(global_dim=GLOBAL_DIM,candidate_dim=DESC_DIM,baseline='445legacyPRE+last8actualrootfeatures;44staticcandidategrid/action/sourcefeatures',goals='40currentgoalglobalfeatures+10perpointdistance/progressfeatures for same5objectivefamilies',memory='21global+6perpointfeatures from forward actual-root goal identity filter. .93decay per actualroot; bounded64identitystates; only personally available action-PRE goals receive movement-progress evidence; missing PRE count explicit; last known remembered location and current-visibility/age explicit. IDs internal association only. No backward smoothing/currentaction/future/sampledrowrecurrence.'),
        architecture='Same506->64tanh/dropout.1 context and60->64sharedcandidateembedding;score64->1,fallback64->1. Ignored feature blocks zeroed AFTER same fullTRAINnormalization. Same parameter initialization, architecture, update budget, row order, seed, point library57, fallbackQ, loss, decoder and regularization in every arm.',
        training=dict(seed=20261110,optimizer='AdamW',lr=.001,weight_decay=.01,batch=512,gradient_clip=5,max_rounds=35,patience=6,minimum_improvement=.0001,checkpoint='full original DEV observed joint NLL',rows=433071,sampling='original augmented TRAIN, unweighted; matched natural TRAIN results reported separately',initialization='zero output weights;fallbackbias0;pointbias-log57, roughly half initial mass to fallback when all slots available'),
        controls=['G00 original action-first hard prediction','Q-only global observed-command MAP','fixed .9fallback/.1uniform available-point mixture using identical decoder','retained A00/A01 and D00 diagnostics, clearly different historical support/decoder'],
        budget='Exactly3 small selector pilots B00/B01/B02, sequential fresh requested Solxhighreview after each substantivefit. No large model, automatic architecture search, threshold tuning or checkpoint replacement. Repeat seeds only under a separately reported promising allocation after original macro/movement/loss/targeting guards; three-seed claim unavailable until actually run.',
        metrics=['all original14439DEVrows/categories','paired whole-group2000resamples seed20261106','TRAIN natural vs augmented, identical metric definitions','rescues/regressions on available point opportunities, destination continuation/change','actionmacroF1/confusion/typeFP/jointFP','all-family parameters from all-family mixture conditional modes, correctlytyped conditional separate','effective fallback probability and selected-command fallback contribution','no claims that oracle coverage is achieved accuracy'],
        ranked=['Verify same mixture probability algebra and exhaustive finite MAP examples','Prepare repaired fullTRAIN and DEV proposals plus matched goal/memory features from alreadyrecordedeligibleevidence','Measure Q-only/fixedmixture controls and rawPRE parity','Fit B00, review, then B01, review, then B02, review','Report paired deltas and diagnostic limitations; update DRAFTPR11 only'],
        datasets=dict(train='39386010575ad30add064fdae750680f34cfcc732c4fd00fb657875ff4c61ffb',validation='01a15e1e10f68922334a5367bb825c8ef9bbe228ae7a9e86e92aae9609b204ed'),jobs_sha256=digest(JOBS),sources=sources,
        safety='Both75+75reservedpartitionssealed. No matches/proposedaction simulations/downloads/bot edits/deployment. No game/group/mapID features. All43DEVshops strictunassessed failures; sparsealtar/teleport/submit uncertified. Original targets unchanged; no promotion on aggregate gain.')
    immutable_json(REPORT/'protocol.json',plan);return plan

class ConsistentSelector(nn.Module):
    def __init__(self):
        super().__init__();self.context=nn.Linear(GLOBAL_DIM,64);self.candidate=nn.Linear(DESC_DIM,64);self.dropout=nn.Dropout(.1);self.score=nn.Linear(64,1);self.fallback=nn.Linear(64,1)
        nn.init.zeros_(self.score.weight);nn.init.constant_(self.score.bias,-np.log(len(NAMES)));nn.init.zeros_(self.fallback.weight);nn.init.zeros_(self.fallback.bias)
    def forward(self,x,desc,available):
        h=self.dropout(torch.tanh(self.context(x)));points=self.score(torch.tanh(h[:,None]+self.candidate(desc))).squeeze(-1)
        return torch.cat((self.fallback(h),points),-1).masked_fill(~available,-torch.inf).log_softmax(-1)

def load(split):
    result={k:np.load(WORK/f'{split}-{k}.npy',mmap_mode='r') for k in ('c','x','desc','point-logq','mode-logq','modes','target-logq','matches')}
    path=BASE/'combined-train.npz' if split=='train' else BASE.parent/'v4/validation.npz'
    with np.load(path) as z:result['raw']={k:z[k] for k in ('y','py','priority','group','flags','hp_alive','channel','ward_charges','gems','move_mask','restrictions','ability_ready','shop')}
    return result

def inputs(data,index,mean,std,variant):
    x=np.clip((np.array(data['x'][index])-mean)/std,-10,10);desc=np.array(data['desc'][index],dtype=np.float32)
    if variant=='B00':x[:,445:]=0;desc[:,:,44:]=0
    elif variant=='B01':x[:,485:]=0;desc[:,:,54:]=0
    available=np.column_stack((np.ones(len(x),bool),data['c'][index,:,0]>=0))
    return torch.from_numpy(x),torch.from_numpy(desc),torch.from_numpy(available)

@torch.no_grad()
def infer(model,data,mean,std,variant):
    model.eval();scores=[];nll=[]
    for a in range(0,len(data['x']),512):
        idx=slice(a,a+512);lp=model(*inputs(data,idx,mean,std,variant));scores.append(lp.numpy());nll.append(-log_mass(lp,torch.from_numpy(np.array(data['matches'][idx])),torch.from_numpy(np.array(data['target-logq'][idx]))).numpy())
    return np.concatenate(scores),np.concatenate(nll)

def predictions(scores,nll,data):
    command,confidence,fraction,families=decode(scores,data['c'],data['point-logq'],data['modes'],data['mode-logq'],return_families=True)
    return dict(prediction=command[:,0],coordinate=command[:,1],priority=command[:,2],nll=nll,command_log_probability=confidence,point_probability_fraction=fraction,family_commands=families,log_weights=scores)

def run(variant):
    plan=freeze();rt.setup(20261110);directory=WORK/'runs'/variant;assert not directory.exists(),'Preserve every attempted fit';directory.mkdir(parents=True)
    data={s:load(s) for s in ('train','validation')};t=data['train'];v=data['validation'];mean=np.array(t['x']).mean(0);std=np.maximum(np.array(t['x']).std(0),.01);model=ConsistentSelector();opt=torch.optim.AdamW(model.parameters(),lr=.001,weight_decay=.01);rng=np.random.default_rng(20261110);trace=[];best=float('inf');selected=0;start=time.perf_counter()
    for epoch in range(1,36):
        model.train();losses=[];tick=time.perf_counter()
        for ids in np.array_split(rng.permutation(len(t['x'])),int(np.ceil(len(t['x'])/512))):
            opt.zero_grad();lp=model(*inputs(t,ids,mean,std,variant));loss=-log_mass(lp,torch.from_numpy(np.array(t['matches'][ids])),torch.from_numpy(np.array(t['target-logq'][ids]))).mean();loss.backward();torch.nn.utils.clip_grad_norm_(model.parameters(),5);opt.step();losses.append(float(loss.detach()))
        scores,nll=infer(model,v,mean,std,variant);value=float(nll.mean());trace.append(dict(round=epoch,training_loss=float(np.mean(losses)),dev_nll=value,seconds=time.perf_counter()-tick));torch.save(dict(state=model.state_dict(),mean=mean,std=std,epoch=epoch,variant=variant,optimizer=opt.state_dict(),rng=torch.get_rng_state(),numpy_rng=rng.bit_generator.state,protocol_sha256=digest(REPORT/'protocol.json')),directory/f'round-{epoch:02d}.pt');print(variant,trace[-1],flush=True)
        if value<best-.0001:best=value;selected=epoch
        if epoch-selected>=6:break
    model.load_state_dict(torch.load(directory/f'round-{selected:02d}.pt',weights_only=False)['state']);reports={}
    for split,d in data.items():
        scores,nll=infer(model,d,mean,std,variant);pred=predictions(scores,nll,d);np.savez_compressed(directory/f'{split}-predictions.npz',**pred);reports[split]=evaluate(d['raw'],pred,np.load(BASE.parent/f'v7/{split}-direction.npy'))
        if split=='train':
            mask=np.load(BASE.parent/'v9/frequency/natural-mask.npy');reports['natural_train']=evaluate({k:v[mask] for k,v in d['raw'].items()},{k:v[mask] for k,v in pred.items()},np.load(BASE.parent/'v7/train-direction.npy')[mask])
    immutable_json(REPORT/f'{variant}.json',dict(variant=VARIANTS[variant],protocol_sha256=digest(REPORT/'protocol.json'),selected_round=selected,trace=trace,reports=reports,checkpoint_sha256=digest(directory/f'round-{selected:02d}.pt'),prediction_hashes={s:digest(directory/f'{s}-predictions.npz') for s in data},parameters=sum(p.numel() for p in model.parameters()),optimizer_updates=len(trace)*int(np.ceil(433071/512)),measured_fit_interval_seconds=time.perf_counter()-start,interval_scope='Firstoptimization through finalallTRAIN/DEV inference/evaluation/serialization, excludesdata preparation/loading/normalization.',new_fits=1,reserved_opened=0,three_seed_confirmed=False))
    print('Completed',variant,'freshSolxhighreviewrequired',flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('variant',choices=list(VARIANTS));run(p.parse_args().variant)
