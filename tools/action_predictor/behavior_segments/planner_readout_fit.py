"""Movement-supervised edits of the existing 65-parameter planner readout."""
import argparse,time
from pathlib import Path
import numpy as np
import torch
from torch import nn
from . import planner_weight_edit as prior
from ..audit import immutable_json
from ..data import digest

ROOT=prior.ROOT;REPORT=ROOT/'tools/action_predictor/experiments/v63';WORK=ROOT/'.cambc/action-predictor/v63'
read,check,bindings=prior.read,prior.check,prior.bindings


class Readout(nn.Module):
    def __init__(self,weights):
        super().__init__();self.output=nn.Linear(64,1)
        with torch.no_grad():self.output.weight.copy_(weights['net.2.weight']);self.output.bias.copy_(weights['net.2.bias'])

    def forward(self,hidden):return self.output(hidden).squeeze(-1).tanh()


def export(net,weights):
    result={k:v.clone() for k,v in weights.items()};result['net.2.weight']=net.output.weight.detach().clone();result['net.2.bias']=net.output.bias.detach().clone();return result


def freeze():
    REPORT.mkdir(parents=True,exist_ok=True);prior.inputs();check(read(prior.REPORT/'verification.json'))
    n=covered=0
    for k in range(4):
        for r in torch.load(prior.WORK/f'fold{k}.pt',weights_only=False)['records']:
            if r['label']>=0:n+=1;covered+=r['label'] in set(r['routes']+[r['baseline']])
    immutable_json(REPORT/'plan.json',dict(sources=bindings([Path(__file__),Path(__file__).with_name('planner_readout_predictor.py'),Path(__file__).with_name('test_planner_readout.py')]),
        inputs=bindings([prior.REPORT/n for n in ('plan.json','selection.json','result.json','verification.json')]),seed=63001,epochs=16,lr=.003,batch=64,utility_weight=.1,temperature=4.,cap=900,minimum_activation=.1,
        oracle=dict(fitting_rows=n,available_correct_outputs=covered),
        intervention='Only existing final output weight64 and bias1 train. Warm start matching V61 heads edited by V62 selected scale/shift. Hidden layer,V59 inputs,movement outputs,candidate routes and retention rules fixed. No architecture changes.',
        loss='Soft choice over candidate routes and abstain, with temperature4 scores and minus log candidate count for candidate logits; abstain logit0. Movement label log likelihood of matching emitted route,plus0.1 per-query mean squared original four-turn utility error where labels available. Uncovered moves have zero selector gradient. This differentiable surrogate is not identical to hard retained-goal inference.',
        selection='Train original canonical fitting windows from other24games with matching fold representations. Evaluate epochs0,4,8,12,16 on held8games. Maximize actual hard combined movement count with positive/nonnegative utility and at least10percent active goals; then earlier epoch. One selected full refit on canonical fitting windows. No evaluation selection.',
        success='Exceed both V62 combined and V59 direct movement on unchanged513queries with positive goal utility and at least10percent activity. Report80percent target separately. No promotion merely from combined improvement.',
        limits='Only canonical fitting windows in this bounded diagnostic. Existing output coverage is a conditional oracle bound,not achievable policy accuracy or a global architectural ceiling. Preexposed groups, inherited fold exposure, teacher-forced history, proxy utilities and no playing-strength evidence. No subagents.'))


def inputs():
    p=read(REPORT/'plan.json');check(p);_,parent,architecture,cache,ids=prior.inputs();return p,parent,architecture,cache,ids


def prepare():
    _,parent,architecture,_,ids=inputs();torch.set_num_threads(4);WORK.mkdir(parents=True,exist_ok=False)
    windows,maps=prior.old.base.heading.expanded.read();windows=[w for i,w in enumerate(windows) if ids[i]['canonical']];mapping={r['key']:r['fold'] for r in ids}
    targets={(r['key'],r['position']):r for r in read(prior.old.WORK/'rows.json')};selected=read(prior.REPORT/'selection.json')['selected']
    for name in ['fold0','fold1','fold2','fold3','full']:
        bank=prior.build(windows,maps,name,parent,architecture,targets)
        bank['weights']=prior.edit(bank['weights'],selected['scale'],selected['shift'])
        for r in bank['records']:r['fold']=mapping[r['key']]
        torch.save(bank,WORK/(name+'.pt'));print('Prepared movement readout',name,flush=True)
    immutable_json(REPORT/'cache.json',dict(bindings=bindings(list(WORK.glob('*.pt'))),evaluation_used=False))


def pack(records,indices):
    rs=[records[i] for i in indices];m=max(1,max(len(r['routes']) for r in rs));h=torch.zeros(len(rs),m,64);mask=torch.zeros(len(rs),m,dtype=torch.bool)
    correct=torch.zeros(len(rs),m+1,dtype=torch.bool);target=torch.zeros(len(rs),m);known=torch.zeros(len(rs),m,dtype=torch.bool);movement=torch.tensor([r['label']>=0 for r in rs])
    for i,r in enumerate(rs):
        n=len(r['routes']);h[i,:n]=r['hidden'];mask[i,:n]=True;correct[i,-1]=r['baseline']==r['label'] and r['label']>=0
        for j,c in enumerate(r['candidates']):
            correct[i,j]=r['routes'][j]==r['label'] and r['label']>=0
            if r['utilities'] is not None and c['key'] in r['utilities']:target[i,j]=r['utilities'][c['key']];known[i,j]=True
    return dict(hidden=h,mask=mask,correct=correct,movement=movement,target=target,known=known)


