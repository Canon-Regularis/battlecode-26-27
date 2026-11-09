"""Supervised updates of existing context/GRU/code weights; architecture unchanged."""
import argparse
import json
import time
from pathlib import Path

import numpy as np
import torch
from torch.nn import functional as F

from . import model
from .data import ROOT, REPORT as BASE, WORK as BASE_WORK, load
from .rare_code_edit import folds, metrics
from .study import check, evaluate
from ..audit import immutable_json
from ..data import digest

REPORT = ROOT/'tools/action_predictor/experiments/v46'
WORK = ROOT/'.cambc/action-predictor/v46'
INITIAL = ROOT/'.cambc/action-predictor/v44/combined.pt'
PREFIXES = ('context.', 'memory.', 'code.')


def configure(net):
    for name, p in net.named_parameters():
        p.requires_grad_(name.startswith(PREFIXES))
    return [p for p in net.parameters() if p.requires_grad]


def code_forward(net, item):
    """Batch independent windows; same context, GRU and readout as SegmentPolicy."""
    observed = item['observed']
    feature = torch.tanh(net.context(item['context'])) * observed[..., None]
    recurrent = torch.cat((feature, item['previous']/5, item['previous_mask'],
                           torch.log1p(item['rounds'])[..., None]/10,
                           observed[..., None]), -1)
    state = torch.zeros(len(recurrent), 48, dtype=recurrent.dtype)
    states = []
    for i in range(recurrent.shape[1]):
        state = net.memory(recurrent[:, i], state)
        states.append(state)
    return net.code(torch.stack(states, 1))


def take(data, indices):
    return {k: v[indices] for k, v in data.items()}


def loss(logits, item):
    mask = item['observed'].bool()
    if not mask.any(): raise ValueError('No supervised query in batch')
    return F.cross_entropy(logits[mask], item['labels'][mask])


@torch.no_grad()
def score(net, data, indices):
    truth, predictions, total_nll = [], [], 0.
    for begin in range(0, len(indices), 16):
        item = take(data, indices[begin:begin+16]); logits = code_forward(net, item)
        mask = item['observed'].bool(); y = item['labels'][mask]
        truth.extend(y.tolist()); predictions.extend(logits[mask].argmax(-1).tolist())
        total_nll += float(F.cross_entropy(logits[mask], y, reduction='sum'))
    return dict(codes=metrics(truth, predictions), nll=total_nll/len(truth),
                rows=len(truth), correct=sum(a == b for a,b in zip(truth,predictions)),
                labels=truth, predictions=predictions)


def freeze():
    REPORT.mkdir(parents=True, exist_ok=True)
    plan = json.loads((BASE/'protocol.json').read_text()); check(plan)
    prior = json.loads((ROOT/'tools/action_predictor/experiments/v44/result.json').read_text())
    assert digest(INITIAL) == prior['bindings'][str(INITIAL.relative_to(ROOT))]
    windows,_ = load(); fitting = [w for w in windows if w['partition'] == 'fit']
    groups = folds([w['group'] for w in fitting]); assert len(groups) == 32
    paths = [BASE/'protocol.json', BASE/'discovery.json', INITIAL,
             ROOT/'tools/action_predictor/experiments/v44/result.json']
    immutable_json(REPORT/'plan.json', dict(
        sources={str(p.relative_to(ROOT)):digest(p) for p in
                 (Path(__file__),Path(__file__).with_name('test_code_weight_fit.py'))},
        inputs={str(p.relative_to(ROOT)):digest(p) for p in paths},
        folds=groups, seed=46001, learning_rates=[.0003,.001], epochs=96,
        evaluate_every=4, batch_windows=16, weight_decay=.01, clip=5., target_accuracy=.85,
        training_threads=1, seconds_cap=1800,
        budget_definition='At most1800seconds for the complete eight-run tuning stage and separately1800seconds for refit. No restarts or extensions. Assessment cap300seconds.',
        objective='Unweighted code cross entropy over observed queries. Existing context, GRU and '
        'code weights only. Fixed map features cached before updates. No new parameters, decoder, '
        'input fields, label changes or sampling of evaluation data.',
        selection='Four whole-game folds on original fitting groups, same initialization. '
        'Across both learning rates and epochs4..96 choose greatest pooled correct count, '
        'then smallest pooled code NLL, then earliest epoch, then smallest learning rate. '
        'Refit same configuration from the same initialization on all32fitting groups. '
        'Write selection before refit and any outer evaluation. No early success selection.',
        caveat='Backbone and discovery were previously trained on all fitting groups, including '
        'fold validation. These folds assess further weight updates, not fresh end-to-end generalization. '
        'All eight outer evaluation groups were previously exposed research data.',
        scope='User requests85percent inferred-code accuracy via existing neural weights. '
        'Report rare-code metrics and goal/movement effects. Original checkpoints preserved. '
        'No subagents, playing-bot changes or automatic promotion.'))


