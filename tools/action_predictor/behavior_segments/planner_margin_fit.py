"""Direct readout weight editing with a hard-choice-aligned latent margin loss."""
import argparse,time
from pathlib import Path
import numpy as np
import torch
from . import planner_readout_fit as prior
from ..audit import immutable_json
from ..data import digest

ROOT=prior.ROOT;REPORT=ROOT/'tools/action_predictor/experiments/v65';WORK=ROOT/'.cambc/action-predictor/v65'
read,check,bindings=prior.read,prior.check,prior.bindings


def freeze():
    REPORT.mkdir(parents=True,exist_ok=True);prior.inputs();check(read(prior.REPORT/'verification.json'));check(read(prior.REPORT/'cache.json'))
    immutable_json(REPORT/'plan.json',dict(sources=bindings([Path(__file__),Path(__file__).with_name('planner_margin_predictor.py'),Path(__file__).with_name('test_planner_margin.py')]),
        inputs=bindings([prior.REPORT/n for n in ('plan.json','cache.json','selection.json','result.json','verification.json')]),seed=65001,epochs=16,lr=.003,batch=64,utility_weight=.1,margin=.2,cap=300,minimum_activation=.1,
        intervention='Existing65parameter readout only,warm start V62-edited matching V61 heads using verified V63 caches. Replace soft aggregate-choice loss with latent maximum margin: best correct-output candidate/abstention must beat best incorrect-output candidate/abstention by0.2. Candidate score tanh; abstention score0. Margin exceeds fixed0.15 retention tolerance. Retention-aware hard inference still selects checkpoints.',
        loss='Movement queries with at least one correct available output and at least one incorrect output contribute ReLU(0.2+best_wrong_score-best_correct_score),averaged over all movement rows so uncovered rows contribute zero. Nonmovement rows have no movement loss. Same0.1 progress-utility regularizer. Hindsight selects a correct-output latent candidate only inside training loss,never inference.',
        selection='Four matching fitting-game folds; canonical other24game windows train and held8game windows validate. Epochs0,4,8,12,16. Highest combined movement count with nonnegative utility and10percent activity; then earliest epoch. One full refit selected duration. No evaluation-dependent choice. Fixed300second fitting/refit cap.',
        scope='Follows failed V63 surrogate and runs independently of pending V64 map adaptation. No new inputs/architecture. Fixed-output oracle coverage remains1598/1997 fitting moves. Hard margin does not guarantee learned ranking,retention behavior or generalization. Repeatedly exposed research evaluation,teacher-forced history,inferred goals,no autonomous strategy proof.'))


def inputs():
    p=read(REPORT/'plan.json');check(p);check(read(prior.REPORT/'cache.json'));return p


def loss(net,d,p):
    score=net(d['hidden']);choices=torch.cat((score,torch.zeros(len(score),1)),1);valid=torch.cat((d['mask'],torch.ones(len(score),1,dtype=torch.bool)),1)
    good=d['correct']&valid;bad=(~d['correct'])&valid;eligible=d['movement']&good.any(-1)&bad.any(-1)
    best_good=choices.masked_fill(~good,-1e9).max(-1).values;best_bad=choices.masked_fill(~bad,-1e9).max(-1).values
    move=(torch.relu(p['margin']+best_bad-best_good)*eligible).sum()/d['movement'].sum().clamp_min(1)
    known=d['known'].any(-1);per_query=((score-d['target']).square()*d['known']).sum(-1)/d['known'].sum(-1).clamp_min(1)
    utility=per_query[known].mean() if known.any() else score.sum()*0
    return move+p['utility_weight']*utility


