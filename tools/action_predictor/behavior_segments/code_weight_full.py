"""Continue the existing code predictor by updating its existing map encoder too."""
import argparse
import json
import time
from pathlib import Path

import numpy as np
import torch
from torch.nn import functional as F

from . import model
from .data import ROOT, REPORT as BASE, load
from .code_weight_fit import REPORT as PRIOR, WORK as PRIOR_WORK, load_cache
from .rare_code_edit import metrics
from .study import evaluate
from ..audit import immutable_json
from ..data import digest

REPORT = ROOT/'tools/action_predictor/experiments/v47'
WORK = ROOT/'.cambc/action-predictor/v47'
PREFIXES = ('maps.', 'context.', 'memory.', 'code.')


def configure(net):
    for name,p in net.named_parameters(): p.requires_grad_(name.startswith(PREFIXES))
    return [p for p in net.parameters() if p.requires_grad]


def backward_batch(net, items):
    denominator=sum(int(args['observed'].sum()) for args,y in items)
    if not denominator: raise ValueError('Empty supervised batch')
    total=0.
    for args,y in items:
        output=net(**args);mask=args['observed'].bool()
        part=F.cross_entropy(output['code'][mask],y[mask],reduction='sum')/denominator
        part.backward();total+=float(part.detach())
    return total,denominator


@torch.no_grad()
def score(net, items, indices):
    y=[];prediction=[];total=0.
    for i in indices:
        args,target=items[int(i)];mask=args['observed'].bool();logits=net(**args)['code'][mask]
        truth=target[mask];y.extend(truth.tolist());prediction.extend(logits.argmax(-1).tolist())
        total+=float(F.cross_entropy(logits,truth,reduction='sum'))
    return dict(rows=len(y),correct=sum(a==b for a,b in zip(y,prediction)),nll=total/len(y),
                codes=metrics(y,prediction),labels=y,predictions=prediction)


def freeze():
    REPORT.mkdir(parents=True,exist_ok=True)
    old,plan,data,ids=load_cache()
    selection=json.loads((PRIOR/'selection.json').read_text());chosen=selection['selected']
    refit=json.loads((PRIOR/'refit.json').read_text())
    for p,h in refit['bindings'].items():assert digest(ROOT/p)==h,p
    initial={str(k):str((PRIOR_WORK/'tuning'/f"lr{chosen['learning_rate']:g}-fold{k}"/f"epoch-{chosen['epoch']:03d}.pt").relative_to(ROOT)) for k in range(4)}
    paths=[PRIOR/'plan.json',PRIOR/'selection.json',PRIOR/'refit.json',PRIOR_WORK/'selected.pt',*(ROOT/p for p in initial.values())]
    immutable_json(REPORT/'plan.json',dict(
        sources={str(p.relative_to(ROOT)):digest(p) for p in (Path(__file__),Path(__file__).with_name('test_code_weight_full.py'))},
        inputs={str(p.relative_to(ROOT)):digest(p) for p in paths},fold_initial=initial,
        full_initial=str((PRIOR_WORK/'selected.pt').relative_to(ROOT)),folds=old['folds'],
        seed=47001,learning_rate=.0003,epochs=16,evaluate_every=2,batch_windows=8,
        weight_decay=.01,clip=5.,threads=4,tuning_seconds_cap=2400,refit_seconds_cap=900,
        target_accuracy=.85,
        intervention='Unfreeze only existing maps/context/memory/code parameters. Same SegmentPolicy, '
        'same features, labels, causal32turn resets, query denominator and prediction interface. '
        'Code cross entropy only; movement/goal outputs are evaluated but their heads remain frozen.',
        selection='Continue each matching V46 fold checkpoint, fresh optimizer. Choose pooled code '
        'accuracy across four fitting-game folds, then NLL, then earliest epoch. Include epoch0 '
        'so a harmful encoder change can be rejected. Refit selected duration from the V46 full-fit '
        'checkpoint. No outer evaluation until one final checkpoint is frozen.',
        limits='Backbone/discovery were exposed to all fitting groups before these folds. '
        'Outer evaluation was also previously exposed research; no fresh generalization claim. '
        'All actual-data updates are explicitly supervised fitting, not unfitted manual edits. '
        'No new architecture, subagents, playing-bot modifications or automatic promotion.'))


