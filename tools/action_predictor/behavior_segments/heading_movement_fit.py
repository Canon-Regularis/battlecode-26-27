"""Fitting-game selection of a small observed-heading residual; fixed evaluation."""
import argparse, time
from pathlib import Path
import numpy as np
import torch
from torch.nn import functional as F
from . import movement_bias_edit as bias, joint_movement_fit as joint, full_movement_fit as full
from . import expanded_code_data as expanded, expanded_code_fit as folds, code_weight_fit as first
from . import data as original, code_path_fit as old
from .joint_movement_weights import JointMovement
from .heading_movement import HeadingCorrection, HeadingPolicy, heading_window
from .study import evaluate
from ..audit import immutable_json
from ..data import digest

ROOT = original.ROOT; REPORT = ROOT/'tools/action_predictor/experiments/v57'; WORK = ROOT/'.cambc/action-predictor/v57'
read, check, bindings = joint.read, joint.check, joint.bindings


def freeze():
    REPORT.mkdir(parents=True, exist_ok=True)
    bias.inputs(); check(read(bias.REPORT/'verification.json'))
    sources = [Path(__file__).with_name(n) for n in ('heading_movement.py', 'heading_movement_fit.py', 'heading_movement_predictor.py', 'heading_movement_verify.py', 'test_heading_movement.py')]
    immutable_json(REPORT/'plan.json', dict(sources=bindings(sources), inputs=bindings([bias.REPORT/n for n in ('plan.json','selection.json','refit.json','result.json','verification.json')]+[full.REPORT/'plan.json',full.REPORT/'verification.json']),
        seed=57001, hidden=[0,16], epochs=32, evaluate_every=8, learning_rate=.003, weight_decay=.01,
        clip=5., batch_windows=64, tuning_seconds_cap=900, refit_seconds_cap=300, target_accuracy=.8,
        intervention='Freeze V55 and add a zero-initialized candidate-heading residual with 228 or 980 parameters. '
        'Four features: cosine and sign-match with displacement from last observed PRE position, each also divided by elapsed rounds. '
        'Coefficients depend on frozen recurrent state48 and soft code8. Missing PRE retains last position, observed absent position clears it. '
        'Actor changes and32turn window resets clear it. Nonincreasing round produces zero features. No current/future command or inferred goal used.',
        selection='Four fitting-game folds; all expanded windows in other24games for training, original64windows in held8games for selection. '
        'Compare epochs0,8,16,24,32; maximize pooled correct movements, then minimize NLL, then earlier epoch and smaller head. '
        'One selected full refit and unchanged513movement query assessment. No evaluation gradients or test-dependent checkpoint selection.',
        limits='New explicit causal feature, not a pure existing-weight edit. Previously exposed research data, inherited fold backbone exposure, '
        'observed command history, conditional movement only. No verified intent, strategy or playing-strength claim. No subagents or promotion.'))


def inputs():
    plan = read(REPORT/'plan.json'); check(plan); check(read(full.REPORT/'plan.json'))
    _, parent, architecture, cache, ids = bias.inputs()
    return plan, parent, architecture, cache, ids


@torch.no_grad()
def features(name, parent, architecture, cache, heading):
    net = full.warm(name, parent, architecture).eval(); data = joint.dataset(name, cache)
    contexts=[]; logits=[]
    for begin in range(0, len(heading), 16):
        states=[]; hook=net.backbone.code.register_forward_pre_hook(lambda module,args:states.append(args[0]))
        try: out=JointMovement.forward(net, first.take(data,slice(begin,begin+16)))
        finally: hook.remove()
        contexts.append(torch.cat((states[0],out['code'].softmax(-1)),-1)); logits.append(out['move'])
    return dict(context=torch.cat(contexts), baseline=torch.cat(logits), heading=heading,
                labels=data['movement_labels'], support=data['support'])


def prepare():
    plan,parent,architecture,cache,ids=inputs(); torch.set_num_threads(1); WORK.mkdir(parents=True,exist_ok=False)
    windows,_=expanded.read()
    assert all(w['key']==ids[i]['key'] and w['partition']=='fit' for i,w in enumerate(windows))
    heading=torch.stack([heading_window(w) for w in windows])
    for name in ['fold0','fold1','fold2','fold3','full']:
        torch.save(features(name,parent,architecture,cache,heading),WORK/(name+'.pt'))
    immutable_json(REPORT/'cache.json',dict(plan_sha256=digest(REPORT/'plan.json'), bindings=bindings(list(WORK.glob('*.pt'))),
        windows=len(ids), rows=sum(int((s['labels']>=0).sum()) for s in [torch.load(WORK/'full.pt',weights_only=True)])))


