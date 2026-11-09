"""Fit an affine logit calibration and fold it into the existing linear code head."""
import argparse
import json
import time
from pathlib import Path
import numpy as np
import torch
from torch.nn import functional as F
from . import expanded_code_fit as previous,code_weight_fit as first,model
from .data import ROOT,REPORT as BASE,load
from .rare_code_edit import metrics
from .study import evaluate
from ..audit import immutable_json
from ..data import digest

REPORT=ROOT/'tools/action_predictor/experiments/v50'
WORK=ROOT/'.cambc/action-predictor/v50'


def solve(logits,labels,regularization,deadline):
    x=torch.as_tensor(logits,dtype=torch.float64);y=torch.as_tensor(labels,dtype=torch.long)
    active=torch.zeros(8,dtype=torch.float64);active[y.unique()]=1
    identity=torch.eye(8,dtype=torch.float64)
    delta=torch.zeros(8,8,dtype=torch.float64,requires_grad=True)
    offset=torch.zeros(8,dtype=torch.float64,requires_grad=True)
    optimizer=torch.optim.LBFGS([delta,offset],lr=1,max_iter=100,max_eval=125,
        tolerance_grad=1e-8,tolerance_change=1e-12,line_search_fn='strong_wolfe')
    evaluations=[]
    def closure():
        if time.perf_counter()>=deadline:raise TimeoutError('Calibration budget exceeded')
        optimizer.zero_grad();d=delta*active[:,None];b=offset*active
        objective=F.cross_entropy(x@(identity+d).T+b,y)+regularization*(d.square().sum()+b.square().sum())
        objective.backward()
        if not torch.isfinite(objective) or not torch.isfinite(delta.grad).all() or not torch.isfinite(offset.grad).all():
            raise ValueError('Nonfinite calibration')
        evaluations.append(float(objective.detach()));return objective
    optimizer.step(closure)
    matrix=(identity+delta.detach()*active[:,None]).numpy();bias=(offset.detach()*active).numpy()
    return matrix,bias,dict(objectives=evaluations,iterations=optimizer.state[delta]['n_iter'],
                            closure_evaluations=optimizer.state[delta]['func_evals'])


def compose(state,matrix,bias):
    result={k:v.clone() for k,v in state.items()}
    a=torch.as_tensor(matrix,dtype=torch.float64);b=torch.as_tensor(bias,dtype=torch.float64)
    result['code.weight']=(a@state['code.weight'].double()).to(state['code.weight'].dtype)
    result['code.bias']=(a@state['code.bias'].double()+b).to(state['code.bias'].dtype)
    return result


def freeze():
    REPORT.mkdir(parents=True,exist_ok=True)
    previous.inputs();chosen=json.loads((previous.REPORT/'selection.json').read_text())['selected']
    initial={str(k):str((previous.WORK/'tuning'/f"lr{chosen['learning_rate']:g}-fold{k}"/
        (f"epoch-{chosen['epoch']:03d}.pt" if chosen['epoch'] else 'initial.pt')).relative_to(ROOT)) for k in range(4)}
    paths=[previous.REPORT/'plan.json',previous.REPORT/'selection.json',previous.REPORT/'refit.json',
           previous.REPORT/'result.json',previous.WORK/'selected.pt',*(ROOT/p for p in initial.values())]
    immutable_json(REPORT/'plan.json',dict(
        sources={str(p.relative_to(ROOT)):digest(p) for p in (Path(__file__),Path(__file__).with_name('test_code_head_calibration.py'))},
        inputs={str(p.relative_to(ROOT)):digest(p) for p in paths},fold_checkpoints=initial,
        regularizations=[.001,.01,.1,1.],seconds_cap=600,target_accuracy=.85,
        fitting='Collect original2945canonical fitting-query logits from matching V49held-game checkpoints. '
        'For each regularizer, fit affine8by8logit map on three fold cohorts and score the fourth. '
        'CE plus summed squared distance from identity; rows for classes absent in fitting remain identity. '
        'Select pooled correct count, then NLL, then strongest regularization. Identity is eligible.',
        final='Fit selected calibration to all fitting-fold logits, then compose into existing code.weight '
        'and code.bias. All other tensors fixed. Publish selection before one outer evaluation. '
        'If identity wins, preserve previous forecasts and perform no new outer inference.',
        limits='Nested calibration uses already exposed fitting-fold logits; those base models were fitted '
        'using other groups, so this is conditional calibration validation rather than fully independent '
        'nested model validation. Follows exposed V49 evaluation; no untouched-test claim. '
        'No evaluation labels used for calibration, architecture changes, subagents or promotion.'))