def inputs():
    frozen=json.loads((REPORT/'plan.json').read_text())
    for kind in ('sources','inputs'):
        for p,h in frozen[kind].items():assert digest(ROOT/p)==h,p
    old,plan,data,ids=load_cache()
    windows,maps=load();fitting=[w for w in windows if w['partition']=='fit']
    assert [w['key'] for w in fitting]==[r['key'] for r in ids]
    discovery=json.loads((BASE/'discovery.json').read_text())
    items=[(model.encode_window(w,maps[w['payload']],plan['schema'])[0],
            torch.tensor(discovery['labels'][w['key']])) for w in fitting]
    return frozen,plan,ids,items


def train(net,items,indices,epochs,frozen,directory,deadline,validation=None):
    directory.mkdir(exist_ok=False);parameters=configure(net)
    optimizer=torch.optim.AdamW(parameters,lr=frozen['learning_rate'],weight_decay=frozen['weight_decay'])
    rng=np.random.default_rng(frozen['seed']);updates=0;trace=[]
    initial=dict(epoch=0,updates=0)
    if validation is not None:initial['validation']=score(net,items,validation)
    torch.save(dict(model=net.state_dict(),optimizer=optimizer.state_dict(),updates=0,epoch=0,
                    rng=rng.bit_generator.state,torch_rng=torch.get_rng_state()),directory/'epoch-000.pt')
    trace.append(initial)
    for epoch in range(1,epochs+1):
        order=rng.permutation(indices);total=0.;count=0;norms=[];denominators=[]
        for begin in range(0,len(order),frozen['batch_windows']):
            if time.perf_counter()>=deadline:raise TimeoutError('Full encoder training cap exceeded')
            chosen=order[begin:begin+frozen['batch_windows']]
            optimizer.zero_grad(set_to_none=True)
            objective,n=backward_batch(net,[items[int(i)] for i in chosen])
            norm=torch.nn.utils.clip_grad_norm_(parameters,frozen['clip'])
            if not np.isfinite(objective) or not torch.isfinite(norm):raise ValueError('Nonfinite full-path gradient')
            optimizer.step();updates+=1;total+=objective*n;count+=n;norms.append(float(norm));denominators.append(n)
        entry=dict(epoch=epoch,updates=updates,window_order=order.tolist(),observed_presentations=count,
                   batch_denominators=denominators,gradient_norms=norms,online_nll=total/count)
        if epoch%frozen['evaluate_every']==0 or epoch==epochs:
            if validation is not None:entry['validation']=score(net,items,validation)
            torch.save(dict(model=net.state_dict(),optimizer=optimizer.state_dict(),updates=updates,epoch=epoch,
                            rng=rng.bit_generator.state,torch_rng=torch.get_rng_state()),directory/f'epoch-{epoch:03d}.pt')
            v=entry.get('validation',{})
            print(directory.name,'epoch',epoch,'updates',updates,'online_NLL',round(total/count,6),
                  'validation',v.get('correct'),'/',v.get('rows'),flush=True)
        trace.append(entry)
    immutable_json(directory/'trace.json',trace)
    return trace


def tune():
    start=time.perf_counter();frozen,plan,ids,items=inputs();torch.set_num_threads(frozen['threads'])
    WORK.mkdir(parents=True,exist_ok=False);directory=WORK/'tuning';directory.mkdir()
    deadline=start+frozen['tuning_seconds_cap'];fold=np.array([r['fold'] for r in ids]);traces={}
    for k in range(4):
        torch.manual_seed(frozen['seed']);net=model.SegmentPolicy(plan['schema'],8)
        net.load_state_dict(torch.load(ROOT/frozen['fold_initial'][str(k)],map_location='cpu',weights_only=False)['model'])
        traces[k]=train(net,items,np.flatnonzero(fold!=k),frozen['epochs'],frozen,directory/f'fold{k}',
                        deadline,np.flatnonzero(fold==k))
    candidates=[]
    for epoch in range(0,frozen['epochs']+1,frozen['evaluate_every']):
        values=[traces[k][epoch]['validation'] for k in range(4)]
        y=sum([v['labels'] for v in values],[]);prediction=sum([v['predictions'] for v in values],[])
        candidates.append(dict(epoch=epoch,rows=len(y),correct=sum(v['correct'] for v in values),
            nll=sum(v['nll']*v['rows'] for v in values)/len(y),codes=metrics(y,prediction)))
    chosen=min(candidates,key=lambda c:(-c['correct'],c['nll'],c['epoch']))
    bindings={str(p.relative_to(ROOT)):digest(p) for p in directory.rglob('*') if p.is_file()}
    elapsed=time.perf_counter()-start
    if elapsed>=frozen['tuning_seconds_cap']:raise TimeoutError('Full encoder tuning publication cap exceeded')
    immutable_json(REPORT/'selection.json',dict(plan_sha256=digest(REPORT/'plan.json'),selected=chosen,
        candidates=candidates,bindings=bindings,seconds=elapsed,outer_evaluation_used=False,
        tuning_target_met=chosen['codes']['accuracy']>=frozen['target_accuracy']))
    print('SELECTED',json.dumps(chosen),flush=True)


