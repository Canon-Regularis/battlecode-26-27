"""One bounded full-map adaptation after adding causal trajectory features."""
import argparse,time
from pathlib import Path
import numpy as np
import torch
from torch.nn import functional as F
from . import planner_readout_fit as previous,planner_weight_edit as planner,trajectory_movement_fit as base
from . import strategic_waypoint_fit as waypoint,model,code_weight_fit as recurrent
from .objective_policy import candidates,choose as choose_goal,movement
from .map_trajectory_weights import MapTrajectory
from ..audit import immutable_json
from ..data import digest

ROOT=base.ROOT;REPORT=ROOT/'tools/action_predictor/experiments/v64';WORK=ROOT/'.cambc/action-predictor/v64'
read,check,bindings=base.read,base.check,base.bindings


def warm(name,parent,architecture):return MapTrajectory(waypoint.selected(name,parent,architecture))


def freeze():
    REPORT.mkdir(parents=True,exist_ok=True);_,parent,architecture,_,_=base.inputs();check(read(previous.REPORT/'verification.json'))
    net=warm('full',parent,architecture)
    immutable_json(REPORT/'plan.json',dict(sources=bindings([Path(__file__).with_name(n) for n in ('map_trajectory_weights.py','map_trajectory_fit.py','map_trajectory_predictor.py','test_map_trajectory.py')]),
        inputs=bindings([base.REPORT/n for n in ('plan.json','selection.json','refit.json','result.json','verification.json')]+[previous.REPORT/n for n in ('plan.json','result.json','verification.json')]+[planner.REPORT/n for n in ('plan.json','selection.json','result.json','verification.json')]),
        seed=64001,epochs=2,learning_rate=.0003,weight_decay=.01,clip=5.,batch_windows=8,coefficient=1.,code_accuracy_allowance=.01,minimum_activation=.1,
        trainable_parameters=sum(p.numel() for p in net.parameters() if p.requires_grad),tuning_seconds_cap=3600,refit_seconds_cap=1200,assessment_seconds_cap=600,
        intervention='Warm start corresponding selected V59 weights. Update existing map encoder,context,GRU,base movement and geometry/heading/command corrections. Freeze code head,embeddings,old goal readout and V62 objective head. No new parameters or features. Unlike V56,this starts after signed trajectory features and V59 adaptation.',
        objective='Original supported movement CE plus code KL to matching selected V59 teacher. Full personal PRE/maps re-encoded. Batch8 complete32turn windows,common actual movement/observed denominators,one update per batch. All1607 expanded fitting windows; four fitting-game folds,held canonical64windows.',
        selection='Epochs0,1,2 on held fitting groups only. Select highest combined planner movement count with at most1point code loss,nonnegative progress utility and at least10percent goal activity; then direct movement NLL,earlier epoch. Same V62 head edits and retention rules across all checkpoints. One full selected refit. Stop incomplete budget without selecting partial results.',
        success='Combined evaluation movement must exceed V62 and V59 direct,with positive utility and at least10percent active goals; code loses at most1point and direct movement NLL worsens at most0.01.80percent requires411of513 original movement queries. No evaluation-dependent selection or promotion.',
        limits='Preexposed research games,inherited fold exposure,teacher-forced past commands,inferred code/objective labels,conditional movement. Encoder changes can change code and goals despite frozen heads. Training tests full-map adaptation plus smaller batches,not isolated map causality. No autonomous rollout/strategy proof,no subagents.'))


def inputs():
    p=read(REPORT/'plan.json');check(p);_,parent,architecture,cache,ids=base.inputs();return p,parent,architecture,cache,ids


def environment(name,parent,architecture,cache,ids):
    windows,maps=base.heading.expanded.read();data=base.dataset(name,cache);teacher=[];net=waypoint.selected(name,parent,architecture)
    assert all(w['key']==ids[i]['key'] and w['partition']=='fit' for i,w in enumerate(windows))
    with torch.no_grad():
        for start in range(0,len(ids),16):teacher.append(net(recurrent.take(data,slice(start,start+16)))['code'].softmax(-1))
    targets={(r['key'],r['position']):{c['key']:c['utility'] for c in r['candidates']} for r in read(planner.old.WORK/'rows.json')}
    head=planner.old.new(read(planner.old.REPORT/'plan.json'));epoch=read(planner.old.REPORT/'selection.json')['selected']['epoch']
    path=planner.old.WORK/'selected.pt' if name=='full' else planner.old.WORK/name/f'epoch-{epoch:03d}.pt'
    selected=read(planner.REPORT/'selection.json')['selected'];head.load_state_dict(planner.edit(torch.load(path,weights_only=True),selected['scale'],selected['shift']));head.requires_grad_(False)
    return dict(windows=windows,maps=maps,schema=architecture['schema'],data=data,teacher=torch.cat(teacher),head=head,targets=targets)


def encoded(env,i):
    w=env['windows'][i];args,_=model.encode_window(w,env['maps'][w['payload']],env['schema'])
    for k in ('geometry','heading','command_heading'):args[k]=env['data'][k][i]
    return args


