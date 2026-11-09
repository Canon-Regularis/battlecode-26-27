"""Fitting-game selection and verification-ready archives for destination weights."""
import argparse,time
from pathlib import Path
import numpy as np
import torch
from . import code_path_fit as movement,code_movement_fit as prior,expanded_code_data as expanded
from . import data as original,model
from .destination_weights import DestinationHead,install,pack
from .study import endpoint_labels,evaluate
from ..audit import immutable_json
from ..data import digest

ROOT=original.ROOT;REPORT=ROOT/'tools/action_predictor/experiments/v53';WORK=ROOT/'.cambc/action-predictor/v53'
read=prior.read;check=prior.check;bindings=prior.bindings


def freeze():
    REPORT.mkdir(parents=True,exist_ok=True);plan,architecture,_,ids=movement.inputs()
    for path in (movement.REPORT/'result.json',movement.REPORT/'refit.json'):check(read(path))
    sources=[Path(__file__).with_name(n) for n in ('destination_weights.py','destination_weight_fit.py','destination_weight_verify.py','destination_predictor.py','test_destination_weights.py')]
    paths=[movement.REPORT/n for n in ('plan.json','result.json','verification.json')]+[prior.REPORT/'cache.json',expanded.WORK/'labels.json']
    immutable_json(REPORT/'plan.json',dict(sources=bindings(sources),inputs=bindings(paths),
        fold_backbones=plan['fold_backbones'],full_backbone=plan['full_backbone'],seed=53001,
        learning_rates=[.0003,.001],epochs=16,evaluate_every=4,batch_rows=16,weight_decay=.01,clip=5.,
        tuning_seconds_cap=1800,refit_seconds_cap=600,
        trainable_parameters=1840,unchanged_architecture=True,
        objective='Supported full-map exact endpoint cross entropy. Update existing query and goal weights only; '
        'freeze final common scalar bias, map encoder, recurrent/code/embedding/movement weights and V52 correction. '
        'The original pointwise goal head is evaluated in equivalent factored linear form for caching.',
        labels='Frozen V43 switching prototypes and unchanged next-segment endpoint definition. '
        'Use all1607 V49 fitting windows;2099 goal labels in32games. Verify exact original369 labels. '
        'Future frames/code assignments supply labels only, never features. No endpoint imputation or new codes.',
        selection='Four fitting-game folds using corresponding V49 backbones; train expanded other24games, '
        'validate only original369 queries across held folds. Choose highest within2 correct count, then '
        'exact count, then smallest mean error, NLL, epoch and learning rate. Epoch0 is eligible. '
        'Refit selected setting on all fitting games; assess one selected checkpoint on unchanged98 evaluation goals.',
        success='At least5percentage points higher within2 endpoint accuracy vsV49/V52, exact accuracy no worse, '
        'lower mean endpoint error and NLL, and A* movement correctness no worse. '
        'Code and direct V52 movement outputs must remain identical. No promotion.',
        limitations='Previously exposed research games; hindsight-inferred endpoints, selected missing frames, '
        'teacher-forced histories and original backbone/discovery fitting-group exposure. '
        'No verified Fish intent, full-command or playing-strength claim. No subagents.'))


def inputs():
    plan=read(REPORT/'plan.json');check(plan);_,architecture,cache,ids=movement.inputs()
    return plan,architecture,cache,ids


