"""Training-only regularization; select final weights across V46/V47/V48 by fitting folds."""
import argparse
import json
import time
from pathlib import Path
import numpy as np
import torch
from torch.nn import functional as F
from . import model, code_weight_fit as first, code_weight_full as second
from .data import ROOT,REPORT as BASE,load
from .rare_code_edit import metrics
from .study import evaluate
from ..audit import immutable_json
from ..data import digest

REPORT=ROOT/'tools/action_predictor/experiments/v48'
WORK=ROOT/'.cambc/action-predictor/v48'
CONFIGS={
    'dropout':dict(context_dropout=.25,state_dropout=.1,smoothing=0.,weight_decay=.01),
    'smooth_decay':dict(context_dropout=0.,state_dropout=0.,smoothing=.05,weight_decay=.1),
    'combined':dict(context_dropout=.25,state_dropout=.1,smoothing=.05,weight_decay=.1),
}


def training_forward(net,item,config):
    feature=torch.tanh(net.context(item['context']))*item['observed'][...,None]
    mask=F.dropout(torch.ones(len(feature),1,32),p=config['context_dropout'],training=True)
    state_mask=F.dropout(torch.ones(len(feature),48),p=config['state_dropout'],training=True)
    recurrent=torch.cat((feature*mask,item['previous']/5,item['previous_mask'],
                         torch.log1p(item['rounds'])[...,None]/10,item['observed'][...,None]),-1)
    state=torch.zeros(len(feature),48);states=[]
    for i in range(recurrent.shape[1]):
        state=net.memory(recurrent[:,i],state*state_mask);states.append(state)
    return net.code(torch.stack(states,1))


def freeze():
    REPORT.mkdir(parents=True,exist_ok=True);p,_,_,_=first.load_cache()
    paths=[first.REPORT/'plan.json',first.REPORT/'selection.json',first.REPORT/'refit.json',
           second.REPORT/'plan.json',first.INITIAL]
    immutable_json(REPORT/'plan.json',dict(
        sources={str(p.relative_to(ROOT)):digest(p) for p in (Path(__file__),Path(__file__).with_name('test_code_weight_regularized.py'))},
        inputs={str(p.relative_to(ROOT)):digest(p) for p in paths},configs=CONFIGS,
        seed=48001,learning_rate=.0003,epochs=96,evaluate_every=4,batch_windows=16,clip=5.,
        tuning_seconds_cap=900,refit_seconds_cap=300,finalize_seconds_cap=1200,folds=p['folds'],target_accuracy=.85,
        training='Existing context/GRU/code weights only, from original V44 initialization. '
        'Window-constant dropout masks on context and previous recurrent state during training only; '
        'label smoothing and weight decay as recorded. No inference change or new parameters.',
        selection='Four fitting-game folds; choose pooled correct count, then NLL, then earliest epoch, '
        'then config name. Compare chosen V46, V47 and V48 on the same pooled fitting-fold queries '
        'by correct count, then NLL, then stage name. Publish winner before final fitting and outer '
        'evaluation. Refit only winning configuration as needed; score one final checkpoint externally.',
        caveat='Backbone/discovery previously saw all fitting groups. Repeated tuning on those '
        'groups increases selection exposure. Outer groups also preexposed research. '
        'No claim of untouched testing, zero rare-code errors, strategy or promotion.'))


def inputs():
    frozen=json.loads((REPORT/'plan.json').read_text())
    for kind in ('sources','inputs'):
        for p,h in frozen[kind].items():assert digest(ROOT/p)==h,p
    _,architecture,data,ids=first.load_cache()
    return frozen,architecture,data,ids