@torch.no_grad()
def score(net,env,indices):
    n=correct=combined=code_rows=code_correct=active=available=utility_rows=0;loss=utility_sum=0.;predictions=[]
    for i in indices:
        w=env['windows'][i];args=encoded(env,i);out=net(args);support=env['data']['support'][i];labels=env['data']['movement_labels'][i]
        lp=out['move'].masked_fill(~support,-1e9).log_softmax(-1);mask=labels>=0;y=labels[mask];n+=len(y);correct+=int((lp[mask].argmax(-1)==y).sum());loss+=float(-lp[mask].gather(1,y[:,None]).double().sum())
        observed=args['observed'].bool();code_rows+=int(observed.sum());code_correct+=int((out['code'][observed].argmax(-1)==env['data']['labels'][i][observed]).sum());remembered=None
        for j,s in enumerate(w['steps']):
            if not s['observed']:continue
            cs=candidates(s['input'],env['maps'][w['payload']]);scores=[]
            if cs:scores=env['head'](torch.stack([torch.cat((out['context'][j],torch.tensor(c['features']))) for c in cs])).tolist()
            chosen,remembered,_=choose_goal(cs,scores,remembered,.15);pred=int(lp[j].argmax())
            if chosen is not None:pred=movement(chosen,s['input'],env['maps'][w['payload']],lp[j].exp().tolist())
            active+=chosen is not None;available+=bool(cs)
            if labels[j]>=0:combined+=pred==int(labels[j])
            target=env['targets'].get((w['key'],j))
            if target is not None:utility_rows+=1;utility_sum+=target.get(remembered,0.)
            predictions.append(dict(key=w['key'],position=j,prediction=pred,selected=remembered,direct=int(lp[j].argmax()),label=int(labels[j])))
    return dict(rows=n,correct=correct,combined=combined,nll=loss/n,code_rows=code_rows,code_correct=code_correct,active=active,available=available,utility_rows=utility_rows,utility_sum=utility_sum,predictions=predictions)


def train(net,env,indices,p,epochs,directory,deadline,held=None):
    directory.mkdir(parents=True,exist_ok=False);params=[x for x in net.parameters() if x.requires_grad];assert sum(x.numel() for x in params)==p['trainable_parameters']
    opt=torch.optim.AdamW(params,lr=p['learning_rate'],weight_decay=p['weight_decay']);rng=np.random.default_rng(p['seed']);updates=0;trace=[]
    initial=score(net,env,held) if held is not None else None;torch.save(dict(model=net.state_dict(),optimizer=opt.state_dict()),directory/'epoch-000.pt')
    for epoch in range(1,epochs+1):
        order=rng.permutation(indices);norms=[];denominators=[];total=0.;count=0
        for start in range(0,len(order),p['batch_windows']):
            batch=order[start:start+p['batch_windows']];m=sum(int((env['data']['movement_labels'][i]>=0).sum()) for i in batch);o=sum(sum(s['observed'] for s in env['windows'][i]['steps']) for i in batch);opt.zero_grad(set_to_none=True)
            for i in batch:
                if time.perf_counter()>=deadline:raise TimeoutError('Map trajectory training cap exceeded')
                args=encoded(env,i);out=net(args);mask=env['data']['movement_labels'][i]>=0;observed=args['observed'].bool();logits=out['move'].masked_fill(~env['data']['support'][i],-1e9)
                move=F.cross_entropy(logits[mask],env['data']['movement_labels'][i][mask],reduction='sum') if mask.any() else logits.sum()*0
                kl=F.kl_div(out['code'][observed].log_softmax(-1),env['teacher'][i][observed],reduction='sum');loss=move/max(m,1)+p['coefficient']*kl/o
                assert torch.isfinite(loss);loss.backward();total+=float(move.detach());count+=int(mask.sum());del out,args,loss,move,kl,logits
            norm=torch.nn.utils.clip_grad_norm_(params,p['clip']);assert torch.isfinite(norm);opt.step();updates+=1;norms.append(float(norm));denominators.append([m,o])
            if updates%32==0:print(directory.name,epoch,'updates',updates,flush=True)
        entry=dict(epoch=epoch,updates=updates,order=order.tolist(),norms=norms,denominators=denominators,movement_presentations=count,online_nll=total/count)
        if held is not None:entry['validation']=score(net,env,held)
        torch.save(dict(model=net.state_dict(),optimizer=opt.state_dict(),rng=rng.bit_generator.state,epoch=epoch,updates=updates),directory/f'epoch-{epoch:03d}.pt');trace.append(entry)
        print(directory.name,epoch,'direct/combined',[(entry.get('validation') or {}).get(k) for k in ('correct','combined')],flush=True)
    immutable_json(directory/'trace.json',dict(initial=initial,epochs=trace));return initial,trace


def combine(values):
    result={k:sum(v[k] for v in values) for k in ('rows','correct','combined','code_rows','code_correct','active','available','utility_rows','utility_sum')};result['nll']=sum(v['nll']*v['rows'] for v in values)/result['rows'];return result