def train(bank,indices,fold,p,epochs,directory,deadline):
    directory.mkdir(parents=True,exist_ok=False);torch.manual_seed(p['seed']);net=prior.Readout(bank['weights']);opt=torch.optim.AdamW(net.parameters(),lr=p['lr']);rng=np.random.default_rng(p['seed'])
    torch.save(net.state_dict(),directory/'epoch-000.pt');values={0:prior.score(net,bank,fold)} if fold is not None else {};trace=[]
    for epoch in range(1,epochs+1):
        order=rng.permutation(indices);norms=[]
        for start in range(0,len(order),p['batch']):
            if time.perf_counter()>=deadline:raise TimeoutError('Margin readout cap exceeded')
            d=prior.pack(bank['records'],order[start:start+p['batch']]);value=loss(net,d,p);opt.zero_grad();value.backward();norm=torch.nn.utils.clip_grad_norm_(net.parameters(),5.);assert torch.isfinite(value) and torch.isfinite(norm);opt.step();norms.append(float(norm))
        trace.append(dict(epoch=epoch,order=order.tolist(),norms=norms))
        if epoch%4==0:
            torch.save(net.state_dict(),directory/f'epoch-{epoch:03d}.pt')
            if fold is not None:values[epoch]=prior.score(net,bank,fold)
            print(directory.name,epoch,values.get(epoch,{}).get('correct'),flush=True)
    torch.save(dict(model=net.state_dict(),optimizer=opt.state_dict(),rng=rng.bit_generator.state),directory/'final.pt');immutable_json(directory/'trace.json',dict(epochs=trace,validation=values));return net,values


def fit():
    start=time.perf_counter();p=inputs();torch.set_num_threads(1);values={}
    for fold in range(4):
        bank=torch.load(prior.WORK/f'fold{fold}.pt',weights_only=False);indices=np.array([i for i,r in enumerate(bank['records']) if r['fold']!=fold and (r['label']>=0 or r['utilities'] is not None)])
        _,v=train(bank,indices,fold,p,p['epochs'],WORK/f'fold{fold}',start+p['cap'])
        for e,s in v.items():values.setdefault(e,[]).append(s)
    cs=[dict(epoch=e,**prior.prior.combined(v)) for e,v in values.items()];chosen=prior.choose(cs,p);immutable_json(REPORT/'selection.json',dict(selected=chosen,candidates=cs,evaluation_used=False))
    bank=torch.load(prior.WORK/'full.pt',weights_only=False);indices=np.array([i for i,r in enumerate(bank['records']) if r['label']>=0 or r['utilities'] is not None]);net,_=train(bank,indices,None,p,chosen['epoch'],WORK/'refit',start+p['cap']);torch.save(prior.export(net,bank['weights']),WORK/'selected.pt')
    bound=bindings([q for q in WORK.rglob('*') if q.is_file()]);elapsed=time.perf_counter()-start
    if elapsed>=p['cap']:raise TimeoutError('Margin publication exceeded cap')
    immutable_json(REPORT/'fit.json',dict(bindings=bound,seconds=elapsed));print('SELECTED',chosen,flush=True)


def assess():
    inputs();check(read(REPORT/'fit.json'));selected=torch.load(WORK/'selected.pt',weights_only=True);results={}
    for split in ('fit','evaluation'):
        bank=torch.load(prior.prior.WORK/(split+'.pt'),weights_only=False)
        assert all(torch.equal(selected[k],bank['weights'][k]) for k in ('net.0.weight','net.0.bias'))
        results[split]=prior.prior.simulate(dict(bank,weights=selected))
    x=results['evaluation'];old=read(prior.prior.REPORT/'result.json')['results']['evaluation']['edited'];gates=dict(combined=x['correct']>old['correct'],direct=x['correct']>x['baseline'],utility=x['utility_sum']>0,active=x['active']>=.1*x['available'])
    immutable_json(REPORT/'result.json',dict(results=results,checks=gates,all_checks_pass=all(gates.values()),target_met=x['correct']>=411 and x['rows']==513,bindings=bindings([WORK/'selected.pt',prior.prior.WORK/'fit.pt',prior.prior.WORK/'evaluation.pt']),promoted=False))
    print('EVALUATION',{k:v for k,v in x.items() if k not in ('predictions','selected')},gates,flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('command',choices=('freeze','fit','assess'));globals()[p.parse_args().command]()
