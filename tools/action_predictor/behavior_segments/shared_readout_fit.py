"""Ranking-sensitive updates to only the shared executor's64readout weights."""
import argparse,time
from pathlib import Path
import numpy as np
import torch
from torch import nn
from torch.nn import functional as F
from . import shared_goal_execution_fit as prior
from .goal_execution import local_features
from ..audit import immutable_json

ROOT=prior.ROOT;REPORT=ROOT/'tools/action_predictor/experiments/v72';WORK=ROOT/'.cambc/action-predictor/v72'
read,check,bindings=prior.read,prior.check,prior.bindings
ARMS=('likelihood','ranking')


def weights(name):
    e=read(prior.REPORT/'selection.json')['selected']['goal']['epoch'];path=prior.WORK/'goal-selected.pt' if name=='full' else prior.WORK/'goal'/name/f'epoch-{e:03d}.pt';return torch.load(path,weights_only=True)


def freeze():
    REPORT.mkdir(parents=True,exist_ok=True);prior.inputs();check(read(prior.REPORT/'verification.json'))
    immutable_json(REPORT/'plan.json',dict(sources=bindings([Path(__file__),Path(__file__).with_name('shared_readout_predictor.py'),Path(__file__).with_name('test_shared_readout.py')]),inputs=bindings([prior.REPORT/n for n in ('plan.json','cache.json','fit.json','selection.json','result.json','verification.json','weight-inspection.json')]),
        seed=72001,epochs=8,every=4,lr=.003,batch=128,clip=5.,anchor=.1,margin=.25,fit_seconds_cap=600,
        intervention='Freeze all V70 feature/goal/backbone weights. Optimize only64 final movement readout weights from each matching selected V70 goal checkpoint. Keep shared output bias fixed. Likelihood control:meanCE plus0.1sum((w-w0)^2). Ranking treatment adds meanReLU(0.25+max_supported_wrong_logit-gold_logit). Singleton support contributes zero hinge. No new parameters or runtime branches. Adam,no weight decay.',
        matched='Same starting weights,rows,permutations,batches,optimizer,8passes and checkpoints0/4/8. All12318fitting movements,whole-game folds,no future-goal inputs. Frozen hidden activations are cached before weight fitting.',
        selection='Select each arm independently by highest count on1997canonical held fitting movements,subject to NLL<=V59direct+0.01 and neither active/absent cohort loses>1point vs V70 initial. Tie lowerNLL,then earlier epoch. Epoch0 eligible. One full refit per arm. No evaluation selection.',
        success='Ranking must exceed V70original311,V59direct318,and matchedlikelihood on unchanged513moves;NLL<=direct+0.01;neither goal-present/absent loses>2points vsdirect. All required.80percent requires411/513. No promotion.',
        interpretation='Tests whether a ranking-sensitive64weight readout update improves decisions; declining likelihood alone did not. It does not establish an objective mismatch as the causal bottleneck. Reused games,inherited exposure,in-sample selector predictions,one seed,observed histories remain. No subagents.'))


def inputs():
    p=read(REPORT/'plan.json');check(p);prior.inputs();return p


@torch.no_grad()
def bank(name):
    data=torch.load(prior.WORK/(name+'.pt'),weights_only=False);net=prior.new('goal',read(prior.REPORT/'plan.json'));net.load_state_dict(weights(name));x=torch.cat((local_features(data['context']),data['goal']),-1);hidden=net.layers[0](x).tanh();return dict(hidden=hidden,baseline=data['baseline']+net.layers[2].bias,support=data['support'],labels=data['labels'],records=data['records'])


class Readout(nn.Module):
    def __init__(self,weight):super().__init__();self.weight=nn.Parameter(weight.clone())
    def forward(self,hidden,baseline):return baseline+F.linear(hidden,self.weight).squeeze(-1)


def objective(raw,labels,support,weight,initial,p,ranking):
    raw=raw.masked_fill(~support,-1e9);ce=F.cross_entropy(raw,labels);gold=raw.gather(1,labels[:,None]).squeeze(1);wrong=raw.scatter(1,labels[:,None],-1e9).max(-1).values;hinge=F.relu(p['margin']+wrong-gold);hinge=torch.where(support.sum(-1)>1,hinge,torch.zeros_like(hinge)).mean()
    return ce+p['anchor']*(weight-initial).square().sum()+(hinge if ranking else 0.)


@torch.no_grad()
def score(net,data,indices):
    predictions=[];losses=[];rs=[data['records'][int(i)] for i in indices]
    for start in range(0,len(indices),256):
        ix=indices[start:start+256];lp=net(data['hidden'][ix],data['baseline'][ix]).masked_fill(~data['support'][ix],-1e9).log_softmax(-1);y=data['labels'][ix];predictions.extend(lp.argmax(-1).tolist());losses.extend((-lp.gather(1,y[:,None]).squeeze(1)).tolist())
    cs={}
    for name,active in [('all',None),('goal',True),('no_goal',False)]:
        ix=[i for i,r in enumerate(rs) if active is None or r['active']==active];cs[name]=dict(rows=len(ix),correct=sum(predictions[i]==rs[i]['label'] for i in ix),nll_sum=sum(losses[i] for i in ix))
    return dict(**cs['all'],cohorts=cs,predictions=predictions,losses=losses)