def choose(cs,p):
    initial=cs[0];eligible=[c for c in cs if c['code_correct']>=initial['code_correct']-p['code_accuracy_allowance']*c['code_rows'] and c['active']>=p['minimum_activation']*c['available'] and c['utility_sum']>=0]
    if not eligible:raise ValueError('No eligible map trajectory checkpoint')
    return min(eligible,key=lambda c:(-c['combined'],c['nll'],c['epoch']))


def tune():
    start=time.perf_counter();p,parent,architecture,cache,ids=inputs();torch.set_num_threads(4);values={}
    for fold in range(4):
        name=f'fold{fold}';env=environment(name,parent,architecture,cache,ids);net=warm(name,parent,architecture);training,held=base.heading.folds.partition_indices(ids,fold)
        initial,trace=train(net,env,training,p,p['epochs'],WORK/'tuning'/name,start+p['tuning_seconds_cap'],held);values[(fold,0)]=initial
        for e in trace:values[(fold,e['epoch'])]=e['validation']
    cs=[dict(epoch=e,**combine([values[(k,e)] for k in range(4)])) for e in range(p['epochs']+1)];bound=bindings([q for q in (WORK/'tuning').rglob('*') if q.is_file()]);elapsed=time.perf_counter()-start
    if elapsed>=p['tuning_seconds_cap']:raise TimeoutError('Map trajectory tuning publication cap exceeded')
    immutable_json(REPORT/'selection.json',dict(selected=choose(cs,p),candidates=cs,bindings=bound,seconds=elapsed,evaluation_used=False));print('SELECTED',choose(cs,p),flush=True)


def refit():
    start=time.perf_counter();p,parent,architecture,cache,ids=inputs();selection=read(REPORT/'selection.json');check(selection);assert choose(selection['candidates'],p)==selection['selected'];torch.set_num_threads(4)
    env=environment('full',parent,architecture,cache,ids);net=warm('full',parent,architecture);_,trace=train(net,env,np.arange(len(ids)),p,selection['selected']['epoch'],WORK/'refit',start+p['refit_seconds_cap'])
    torch.save(dict(model=net.state_dict()),WORK/'selected.pt');bound=bindings([WORK/'selected.pt',*(q for q in (WORK/'refit').iterdir() if q.is_file())]);elapsed=time.perf_counter()-start
    if elapsed>=p['refit_seconds_cap']:raise TimeoutError('Map trajectory refit publication cap exceeded')
    immutable_json(REPORT/'refit.json',dict(bindings=bound,seconds=elapsed,updates=trace[-1]['updates'] if trace else 0))


def assessment_environment(parent,architecture,cache,ids):
    env=environment('full',parent,architecture,cache,ids);windows,maps=base.heading.original.load();encoded_data,history,bound=base.prior.encoded(windows,maps,architecture)
    examples=planner.old.examples(windows,maps,history,[dict(fold=-1,canonical=True) for w in windows]);env.update(windows=windows,maps=maps,targets={(r['key'],r['position']):{c['key']:c['utility'] for c in r['candidates']} for r in examples})
    env['data']={k:torch.stack([encoded_data[w['key']][k] for w in windows]) for k in ('geometry','heading','command_heading')}
    discovery=read(base.heading.original.REPORT/'discovery.json')
    env['data'].update(support=torch.stack([model.move_support(w)[0] for w in windows]),movement_labels=torch.stack([model.move_support(w)[1] for w in windows]),labels=torch.stack([torch.tensor(discovery['labels'][w['key']]) for w in windows]))
    return env,bound


def assess():
    start=time.perf_counter();p,parent,architecture,cache,ids=inputs();check(read(REPORT/'refit.json'));torch.set_num_threads(4);env,bound=assessment_environment(parent,architecture,cache,ids)
    net=warm('full',parent,architecture);net.load_state_dict(torch.load(WORK/'selected.pt',weights_only=False)['model']);results={}
    for split in ('fit','evaluation'):
        results[split]=score(net,env,[i for i,w in enumerate(env['windows']) if w['partition']==split]);print(split,{k:v for k,v in results[split].items() if k!='predictions'},flush=True)
    x=results['evaluation'];b=read(base.REPORT/'result.json')['results']['evaluation'];previous_value=read(planner.REPORT/'result.json')['results']['evaluation']['edited']
    gates=dict(combined=x['combined']>previous_value['correct'],direct_reference=x['combined']>318,utility=x['utility_sum']>0,active=x['active']>=.1*x['available'],code=x['code_correct']/x['code_rows']>=b['code_accuracy']-.01,nll=x['nll']<=b['movement_nll']+.01)
    elapsed=time.perf_counter()-start
    if elapsed>=p['assessment_seconds_cap']:raise TimeoutError('Map trajectory assessment cap exceeded')
    immutable_json(REPORT/'result.json',dict(results=results,checks=gates,all_checks_pass=all(gates.values()),target_met=x['combined']>=411 and x['rows']==513,bindings=bindings([WORK/'selected.pt']),source_bindings=bound,seconds=elapsed,promoted=False))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('command',choices=('freeze','tune','refit','assess'));globals()[p.parse_args().command]()
