"""Fitting-only selection toward80% direct movement on unchanged research queries."""
import argparse,time
from pathlib import Path
import numpy as np
import torch
from . import code_path_fit as old,code_movement_fit as prior,expanded_code_fit as expanded,code_weight_fit as first
from . import data as original
from .code_path_movement import PathCorrection
from .joint_movement_weights import JointMovement,losses,inference
from .study import evaluate
from ..audit import immutable_json
from ..data import digest

ROOT=original.ROOT;REPORT=ROOT/'tools/action_predictor/experiments/v54';WORK=ROOT/'.cambc/action-predictor/v54'
read=prior.read;check=prior.check;bindings=prior.bindings


def freeze():
    REPORT.mkdir(parents=True,exist_ok=True);plan,architecture,cache,ids=old.inputs()
    check(read(old.REPORT/'selection.json'));check(read(old.REPORT/'result.json'))
    sources=[Path(__file__).with_name(n) for n in ('joint_movement_weights.py','joint_movement_fit.py','joint_movement_predictor.py','joint_movement_verify.py','test_joint_movement.py')]
    paths=[old.REPORT/n for n in ('plan.json','cache.json','selection.json','refit.json','result.json','verification.json')]
    immutable_json(REPORT/'plan.json',dict(sources=bindings(sources),inputs=bindings(paths),
        fold_backbones=plan['fold_backbones'],full_backbone=plan['full_backbone'],
        seed=54001,learning_rate=.0003,distillation_weights=[.2,1.],epochs=32,evaluate_every=8,batch_windows=16,
        weight_decay=.01,clip=5.,tuning_seconds_cap=1800,refit_seconds_cap=600,target_accuracy=.8,code_accuracy_allowance=.01,
        trainable_parameters=24293,
        architecture='Unchanged V49 backbone plus V52 geometry correction. Start each fold from matching V49 '
        'backbone and V52 selected predicted-code head; full refit from matching full checkpoints. '
        'Update existing context,GRU,base movement and correction weights. Map encoder,code readout, '
        'code embedding and goal-query/readout weights stay frozen. No new features or layers.',
        objective='Mean supported movement CE over actual movement rows plus coefficient times mean code '
        'KL over observed rows to the frozen matching V49 teacher. Hindsight codes used for validation '
        'metrics only. Full32-turn recurrence,original masks/resets,identical schedules across configurations.',
        selection='Four fitting-game folds; train all expanded windows from other24games,validate original '
        '64windows of held8games. Retain candidates whose pooled inferred-code correct count loses at '
        'most1percentage point vs warm start. Maximize movement correct count,then minimize movement '
        'NLL,then earlier epoch,then smaller distillation weight. Include epoch0. '
        'Refit one chosen setting; assess it once on unchanged513 movement and699 code queries.',
        limitations='Target80percent is not guaranteed. Repeatedly exposed research data,teacher-forced '
        'history,original backbone/discovery fitting-group exposure,inferred codes,sparse goals and '
        'conditional movement only. Goal forecasts may change through recurrent inputs despite frozen '
        'goal weights; report them. No evaluation-gradient updates,subagents or playing-bot changes.'))


def inputs():
    plan=read(REPORT/'plan.json');check(plan);_,architecture,cache,ids=old.inputs()
    return plan,architecture,cache,ids


def dataset(name,cache):
    receipt=read(old.REPORT/'cache.json');check(receipt)
    geometry=torch.load(old.WORK/'geometry.pt',weights_only=True);targets=torch.load(prior.WORK/'targets.pt',weights_only=True)
    teacher=prior.cached(name)['probabilities']
    return dict(cache,geometry=geometry,support=targets['support'],movement_labels=targets['labels'],teacher=teacher)


def new_model(name,plan,architecture):
    epoch=read(old.REPORT/'selection.json')['selected']['epoch']
    if name=='full':path=ROOT/plan['full_backbone'];saved=torch.load(old.WORK/'predicted.pt',weights_only=False)['correction']
    else:
        k=int(name[-1]);path=ROOT/plan['fold_backbones'][k]
        saved=torch.load(old.WORK/'tuning'/f'predicted-fold{k}'/f'epoch-{epoch:03d}.pt',weights_only=False)['model']
    correction=PathCorrection(saved['mean_probabilities'],True);correction.load_state_dict(saved)
    return JointMovement(prior.backbone(path,architecture),correction)


