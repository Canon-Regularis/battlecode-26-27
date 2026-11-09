"""Matched all-movement training with predicted goals, never achieved endpoints."""
import argparse,time
from pathlib import Path
import numpy as np
import torch
from torch.nn import functional as F
from . import universal_execution_fit as previous
from .shared_goal_execution import SharedGoalExecutor,optional_goal
from ..audit import immutable_json

prior=previous.prior;calibration=previous.calibration
ROOT=prior.ROOT;REPORT=ROOT/'tools/action_predictor/experiments/v70';WORK=ROOT/'.cambc/action-predictor/v70'
read,check,bindings=prior.read,prior.check,prior.bindings
ARMS=('blind','goal')


def freeze():
    REPORT.mkdir(parents=True,exist_ok=True);previous.inputs();check(read(previous.REPORT/'verification.json'))
    immutable_json(REPORT/'plan.json',dict(sources=bindings([Path(__file__).with_name(n) for n in ('shared_goal_execution.py','shared_goal_execution_fit.py','shared_goal_execution_predictor.py','test_shared_goal_execution.py')]),
        inputs=bindings([previous.REPORT/n for n in ('plan.json','cache.json','fit.json','result.json','verification.json')]+[calibration.REPORT/n for n in ('plan.json','cache.json','result.json','verification.json')]),
        seed=70001,epochs=16,every=4,lr=.001,weight_decay=.01,batch=128,clip=5.,fit_seconds_cap=600,
        architecture='One137-64-1 tanh residual on every supported movement.128 existing causal local/state features,8 goal geometry fields including availability,plus selected predicted utility (bounded model score,not calibrated confidence).8897 parameters. Zero initial residual. Goal-blind matched arm zeros all9 goal fields. Same initialization,rows,permutations,loss,optimizer and checkpoints.',
        population='All12318 expanded fitting movements once per epoch. No achieved-future-goal inputs or horizon filtering. Both goal-present and goal-absent rows train shared weights. V59 backbone and V62 selector frozen. Absence zeros all goal fields,executor still runs.',
        goals='Run the frozen matched V62 selector on current observations and causal V59 states,retaining its identity through every observed/nonobserved turn exactly as runtime. Each outer fold uses only its training-group model. Training goals are in-sample predictions from that frozen training-group model; validation goals exclude the held groups. No inner cross-fitting; inherited fold exposure remains. Future labels never directly supply executor inputs.',
        selection='Four existing fitting-game folds; expanded other24games train,canonical held movements validate. Independently choose each arm among0,4,8,12,16 by highest correct count subject to movementNLL<=initial+0.01; tie NLL then earlier epoch. All1997 held movements. One full refit per selected arm. No evaluation selection.',
        success='Goal arm must beat direct318/513 and matched blind on fixed513 evaluation moves; NLL<=direct+0.01; neither goal-present nor absent cohort accuracy may lose>2points vs direct. Goal identities unchanged. All required.80percent requires411/513. No automatic promotion.',
        diagnostics='Read selected/final weights and fitting activations: per-input-group norms,changes,gradient finiteness,saturation,residual magnitude,and fitting-only goal ablation. These diagnostics cannot select alternative evaluation weights or justify repeats.',
        limits='Shared execution is not outcome-value learning or demonstrated strategy. Preexposed research groups,inherited fitting exposure,in-sample training predictions,one paired seed,observed past commands,inferred goals. No subagents.'))


def inputs():
    p=read(REPORT/'plan.json');check(p);_,parent,architecture,cache,ids=previous.inputs();return p,parent,architecture,cache,ids


def new(arm,p):
    torch.manual_seed(p['seed']);return SharedGoalExecutor(arm=='goal')


def selector(name):
    head=prior.planner.old.new(read(prior.planner.old.REPORT/'plan.json'));e=read(prior.planner.old.REPORT/'selection.json')['selected']['epoch'];path=prior.planner.old.WORK/'selected.pt' if name=='full' else prior.planner.old.WORK/name/f'epoch-{e:03d}.pt';s=read(prior.planner.REPORT/'selection.json')['selected']
    head.load_state_dict(prior.planner.edit(torch.load(path,weights_only=True),s['scale'],s['shift']));return head.eval()


