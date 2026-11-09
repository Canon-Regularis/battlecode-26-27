"""Fixed fitting-fold experiment adding signed previous-command history to V57."""
import argparse,time
from pathlib import Path
import numpy as np
import torch
from . import heading_movement_fit as prior,command_heading_audit as audit
from .command_movement import CommandCorrection,CommandPolicy,command_window
from ..audit import immutable_json
from ..data import digest

ROOT=prior.ROOT;REPORT=ROOT/'tools/action_predictor/experiments/v58';WORK=ROOT/'.cambc/action-predictor/v58'
read,check,bindings=prior.read,prior.check,prior.bindings


def freeze():
    REPORT.mkdir(parents=True,exist_ok=True);prior.inputs();check(read(prior.REPORT/'verification.json'));check(read(REPORT/'command-history-audit.json'))
    sources=[Path(__file__).with_name(n) for n in ('command_heading_audit.py','command_movement.py','command_movement_fit.py','command_movement_predictor.py','command_movement_verify.py','test_command_movement.py')]
    immutable_json(REPORT/'plan.json',dict(sources=bindings(sources),inputs=bindings([prior.REPORT/n for n in ('plan.json','cache.json','selection.json','refit.json','result.json','verification.json')]+[REPORT/'command-history-audit.json']),
        seed=58001,hidden=[0,16],epochs=32,evaluate_every=8,learning_rate=.003,weight_decay=.01,clip=5.,batch_windows=64,
        tuning_seconds_cap=900,refit_seconds_cap=300,target_accuracy=.8,
        intervention='Freeze V57 and add a zero-initialized 456 or1048 parameter movement correction. '
        'Eight candidate features: cosine/sign match to last prior executed move, also divided by age in own turns; '
        'cosine/sign match to previous-turn net movement, also multiplied by net-length/path-length. '
        'Only complete previous own turns inside current32turn window. Original signed direction was omitted from the descriptor. '
        'Observed previous commands already supply original history; runtime explicitly requires previous_moves after the first query.',
        selection='Four fitting-game folds and same original held64windows. Start from matched V55 plus selected V57 head. '
        'Select most pooled correct movements,then NLL,earlier epoch,smaller head among0,8,16,24,32. '
        'One full refit then unchanged513evaluationmoves. No evaluation gradients or evaluation-dependent checkpoint choices.',
        limits='New causal history representation,not pure existing-weight editing. Teacher-forced past commands,preexposed research groups, '
        'inherited fold exposure and conditional movement. No verified intent,autonomous strategy or promotion.'))


def inputs():
    plan=read(REPORT/'plan.json');check(plan);_,parent,architecture,cache,ids=prior.inputs()
    return plan,parent,architecture,cache,ids


def new_head(hidden,plan):torch.manual_seed(plan['seed']);return CommandCorrection(hidden)


@torch.no_grad()
def features(name,heading):
    data=prior.cached(name);selected=read(prior.REPORT/'selection.json')['selected'];parent_plan=read(prior.REPORT/'plan.json')
    path=prior.WORK/'selected.pt' if name=='full' else prior.WORK/'tuning'/f"h{selected['hidden']}-{name}"/f"epoch-{selected['epoch']:03d}.pt"
    head=prior.new_head(selected['hidden'],parent_plan);head.load_state_dict(torch.load(path,weights_only=False)['model'])
    baseline=head(data['context'],data['heading'],data['baseline'])
    return dict(data,baseline=baseline,heading=heading)


def prepare():
    inputs();torch.set_num_threads(1);WORK.mkdir(parents=True,exist_ok=False);windows,_=prior.expanded.read()
    assert all(w['partition']=='fit' for w in windows)
    history,source_bindings=audit.prior_moves(windows);heading=torch.stack([command_window(history[w['key']]) for w in windows])
    for name in ['fold0','fold1','fold2','fold3','full']:torch.save(features(name,heading),WORK/(name+'.pt'))
    immutable_json(REPORT/'cache.json',dict(plan_sha256=digest(REPORT/'plan.json'),source_bindings=source_bindings,
        bindings=bindings(list(WORK.glob('*.pt'))),windows=len(windows)))


def cached(name):
    receipt=read(REPORT/'cache.json');check(receipt);assert receipt['plan_sha256']==digest(REPORT/'plan.json')
    for path,h in receipt['source_bindings'].items():assert digest(path)==h
    return torch.load(WORK/(name+'.pt'),weights_only=True)