@torch.no_grad()
def score(net,data,indices):
    total=0.;n=0;correct=0;code_correct=0;code_rows=0;predictions=[];codes=[]
    for start in range(0,len(indices),16):
        item=first.take(data,indices[start:start+16]);out=net(item);mask=item['movement_labels']>=0;observed=item['observed'].bool()
        lp=out['move'].masked_fill(~item['support'],-1e9).log_softmax(-1)[mask];y=item['movement_labels'][mask];p=lp.argmax(-1)
        total+=float((-lp.gather(1,y[:,None]).squeeze(1)).double().sum());n+=len(y);correct+=int((p==y).sum());predictions.extend(p.tolist())
        cp=out['code'][observed].argmax(-1);code_correct+=int((cp==item['labels'][observed]).sum());code_rows+=len(cp);codes.extend(cp.tolist())
    return dict(rows=n,correct=correct,nll=total/n,code_rows=code_rows,code_correct=code_correct,predictions=predictions,code_predictions=codes)


def train(net,data,indices,plan,coefficient,epochs,directory,deadline,held=None):
    directory.mkdir(parents=True,exist_ok=False);parameters=[p for p in net.parameters() if p.requires_grad]
    assert sum(p.numel() for p in parameters)==plan['trainable_parameters']
    opt=torch.optim.AdamW(parameters,lr=plan['learning_rate'],weight_decay=plan['weight_decay']);rng=np.random.default_rng(plan['seed'])
    zero=score(net,data,held) if held is not None else None;torch.save(dict(model=net.state_dict(),optimizer=opt.state_dict()),directory/'epoch-000.pt')
    trace=[];updates=0
    for epoch in range(1,epochs+1):
        order=rng.permutation(indices);norms=[];denominators=[];total=0.;count=0
        for start in range(0,len(order),plan['batch_windows']):
            if time.perf_counter()>=deadline:raise TimeoutError('Joint weight budget exceeded')
            item=first.take(data,order[start:start+plan['batch_windows']]);opt.zero_grad(set_to_none=True)
            loss,movement,kl=losses(net(item),item,coefficient);loss.backward();norm=torch.nn.utils.clip_grad_norm_(parameters,plan['clip'])
            if not torch.isfinite(loss) or not torch.isfinite(norm):raise ValueError('Nonfinite joint update')
            opt.step();updates+=1;m=int((item['movement_labels']>=0).sum());o=int(item['observed'].sum())
            denominators.append([m,o]);norms.append(float(norm));total+=float(movement.detach())*m;count+=m
        entry=dict(epoch=epoch,updates=updates,order=order.tolist(),denominators=denominators,gradient_norms=norms,movement_presentations=count,online_nll=total/count)
        if epoch%plan['evaluate_every']==0 or epoch==epochs:
            if held is not None:entry['validation']=score(net,data,held)
            torch.save(dict(model=net.state_dict(),optimizer=opt.state_dict(),epoch=epoch,updates=updates,rng=rng.bit_generator.state),directory/f'epoch-{epoch:03d}.pt')
            v=entry.get('validation',{});print(directory.name,epoch,'NLL',round(total/count,4),'held moves',v.get('correct'),'codes',v.get('code_correct'),flush=True)
        trace.append(entry)
    immutable_json(directory/'trace.json',dict(initial=zero,epochs=trace));return trace


def combine(values):
    n=sum(v['rows'] for v in values)
    return dict(rows=n,correct=sum(v['correct'] for v in values),nll=sum(v['nll']*v['rows'] for v in values)/n,
                code_rows=sum(v['code_rows'] for v in values),code_correct=sum(v['code_correct'] for v in values))


def choose(candidates,allowance):
    baseline=next(c for c in candidates if c['epoch']==0)
    eligible=[c for c in candidates if c['code_correct']>=baseline['code_correct']-allowance*c['code_rows']]
    return min(eligible,key=lambda c:(-c['correct'],c['nll'],c['epoch'],c['coefficient']))


