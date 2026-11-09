"""Bounded full-map weight adaptation toward the unchanged80% movement target."""
import argparse,time
from pathlib import Path
import numpy as np
import torch
from torch.nn import functional as F
from . import movement_bias_edit as bias,joint_movement_fit as joint,code_path_fit as old,expanded_code_data as expanded
from . import expanded_code_fit as expanded_fit,code_weight_fit as first,data as original,model
from .full_movement_weights import FullMovement
from .joint_movement_weights import JointMovement,inference
from .study import evaluate
from ..audit import immutable_json
from ..data import digest

ROOT=original.ROOT;REPORT=ROOT/'tools/action_predictor/experiments/v56';WORK=ROOT/'.cambc/action-predictor/v56'
read=joint.read;check=joint.check;bindings=joint.bindings


def freeze():
    REPORT.mkdir(parents=True,exist_ok=True);_,parent,architecture,cache,ids=bias.inputs()
    check(read(bias.REPORT/'result.json'));check(read(bias.REPORT/'refit.json'))
    sources=[Path(__file__).with_name(n) for n in ('full_movement_weights.py','full_movement_fit.py','full_movement_predictor.py','full_movement_verify.py','test_full_movement.py')]
    paths=[bias.REPORT/n for n in ('plan.json','selection.json','refit.json','result.json','verification.json')]
    immutable_json(REPORT/'plan.json',dict(sources=bindings(sources),inputs=bindings(paths),seed=56001,
        epochs=2,learning_rate=.0003,batch_windows=8,coefficient=1.,weight_decay=.01,clip=5.,
        tuning_seconds_cap=3600,refit_seconds_cap=1200,target_accuracy=.8,code_accuracy_allowance=.01,
        trainable_parameters=46821,
        intervention='Same V49/V52 neural architecture and features; warm start each fold/full model '
        'from its corresponding selected V54 weights plus V55 bias. Update map encoder,context,GRU, '
        'base movement and geometry correction. Freeze code readout,code embeddings and goal-query/readout weights. '
        'A complete32-turn window forward/backward is freed before the next window; accumulate8windows '
        'with their common movement and observed-row denominators before one optimizer update.',
        objective='Supported movement CE plus code KL to the frozen matching warm-start teacher with weight1. '
        'All1607 existing fitting windows retained; four whole-game folds train other24games and validate '
        'the original64windows in held8games. No future/code labels in inputs. Full personal PRE/maps '
        're-encoded for every window, with original masking and reset semantics.',
        selection='Evaluate epochs0,1,2. Choose most pooled correct moves among candidates losing at most '
        '1percentage point of inferred-code accuracy vs warm start; then lowest movementNLL,earliest epoch. '
        'Refit one setting on all fitting windows; assess selected checkpoint once on unchanged research queries.',
        limitations='This also changes batch size/update cadence relative to V54; it does not isolate map '
        'weights as a unique cause. Previously exposed groups,inherited fitting-group exposure,observed '
        'command history,inferred codes,sparse goals and conditional movement. Frozen goal weights do '
        'not guarantee unchanged goal outputs when encoder states change. No subagents or promotion.'))


def inputs():
    plan=read(REPORT/'plan.json');check(plan);_,parent,architecture,cache,ids=bias.inputs()
    return plan,parent,architecture,cache,ids


def warm(name,parent,architecture):
    net=joint.new_model(name,parent,architecture)
    if name=='full':saved=torch.load(bias.WORK/'selected.pt',weights_only=False)['model']
    else:
        selected=read(joint.REPORT/'selection.json')['selected'];fold=int(name[-1])
        saved=torch.load(joint.WORK/'tuning'/f"kl{selected['coefficient']:g}-fold{fold}"/f"epoch-{selected['epoch']:03d}.pt",weights_only=False)['model']
        bound=read(bias.REPORT/'selection.json')['selected']['bound'];delta=read(bias.WORK/'calibration.json')[f'{fold}/{bound:g}']['bias']
        saved['backbone.movement.bias']=saved['backbone.movement.bias']+torch.tensor(delta)
    net.load_state_dict(saved);return FullMovement(net.backbone,net.correction)


def environment(parent,architecture,cache,ids,name):
    windows,maps=expanded.read();data=joint.dataset(name,cache)
    assert all(w['key']==ids[i]['key'] and w['partition']=='fit' for i,w in enumerate(windows))
    net=warm(name,parent,architecture);teacher=[]
    with torch.no_grad():
        for start in range(0,len(ids),16):teacher.append(JointMovement.forward(net,first.take(data,slice(start,start+16)))['code'].softmax(-1))
    return dict(windows=windows,maps=maps,schema=architecture['schema'],geometry=data['geometry'],
                support=data['support'],labels=data['movement_labels'],codes=data['labels'],teacher=torch.cat(teacher))