def binding_check():
    frozen = json.loads((REPORT/'plan.json').read_text())
    for kind in ('sources','inputs'):
        for p,h in frozen[kind].items(): assert digest(ROOT/p) == h,p
    plan = json.loads((BASE/'protocol.json').read_text()); check(plan)
    return frozen,plan


def prepare():
    frozen,plan = binding_check(); WORK.mkdir(parents=True,exist_ok=False)
    torch.set_num_threads(4)
    discovery = json.loads((BASE/'discovery.json').read_text())
    windows,maps = load(); fitting = [w for w in windows if w['partition']=='fit']
    net = model.SegmentPolicy(plan['schema'],8).eval()
    net.load_state_dict(torch.load(INITIAL,map_location='cpu',weights_only=False)['model'])
    captured = {}
    handle = net.context.register_forward_pre_hook(lambda module,args: captured.update(context=args[0].detach()))
    rows = []; identities = []; maximum_error = 0.
    with torch.no_grad():
        for w in fitting:
            args,_ = model.encode_window(w,maps[w['payload']],plan['schema']); original=net(**args)
            item = dict(context=captured['context'].clone(),
                        **{k:args[k] for k in ('previous','previous_mask','rounds','observed')},
                        labels=torch.tensor(discovery['labels'][w['key']]))
            batched = {k:v[None] for k,v in item.items()}
            cached = code_forward(net,batched)[0]
            torch.testing.assert_close(cached,original['code'],atol=2e-6,rtol=2e-5)
            maximum_error=max(maximum_error,float((cached-original['code']).abs().max()))
            rows.append(item); identities.append(dict(key=w['key'],group=w['group'],fold=frozen['folds'][w['group']]))
    handle.remove()
    data = {k:torch.stack([r[k] for r in rows]) for k in rows[0]}
    assert len(data['observed']) == 256 and int(data['observed'].sum()) == 2945
    torch.save(data,WORK/'fit-cache.pt'); immutable_json(WORK/'identities.json',identities)
    immutable_json(REPORT/'cache.json',dict(plan_sha256=digest(REPORT/'plan.json'),
        bindings={str(p.relative_to(ROOT)):digest(p) for p in (WORK/'fit-cache.pt',WORK/'identities.json')},
        windows=len(rows),observed_queries=int(data['observed'].sum()),maximum_code_error=maximum_error,
        only_fitting_windows=True))
    print('Prepared',len(rows),'fitting windows; maximum code error',maximum_error,flush=True)


def load_cache():
    frozen,plan = binding_check()
    receipt=json.loads((REPORT/'cache.json').read_text())
    assert receipt['plan_sha256']==digest(REPORT/'plan.json')
    for p,h in receipt['bindings'].items(): assert digest(ROOT/p)==h,p
    return frozen,plan,torch.load(WORK/'fit-cache.pt',weights_only=True),json.loads((WORK/'identities.json').read_text())