@torch.no_grad()
def goals(windows,maps,contexts,name,progress=False):
    head=selector(name);result={}
    for wi,w in enumerate(windows):
        remembered=None
        for i,step in enumerate(w['steps']):
            if not step['observed']:continue
            current=step['input'];cs=prior.candidates(current,maps[w['payload']]);x=contexts[(w['key'],i)]
            scores=head(torch.stack([torch.cat((x[:56],torch.tensor(c['features']))) for c in cs])).tolist() if cs else []
            chosen,remembered,_=prior.choose(cs,scores,remembered,.15);value=0. if chosen is None else scores[next(j for j,c in enumerate(cs) if c['key']==chosen['key'])]
            result[(w['key'],i)]=dict(goal=optional_goal(current,maps[w['payload']],chosen,value),selected=remembered,active=chosen is not None,utility=value)
        if progress and (wi+1)%400==0:print('Predicted goals',name,wi+1,'/',len(windows),flush=True)
    return result


def prepare():
    p,parent,architecture,cache,ids=inputs();torch.set_num_threads(4);WORK.mkdir(parents=True,exist_ok=False);check(read(previous.REPORT/'cache.json'));rows=read(previous.WORK/'rows.json');windows,maps=prior.base.heading.expanded.read();counts={}
    assert all(w['partition']=='fit' and w['key']==ids[i]['key'] for i,w in enumerate(windows))
    for name in ['fold0','fold1','fold2','fold3','full']:
        context=prior.waypoint.cached_features(name,parent,architecture,cache);lookup={(w['key'],i):context[wi,i] for wi,w in enumerate(windows) for i,s in enumerate(w['steps']) if s['observed']};gs=goals(windows,maps,lookup,name,True);bank=torch.load(previous.WORK/(name+'.pt'),weights_only=True)
        assert all(torch.equal(bank['context'][i],lookup[(r['key'],r['position'])]) for i,r in enumerate(rows))
        rs=[dict(r,**{k:v for k,v in gs[(r['key'],r['position'])].items() if k!='goal'}) for r in rows];bank['goal']=torch.stack([gs[(r['key'],r['position'])]['goal'] for r in rows]);bank['records']=rs;torch.save(bank,WORK/(name+'.pt'));counts[name]=dict(rows=len(rs),active=sum(r['active'] for r in rs))
        if name!='full':
            old=torch.load(calibration.WORK/(name+'.pt'),weights_only=False)
            for r,g in zip(old['records'],old['goal']):
                actual=gs[(r['key'],r['position'])];assert actual['selected']==r['selected'] and actual['active']==r['active'] and torch.equal(actual['goal'][:,:8],g)
        a=new('blind',p);b=new('goal',p);assert all(torch.equal(v,b.state_dict()[k]) for k,v in a.state_dict().items());assert torch.equal(b(bank['context'][:128],bank['goal'][:128],bank['baseline'][:128]),bank['baseline'][:128])
        print('Prepared shared executor',name,counts[name],flush=True)
    immutable_json(REPORT/'cache.json',dict(bindings=bindings(list(WORK.iterdir())),counts=counts,evaluation_used=False,canonical_goal_parity=True,matched_initialization=True))


@torch.no_grad()
def score(net,bank,indices=None):
    indices=np.arange(len(bank['records'])) if indices is None else indices;rs=[bank['records'][int(i)] for i in indices];predictions=[];losses=[]
    for start in range(0,len(indices),256):
        ix=indices[start:start+256];lp=net(bank['context'][ix],bank['goal'][ix],bank['baseline'][ix]).masked_fill(~bank['support'][ix],-1e9).log_softmax(-1);y=bank['labels'][ix];predictions.extend(lp.argmax(-1).tolist());losses.extend((-lp.gather(1,y.clamp_min(0)[:,None]).squeeze(1)).tolist())
    cohorts={}
    for name,wanted in [('all',None),('goal',True),('no_goal',False)]:
        ix=[i for i,r in enumerate(rs) if r['label']>=0 and (wanted is None or r['active']==wanted)];cohorts[name]=dict(rows=len(ix),correct=sum(predictions[i]==rs[i]['label'] for i in ix),nll_sum=sum(losses[i] for i in ix))
    return dict(**cohorts['all'],cohorts=cohorts,predictions=predictions,losses=losses)