def tune():
    start=time.perf_counter();plan,_,_,_,ids=inputs();torch.set_num_threads(1);values={};directory=WORK/'tuning';directory.mkdir(parents=True,exist_ok=False)
    for fold in range(4):
        data=cached('fold'+str(fold));training,held=prior.folds.partition_indices(ids,fold)
        for hidden in plan['hidden']:
            net=new_head(hidden,plan);values[(hidden,fold,0)]=prior.score(net,data,held)
            trace=prior.train(net,data,training,plan,plan['epochs'],directory/f'h{hidden}-fold{fold}',start+plan['tuning_seconds_cap'],held)
            for e in trace:
                if 'validation' in e:values[(hidden,fold,e['epoch'])]=e['validation']
    candidates=[dict(hidden=h,epoch=e,**prior.combine([values[(h,k,e)] for k in range(4)])) for h in plan['hidden'] for e in range(0,plan['epochs']+1,plan['evaluate_every'])]
    bound=bindings([p for p in directory.rglob('*') if p.is_file()]);elapsed=time.perf_counter()-start
    if elapsed>=plan['tuning_seconds_cap']:raise TimeoutError('Command heading tuning budget exceeded')
    immutable_json(REPORT/'selection.json',dict(plan_sha256=digest(REPORT/'plan.json'),selected=prior.choose(candidates),candidates=candidates,bindings=bound,seconds=elapsed,outer_evaluation_used=False))
    print('SELECTED',prior.choose(candidates),flush=True)


def refit():
    start=time.perf_counter();plan,_,_,_,ids=inputs();selection=read(REPORT/'selection.json');check(selection);chosen=selection['selected'];assert chosen==prior.choose(selection['candidates'])
    torch.set_num_threads(1);data=cached('full');net=new_head(chosen['hidden'],plan)
    trace=prior.train(net,data,np.arange(len(ids)),plan,chosen['epoch'],WORK/'refit',start+plan['refit_seconds_cap'])
    torch.save(dict(model=net.state_dict(),plan_sha256=digest(REPORT/'plan.json'),selection_sha256=digest(REPORT/'selection.json')),WORK/'selected.pt')
    score=prior.score(net,data,np.arange(len(ids)));bound=bindings([WORK/'selected.pt',*(p for p in (WORK/'refit').iterdir() if p.is_file())]);elapsed=time.perf_counter()-start
    if elapsed>=plan['refit_seconds_cap']:raise TimeoutError('Command heading refit budget exceeded')
    immutable_json(REPORT/'refit.json',dict(selection_sha256=digest(REPORT/'selection.json'),fit=score,updates=trace[-1]['updates'] if trace else 0,bindings=bound,seconds=elapsed))


def policy(plan,parent,architecture):
    saved=torch.load(WORK/'selected.pt',weights_only=False);chosen=read(REPORT/'selection.json')['selected']
    assert saved['plan_sha256']==digest(REPORT/'plan.json') and saved['selection_sha256']==digest(REPORT/'selection.json')
    net=new_head(chosen['hidden'],plan);net.load_state_dict(saved['model'])
    return CommandPolicy(prior.policy(read(prior.REPORT/'plan.json'),parent,architecture),net).eval()


def encoded(windows,maps,architecture):
    cache=prior.encoded(windows,maps,architecture);history,source_bindings=audit.prior_moves(windows)
    for w in windows:cache[w['key']]['command_heading']=command_window(history[w['key']])
    return cache,history,source_bindings


def assess():
    start=time.perf_counter();plan,parent,architecture,_,_=inputs();check(read(REPORT/'refit.json'));torch.set_num_threads(4)
    windows,maps=prior.original.load();cache,_,source_bindings=encoded(windows,maps,architecture);discovery=read(prior.original.REPORT/'discovery.json');net=policy(plan,parent,architecture);results={};comparisons={}
    for split in ('fit','evaluation'):
        value=prior.evaluate(net,windows,maps,cache,discovery,split,start+600);baseline=read(prior.WORK/(split+'-predictions.json'));prior.unchanged(value,baseline)
        immutable_json(WORK/(split+'-predictions.json'),value);results[split]=value['summary'];comparisons[split]=prior.joint.prior.paired(value['records'],baseline['records']);print(split,value['summary'],flush=True)
    bound=bindings([WORK/'selected.pt',WORK/'fit-predictions.json',WORK/'evaluation-predictions.json']);elapsed=time.perf_counter()-start
    if elapsed>=600:raise TimeoutError('Command heading assessment budget exceeded')
    immutable_json(REPORT/'result.json',dict(refit_sha256=digest(REPORT/'refit.json'),results=results,comparisons=comparisons,source_bindings=source_bindings,
        target_met=results['evaluation']['movement_accuracy']>=.8,bindings=bound,seconds=elapsed,promoted=False))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('command',choices=('freeze','prepare','tune','refit','assess'));globals()[p.parse_args().command]()