def train(net,data,indices,epochs,lr,frozen,directory,validation=None,deadline=None):
    directory.mkdir(exist_ok=False)
    parameters=configure(net)
    optimizer=torch.optim.AdamW(parameters,lr=lr,weight_decay=frozen['weight_decay'])
    rng=np.random.default_rng(frozen['seed']); trace=[]; updates=0; checkpoints=[]
    torch.save(dict(model=net.state_dict(),rng=torch.get_rng_state(),optimizer=optimizer.state_dict()),directory/'initial.pt')
    for epoch in range(1,epochs+1):
        order=rng.permutation(indices); total=0.; count=0; norms=[]; denominators=[]
        for begin in range(0,len(order),frozen['batch_windows']):
            if time.perf_counter()>=deadline: raise TimeoutError('Weight-update budget exceeded')
            batch=order[begin:begin+frozen['batch_windows']]; item=take(data,batch)
            optimizer.zero_grad(set_to_none=True); logits=code_forward(net,item); objective=loss(logits,item)
            objective.backward(); norm=torch.nn.utils.clip_grad_norm_(parameters,frozen['clip'])
            if not torch.isfinite(objective) or not torch.isfinite(norm): raise ValueError('Nonfinite training')
            optimizer.step(); updates+=1
            n=int(item['observed'].sum()); total+=float(objective.detach())*n; count+=n
            denominators.append(n); norms.append(float(norm))
        entry=dict(epoch=epoch,updates=updates,window_order=order.tolist(),observed_presentations=count,
                   batch_denominators=denominators,gradient_norms=norms,online_nll=total/count)
        if epoch%frozen['evaluate_every']==0 or epoch==epochs:
            if validation is not None: entry['validation']=score(net,data,validation)
            path=directory/f'epoch-{epoch:03d}.pt'
            torch.save(dict(model=net.state_dict(),optimizer=optimizer.state_dict(),epoch=epoch,
                            updates=updates,rng=rng.bit_generator.state,torch_rng=torch.get_rng_state()),path)
            checkpoints.append(path)
            v=entry.get('validation',{})
            print(directory.name,'epoch',epoch,'updates',updates,'online_NLL',round(total/count,5),
                  'validation',v.get('correct'), '/',v.get('rows'),flush=True)
        trace.append(entry)
    immutable_json(directory/'trace.json',trace)
    return trace,checkpoints


def tune():
    frozen,plan,data,identities=load_cache(); start=time.perf_counter();deadline=start+frozen['seconds_cap']
    torch.set_num_threads(frozen['training_threads']); torch.manual_seed(frozen['seed'])
    directory=WORK/'tuning';directory.mkdir(exist_ok=False); traces={}
    initial=torch.load(INITIAL,map_location='cpu',weights_only=False)['model']; fold=np.array([r['fold'] for r in identities])
    for lr in frozen['learning_rates']:
        for k in range(4):
            torch.manual_seed(frozen['seed'])
            net=model.SegmentPolicy(plan['schema'],8);net.load_state_dict(initial)
            name=f'lr{lr:g}-fold{k}'
            trace,_=train(net,data,np.flatnonzero(fold!=k),frozen['epochs'],lr,frozen,directory/name,
                          np.flatnonzero(fold==k),deadline)
            traces[name]=trace
    candidates=[]
    for lr in frozen['learning_rates']:
        for epoch in range(frozen['evaluate_every'],frozen['epochs']+1,frozen['evaluate_every']):
            values=[traces[f'lr{lr:g}-fold{k}'][epoch-1]['validation'] for k in range(4)]
            y=sum([v['labels'] for v in values],[]);prediction=sum([v['predictions'] for v in values],[])
            candidates.append(dict(learning_rate=lr,epoch=epoch,correct=sum(v['correct'] for v in values),
                rows=len(y),nll=sum(v['nll']*v['rows'] for v in values)/len(y),codes=metrics(y,prediction)))
    chosen=min(candidates,key=lambda c:(-c['correct'],c['nll'],c['epoch'],c['learning_rate']))
    bindings={str(p.relative_to(ROOT)):digest(p) for p in directory.rglob('*') if p.is_file()}
    elapsed=time.perf_counter()-start
    if elapsed>=frozen['seconds_cap']: raise TimeoutError('Tuning publication budget exceeded')
    immutable_json(REPORT/'selection.json',dict(plan_sha256=digest(REPORT/'plan.json'),selected=chosen,
        candidates=candidates,seconds=elapsed,bindings=bindings,outer_evaluation_used=False,
        tuning_target_met=chosen['codes']['accuracy']>=frozen['target_accuracy']))
    print('SELECTED',json.dumps(chosen),flush=True)


