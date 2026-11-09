"""Bounded joint weight update after explicit causal direction features were added."""
import argparse,time
from pathlib import Path
import numpy as np
import torch
from . import command_movement_fit as prior,heading_movement_fit as heading,joint_movement_fit as joint
from .trajectory_movement_weights import TrajectoryMovement,inference
from ..audit import immutable_json
from ..data import digest

ROOT=prior.ROOT;REPORT=ROOT/'tools/action_predictor/experiments/v59';WORK=ROOT/'.cambc/action-predictor/v59'
read,check,bindings=prior.read,prior.check,prior.bindings


def freeze():
    REPORT.mkdir(parents=True,exist_ok=True);prior.inputs();check(read(prior.REPORT/'verification.json'))
    sources=[Path(__file__).with_name(n) for n in ('trajectory_movement_weights.py','trajectory_movement_fit.py','trajectory_movement_predictor.py','trajectory_movement_verify.py','test_trajectory_movement.py')]
    immutable_json(REPORT/'plan.json',dict(sources=bindings(sources),inputs=bindings([prior.REPORT/n for n in ('plan.json','cache.json','selection.json','refit.json','result.json','verification.json')]),
        seed=59001,coefficient=1.,epochs=16,evaluate_every=4,learning_rate=.0003,weight_decay=.01,clip=5.,batch_windows=16,
        trainable_parameters=25569,tuning_seconds_cap=900,refit_seconds_cap=300,target_accuracy=.8,code_accuracy_allowance=.01,
        intervention='No new architecture or inputs. Start from matched V58 checkpoint and update existing context,GRU,base movement, '
        'geometry correction,observed-heading and prior-command correction weights together. Map encoder,code readout/embedding, '
        'goal query/readout stay frozen. Movement CE plus code KL coefficient1 to matching V55 code predictions.',
        selection='Four fitting-game folds; all expanded other24game windows for training and original held64windows for validation. '
        'Choose most pooled correct movements subject to at most1point code loss,then NLL,earlier epoch. Epoch0 eligible. '
        'One full refit then unchanged513evaluationmoves. No evaluation-guided weight updates or checkpoint selection.',
        limits='Previously exposed research games,inherited fold exposure,actual past commands,inferred codes and conditional movement. '
        'Goal outputs may change via recurrent features despite frozen goal weights. No subagents or promotion.'))


def inputs():
    plan=read(REPORT/'plan.json');check(plan);_,parent,architecture,cache,ids=prior.inputs()
    return plan,parent,architecture,cache,ids


def warm(name,parent,architecture):
    base=heading.full.warm(name,parent,architecture)
    h=read(heading.REPORT/'selection.json')['selected'];c=read(prior.REPORT/'selection.json')['selected']
    hp=heading.WORK/'selected.pt' if name=='full' else heading.WORK/'tuning'/f"h{h['hidden']}-{name}"/f"epoch-{h['epoch']:03d}.pt"
    cp=prior.WORK/'selected.pt' if name=='full' else prior.WORK/'tuning'/f"h{c['hidden']}-{name}"/f"epoch-{c['epoch']:03d}.pt"
    head=heading.new_head(h['hidden'],read(heading.REPORT/'plan.json'));head.load_state_dict(torch.load(hp,weights_only=False)['model'])
    command=prior.new_head(c['hidden'],read(prior.REPORT/'plan.json'));command.load_state_dict(torch.load(cp,weights_only=False)['model'])
    return TrajectoryMovement(base.backbone,base.correction,head,command)


def dataset(name,cache):
    data=joint.dataset(name,cache);observed=heading.cached(name);commands=prior.cached(name)
    return dict(data,heading=observed['heading'],command_heading=commands['heading'],teacher=observed['context'][...,48:])


def choose(candidates,allowance):
    initial=candidates[0];eligible=[c for c in candidates if c['code_correct']>=initial['code_correct']-allowance*c['code_rows']]
    return min(eligible,key=lambda c:(-c['correct'],c['nll'],c['epoch']))