def tune():
    start=time.perf_counter();plan,architecture,cache,ids=inputs();torch.set_num_threads(1);directory=WORK/'tuning';directory.mkdir(parents=True,exist_ok=False);values={}
    for coefficient in plan['distillation_weights']:
        for fold in range(4):
            data=dataset('fold'+str(fold),cache);training,held=expanded.partition_indices(ids,fold);net=new_model('fold'+str(fold),plan,architecture)
            values[(coefficient,fold,0)]=score(net,data,held)
            trace=train(net,data,training,plan,coefficient,plan['epochs'],directory/f'kl{coefficient:g}-fold{fold}',start+plan['tuning_seconds_cap'],held)
            for entry in trace:
                if 'validation' in entry:values[(coefficient,fold,entry['epoch'])]=entry['validation']
    candidates=[dict(coefficient=c,epoch=e,**combine([values[(c,k,e)] for k in range(4)])) for c in plan['distillation_weights'] for e in range(0,plan['epochs']+1,plan['evaluate_every'])]
    chosen=choose(candidates,plan['code_accuracy_allowance']);bound=bindings([p for p in directory.rglob('*') if p.is_file()]);elapsed=time.perf_counter()-start
    if elapsed>=plan['tuning_seconds_cap']:raise TimeoutError('Joint tuning publication budget exceeded')
    immutable_json(REPORT/'selection.json',dict(plan_sha256=digest(REPORT/'plan.json'),selected=chosen,candidates=candidates,bindings=bound,seconds=elapsed,outer_evaluation_used=False));print('SELECTED',chosen,flush=True)


def refit():
    start=time.perf_counter();plan,architecture,cache,ids=inputs();selection=read(REPORT/'selection.json');check(selection);chosen=selection['selected']
    assert chosen==choose(selection['candidates'],plan['code_accuracy_allowance']);torch.set_num_threads(1)
    data=dataset('full',cache);net=new_model('full',plan,architecture)
    trace=train(net,data,np.arange(len(ids)),plan,chosen['coefficient'],chosen['epoch'],WORK/'refit',start+plan['refit_seconds_cap'])
    torch.save(dict(model=net.state_dict(),inference_only=True,plan_sha256=digest(REPORT/'plan.json'),selection_sha256=digest(REPORT/'selection.json')),WORK/'selected.pt')
    value=score(net,data,np.arange(len(ids)));bound=bindings([WORK/'selected.pt',*(p for p in (WORK/'refit').iterdir() if p.is_file())]);elapsed=time.perf_counter()-start
    if elapsed>=plan['refit_seconds_cap']:raise TimeoutError('Joint refit publication budget exceeded')
    immutable_json(REPORT/'refit.json',dict(selection_sha256=digest(REPORT/'selection.json'),fit=value,updates=trace[-1]['updates'] if trace else 0,bindings=bound,seconds=elapsed))


def policy(plan,architecture):
    saved=torch.load(WORK/'selected.pt',map_location='cpu',weights_only=False)
    assert saved['plan_sha256']==digest(REPORT/'plan.json') and saved['selection_sha256']==digest(REPORT/'selection.json')
    net=new_model('full',plan,architecture);net.load_state_dict(saved['model']);return inference(net)


def assess():
    start=time.perf_counter();plan,architecture,_,_=inputs();check(read(REPORT/'refit.json'));torch.set_num_threads(4)
    windows,maps=original.load();cache=old.encoded_windows(windows,maps,architecture);discovery=read(original.REPORT/'discovery.json');net=policy(plan,architecture);results={};comparison={}
    for split in ('fit','evaluation'):
        value=evaluate(net,windows,maps,cache,discovery,split,start+600);baseline=read(old.WORK/f'predicted-{split}-predictions.json')
        immutable_json(WORK/(split+'-predictions.json'),value);results[split]=value['summary'];comparison[split]=prior.paired(value['records'],baseline['records']);print(split,value['summary'],flush=True)
    x=results['evaluation'];b=read(old.REPORT/'result.json')['results']['predicted']['evaluation']
    target=x['movement_accuracy']>=plan['target_accuracy'];guards=dict(code=x['code_accuracy']>=b['code_accuracy']-plan['code_accuracy_allowance'],movement_nll=x['movement_nll']<=b['movement_nll']+.01)
    bound=bindings([WORK/'selected.pt',WORK/'fit-predictions.json',WORK/'evaluation-predictions.json']);elapsed=time.perf_counter()-start
    if elapsed>=600:raise TimeoutError('Joint assessment publication budget exceeded')
    immutable_json(REPORT/'result.json',dict(refit_sha256=digest(REPORT/'refit.json'),results=results,comparisons=comparison,target_met=target,
        guards=guards,bindings=bound,seconds=elapsed,promoted=False))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('command',choices=('freeze','tune','refit','assess'));globals()[p.parse_args().command]()