def refit():
    frozen,plan,data,ids=load_cache(); selection=json.loads((REPORT/'selection.json').read_text())
    assert selection['plan_sha256']==digest(REPORT/'plan.json')
    chosen=selection['selected'];torch.set_num_threads(frozen['training_threads']);torch.manual_seed(frozen['seed'])
    start=time.perf_counter();deadline=start+frozen['seconds_cap']
    net=model.SegmentPolicy(plan['schema'],8)
    net.load_state_dict(torch.load(INITIAL,map_location='cpu',weights_only=False)['model'])
    trace,paths=train(net,data,np.arange(len(ids)),chosen['epoch'],chosen['learning_rate'],frozen,WORK/'refit',deadline=deadline)
    torch.save(dict(model=net.state_dict(),plan_sha256=digest(REPORT/'plan.json'),
                    selection_sha256=digest(REPORT/'selection.json'),initial_sha256=digest(INITIAL),
                    selected_epoch=chosen['epoch'],inference_only=True),WORK/'selected.pt')
    final=score(net,data,np.arange(len(ids)))
    bindings={str(p.relative_to(ROOT)):digest(p) for p in [WORK/'selected.pt',*(WORK/'refit').iterdir()] if p.is_file()}
    elapsed=time.perf_counter()-start
    if elapsed>=frozen['seconds_cap']: raise TimeoutError('Refit publication budget exceeded')
    immutable_json(REPORT/'refit.json',dict(selection_sha256=digest(REPORT/'selection.json'),
        seconds=elapsed,updates=trace[-1]['updates'],fit=final,bindings=bindings))
    print('REFIT',json.dumps(dict(correct=final['correct'],rows=final['rows'],codes=final['codes'])),flush=True)


def assess():
    frozen,plan=binding_check();receipt=json.loads((REPORT/'refit.json').read_text())
    for p,h in receipt['bindings'].items(): assert digest(ROOT/p)==h,p
    torch.set_num_threads(4);start=time.perf_counter();deadline=start+300
    windows,maps=load();discovery=json.loads((BASE/'discovery.json').read_text())
    cache={w['key']:model.encode_window(w,maps[w['payload']],plan['schema'])[0] for w in windows}
    net=model.SegmentPolicy(plan['schema'],8).eval()
    net.load_state_dict(torch.load(WORK/'selected.pt',map_location='cpu',weights_only=False)['model']);results={}
    for split in ('fit','evaluation'):
        value=evaluate(net,windows,maps,cache,discovery,split,deadline)
        codes=metrics([r['code_label'] for r in value['records']],[r['code_prediction'] for r in value['records']])
        results[split]=dict(summary=value['summary'],codes=codes,target_met=codes['accuracy']>=frozen['target_accuracy'])
        immutable_json(WORK/f'{split}-predictions.json',value);print(split,json.dumps(results[split]),flush=True)
    bindings={str(p.relative_to(ROOT)):digest(p) for p in (WORK/'selected.pt',WORK/'fit-predictions.json',WORK/'evaluation-predictions.json')}
    elapsed=time.perf_counter()-start
    if elapsed>=300: raise TimeoutError('Assessment publication budget exceeded')
    immutable_json(REPORT/'result.json',dict(refit_sha256=digest(REPORT/'refit.json'),results=results,
        target_met=results['evaluation']['target_met'],seconds=elapsed,bindings=bindings,
        qualification='Previously exposed research evaluation, inferred labels. Fixed neural architecture and forward interface. No runtime promotion.'))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('command',choices=('freeze','prepare','tune','refit','assess'))
    globals()[parser.parse_args().command]()