def prepare():
    plan,architecture,cache,ids=inputs();WORK.mkdir(parents=True,exist_ok=False);torch.set_num_threads(4)
    windows,maps=expanded.read();codes=read(expanded.WORK/'labels.json')['labels'];old=read(original.REPORT/'discovery.json')
    net=prior.backbone(ROOT/plan['full_backbone'],architecture);rows=[];identities=[];canonical=0;max_error=0.;captured=[]
    head=DestinationHead(net).eval();hook=net.goal.register_forward_pre_hook(lambda module,args:captured.append(args[0]))
    full=prior.cached('full');weight_stats={k:dict(shape=list(v.shape),norm=float(v.norm()),minimum=float(v.min()),maximum=float(v.max()))
        for k,v in net.state_dict().items() if k.startswith(('query.','goal.'))}
    with torch.no_grad():
        for wi,w in enumerate(windows):
            goals,_=endpoint_labels(w,codes[w['key']],maps[w['payload']])
            if ids[wi]['canonical']:
                assert goals==old['endpoints'][w['key']];canonical+=sum(g is not None for g in goals)
            selected=[i for i,g in enumerate(goals) if g is not None]
            if not selected:continue
            args,_=model.encode_window(w,maps[w['payload']],architecture['schema']);output=net(**args);feature=captured.pop()
            width=maps[w['payload']]['width']
            shared=torch.cat((full['states'][wi],full['probabilities'][wi]@net.embeddings),-1)
            for i in selected:
                mask=args['batch']['valid'][i].flatten();cells=mask.nonzero().flatten();target=goals[i][1]*width+goals[i][0]
                index=(cells==target).nonzero().flatten();assert len(index)==1
                row=dict(spatial=feature[i,:16].flatten(1).T[mask].clone(),whole=feature[i,32:,0,0].clone(),
                         cells=cells.clone(),width=width,target=int(index[0]),goal=goals[i])
                packed,y=pack([row],shared[i:i+1],[0]);actual=head(**packed)[0]
                expected=output['goal'][i].flatten()[mask]
                torch.testing.assert_close(actual,expected,atol=3e-6,rtol=3e-5)
                max_error=max(max_error,float((actual-expected).abs().max()))
                rows.append(row);identities.append(dict(**ids[wi],window=wi,position=i,event=w['steps'][i]['event']))
            if (wi+1)%200==0:print('Destination features',wi+1,'/',len(windows),flush=True)
    hook.remove();assert len(rows)==2099 and canonical==369
    torch.save(rows,WORK/'rows.pt');immutable_json(WORK/'identities.json',identities)
    for name,path in [*(('fold'+str(k),ROOT/p) for k,p in enumerate(plan['fold_backbones'])),('full',ROOT/plan['full_backbone'])]:
        other=prior.backbone(path,architecture)
        for k,v in net.state_dict().items():
            if k.startswith(('maps.','embeddings','goal.','query.')):assert torch.equal(v,other.state_dict()[k]),k
        features=prior.cached(name);shared=torch.cat((features['states'],features['probabilities']@other.embeddings),-1)
        torch.save(torch.stack([shared[r['window'],r['position']] for r in identities]),WORK/(name+'-shared.pt'))
    paths=[WORK/'rows.pt',WORK/'identities.json',*(WORK/(n+'-shared.pt') for n in ('full','fold0','fold1','fold2','fold3'))]
    immutable_json(REPORT/'cache.json',dict(plan_sha256=digest(REPORT/'plan.json'),bindings=bindings(paths),
        rows=len(rows),original_labels_exact=canonical,maximum_factored_logit_error=max_error,weight_statistics=weight_stats,
        common_bias_cannot_change_softmax_or_argmax=True,fitting_only=True))
    print('Prepared',len(rows),'destination examples; original labels',canonical,'max logit error',max_error,flush=True)


def cached():
    receipt=read(REPORT/'cache.json');check(receipt);assert receipt['plan_sha256']==digest(REPORT/'plan.json')
    return torch.load(WORK/'rows.pt',weights_only=True),read(WORK/'identities.json')


def new_head(path,architecture):return DestinationHead(prior.backbone(path,architecture))