def refit():
    start=time.perf_counter();frozen,plan,ids,items=inputs();selection=json.loads((REPORT/'selection.json').read_text())
    assert selection['plan_sha256']==digest(REPORT/'plan.json')
    epoch=selection['selected']['epoch'];torch.set_num_threads(frozen['threads']);torch.manual_seed(frozen['seed'])
    net=model.SegmentPolicy(plan['schema'],8)
    net.load_state_dict(torch.load(ROOT/frozen['full_initial'],map_location='cpu',weights_only=False)['model'])
    trace=train(net,items,np.arange(len(ids)),epoch,frozen,WORK/'refit',start+frozen['refit_seconds_cap'])
    torch.save(dict(model=net.state_dict(),plan_sha256=digest(REPORT/'plan.json'),
                    selection_sha256=digest(REPORT/'selection.json'),selected_epoch=epoch,inference_only=True),WORK/'selected.pt')
    final=score(net,items,np.arange(len(ids)))
    bindings={str(p.relative_to(ROOT)):digest(p) for p in [WORK/'selected.pt',*(WORK/'refit').iterdir()] if p.is_file()}
    elapsed=time.perf_counter()-start
    if elapsed>=frozen['refit_seconds_cap']:raise TimeoutError('Full encoder refit publication cap exceeded')
    immutable_json(REPORT/'refit.json',dict(selection_sha256=digest(REPORT/'selection.json'),seconds=elapsed,
        updates=trace[-1]['updates'],fit=final,bindings=bindings))
    print('REFIT',json.dumps(dict(correct=final['correct'],rows=final['rows'],codes=final['codes'])),flush=True)


def assess():
    start=time.perf_counter();frozen,plan,ids,items=inputs()
    refit=json.loads((REPORT/'refit.json').read_text())
    for p,h in refit['bindings'].items():assert digest(ROOT/p)==h,p
    torch.set_num_threads(4);windows,maps=load();discovery=json.loads((BASE/'discovery.json').read_text())
    cache={w['key']:model.encode_window(w,maps[w['payload']],plan['schema'])[0] for w in windows}
    net=model.SegmentPolicy(plan['schema'],8).eval()
    net.load_state_dict(torch.load(WORK/'selected.pt',map_location='cpu',weights_only=False)['model']);results={}
    for split in ('fit','evaluation'):
        value=evaluate(net,windows,maps,cache,discovery,split,start+300)
        codes=metrics([r['code_label'] for r in value['records']],[r['code_prediction'] for r in value['records']])
        results[split]=dict(summary=value['summary'],codes=codes,target_met=codes['accuracy']>=frozen['target_accuracy'])
        immutable_json(WORK/f'{split}-predictions.json',value);print(split,json.dumps(results[split]),flush=True)
    bindings={str(p.relative_to(ROOT)):digest(p) for p in (WORK/'selected.pt',WORK/'fit-predictions.json',WORK/'evaluation-predictions.json')}
    elapsed=time.perf_counter()-start
    if elapsed>=300:raise TimeoutError('Assessment publication cap exceeded')
    immutable_json(REPORT/'result.json',dict(refit_sha256=digest(REPORT/'refit.json'),results=results,
        target_met=results['evaluation']['target_met'],seconds=elapsed,bindings=bindings,
        qualification='Single selected fixed-architecture checkpoint; preexposed research evaluation. '
        'Code accuracy is inferred-label agreement, not verified intent or playing strength. No promotion.'))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('command',choices=('freeze','tune','refit','assess'))
    globals()[parser.parse_args().command]()