def cached(name):
    receipt=read(REPORT/'cache.json'); check(receipt)
    assert receipt['plan_sha256']==digest(REPORT/'plan.json')
    return torch.load(WORK/(name+'.pt'),weights_only=True)


def new_head(hidden,plan):
    torch.manual_seed(plan['seed']); return HeadingCorrection(hidden)


@torch.no_grad()
def score(net,data,indices):
    correct=0; n=0; total=0.; predictions=[]
    for start in range(0,len(indices),64):
        d=first.take(data,indices[start:start+64]); mask=d['labels']>=0
        lp=net(d['context'],d['heading'],d['baseline']).masked_fill(~d['support'],-1e9).log_softmax(-1)[mask]
        y=d['labels'][mask]; p=lp.argmax(-1); n+=len(y); correct+=int((p==y).sum())
        total+=float((-lp.gather(1,y[:,None]).squeeze(1)).double().sum()); predictions.extend(p.tolist())
    return dict(rows=n,correct=correct,nll=total/n,predictions=predictions)


def train(net,data,indices,plan,epochs,directory,deadline,held=None):
    directory.mkdir(parents=True,exist_ok=False); opt=torch.optim.AdamW(net.parameters(),lr=plan['learning_rate'],weight_decay=plan['weight_decay'])
    rng=np.random.default_rng(plan['seed']); updates=0; trace=[]
    initial=score(net,data,held) if held is not None else None
    torch.save(dict(model=net.state_dict(),optimizer=opt.state_dict()),directory/'epoch-000.pt')
    for epoch in range(1,epochs+1):
        order=rng.permutation(indices); denominators=[]; norms=[]
        for start in range(0,len(order),plan['batch_windows']):
            if time.perf_counter()>=deadline: raise TimeoutError('Heading fit budget exceeded')
            d=first.take(data,order[start:start+plan['batch_windows']]); mask=d['labels']>=0
            logits=net(d['context'],d['heading'],d['baseline']).masked_fill(~d['support'],-1e9)
            loss=F.cross_entropy(logits[mask],d['labels'][mask]); opt.zero_grad(set_to_none=True); loss.backward()
            norm=torch.nn.utils.clip_grad_norm_(net.parameters(),plan['clip'])
            if not torch.isfinite(loss) or not torch.isfinite(norm): raise ValueError('Nonfinite heading update')
            opt.step(); updates+=1; denominators.append(int(mask.sum())); norms.append(float(norm))
        entry=dict(epoch=epoch,updates=updates,order=order.tolist(),denominators=denominators,gradient_norms=norms)
        if epoch%plan['evaluate_every']==0 or epoch==epochs:
            if held is not None: entry['validation']=score(net,data,held)
            torch.save(dict(model=net.state_dict(),optimizer=opt.state_dict(),rng=rng.bit_generator.state,updates=updates),directory/f'epoch-{epoch:03d}.pt')
            print(directory.name,epoch,entry.get('validation',{}).get('correct'),flush=True)
        trace.append(entry)
    immutable_json(directory/'trace.json',dict(initial=initial,epochs=trace)); return trace


def combine(values):
    n=sum(v['rows'] for v in values)
    return dict(rows=n,correct=sum(v['correct'] for v in values),nll=sum(v['nll']*v['rows'] for v in values)/n)


def choose(candidates): return min(candidates,key=lambda c:(-c['correct'],c['nll'],c['epoch'],c['hidden']))