@torch.no_grad()
def score(head,rows,shared,indices):
    errors=[];losses=[];predictions=[]
    for start in range(0,len(indices),16):
        batch=indices[start:start+16];args,y=pack(rows,shared,batch);lp=head(**args).log_softmax(-1)
        predicted=lp.argmax(-1);losses.extend((-lp.gather(1,y[:,None]).squeeze(1)).double().tolist())
        for ri,pi in zip(batch,predicted.tolist()):
            r=rows[ri];cell=int(r['cells'][pi]);p=[cell%r['width'],cell//r['width']];predictions.append(p)
            errors.append(max(abs(p[0]-r['goal'][0]),abs(p[1]-r['goal'][1])))
    return dict(rows=len(errors),within2=sum(e<=2 for e in errors),exact=errors.count(0),
                error_sum=sum(errors),nll=sum(losses)/len(errors),predictions=predictions)


def train(head,rows,shared,indices,plan,lr,epochs,directory,deadline,held=None):
    directory.mkdir(parents=True,exist_ok=False);parameters=[p for p in head.parameters() if p.requires_grad]
    assert sum(p.numel() for p in parameters)==plan['trainable_parameters']
    opt=torch.optim.AdamW(parameters,lr=lr,weight_decay=plan['weight_decay']);rng=np.random.default_rng(plan['seed'])
    trace=[];updates=0;zero=score(head,rows,shared,held) if held is not None else None
    torch.save(dict(model=head.state_dict(),optimizer=opt.state_dict()),directory/'epoch-000.pt')
    for epoch in range(1,epochs+1):
        order=rng.permutation(indices);norms=[];counts=[];total=0.
        for start in range(0,len(order),plan['batch_rows']):
            if time.perf_counter()>=deadline:raise TimeoutError('Destination fitting budget exceeded')
            batch=order[start:start+plan['batch_rows']];args,y=pack(rows,shared,batch)
            opt.zero_grad(set_to_none=True);loss=torch.nn.functional.cross_entropy(head(**args),y);loss.backward()
            norm=torch.nn.utils.clip_grad_norm_(parameters,plan['clip'])
            if not torch.isfinite(loss) or not torch.isfinite(norm):raise ValueError('Nonfinite destination fit')
            opt.step();updates+=1;norms.append(float(norm));counts.append(len(batch));total+=float(loss.detach())*len(batch)
        entry=dict(epoch=epoch,updates=updates,order=order.tolist(),denominators=counts,gradient_norms=norms,online_nll=total/len(order))
        if epoch%plan['evaluate_every']==0 or epoch==epochs:
            if held is not None:entry['validation']=score(head,rows,shared,held)
            torch.save(dict(model=head.state_dict(),optimizer=opt.state_dict(),epoch=epoch,updates=updates,rng=rng.bit_generator.state),directory/f'epoch-{epoch:03d}.pt')
            print(directory.name,epoch,'NLL',round(total/len(order),4),'held within2',entry.get('validation',{}).get('within2'),flush=True)
        trace.append(entry)
    immutable_json(directory/'trace.json',dict(initial=zero,epochs=trace));return trace


def combine(values):
    n=sum(v['rows'] for v in values)
    return dict(rows=n,within2=sum(v['within2'] for v in values),exact=sum(v['exact'] for v in values),
                error_sum=sum(v['error_sum'] for v in values),nll=sum(v['nll']*v['rows'] for v in values)/n)


def choose(candidates):return min(candidates,key=lambda c:(-c['within2'],-c['exact'],c['error_sum']/c['rows'],c['nll'],c['epoch'],c['learning_rate']))


def tune():
    start=time.perf_counter();plan,architecture,_,_=inputs();rows,ids=cached();torch.set_num_threads(1)
    directory=WORK/'tuning';directory.mkdir(exist_ok=False);values={}
    for lr in plan['learning_rates']:
        for fold in range(4):
            training=np.array([i for i,r in enumerate(ids) if r['fold']!=fold]);held=np.array([i for i,r in enumerate(ids) if r['fold']==fold and r['canonical']])
            assert not {ids[i]['group'] for i in training}&{ids[i]['group'] for i in held}
            shared=torch.load(WORK/f'fold{fold}-shared.pt',weights_only=True);head=new_head(ROOT/plan['fold_backbones'][fold],architecture)
            values[(lr,fold,0)]=score(head,rows,shared,held)
            trace=train(head,rows,shared,training,plan,lr,plan['epochs'],directory/f'lr{lr:g}-fold{fold}',start+plan['tuning_seconds_cap'],held)
            for entry in trace:
                if 'validation' in entry:values[(lr,fold,entry['epoch'])]=entry['validation']
    candidates=[dict(learning_rate=lr,epoch=e,**combine([values[(lr,k,e)] for k in range(4)])) for lr in plan['learning_rates'] for e in range(0,plan['epochs']+1,plan['evaluate_every'])]
    chosen=choose(candidates);bound=bindings([p for p in directory.rglob('*') if p.is_file()]);elapsed=time.perf_counter()-start
    if elapsed>=plan['tuning_seconds_cap']:raise TimeoutError('Destination tuning publication budget exceeded')
    immutable_json(REPORT/'selection.json',dict(plan_sha256=digest(REPORT/'plan.json'),selected=chosen,candidates=candidates,bindings=bound,seconds=elapsed,outer_evaluation_used=False))
    print('SELECTED',chosen,flush=True)


def refit():
    start=time.perf_counter();plan,architecture,_,_=inputs();rows,ids=cached();selection=read(REPORT/'selection.json');check(selection)
    chosen=selection['selected'];assert chosen==choose(selection['candidates']);torch.set_num_threads(1)
    net=prior.backbone(ROOT/plan['full_backbone'],architecture);head=DestinationHead(net);shared=torch.load(WORK/'full-shared.pt',weights_only=True)
    trace=train(head,rows,shared,np.arange(len(rows)),plan,chosen['learning_rate'],chosen['epoch'],WORK/'refit',start+plan['refit_seconds_cap'])
    install(net,head);torch.save(dict(model=net.state_dict(),inference_only=True,plan_sha256=digest(REPORT/'plan.json'),
        selection_sha256=digest(REPORT/'selection.json')),WORK/'selected.pt')
    value=score(head,rows,shared,np.arange(len(rows)));bound=bindings([WORK/'selected.pt',*(p for p in (WORK/'refit').iterdir() if p.is_file())]);elapsed=time.perf_counter()-start
    if elapsed>=plan['refit_seconds_cap']:raise TimeoutError('Destination refit publication budget exceeded')
    immutable_json(REPORT/'refit.json',dict(selection_sha256=digest(REPORT/'selection.json'),fit=value,
        updates=trace[-1]['updates'] if trace else 0,seconds=elapsed,bindings=bound))


def policy(architecture):
    net=movement.policy('predicted',read(movement.REPORT/'plan.json'),architecture)
    saved=torch.load(WORK/'selected.pt',map_location='cpu',weights_only=False)
    assert saved['plan_sha256']==digest(REPORT/'plan.json') and saved['selection_sha256']==digest(REPORT/'selection.json')
    old=net.backbone.state_dict()
    for k,v in saved['model'].items():
        if not k.startswith(('query.','goal.')) or k=='goal.2.bias':assert torch.equal(v,old[k]),k
    net.backbone.load_state_dict(saved['model']);return net.eval()


def assess():
    start=time.perf_counter();plan,architecture,_,_=inputs();check(read(REPORT/'refit.json'));torch.set_num_threads(4)
    windows,maps=original.load();cache=movement.encoded_windows(windows,maps,architecture);discovery=read(original.REPORT/'discovery.json')
    net=policy(architecture);results={};comparisons={}
    for split in ('fit','evaluation'):
        value=evaluate(net,windows,maps,cache,discovery,split,start+600);baseline=read(movement.WORK/f'predicted-{split}-predictions.json')
        assert len(value['records'])==len(baseline['records'])
        for a,b in zip(value['records'],baseline['records']):
            assert {k:v for k,v in a.items() if k not in ('goal_prediction','goal_error','goal_nll','astar_correct')}=={k:v for k,v in b.items() if k not in ('goal_prediction','goal_error','goal_nll','astar_correct')}
        immutable_json(WORK/(split+'-predictions.json'),value);results[split]=value['summary'];print(split,value['summary'],flush=True)
        goals=[(a,b) for a,b in zip(value['records'],baseline['records']) if a['goal_label'] is not None]
        comparisons[split]=dict(rows=len(goals),within2_rescues=sum(a['goal_error']<=2<b['goal_error'] for a,b in goals),within2_regressions=sum(b['goal_error']<=2<a['goal_error'] for a,b in goals))
    x=results['evaluation'];b=read(movement.REPORT/'result.json')['results']['predicted']['evaluation']
    checks=dict(within2=x['goal_within2']>=b['goal_within2']+.05,exact=x['goal_exact']>=b['goal_exact'],
        mean_error=x['mean_goal_error']<b['mean_goal_error'],nll=x['goal_nll']<b['goal_nll'],astar=x['astar_movement_accuracy']>=b['astar_movement_accuracy'])
    bound=bindings([WORK/'selected.pt',WORK/'fit-predictions.json',WORK/'evaluation-predictions.json']);elapsed=time.perf_counter()-start
    if elapsed>=600:raise TimeoutError('Destination assessment publication budget exceeded')
    immutable_json(REPORT/'result.json',dict(refit_sha256=digest(REPORT/'refit.json'),results=results,comparisons=comparisons,
        checks=checks,all_checks_pass=all(checks.values()),bindings=bound,seconds=elapsed,promoted=False))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('command',choices=('freeze','prepare','tune','refit','assess'));globals()[p.parse_args().command]()