def train(arm,bank,indices,p,epochs,directory,deadline,held=None):
    directory.mkdir(parents=True,exist_ok=False);net=new(arm,p);opt=torch.optim.AdamW(net.parameters(),lr=p['lr'],weight_decay=p['weight_decay']);rng=np.random.default_rng(p['seed']);trace=[];torch.save(net.state_dict(),directory/'epoch-000.pt');values={0:score(net,bank,held)} if held is not None else {}
    for epoch in range(1,epochs+1):
        order=rng.permutation(indices);norms=[];loss_sum=0.
        for start in range(0,len(order),p['batch']):
            if time.perf_counter()>=deadline:raise TimeoutError('Shared executor fit cap')
            ix=order[start:start+p['batch']];raw=net(bank['context'][ix],bank['goal'][ix],bank['baseline'][ix]).masked_fill(~bank['support'][ix],-1e9);loss=F.cross_entropy(raw,bank['labels'][ix]);opt.zero_grad();loss.backward();norm=torch.nn.utils.clip_grad_norm_(net.parameters(),p['clip']);assert torch.isfinite(loss) and torch.isfinite(norm);opt.step();norms.append(float(norm));loss_sum+=float(loss.detach())*len(ix)
        trace.append(dict(epoch=epoch,order=order.tolist(),norms=norms,online_nll=loss_sum/len(order)))
        if epoch%p['every']==0:
            torch.save(net.state_dict(),directory/f'epoch-{epoch:03d}.pt')
            if held is not None:values[epoch]=score(net,bank,held)
            print(arm,directory.name,epoch,values.get(epoch,{}).get('correct'),flush=True)
    torch.save(dict(model=net.state_dict(),optimizer=opt.state_dict(),rng=rng.bit_generator.state),directory/'final.pt');immutable_json(directory/'trace.json',dict(epochs=trace,validation=values));return net,values


def fit():
    start=time.perf_counter();p,_,_,_,_=inputs();check(read(REPORT/'cache.json'));torch.set_num_threads(1);selections={};candidates={}
    for arm in ARMS:
        values={}
        for fold in range(4):
            name=f'fold{fold}';bank=torch.load(WORK/(name+'.pt'),weights_only=False);rs=bank['records'];ix=np.array([i for i,r in enumerate(rs) if r['fold']!=fold]);held=np.array([i for i,r in enumerate(rs) if r['fold']==fold and r['canonical']]);_,v=train(arm,bank,ix,p,p['epochs'],WORK/arm/name,start+p['fit_seconds_cap'],held)
            for e,s in v.items():values.setdefault(e,[]).append(s)
        cs=[dict(epoch=e,**{k:sum(v[k] for v in vs) for k in ('rows','correct','nll_sum')}) for e,vs in values.items()];assert all(c['rows']==1997 for c in cs);candidates[arm]=cs;selections[arm]=previous.select(cs)
    immutable_json(REPORT/'selection.json',dict(candidates=candidates,selected=selections,evaluation_used=False))
    for arm in ARMS:
        bank=torch.load(WORK/'full.pt',weights_only=False);net,_=train(arm,bank,np.arange(len(bank['records'])),p,selections[arm]['epoch'],WORK/arm/'refit',start+p['fit_seconds_cap']);torch.save(net.state_dict(),WORK/(arm+'-selected.pt'))
    bound=bindings([q for q in WORK.rglob('*') if q.is_file()]);elapsed=time.perf_counter()-start
    if elapsed>=p['fit_seconds_cap']:raise TimeoutError('Shared executor publication cap')
    immutable_json(REPORT/'fit.json',dict(bindings=bound,seconds=elapsed));print('SELECTED',selections,flush=True)


def selected(arm,p):
    net=new(arm,p);net.load_state_dict(torch.load(WORK/(arm+'-selected.pt'),weights_only=True));return net.eval()