def encoded(env,i):
    w=env['windows'][i];args,_=model.encode_window(w,env['maps'][w['payload']],env['schema']);args['geometry']=env['geometry'][i]
    return args


@torch.no_grad()
def score(net,env,indices):
    total=0.;n=0;correct=0;code_correct=0;code_rows=0;predictions=[];codes=[]
    for i in indices:
        args=encoded(env,i);out=net(args);mask=env['labels'][i]>=0;observed=args['observed'].bool()
        lp=out['move'].masked_fill(~env['support'][i],-1e9).log_softmax(-1)[mask];y=env['labels'][i][mask];p=lp.argmax(-1)
        n+=len(y);correct+=int((p==y).sum());total+=float((-lp.gather(1,y[:,None]).squeeze(1)).double().sum());predictions.extend(p.tolist())
        cp=out['code'][observed].argmax(-1);code_rows+=len(cp);code_correct+=int((cp==env['codes'][i][observed]).sum());codes.extend(cp.tolist())
    return dict(rows=n,correct=correct,nll=total/n,code_rows=code_rows,code_correct=code_correct,predictions=predictions,code_predictions=codes)


def train(net,env,indices,plan,epochs,directory,deadline,held=None):
    directory.mkdir(parents=True,exist_ok=False);parameters=[p for p in net.parameters() if p.requires_grad]
    assert sum(p.numel() for p in parameters)==plan['trainable_parameters']
    opt=torch.optim.AdamW(parameters,lr=plan['learning_rate'],weight_decay=plan['weight_decay']);rng=np.random.default_rng(plan['seed'])
    zero=score(net,env,held) if held is not None else None;torch.save(dict(model=net.state_dict(),optimizer=opt.state_dict()),directory/'epoch-000.pt')
    trace=[];updates=0
    for epoch in range(1,epochs+1):
        order=rng.permutation(indices);denominators=[];norms=[];total=0.;count=0
        for start in range(0,len(order),plan['batch_windows']):
            if time.perf_counter()>=deadline:raise TimeoutError('Full movement weight budget exceeded')
            batch=order[start:start+plan['batch_windows']]
            m=sum(int((env['labels'][i]>=0).sum()) for i in batch)
            o=sum(sum(s['observed'] for s in env['windows'][i]['steps']) for i in batch)
            opt.zero_grad(set_to_none=True)
            for i in batch:
                if time.perf_counter()>=deadline:raise TimeoutError('Full movement batch exceeded budget')
                args=encoded(env,i);out=net(args);mask=env['labels'][i]>=0;observed=args['observed'].bool()
                logits=out['move'].masked_fill(~env['support'][i],-1e9)
                move=F.cross_entropy(logits[mask],env['labels'][i][mask],reduction='sum') if mask.any() else logits.sum()*0
                kl=F.kl_div(out['code'][observed].log_softmax(-1),env['teacher'][i][observed],reduction='sum')
                loss=move/max(m,1)+plan['coefficient']*kl/o
                if not torch.isfinite(loss):raise ValueError('Nonfinite full movement loss')
                loss.backward();total+=float(move.detach());count+=int(mask.sum())
                del out,args,loss,move,kl,logits
            norm=torch.nn.utils.clip_grad_norm_(parameters,plan['clip'])
            if not torch.isfinite(norm):raise ValueError('Nonfinite full movement gradient')
            opt.step();updates+=1;denominators.append([m,o]);norms.append(float(norm))
            if updates%32==0:print(directory.name,'epoch',epoch,'updates',updates,flush=True)
        entry=dict(epoch=epoch,updates=updates,order=order.tolist(),denominators=denominators,gradient_norms=norms,movement_presentations=count,online_nll=total/count)
        if held is not None:entry['validation']=score(net,env,held)
        torch.save(dict(model=net.state_dict(),optimizer=opt.state_dict(),epoch=epoch,updates=updates,rng=rng.bit_generator.state),directory/f'epoch-{epoch:03d}.pt')
        trace.append(entry);v=entry.get('validation',{});print(directory.name,'epoch',epoch,'NLL',total/count,'held moves',v.get('correct'),'codes',v.get('code_correct'),flush=True)
    immutable_json(directory/'trace.json',dict(initial=zero,epochs=trace));return trace


def choose(candidates,allowance):
    initial=candidates[0];eligible=[c for c in candidates if c['code_correct']>=initial['code_correct']-allowance*c['code_rows']]
    return min(eligible,key=lambda c:(-c['correct'],c['nll'],c['epoch']))