def train(arm,data,name,indices,held,p,epochs,directory,deadline):
    directory.mkdir(parents=True,exist_ok=False);initial=weights(name)['layers.2.weight'];net=Readout(initial);opt=torch.optim.Adam(net.parameters(),lr=p['lr']);rng=np.random.default_rng(p['seed']);trace=[];values={0:score(net,data,held)} if held is not None else {};torch.save(net.state_dict(),directory/'epoch-000.pt')
    for epoch in range(1,epochs+1):
        order=rng.permutation(indices);norms=[]
        for start in range(0,len(order),p['batch']):
            if time.perf_counter()>=deadline:raise TimeoutError('Readout fit cap')
            ix=order[start:start+p['batch']];raw=net(data['hidden'][ix],data['baseline'][ix]);loss=objective(raw,data['labels'][ix],data['support'][ix],net.weight,initial,p,arm=='ranking');opt.zero_grad();loss.backward();norm=torch.nn.utils.clip_grad_norm_(net.parameters(),p['clip']);assert torch.isfinite(loss) and torch.isfinite(norm);opt.step();norms.append(float(norm))
        trace.append(dict(epoch=epoch,order=order.tolist(),norms=norms))
        if epoch%p['every']==0:
            torch.save(net.state_dict(),directory/f'epoch-{epoch:03d}.pt')
            if held is not None:values[epoch]=score(net,data,held)
            print(arm,name,epoch,values.get(epoch,{}).get('correct'),flush=True)
    torch.save(dict(model=net.state_dict(),optimizer=opt.state_dict(),rng=rng.bit_generator.state),directory/'final.pt');immutable_json(directory/'trace.json',dict(epochs=trace,validation=values));return net,values


def combine(vs):
    return dict(**{k:sum(v[k] for v in vs) for k in ('rows','correct','nll_sum')},cohorts={c:{k:sum(v['cohorts'][c][k] for v in vs) for k in ('rows','correct','nll_sum')} for c in ('goal','no_goal')})


def select(cs,direct):
    original=next(c for c in cs if c['epoch']==0);eligible=[c for c in cs if c['nll_sum']<=direct+.01*c['rows'] and all(c['cohorts'][k]['correct']>=original['cohorts'][k]['correct']-.01*c['cohorts'][k]['rows'] for k in ('goal','no_goal'))];return prior.previous.select(eligible)


def fit():
    start=time.perf_counter();p=inputs();torch.set_num_threads(1);WORK.mkdir(parents=True,exist_ok=False);data={n:bank(n) for n in ['fold0','fold1','fold2','fold3','full']};cs={};chosen={};direct=read(prior.REPORT/'selection.json')['candidates']['goal'][0]['nll_sum']
    for arm in ARMS:
        values={}
        for fold in range(4):
            name=f'fold{fold}';b=data[name];rs=b['records'];ix=np.array([i for i,r in enumerate(rs) if r['fold']!=fold]);held=np.array([i for i,r in enumerate(rs) if r['fold']==fold and r['canonical']]);_,v=train(arm,b,name,ix,held,p,p['epochs'],WORK/arm/name,start+p['fit_seconds_cap'])
            for e,s in v.items():values.setdefault(e,[]).append(s)
        cs[arm]=[dict(epoch=e,**combine(vs)) for e,vs in values.items()];chosen[arm]=select(cs[arm],direct)
    immutable_json(REPORT/'selection.json',dict(candidates=cs,selected=chosen,evaluation_used=False))
    for arm in ARMS:
        b=data['full'];net,_=train(arm,b,'full',np.arange(len(b['records'])),None,p,chosen[arm]['epoch'],WORK/arm/'refit',start+p['fit_seconds_cap']);full=weights('full');full['layers.2.weight']=net.weight.detach().clone();torch.save(full,WORK/(arm+'-selected.pt'))
    bound=bindings([q for q in WORK.rglob('*') if q.is_file()]);elapsed=time.perf_counter()-start
    if elapsed>=p['fit_seconds_cap']:raise TimeoutError('Readout publication cap')
    immutable_json(REPORT/'fit.json',dict(bindings=bound,seconds=elapsed));print('SELECTED',chosen,flush=True)


def assessment():
    values={};p=read(prior.REPORT/'plan.json');old=read(prior.REPORT/'result.json')['results']
    for split in ('fit','evaluation'):
        b=torch.load(prior.WORK/(split+'.pt'),weights_only=False);values[split]={}
        for arm in ARMS:
            net=prior.new('goal',p);net.load_state_dict(torch.load(WORK/(arm+'-selected.pt'),weights_only=True));v=prior.score(net,b);before=old[split]['direct']['predictions'];v['vs_direct']=dict(rescues=sum(a!=r['label'] and z==r['label'] for a,z,r in zip(before,v['predictions'],b['records']) if r['label']>=0),regressions=sum(a==r['label'] and z!=r['label'] for a,z,r in zip(before,v['predictions'],b['records']) if r['label']>=0));values[split][arm]=v
    x=values['evaluation'];g=x['ranking'];d=old['evaluation']['direct'];original=old['evaluation']['goal'];checks=dict(original=g['correct']>original['correct'],direct=g['correct']>d['correct'],likelihood=g['correct']>x['likelihood']['correct'],nll=g['nll_sum']<=d['nll_sum']+.01*g['rows'])
    for c in ('goal','no_goal'):checks[c+'_guard']=g['cohorts'][c]['correct']>=d['cohorts'][c]['correct']-.02*d['cohorts'][c]['rows']
    return dict(results=values,checks=checks,all_checks_pass=all(checks.values()),target_met=g['rows']==513 and g['correct']>=411,promoted=False)


def assess():
    inputs();check(read(REPORT/'fit.json'));torch.set_num_threads(4);r=assessment();immutable_json(REPORT/'result.json',dict(**r,bindings=bindings([*(WORK/(a+'-selected.pt') for a in ARMS),prior.WORK/'fit.pt',prior.WORK/'evaluation.pt'])));print('RESULT',r['checks'],{a:(v['correct'],v['rows'],v['nll_sum']/v['rows']) for a,v in r['results']['evaluation'].items()},flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('command',choices=('freeze','fit','assess'));globals()[parser.parse_args().command]()
