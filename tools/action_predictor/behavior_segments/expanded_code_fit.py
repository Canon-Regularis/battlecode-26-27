"""Update existing neural weights with more windows from the same fitting games."""
import argparse
import json
import time
from pathlib import Path
import numpy as np
import torch
from . import expanded_code_data as expanded,code_weight_fit as first,model
from .data import ROOT,REPORT as BASE,load
from .rare_code_edit import metrics
from .study import evaluate
from ..audit import immutable_json
from ..data import digest

REPORT=expanded.REPORT
WORK=expanded.WORK


def partition_indices(ids,fold):
    training=np.array([i for i,r in enumerate(ids) if r['fold']!=fold],dtype=np.int64)
    validation=np.array([i for i,r in enumerate(ids) if r['fold']==fold and r['canonical']],dtype=np.int64)
    if not len(training) or not len(validation):raise ValueError('Empty fold')
    if {ids[i]['group'] for i in training}&{ids[i]['group'] for i in validation}:raise ValueError('Group leakage')
    return training,validation


def freeze():
    old,architecture,canonical,ids=first.load_cache()
    receipt=json.loads((REPORT/'cache.json').read_text());parity=json.loads((REPORT/'parity.json').read_text())
    assert receipt['exact_canonical_windows']==256 and parity['original_labels_exact']==256
    for p,h in receipt['bindings'].items():assert digest(ROOT/p)==h,p
    selection=json.loads((first.REPORT/'selection.json').read_text())['selected']
    initial={str(k):str((first.WORK/'tuning'/f"lr{selection['learning_rate']:g}-fold{k}"/f"epoch-{selection['epoch']:03d}.pt").relative_to(ROOT)) for k in range(4)}
    paths=[REPORT/'assembly-plan.json',REPORT/'data.json',REPORT/'parity.json',REPORT/'cache.json',
           WORK/'labels.json',first.REPORT/'selection.json',first.REPORT/'refit.json',first.WORK/'selected.pt',
           *(ROOT/p for p in initial.values())]
    immutable_json(REPORT/'plan.json',dict(
        sources={str(p.relative_to(ROOT)):digest(p) for p in (Path(__file__),Path(__file__).with_name('test_expanded_code_fit.py'))},
        inputs={str(p.relative_to(ROOT)):digest(p) for p in paths},fold_initial=initial,
        full_initial=str((first.WORK/'selected.pt').relative_to(ROOT)),seed=49001,learning_rates=[.0001,.0003],
        epochs=32,evaluate_every=4,batch_windows=16,weight_decay=.01,clip=5.,
        tuning_seconds_cap=1800,refit_seconds_cap=600,target_accuracy=.85,
        objective='Same context/GRU/code weights and unweighted observed-query CE asV46. '
        'Warm start from the corresponding V46fold or full-fit checkpoint, fresh optimizer. '
        'All1607eligible windows in the same32fitting groups are available; no map or head architecture changes.',
        selection='Each fold trains on all expanded windows from the other24games. Validation uses only '
        'the original64windows of its eight held fitting games. Choose pooled correct count, then NLL, '
        'earliest epoch, then learning rate. Include zero further epochs. Refit selected configuration '
        'on all expanded fitting windows; evaluate one selected checkpoint on unchanged original queries.',
        limitations='This follow-up follows the exposed V48 evaluation result. Evaluation is reused research, '
        'not independent certification. Frozen code meanings and schema; original labels/rows retained exactly. '
        'No new evaluation-game reconstruction, label-driven window selection, subagents or playing-bot edits.'))


def inputs():
    plan=json.loads((REPORT/'plan.json').read_text())
    for kind in ('sources','inputs'):
        for p,h in plan[kind].items():assert digest(ROOT/p)==h,p
    receipt=json.loads((REPORT/'cache.json').read_text())
    for p,h in receipt['bindings'].items():assert digest(ROOT/p)==h,p
    old,architecture,canonical,old_ids=first.load_cache()
    data=torch.load(WORK/'fit-cache.pt',weights_only=True);ids=json.loads((WORK/'identities.json').read_text())
    assert len(ids)==1607 and sum(r['canonical'] for r in ids)==256
    for fold in range(4):
        training,validation=partition_indices(ids,fold)
        assert len({ids[i]['group'] for i in training})==24 and len(validation)==64
    return plan,architecture,data,ids