def tune():
    start=time.perf_counter();plan,parent,architecture,cache,ids=inputs();torch.set_num_threads(1);values={};directory=WORK/'tuning';directory.mkdir(parents=True,exist_ok=False)
    for fold in range(4):
        name='fold'+str(fold);data=dataset(name,cache);training,held=heading.folds.partition_indices(ids,fold);net=warm(name,parent,architecture)
        values[(fold,0)]=joint.score(net,data,held)
        trace=joint.train(net,data,training,plan,plan['coefficient'],plan['epochs'],directory/name,start+plan['tuning_seconds_cap'],held)
        for e in trace:
            if 'validation' in e:values[(fold,e['epoch'])]=e['validation']
    candidates=[dict(epoch=e,**joint.combine([values[(k,e)] for k in range(4)])) for e in range(0,plan['epochs']+1,plan['evaluate_every'])]
    bound=bindings([p for p in directory.rglob('*') if p.is_file()]);elapsed=time.perf_counter()-start
    if elapsed>=plan['tuning_seconds_cap']:raise TimeoutError('Trajectory tuning publication exceeded')
    immutable_json(REPORT/'selection.json',dict(plan_sha256=digest(REPORT/'plan.json'),selected=choose(candidates,plan['code_accuracy_allowance']),candidates=candidates,bindings=bound,seconds=elapsed,outer_evaluation_used=False))
    print('SELECTED',choose(candidates,plan['code_accuracy_allowance']),flush=True)


def refit():
    start=time.perf_counter();plan,parent,architecture,cache,ids=inputs();selection=read(REPORT/'selection.json');check(selection);chosen=selection['selected'];assert chosen==choose(selection['candidates'],plan['code_accuracy_allowance'])
    torch.set_num_threads(1);data=dataset('full',cache);net=warm('full',parent,architecture)
    trace=joint.train(net,data,np.arange(len(ids)),plan,plan['coefficient'],chosen['epoch'],WORK/'refit',start+plan['refit_seconds_cap'])
    torch.save(dict(model=net.state_dict(),plan_sha256=digest(REPORT/'plan.json'),selection_sha256=digest(REPORT/'selection.json')),WORK/'selected.pt')
    score=joint.score(net,data,np.arange(len(ids)));bound=bindings([WORK/'selected.pt',*(p for p in (WORK/'refit').iterdir() if p.is_file())]);elapsed=time.perf_counter()-start
    if elapsed>=plan['refit_seconds_cap']:raise TimeoutError('Trajectory refit publication exceeded')
    immutable_json(REPORT/'refit.json',dict(selection_sha256=digest(REPORT/'selection.json'),fit=score,updates=trace[-1]['updates'] if trace else 0,bindings=bound,seconds=elapsed))


def policy(plan,parent,architecture):
    saved=torch.load(WORK/'selected.pt',weights_only=False)
    assert saved['plan_sha256']==digest(REPORT/'plan.json') and saved['selection_sha256']==digest(REPORT/'selection.json')
    net=warm('full',parent,architecture);net.load_state_dict(saved['model']);return inference(net)


def assess():
    start=time.perf_counter();plan,parent,architecture,_,_=inputs();check(read(REPORT/'refit.json'));torch.set_num_threads(4)
    windows,maps=heading.original.load();encoded,_,source_bindings=prior.encoded(windows,maps,architecture);net=policy(plan,parent,architecture);discovery=read(heading.original.REPORT/'discovery.json');results={};comparisons={}
    for split in ('fit','evaluation'):
        value=heading.evaluate(net,windows,maps,encoded,discovery,split,start+600);baseline=read(prior.WORK/(split+'-predictions.json'))
        immutable_json(WORK/(split+'-predictions.json'),value);results[split]=value['summary'];comparisons[split]=joint.prior.paired(value['records'],baseline['records']);print(split,value['summary'],flush=True)
    x=results['evaluation'];b=read(prior.REPORT/'result.json')['results']['evaluation'];guards=dict(code=x['code_accuracy']>=b['code_accuracy']-.01,nll=x['movement_nll']<=b['movement_nll']+.01)
    bound=bindings([WORK/'selected.pt',WORK/'fit-predictions.json',WORK/'evaluation-predictions.json']);elapsed=time.perf_counter()-start
    if elapsed>=600:raise TimeoutError('Trajectory assessment publication exceeded')
    immutable_json(REPORT/'result.json',dict(refit_sha256=digest(REPORT/'refit.json'),results=results,comparisons=comparisons,guards=guards,
        source_bindings=source_bindings,target_met=x['movement_accuracy']>=.8,bindings=bound,seconds=elapsed,promoted=False))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('command',choices=('freeze','tune','refit','assess'));globals()[p.parse_args().command]()