@torch.no_grad()
def inspect():
    from .goal_execution import local_features
    p,_,_,_,_=inputs();check(read(REPORT/'fit.json'));torch.set_num_threads(1);bank=torch.load(WORK/'full.pt',weights_only=False);reports={};x=torch.cat((local_features(bank['context']),bank['goal']),-1)
    for arm in ARMS:
        net=selected(arm,p);initial=new(arm,p);weights=net.state_dict();initial=initial.state_dict();xx=x.clone()
        if arm=='blind':xx[...,128:]=0
        z=net.layers[0](xx);residual=net.layers[2](z.tanh()).squeeze(-1);normal=score(net,bank);ablated=dict(bank,goal=torch.zeros_like(bank['goal']));no_goal=score(net,ablated)
        reports[arm]=dict(selected_epoch=read(REPORT/'selection.json')['selected'][arm]['epoch'],weight_changes={k:float((v-initial[k]).norm()) for k,v in weights.items()},input_group_weight_norms={n:float(weights['layers.0.weight'][:,a:b].norm()) for n,a,b in [('state_code',0,56),('geometry',56,116),('observed_heading',116,120),('command_heading',120,128),('goal_geometry',128,135),('availability',135,136),('utility',136,137)]},goal_column_weight_changes=(weights['layers.0.weight'][:,128:]-initial['layers.0.weight'][:,128:]).norm(dim=0).tolist(),supported_saturation_fraction=float((z.tanh().abs()>.99)[bank['support']].float().mean()),supported_residual_rms=float(residual[bank['support']].square().mean().sqrt()),fitting_normal={k:normal[k] for k in ('rows','correct','nll_sum')},fitting_goal_masked={k:no_goal[k] for k in ('rows','correct','nll_sum')},fitting_goal_ablation_changed_predictions=sum(a!=b for a,b in zip(normal['predictions'],no_goal['predictions'])))
    g=bank['goal'].reshape(-1,9);immutable_json(REPORT/'weight-inspection.json',dict(bindings=bindings([WORK/'full.pt',*(WORK/(a+'-selected.pt') for a in ARMS)]),weights=reports,training_goal_min=g.min(0).values.tolist(),training_goal_max=g.max(0).values.tolist(),evaluation_used=False,interpretation='Norms and activations describe learned computation,not semantic neuron labels or proof of strategic learning. Ablation uses fitting rows only and does not select new weights.'))
    print('WEIGHTS',reports,flush=True)


def assessment():
    p,_,_,_,_=inputs();values={};nets={a:selected(a,p) for a in ARMS};direct=new('goal',p)
    for split in ('fit','evaluation'):
        bank=torch.load(WORK/(split+'.pt'),weights_only=False);values[split]={a:score(n,bank) for a,n in dict(nets,direct=direct).items()}
        for a in ARMS:
            pred=values[split][a]['predictions'];old=values[split]['direct']['predictions'];rs=bank['records'];values[split][a]['vs_direct']=dict(rescues=sum(q!=r['label'] and t==r['label'] for q,t,r in zip(old,pred,rs) if r['label']>=0),regressions=sum(q==r['label'] and t!=r['label'] for q,t,r in zip(old,pred,rs) if r['label']>=0))
    x=values['evaluation'];g=x['goal'];d=x['direct'];checks=dict(direct=g['correct']>d['correct'],blind=g['correct']>x['blind']['correct'],nll=g['nll_sum']<=d['nll_sum']+.01*g['rows'])
    for c in ('goal','no_goal'):checks[c+'_guard']=g['cohorts'][c]['correct']>=d['cohorts'][c]['correct']-.02*d['cohorts'][c]['rows']
    return dict(results=values,checks=checks,all_checks_pass=all(checks.values()),target_met=g['rows']==513 and g['correct']>=411,promoted=False)


def assess():
    inputs();check(read(REPORT/'fit.json'));torch.set_num_threads(4);windows,maps=prior.base.heading.original.load()
    for split in ('fit','evaluation'):
        bank=torch.load(calibration.WORK/(split+'.pt'),weights_only=False);ws=[w for w in windows if w['partition']==split];lookup={(r['key'],r['position']):bank['context'][i] for i,r in enumerate(bank['records'])};gs=goals(ws,maps,lookup,'full')
        assert all(gs[(r['key'],r['position'])]['selected']==r['selected'] and gs[(r['key'],r['position'])]['active']==r['active'] for r in bank['records'])
        bank['goal']=torch.stack([gs[(r['key'],r['position'])]['goal'] for r in bank['records']]);bank['labels']=torch.tensor([r['label'] for r in bank['records']]);torch.save(bank,WORK/(split+'.pt'))
    result=assessment();immutable_json(REPORT/'result.json',dict(**result,bindings=bindings([WORK/'fit.pt',WORK/'evaluation.pt',*(WORK/(a+'-selected.pt') for a in ARMS)])))
    print('RESULT',result['checks'],{a:(v['correct'],v['rows'],v['nll_sum']/v['rows']) for a,v in result['results']['evaluation'].items()},flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('command',choices=('freeze','prepare','fit','inspect','assess'));globals()[parser.parse_args().command]()