def train(net,data,indices,epochs,config,plan,directory,deadline,validation=None):
    directory.mkdir(exist_ok=False)
    optimizer=torch.optim.AdamW(first.configure(net),lr=plan['learning_rate'],weight_decay=config['weight_decay'])
    rng=np.random.default_rng(plan['seed']);trace=[];updates=0
    torch.save(dict(model=net.state_dict(),optimizer=optimizer.state_dict(),rng=torch.get_rng_state()),directory/'initial.pt')
    for epoch in range(1,epochs+1):
        order=rng.permutation(indices);total=0.;count=0;norms=[];denominators=[]
        for begin in range(0,len(order),plan['batch_windows']):
            if time.perf_counter()>=deadline:raise TimeoutError('Regularized training cap exceeded')
            item=first.take(data,order[begin:begin+plan['batch_windows']]);mask=item['observed'].bool()
            optimizer.zero_grad(set_to_none=True)
            logits=training_forward(net,item,config)
            objective=F.cross_entropy(logits[mask],item['labels'][mask],label_smoothing=config['smoothing'])
            objective.backward();norm=torch.nn.utils.clip_grad_norm_([p for p in net.parameters() if p.requires_grad],plan['clip'])
            if not torch.isfinite(objective) or not torch.isfinite(norm):raise ValueError('Nonfinite regularized update')
            optimizer.step();updates+=1;n=int(mask.sum());total+=float(objective.detach())*n;count+=n
            norms.append(float(norm));denominators.append(n)
        entry=dict(epoch=epoch,updates=updates,window_order=order.tolist(),observed_presentations=count,
                   batch_denominators=denominators,gradient_norms=norms,online_loss=total/count)
        if epoch%plan['evaluate_every']==0 or epoch==epochs:
            if validation is not None:entry['validation']=first.score(net,data,validation)
            torch.save(dict(model=net.state_dict(),optimizer=optimizer.state_dict(),epoch=epoch,updates=updates,
                            rng=rng.bit_generator.state,torch_rng=torch.get_rng_state()),directory/f'epoch-{epoch:03d}.pt')
            v=entry.get('validation',{})
            print(directory.name,'epoch',epoch,'validation',v.get('correct'),'/',v.get('rows'),flush=True)
        trace.append(entry)
    immutable_json(directory/'trace.json',trace)
    return trace


def tune():
    start=time.perf_counter();plan,architecture,data,ids=inputs();torch.set_num_threads(1)
    WORK.mkdir(parents=True,exist_ok=False);directory=WORK/'tuning';directory.mkdir()
    fold=np.array([r['fold'] for r in ids]);base=torch.load(first.INITIAL,map_location='cpu',weights_only=False)['model'];traces={}
    for name,config in plan['configs'].items():
        for k in range(4):
            torch.manual_seed(plan['seed']);net=model.SegmentPolicy(architecture['schema'],8);net.load_state_dict(base)
            traces[(name,k)]=train(net,data,np.flatnonzero(fold!=k),plan['epochs'],config,plan,
                directory/f'{name}-fold{k}',start+plan['tuning_seconds_cap'],np.flatnonzero(fold==k))
    candidates=[]
    for name in plan['configs']:
        for epoch in range(plan['evaluate_every'],plan['epochs']+1,plan['evaluate_every']):
            values=[traces[(name,k)][epoch-1]['validation'] for k in range(4)]
            y=sum([v['labels'] for v in values],[]);pred=sum([v['predictions'] for v in values],[])
            candidates.append(dict(config=name,epoch=epoch,rows=len(y),correct=sum(v['correct'] for v in values),
                nll=sum(v['nll']*v['rows'] for v in values)/len(y),codes=metrics(y,pred)))
    chosen=min(candidates,key=lambda c:(-c['correct'],c['nll'],c['epoch'],c['config']))
    bindings={str(p.relative_to(ROOT)):digest(p) for p in directory.rglob('*') if p.is_file()}
    elapsed=time.perf_counter()-start
    if elapsed>=plan['tuning_seconds_cap']:raise TimeoutError('Regularized tuning publication cap exceeded')
    immutable_json(REPORT/'selection.json',dict(plan_sha256=digest(REPORT/'plan.json'),selected=chosen,candidates=candidates,
        bindings=bindings,seconds=elapsed,outer_evaluation_used=False,tuning_target_met=chosen['codes']['accuracy']>=.85))
    print('SELECTED',json.dumps(chosen),flush=True)