def run():
    start=time.perf_counter();plan=json.loads((REPORT/'plan.json').read_text());deadline=start+plan['seconds_cap']
    for kind in ('sources','inputs'):
        for p,h in plan[kind].items():assert digest(ROOT/p)==h,p
    _,architecture,data,ids=previous.inputs();torch.set_num_threads(1);WORK.mkdir(parents=True,exist_ok=False)
    logits=[];labels=[];folds=[]
    net=model.SegmentPolicy(architecture['schema'],8).eval()
    with torch.no_grad():
        for fold in range(4):
            net.load_state_dict(torch.load(ROOT/plan['fold_checkpoints'][str(fold)],map_location='cpu',weights_only=False)['model'])
            _,held=previous.partition_indices(ids,fold)
            for begin in range(0,len(held),16):
                item=first.take(data,held[begin:begin+16]);mask=item['observed'].bool()
                x=first.code_forward(net,item)[mask];y=item['labels'][mask]
                logits.extend(x.double().numpy());labels.extend(y.tolist());folds.extend([fold]*len(y))
    x=np.asarray(logits);y=np.asarray(labels);folds=np.asarray(folds);assert len(y)==2945
    np.savez_compressed(WORK/'fitting-logits.npz',logits=x,labels=y,folds=folds)
    def summary(values):
        return dict(correct=int((values.argmax(1)==y).sum()),rows=len(y),codes=metrics(y,values.argmax(1)),
                    nll=float(F.cross_entropy(torch.from_numpy(values),torch.from_numpy(y))))
    candidates={'identity':summary(x)};maps={};traces={}
    for reg in plan['regularizations']:
        values=np.empty_like(x)
        for fold in range(4):
            train,held=folds!=fold,folds==fold
            a,b,trace=solve(x[train],y[train],reg,deadline)
            values[held]=x[held]@a.T+b;maps[f'{reg:g}/{fold}']=dict(matrix=a.tolist(),bias=b.tolist());traces[f'{reg:g}/{fold}']=trace
        candidates[f'{reg:g}']=summary(values)
        print('Calibration',reg,json.dumps(candidates[f'{reg:g}']),flush=True)
    selected=min(candidates,key=lambda k:(-candidates[k]['correct'],candidates[k]['nll'],-(float(k) if k!='identity' else float('inf'))))
    if selected=='identity':a,b=np.eye(8),np.zeros(8)
    else:a,b,trace=solve(x,y,float(selected),deadline);traces['final']=trace
    immutable_json(WORK/'fold-maps.json',maps);immutable_json(WORK/'trace.json',traces)
    base=torch.load(previous.WORK/'selected.pt',map_location='cpu',weights_only=False)['model'];state=compose(base,a,b)
    assert all(torch.isfinite(v).all() for v in state.values())
    torch.save(dict(model=state,plan_sha256=digest(REPORT/'plan.json'),matrix=a,bias=b,inference_only=True),WORK/'selected.pt')
    immutable_json(REPORT/'selection.json',dict(plan_sha256=digest(REPORT/'plan.json'),selected=selected,
        candidates=candidates,matrix=a.tolist(),bias=b.tolist(),checkpoint_sha256=digest(WORK/'selected.pt'),
        outer_evaluation_used=False,source_logits_sha256=digest(WORK/'fitting-logits.npz')))
    torch.set_num_threads(4);net.load_state_dict(state);results={}
    if selected!='identity':
        windows,map_data=load();discovery=json.loads((BASE/'discovery.json').read_text())
        cache={w['key']:model.encode_window(w,map_data[w['payload']],architecture['schema'])[0] for w in windows}
    for split in ('fit','evaluation'):
        if selected=='identity':
            assert all(torch.equal(v,base[k]) for k,v in state.items())
            value=json.loads((previous.WORK/f'{split}-predictions.json').read_text())
        else:value=evaluate(net,windows,map_data,cache,discovery,split,deadline)
        codes=metrics([r['code_label'] for r in value['records']],[r['code_prediction'] for r in value['records']])
        results[split]=dict(summary=value['summary'],codes=codes,target_met=codes['accuracy']>=.85)
        immutable_json(WORK/f'{split}-predictions.json',value)
    bindings={str(p.relative_to(ROOT)):digest(p) for p in WORK.iterdir() if p.is_file()};elapsed=time.perf_counter()-start
    if elapsed>=plan['seconds_cap']:raise TimeoutError('Calibration publication budget exceeded')
    immutable_json(REPORT/'result.json',dict(selection_sha256=digest(REPORT/'selection.json'),selected=selected,
        results=results,target_met=results['evaluation']['target_met'],seconds=elapsed,bindings=bindings,
        new_outer_inference=selected!='identity',changed_tensors=[k for k,v in state.items() if not torch.equal(v,base[k])]))
    print('FINAL',selected,json.dumps(results['evaluation']),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('command',choices=('freeze','run'))
    globals()[parser.parse_args().command]()