def loss(net,d,p):
    s=net(d['hidden']);count=d['mask'].sum(-1).clamp_min(1)
    logits=(p['temperature']*s-count.log()[:,None]).masked_fill(~d['mask'],-1e9);logits=torch.cat((logits,torch.zeros(len(s),1)),1)
    probability=(logits.softmax(-1)*d['correct']).sum(-1)
    move=-probability[d['movement']].clamp_min(1e-6).log().mean() if d['movement'].any() else s.sum()*0
    available=d['known'].any(-1);per_query=((s-d['target']).square()*d['known']).sum(-1)/d['known'].sum(-1).clamp_min(1)
    utility=per_query[available].mean() if available.any() else s.sum()*0
    return move+p['utility_weight']*utility


def score(net,bank,fold=None):
    records=bank['records'] if fold is None else [r for r in bank['records'] if r['fold']==fold]
    return prior.simulate(dict(bank,records=records,weights=export(net,bank['weights'])))


def train(bank,indices,fold,p,epochs,directory,deadline):
    directory.mkdir(parents=True,exist_ok=False);torch.manual_seed(p['seed']);net=Readout(bank['weights']);opt=torch.optim.AdamW(net.parameters(),lr=p['lr']);rng=np.random.default_rng(p['seed'])
    torch.save(net.state_dict(),directory/'epoch-000.pt');values={0:score(net,bank,fold)} if fold is not None else {};trace=[]
    for epoch in range(1,epochs+1):
        order=rng.permutation(indices);norms=[]
        for start in range(0,len(order),p['batch']):
            if time.perf_counter()>deadline:raise TimeoutError('Readout budget exceeded')
            d=pack(bank['records'],order[start:start+p['batch']]);l=loss(net,d,p);opt.zero_grad();l.backward();norm=torch.nn.utils.clip_grad_norm_(net.parameters(),5.)
            assert torch.isfinite(l) and torch.isfinite(norm);opt.step();norms.append(float(norm))
        trace.append(dict(epoch=epoch,order=order.tolist(),norms=norms))
        if epoch%4==0:
            torch.save(net.state_dict(),directory/f'epoch-{epoch:03d}.pt')
            if fold is not None:values[epoch]=score(net,bank,fold)
            print(directory.name,epoch,values.get(epoch,{}).get('correct'),flush=True)
    torch.save(dict(model=net.state_dict(),optimizer=opt.state_dict(),rng=rng.bit_generator.state),directory/'final.pt');immutable_json(directory/'trace.json',dict(epochs=trace,validation=values));return net,values


def choose(cs,p):
    ok=[c for c in cs if c['active']>=p['minimum_activation']*c['available'] and c['utility_sum']>=0]
    if not ok:raise ValueError('No eligible readout checkpoint')
    return min(ok,key=lambda c:(-c['correct'],c['epoch']))


def fit():
    start=time.perf_counter();p,_,_,_,_=inputs();check(read(REPORT/'cache.json'));torch.set_num_threads(1);values={}
    for fold in range(4):
        bank=torch.load(WORK/f'fold{fold}.pt',weights_only=False);indices=np.array([i for i,r in enumerate(bank['records']) if r['fold']!=fold and (r['label']>=0 or r['utilities'] is not None)])
        _,v=train(bank,indices,fold,p,p['epochs'],WORK/f'fold{fold}',start+p['cap'])
        for e,s in v.items():values.setdefault(e,[]).append(s)
    cs=[dict(epoch=e,**prior.combined(v)) for e,v in values.items()];chosen=choose(cs,p)
    immutable_json(REPORT/'selection.json',dict(selected=chosen,candidates=cs,evaluation_used=False))
    bank=torch.load(WORK/'full.pt',weights_only=False);indices=np.array([i for i,r in enumerate(bank['records']) if r['label']>=0 or r['utilities'] is not None])
    net,_=train(bank,indices,None,p,chosen['epoch'],WORK/'refit',start+p['cap']);torch.save(export(net,bank['weights']),WORK/'selected.pt')
    bound=bindings([q for q in WORK.rglob('*') if q.is_file()]);elapsed=time.perf_counter()-start
    if elapsed>p['cap']:raise TimeoutError('Readout publication budget exceeded')
    immutable_json(REPORT/'fit.json',dict(bindings=bound,seconds=elapsed));print('SELECTED',chosen,flush=True)


def assess():
    inputs();check(read(REPORT/'fit.json'));selected=torch.load(WORK/'selected.pt',weights_only=True);results={}
    for split in ('fit','evaluation'):
        bank=torch.load(prior.WORK/(split+'.pt'),weights_only=False)
        assert torch.equal(selected['net.0.weight'],bank['weights']['net.0.weight']) and torch.equal(selected['net.0.bias'],bank['weights']['net.0.bias'])
        results[split]=prior.simulate(dict(bank,weights=selected))
    x=results['evaluation'];b=read(prior.REPORT/'result.json')['results']['evaluation']['edited'];gates=dict(combined=x['correct']>b['correct'],direct=x['correct']>x['baseline'],utility=x['utility_sum']>0,active=x['active']>=.1*x['available'])
    immutable_json(REPORT/'result.json',dict(results=results,checks=gates,all_checks_pass=all(gates.values()),target_met=x['correct']/x['rows']>=.8,bindings=bindings([WORK/'selected.pt',prior.WORK/'fit.pt',prior.WORK/'evaluation.pt']),promoted=False))
    print('EVALUATION',{k:v for k,v in x.items() if k not in ('predictions','selected')},gates,flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('command',choices=('freeze','prepare','fit','assess'));globals()[p.parse_args().command]()