def finalize():
    start=time.perf_counter();plan,architecture,data,ids=inputs()
    paths={'recurrent':first.REPORT/'selection.json','encoder':second.REPORT/'selection.json','regularized':REPORT/'selection.json'}
    candidates={name:json.loads(path.read_text())['selected'] for name,path in paths.items()}
    stage=min(candidates,key=lambda s:(-candidates[s]['correct'],candidates[s]['nll'],s));chosen=candidates[stage]
    immutable_json(REPORT/'winner.json',dict(stage=stage,selected=chosen,candidates=candidates,
        inputs={str(p.relative_to(ROOT)):digest(p) for p in paths.values()},outer_evaluation_used=False))
    torch.set_num_threads(1);torch.manual_seed(plan['seed']);net=model.SegmentPolicy(architecture['schema'],8)
    if stage=='regularized':
        net.load_state_dict(torch.load(first.INITIAL,map_location='cpu',weights_only=False)['model'])
        trace=train(net,data,np.arange(len(ids)),chosen['epoch'],plan['configs'][chosen['config']],plan,
                    WORK/'refit',start+plan['refit_seconds_cap'])
        final=first.score(net,data,np.arange(len(ids)));source=None;updates=trace[-1]['updates']
    else:
        if stage=='encoder':
            second.refit()
            source=second.WORK/'selected.pt'
        else:source=first.WORK/'selected.pt'
        receipt=json.loads(((second.REPORT if stage=='encoder' else first.REPORT)/'refit.json').read_text())
        assert digest(source)==receipt['bindings'][str(source.relative_to(ROOT))]
        net.load_state_dict(torch.load(source,map_location='cpu',weights_only=False)['model'])
        final=first.score(net,data,np.arange(len(ids))) if stage=='recurrent' else None
        updates=0
    torch.save(dict(model=net.state_dict(),plan_sha256=digest(REPORT/'plan.json'),winner_sha256=digest(REPORT/'winner.json'),
                    source_checkpoint=None if source is None else str(source.relative_to(ROOT)),
                    source_sha256=None if source is None else digest(source),stage=stage,inference_only=True),WORK/'selected.pt')
    files=[WORK/'selected.pt']+(list((WORK/'refit').iterdir()) if (WORK/'refit').exists() else [])
    bindings={str(p.relative_to(ROOT)):digest(p) for p in files if p.is_file()}
    elapsed=time.perf_counter()-start
    cap=plan['refit_seconds_cap'] if stage=='regularized' else plan['finalize_seconds_cap']
    if elapsed>=cap:raise TimeoutError('Final checkpoint publication cap exceeded')
    immutable_json(REPORT/'refit.json',dict(winner_sha256=digest(REPORT/'winner.json'),stage=stage,fit=final,
        updates_in_this_phase=updates,seconds=elapsed,bindings=bindings))
    print('FINAL WINNER',stage,json.dumps(chosen),flush=True)


def assess():
    start=time.perf_counter();plan,architecture,data,ids=inputs()
    refit=json.loads((REPORT/'refit.json').read_text())
    for p,h in refit['bindings'].items():assert digest(ROOT/p)==h,p
    torch.set_num_threads(4);windows,maps=load();discovery=json.loads((BASE/'discovery.json').read_text())
    cache={w['key']:model.encode_window(w,maps[w['payload']],architecture['schema'])[0] for w in windows}
    net=model.SegmentPolicy(architecture['schema'],8).eval()
    net.load_state_dict(torch.load(WORK/'selected.pt',map_location='cpu',weights_only=False)['model']);results={}
    for split in ('fit','evaluation'):
        value=evaluate(net,windows,maps,cache,discovery,split,start+300)
        codes=metrics([r['code_label'] for r in value['records']],[r['code_prediction'] for r in value['records']])
        results[split]=dict(summary=value['summary'],codes=codes,target_met=codes['accuracy']>=.85)
        immutable_json(WORK/f'{split}-predictions.json',value);print(split,json.dumps(results[split]),flush=True)
    bindings={str(p.relative_to(ROOT)):digest(p) for p in (WORK/'selected.pt',WORK/'fit-predictions.json',WORK/'evaluation-predictions.json')}
    elapsed=time.perf_counter()-start
    if elapsed>=300:raise TimeoutError('Final assessment publication cap exceeded')
    immutable_json(REPORT/'result.json',dict(refit_sha256=digest(REPORT/'refit.json'),results=results,
        target_met=results['evaluation']['target_met'],seconds=elapsed,bindings=bindings,
        qualification='One final fixed-architecture checkpoint selected by fitting folds; preexposed research evaluation. '
        'Inferred-label accuracy only, no claim of verified intent, playing strength or promotion.'))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('command',choices=('freeze','tune','finalize','assess'))
    globals()[parser.parse_args().command]()