def tune():
    start=time.perf_counter();plan,architecture,data,ids=inputs();torch.set_num_threads(1)
    directory=WORK/'tuning';directory.mkdir(exist_ok=False);traces={};baseline={}
    for lr in plan['learning_rates']:
        for fold in range(4):
            torch.manual_seed(plan['seed']);net=model.SegmentPolicy(architecture['schema'],8)
            net.load_state_dict(torch.load(ROOT/plan['fold_initial'][str(fold)],map_location='cpu',weights_only=False)['model'])
            training,validation=partition_indices(ids,fold)
            baseline[(lr,fold)]=first.score(net,data,validation)
            traces[(lr,fold)],_=first.train(net,data,training,plan['epochs'],lr,plan,
                directory/f'lr{lr:g}-fold{fold}',validation,start+plan['tuning_seconds_cap'])
    candidates=[]
    for lr in plan['learning_rates']:
        for epoch in range(0,plan['epochs']+1,plan['evaluate_every']):
            values=[baseline[(lr,k)] if epoch==0 else traces[(lr,k)][epoch-1]['validation'] for k in range(4)]
            y=sum([v['labels'] for v in values],[]);pred=sum([v['predictions'] for v in values],[])
            assert len(y)==2945
            candidates.append(dict(learning_rate=lr,epoch=epoch,correct=sum(v['correct'] for v in values),rows=len(y),
                nll=sum(v['nll']*v['rows'] for v in values)/len(y),codes=metrics(y,pred)))
    chosen=min(candidates,key=lambda c:(-c['correct'],c['nll'],c['epoch'],c['learning_rate']))
    immutable_json(directory/'baseline.json',{f'{lr:g}/{k}':v for (lr,k),v in baseline.items()})
    bindings={str(p.relative_to(ROOT)):digest(p) for p in directory.rglob('*') if p.is_file()}
    elapsed=time.perf_counter()-start
    if elapsed>=plan['tuning_seconds_cap']:raise TimeoutError('Expanded tuning publication budget exceeded')
    immutable_json(REPORT/'selection.json',dict(plan_sha256=digest(REPORT/'plan.json'),selected=chosen,candidates=candidates,
        bindings=bindings,seconds=elapsed,outer_evaluation_used=False,tuning_target_met=chosen['codes']['accuracy']>=.85))
    print('SELECTED',json.dumps(chosen),flush=True)


def refit():
    start=time.perf_counter();plan,architecture,data,ids=inputs();selection=json.loads((REPORT/'selection.json').read_text())
    assert selection['plan_sha256']==digest(REPORT/'plan.json');chosen=selection['selected']
    torch.set_num_threads(1);torch.manual_seed(plan['seed']);net=model.SegmentPolicy(architecture['schema'],8)
    net.load_state_dict(torch.load(ROOT/plan['full_initial'],map_location='cpu',weights_only=False)['model'])
    trace,_=first.train(net,data,np.arange(len(ids)),chosen['epoch'],chosen['learning_rate'],plan,
                        WORK/'refit',deadline=start+plan['refit_seconds_cap'])
    torch.save(dict(model=net.state_dict(),inference_only=True,plan_sha256=digest(REPORT/'plan.json'),
                    selection_sha256=digest(REPORT/'selection.json'),selected_epoch=chosen['epoch']),WORK/'selected.pt')
    final=first.score(net,data,np.arange(len(ids)))
    bindings={str(p.relative_to(ROOT)):digest(p) for p in [WORK/'selected.pt',*(WORK/'refit').iterdir()] if p.is_file()}
    elapsed=time.perf_counter()-start
    if elapsed>=plan['refit_seconds_cap']:raise TimeoutError('Expanded refit publication budget exceeded')
    immutable_json(REPORT/'refit.json',dict(selection_sha256=digest(REPORT/'selection.json'),fit=final,
        updates=trace[-1]['updates'] if trace else 0,seconds=elapsed,bindings=bindings))
    print('REFIT',final['correct'],'/',final['rows'],flush=True)


def assess():
    start=time.perf_counter();plan,architecture,data,ids=inputs();refit=json.loads((REPORT/'refit.json').read_text())
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
    if elapsed>=300:raise TimeoutError('Expanded assessment publication budget exceeded')
    immutable_json(REPORT/'result.json',dict(refit_sha256=digest(REPORT/'refit.json'),results=results,
        target_met=results['evaluation']['target_met'],seconds=elapsed,bindings=bindings,
        qualification='Unchanged evaluation queries and labels; more existing fitting-game windows. '
        'Preexposed research evaluation, fixed neural architecture, no promotion.'))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('command',choices=('freeze','tune','refit','assess'))
    globals()[parser.parse_args().command]()