def tune():
    start=time.perf_counter();plan,parent,architecture,cache,ids=inputs();torch.set_num_threads(4);directory=WORK/'tuning';directory.mkdir(parents=True,exist_ok=False);values={}
    for fold in range(4):
        name='fold'+str(fold);env=environment(parent,architecture,cache,ids,name);training,held=expanded_fit.partition_indices(ids,fold);net=warm(name,parent,architecture)
        values[(fold,0)]=score(net,env,held)
        trace=train(net,env,training,plan,plan['epochs'],directory/name,start+plan['tuning_seconds_cap'],held)
        for e in trace:values[(fold,e['epoch'])]=e['validation']
    candidates=[dict(epoch=e,**joint.combine([values[(k,e)] for k in range(4)])) for e in range(plan['epochs']+1)]
    chosen=choose(candidates,plan['code_accuracy_allowance']);bound=bindings([p for p in directory.rglob('*') if p.is_file()]);elapsed=time.perf_counter()-start
    if elapsed>=plan['tuning_seconds_cap']:raise TimeoutError('Full movement tuning publication budget exceeded')
    immutable_json(REPORT/'selection.json',dict(plan_sha256=digest(REPORT/'plan.json'),selected=chosen,candidates=candidates,bindings=bound,seconds=elapsed,outer_evaluation_used=False));print('SELECTED',chosen,flush=True)


def refit():
    start=time.perf_counter();plan,parent,architecture,cache,ids=inputs();selection=read(REPORT/'selection.json');check(selection);chosen=selection['selected']
    assert chosen==choose(selection['candidates'],plan['code_accuracy_allowance']);torch.set_num_threads(4)
    env=environment(parent,architecture,cache,ids,'full');net=warm('full',parent,architecture)
    trace=train(net,env,np.arange(len(ids)),plan,chosen['epoch'],WORK/'refit',start+plan['refit_seconds_cap'])
    torch.save(dict(model=net.state_dict(),inference_only=True,plan_sha256=digest(REPORT/'plan.json'),selection_sha256=digest(REPORT/'selection.json')),WORK/'selected.pt')
    value=score(net,env,[i for i,r in enumerate(ids) if r['canonical']]);bound=bindings([WORK/'selected.pt',*(p for p in (WORK/'refit').iterdir() if p.is_file())]);elapsed=time.perf_counter()-start
    if elapsed>=plan['refit_seconds_cap']:raise TimeoutError('Full movement refit publication budget exceeded')
    immutable_json(REPORT/'refit.json',dict(selection_sha256=digest(REPORT/'selection.json'),original_fit=value,updates=trace[-1]['updates'] if trace else 0,seconds=elapsed,bindings=bound))


def policy(plan,parent,architecture):
    saved=torch.load(WORK/'selected.pt',weights_only=False)
    assert saved['plan_sha256']==digest(REPORT/'plan.json') and saved['selection_sha256']==digest(REPORT/'selection.json')
    net=warm('full',parent,architecture);net.load_state_dict(saved['model']);return inference(net)


def assess():
    start=time.perf_counter();plan,parent,architecture,cache,ids=inputs();check(read(REPORT/'refit.json'));torch.set_num_threads(4)
    windows,maps=original.load();encoded_data=old.encoded_windows(windows,maps,architecture);discovery=read(original.REPORT/'discovery.json');net=policy(plan,parent,architecture);results={};comparisons={}
    for split in ('fit','evaluation'):
        value=evaluate(net,windows,maps,encoded_data,discovery,split,start+600);baseline=read(bias.WORK/(split+'-predictions.json'))
        immutable_json(WORK/(split+'-predictions.json'),value);results[split]=value['summary'];comparisons[split]=joint.prior.paired(value['records'],baseline['records']);print(split,value['summary'],flush=True)
    b=read(bias.REPORT/'result.json')['results']['evaluation'];x=results['evaluation'];guards=dict(code=x['code_accuracy']>=b['code_accuracy']-.01,nll=x['movement_nll']<=b['movement_nll']+.01)
    bound=bindings([WORK/'selected.pt',WORK/'fit-predictions.json',WORK/'evaluation-predictions.json']);elapsed=time.perf_counter()-start
    if elapsed>=600:raise TimeoutError('Full movement assessment exceeded')
    immutable_json(REPORT/'result.json',dict(refit_sha256=digest(REPORT/'refit.json'),results=results,comparisons=comparisons,target_met=x['movement_accuracy']>=.8,
        guards=guards,bindings=bound,seconds=elapsed,promoted=False))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('command',choices=('freeze','tune','refit','assess'));globals()[p.parse_args().command]()