def tune():
    start=time.perf_counter(); plan,_,_,_,ids=inputs(); torch.set_num_threads(1); values={}
    directory=WORK/'tuning'; directory.mkdir(parents=True,exist_ok=False)
    for hidden in plan['hidden']:
        for fold in range(4):
            data=cached('fold'+str(fold)); training,held=folds.partition_indices(ids,fold); net=new_head(hidden,plan)
            values[(hidden,fold,0)]=score(net,data,held)
            trace=train(net,data,training,plan,plan['epochs'],directory/f'h{hidden}-fold{fold}',start+plan['tuning_seconds_cap'],held)
            for e in trace:
                if 'validation' in e: values[(hidden,fold,e['epoch'])]=e['validation']
    candidates=[dict(hidden=h,epoch=e,**combine([values[(h,k,e)] for k in range(4)])) for h in plan['hidden'] for e in range(0,plan['epochs']+1,plan['evaluate_every'])]
    bound=bindings([p for p in directory.rglob('*') if p.is_file()]); elapsed=time.perf_counter()-start
    if elapsed>=plan['tuning_seconds_cap']: raise TimeoutError('Heading tuning publication exceeded')
    immutable_json(REPORT/'selection.json',dict(plan_sha256=digest(REPORT/'plan.json'),selected=choose(candidates),candidates=candidates,bindings=bound,seconds=elapsed,outer_evaluation_used=False))
    print('SELECTED',choose(candidates),flush=True)


def refit():
    start=time.perf_counter(); plan,_,_,_,ids=inputs(); selection=read(REPORT/'selection.json');check(selection);chosen=selection['selected']
    assert chosen==choose(selection['candidates']); torch.set_num_threads(1); net=new_head(chosen['hidden'],plan);data=cached('full')
    trace=train(net,data,np.arange(len(ids)),plan,chosen['epoch'],WORK/'refit',start+plan['refit_seconds_cap'])
    torch.save(dict(model=net.state_dict(),plan_sha256=digest(REPORT/'plan.json'),selection_sha256=digest(REPORT/'selection.json')),WORK/'selected.pt')
    fit=score(net,data,np.arange(len(ids)));bound=bindings([WORK/'selected.pt',*(p for p in (WORK/'refit').iterdir() if p.is_file())]);elapsed=time.perf_counter()-start
    if elapsed>=plan['refit_seconds_cap']:raise TimeoutError('Heading refit publication exceeded')
    immutable_json(REPORT/'refit.json',dict(selection_sha256=digest(REPORT/'selection.json'),fit=fit,updates=trace[-1]['updates'] if trace else 0,bindings=bound,seconds=elapsed))


def policy(plan,parent,architecture):
    chosen=read(REPORT/'selection.json')['selected']; saved=torch.load(WORK/'selected.pt',weights_only=False)
    assert saved['plan_sha256']==digest(REPORT/'plan.json') and saved['selection_sha256']==digest(REPORT/'selection.json')
    net=new_head(chosen['hidden'],plan);net.load_state_dict(saved['model'])
    return HeadingPolicy(bias.policy(parent,architecture),net).eval()


def encoded(windows,maps,architecture):
    cache=old.encoded_windows(windows,maps,architecture)
    for w in windows:cache[w['key']]['heading']=heading_window(w)
    return cache


def unchanged(value,baseline):
    assert len(value['records'])==len(baseline['records'])
    for a,b in zip(value['records'],baseline['records']):
        assert {k:v for k,v in a.items() if k not in ('move_prediction','movement_nll')}=={k:v for k,v in b.items() if k not in ('move_prediction','movement_nll')}


def assess():
    start=time.perf_counter();plan,parent,architecture,_,_=inputs();check(read(REPORT/'refit.json'));torch.set_num_threads(4)
    windows,maps=original.load();cache=encoded(windows,maps,architecture);discovery=read(original.REPORT/'discovery.json');net=policy(plan,parent,architecture);results={};comparisons={}
    for split in ('fit','evaluation'):
        value=evaluate(net,windows,maps,cache,discovery,split,start+600);baseline=read(bias.WORK/(split+'-predictions.json'));unchanged(value,baseline)
        immutable_json(WORK/(split+'-predictions.json'),value);results[split]=value['summary'];comparisons[split]=joint.prior.paired(value['records'],baseline['records']);print(split,value['summary'],flush=True)
    bound=bindings([WORK/'selected.pt',WORK/'fit-predictions.json',WORK/'evaluation-predictions.json']);elapsed=time.perf_counter()-start
    if elapsed>=600:raise TimeoutError('Heading assessment publication exceeded')
    immutable_json(REPORT/'result.json',dict(refit_sha256=digest(REPORT/'refit.json'),results=results,comparisons=comparisons,target_met=results['evaluation']['movement_accuracy']>=.8,bindings=bound,seconds=elapsed,promoted=False))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('command',choices=('freeze','prepare','tune','refit','assess'));globals()[p.parse_args().command]()
