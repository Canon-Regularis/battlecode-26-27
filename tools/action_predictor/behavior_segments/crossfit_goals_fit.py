"""Nested, size-matched cross-fitting of goals used to train a shared executor."""
import argparse,time,itertools
from pathlib import Path
import numpy as np
import torch
from . import shared_goal_execution_fit as prior
from .crossfit_goals import RawGoalSelector,head_name,head_exclusions,selected_head,selector_features
from .code_path_movement import candidate_features
from .heading_movement import heading_window
from .command_movement import command_window
from ..audit import immutable_json

ROOT=prior.ROOT;REPORT=ROOT/'tools/action_predictor/experiments/v73';WORK=ROOT/'.cambc/action-predictor/v73'
read,check,bindings=prior.read,prior.check,prior.bindings
OLD=prior.prior.planner.old
ARMS=('insample','crossfit')
HEADS=[head_name(v) for size in (2,1,0) for v in itertools.combinations(range(4),size)]


def freeze():
    REPORT.mkdir(parents=True,exist_ok=True);prior.inputs();check(read(prior.REPORT/'verification.json'));check(read(OLD.REPORT/'cache.json'))
    immutable_json(REPORT/'plan.json',dict(sources=bindings([Path(__file__).with_name(n) for n in ('crossfit_goals.py','crossfit_goals_fit.py','crossfit_goals_predictor.py','test_crossfit_goals.py')]),inputs=bindings([prior.REPORT/n for n in ('plan.json','cache.json','fit.json','selection.json','result.json','verification.json')]+[OLD.REPORT/n for n in ('plan.json','cache.json','selection.json')]),
        seed=70001,epochs=16,every=4,lr=.001,weight_decay=.01,batch=128,clip=5.,executor_seconds_cap=600,selector_seed=73001,selector_epochs=12,selector_lr=.001,selector_batch=256,selector_seconds_cap=900,
        goal_architecture='Fresh660-64-1 tanh utility head.648 deterministic current geometry/observed-heading/prior-command features plus12candidate features. NO learned backbone,state/code,normalizer,pretrained weights,game identity or current/future action input in goal prediction. Existing four-turn replay progress targets supervise training only. Fixed12passes,no selector selection on excluded groups. Fixed legacy readout scale0.5/shift-0.25 and retention0.15;not recalibrated.',
        crossfit='Four existing8game folds. For each outer held fold,train pair-excluded heads on16games. Treatment goals for training groupG use a head excluding both outer andG. Size-matched in-sample control excludes outer and the next other fold cyclically,thus includesG. Validation uses the24game head excluding outer for BOTH arms. Six pair-excluded heads are shared between symmetric jobs because raw features and initialization are identical.',
        refit='For full executor refit,treatment goals use24game heads excluding their own groupfold;control uses a24game head excluding nextfold and includes its group. Both inference arms use the same32fitting-game head. No original evaluation group enters any selector/executor training. All11selectors start fresh and their group membership is archived.',
        executor='Unchanged V70 shared executor,8897parameters,matching seed70001/initialization/rows/sampling/optimizer/checkpoints. Both train all12318movement rows;only goal predictions differ. V59 frozen. Select each arm among0/4/8/12/16 by highest canonical held movement count withNLL<=initial+0.01,then NLL,earlier epoch. No evaluation selection.',
        success='Crossfit must exceed size-matched insample and direct318 on fixed513evaluation moves,NLL<=direct+0.01,and neither shared evaluation goal-present/absent cohort loses>2points vsdirect. All required.80percent requires411/513. No automatic promotion.',
        scope='This tests cross-fitting within a NEW deterministic-feature selector family with matched controls. It does not isolate cross-fitting against legacy V70 because goal features change. Goal-model updates genuinely exclude predicted training groups;executor backbone still has inherited historical exposure. Recipes,research partitions and source schemas are previously exposed,not fresh certification. No goal mixtures,latent plans,autonomous rollout or subagents.'))


def inputs():
    p=read(REPORT/'plan.json');check(p);_,parent,architecture,cache,ids=prior.inputs();return p,parent,architecture,cache,ids


def raw_window(w,route,history):
    geometry=torch.stack([candidate_features(s['input'] if s['observed'] else None,route) for s in w['steps']]);return torch.cat((geometry.flatten(1),heading_window(w).flatten(1),command_window(history).flatten(1)),-1)


def prepare():
    p,_,_,_,ids=inputs();torch.set_num_threads(1);WORK.mkdir(parents=True,exist_ok=False);windows,maps=prior.prior.base.heading.expanded.read();history,bound=OLD.audit.prior_moves(windows);queries=[];raw=[];lookup={}
    for wi,w in enumerate(windows):
        assert w['partition']=='fit' and w['key']==ids[wi]['key'];x=raw_window(w,maps[w['payload']],history[w['key']])
        for i,s in enumerate(w['steps']):
            if not s['observed']:continue
            lookup[(w['key'],i)]=len(queries);queries.append(dict(window=wi,key=w['key'],position=i,group=w['group'],fold=ids[wi]['fold'],canonical=ids[wi]['canonical'],candidates=prior.prior.candidates(s['input'],maps[w['payload']])));raw.append(x[i])
        if (wi+1)%400==0:print('Raw selector features',wi+1,'/',len(windows),flush=True)
    raw=torch.stack(raw);targets=read(OLD.WORK/'rows.json');xs=[];ys=[];folds=[];groups=[]
    for r in targets:
        q=lookup[(r['key'],r['position'])];assert queries[q]['group']==r['group'] and queries[q]['fold']==r['fold']
        for c in r['candidates']:xs.append(selector_features(raw[q],c['features']));ys.append(c['utility']);folds.append(r['fold']);groups.append(r['group'])
    bank=torch.load(prior.WORK/'full.pt',weights_only=False)
    for i,r in enumerate(bank['records']):assert torch.equal(bank['context'][i,56:],raw[lookup[(r['key'],r['position'])]])
    torch.save(dict(raw=raw,queries=queries),WORK/'raw.pt');torch.save(dict(x=torch.stack(xs),y=torch.tensor(ys),folds=torch.tensor(folds),groups=groups),WORK/'selector-data.pt')
    immutable_json(REPORT/'cache.json',dict(bindings=bindings([WORK/'raw.pt',WORK/'selector-data.pt']),source_bindings=bound,queries=len(queries),candidate_targets=len(ys),raw_feature_parity_rows=len(bank['records']),evaluation_used=False));print('PREPARED',len(queries),len(ys),flush=True)


def new_selector(p):torch.manual_seed(p['selector_seed']);return RawGoalSelector()


def selectors():
    start=time.perf_counter();p,_,_,_,_=inputs();check(read(REPORT/'cache.json'));torch.set_num_threads(1);data=torch.load(WORK/'selector-data.pt',weights_only=False);members={}
    for name in HEADS:
        excluded=head_exclusions(name);indices=np.array([i for i,f in enumerate(data['folds'].tolist()) if f not in excluded]);groups=sorted({data['groups'][i] for i in indices});assert len(groups)==8*(4-len(excluded));directory=WORK/'selectors'/name;directory.mkdir(parents=True,exist_ok=False);net=new_selector(p);opt=torch.optim.AdamW(net.parameters(),lr=p['selector_lr'],weight_decay=.01);rng=np.random.default_rng(p['selector_seed']);trace=[];torch.save(net.state_dict(),directory/'initial.pt')
        for epoch in range(1,p['selector_epochs']+1):
            order=rng.permutation(indices);norms=[];total=0.
            for start_row in range(0,len(order),p['selector_batch']):
                if time.perf_counter()-start>=p['selector_seconds_cap']:raise TimeoutError('Selector fit cap')
                ix=order[start_row:start_row+p['selector_batch']];loss=(net(data['x'][ix])-data['y'][ix]).square().mean();opt.zero_grad();loss.backward();norm=torch.nn.utils.clip_grad_norm_(net.parameters(),5.);assert torch.isfinite(loss) and torch.isfinite(norm);opt.step();norms.append(float(norm));total+=float(loss.detach())*len(ix)
            trace.append(dict(epoch=epoch,order=order.tolist(),norms=norms,online_mse=total/len(order)))
            if epoch%4==0:print('Selector',name,epoch,total/len(order),flush=True)
        torch.save(dict(model=net.state_dict(),optimizer=opt.state_dict(),rng=rng.bit_generator.state),directory/'final.pt');immutable_json(directory/'trace.json',trace);members[name]=dict(excluded_folds=excluded,training_groups=groups,examples=len(indices))
    bound=bindings([q for q in (WORK/'selectors').rglob('*') if q.is_file()]);elapsed=time.perf_counter()-start
    if elapsed>=p['selector_seconds_cap']:raise TimeoutError('Selector publication cap')
    immutable_json(REPORT/'selectors.json',dict(bindings=bound,membership=members,seconds=elapsed,selection_on_excluded_groups=False));print('SELECTORS COMPLETE',flush=True)


def selector(name):
    net=RawGoalSelector();w=torch.load(WORK/'selectors'/name/'final.pt',weights_only=False)['model'];net.load_state_dict(prior.prior.planner.edit(w,.5,-.25));return net.eval()


@torch.no_grad()
def predicted(queries,raw,windows,maps,head_for_query):
    heads={name:selector(name) for name in set(head_for_query)};out=[];remembered=None;last_key=None
    for q,x,name in zip(queries,raw,head_for_query):
        if q['key']!=last_key:remembered=None;last_key=q['key']
        cs=q['candidates'];scores=heads[name](torch.stack([selector_features(x,c['features']) for c in cs])).tolist() if cs else [];chosen,remembered,_=prior.prior.choose(cs,scores,remembered,.15);utility=0. if chosen is None else scores[next(j for j,c in enumerate(cs) if c['key']==chosen['key'])];w=windows[q['window']]
        out.append(dict(goal=prior.optional_goal(w['steps'][q['position']]['input'],maps[w['payload']],chosen,utility),selected=remembered,active=chosen is not None,utility=utility,selector=name))
    return out


def assemble():
    p,_,_,_,_=inputs();check(read(REPORT/'selectors.json'));torch.set_num_threads(1);data=torch.load(WORK/'raw.pt',weights_only=False);windows,maps=prior.prior.base.heading.expanded.read();lookup={(q['key'],q['position']):i for i,q in enumerate(data['queries'])};membership=read(REPORT/'selectors.json')['membership'];counts={}
    for outer in [0,1,2,3,None]:
        name='full' if outer is None else f'fold{outer}';original=torch.load(prior.WORK/(name+'.pt'),weights_only=False);outer_groups={q['group'] for q in data['queries'] if q['fold']==outer}
        for arm in ARMS:
            names=[selected_head(outer,q['fold'],arm=='crossfit') for q in data['queries']];goals=predicted(data['queries'],data['raw'],windows,maps,names);bank=dict(original);rs=[];gs=[]
            for r in original['records']:
                j=lookup[(r['key'],r['position'])];g=goals[j];trained=membership[g['selector']]['training_groups'];held=outer is not None and r['fold']==outer
                assert (r['group'] not in trained)==(held or arm=='crossfit')
                assert outer_groups.isdisjoint(trained)
                rs.append(dict(r,**{k:v for k,v in g.items() if k!='goal'}));gs.append(g['goal'])
            bank['goal']=torch.stack(gs);bank['records']=rs;path=WORK/'banks'/arm/(name+'.pt');path.parent.mkdir(parents=True,exist_ok=True);torch.save(bank,path);counts[arm+'/'+name]=dict(rows=len(rs),active=sum(r['active'] for r in rs));print('ASSEMBLED',arm,name,counts[arm+'/'+name],flush=True)
    immutable_json(REPORT/'assembled.json',dict(bindings=bindings([q for q in (WORK/'banks').rglob('*.pt')]),counts=counts,exclusion_checked_per_movement=True,evaluation_used=False))


def fit():
    start=time.perf_counter();p,_,_,_,_=inputs();check(read(REPORT/'assembled.json'));torch.set_num_threads(1);selections={};candidates={}
    for arm in ARMS:
        values={}
        for fold in range(4):
            name=f'fold{fold}';b=torch.load(WORK/'banks'/arm/(name+'.pt'),weights_only=False);rs=b['records'];ix=np.array([i for i,r in enumerate(rs) if r['fold']!=fold]);held=np.array([i for i,r in enumerate(rs) if r['fold']==fold and r['canonical']]);_,v=prior.train('goal',b,ix,p,p['epochs'],WORK/'executors'/arm/name,start+p['executor_seconds_cap'],held)
            for e,s in v.items():values.setdefault(e,[]).append(s)
        cs=[dict(epoch=e,**{k:sum(v[k] for v in vs) for k in ('rows','correct','nll_sum')}) for e,vs in values.items()];assert all(c['rows']==1997 for c in cs);selections[arm]=prior.previous.select(cs);candidates[arm]=cs
    immutable_json(REPORT/'selection.json',dict(selected=selections,candidates=candidates,evaluation_used=False))
    for arm in ARMS:
        b=torch.load(WORK/'banks'/arm/'full.pt',weights_only=False);net,_=prior.train('goal',b,np.arange(len(b['records'])),p,selections[arm]['epoch'],WORK/'executors'/arm/'refit',start+p['executor_seconds_cap']);torch.save(net.state_dict(),WORK/(arm+'-selected.pt'))
    bound=bindings([q for q in (WORK/'executors').rglob('*') if q.is_file()]+[WORK/(a+'-selected.pt') for a in ARMS]);elapsed=time.perf_counter()-start
    if elapsed>=p['executor_seconds_cap']:raise TimeoutError('Executor publication cap')
    immutable_json(REPORT/'fit.json',dict(bindings=bound,seconds=elapsed));print('SELECTED',selections,flush=True)


def assessment():
    p,_,_,_,_=inputs();values={}
    for split in ('fit','evaluation'):
        b=torch.load(WORK/(split+'.pt'),weights_only=False);values[split]={}
        for arm in (*ARMS,'direct'):
            net=prior.new('goal',p)
            if arm!='direct':net.load_state_dict(torch.load(WORK/(arm+'-selected.pt'),weights_only=True))
            values[split][arm]=prior.score(net,b)
    x=values['evaluation'];g=x['crossfit'];d=x['direct'];checks=dict(control=g['correct']>x['insample']['correct'],direct=g['correct']>d['correct'],nll=g['nll_sum']<=d['nll_sum']+.01*g['rows'])
    for c in ('goal','no_goal'):checks[c+'_guard']=g['cohorts'][c]['correct']>=d['cohorts'][c]['correct']-.02*d['cohorts'][c]['rows']
    return dict(results=values,checks=checks,all_checks_pass=all(checks.values()),target_met=g['rows']==513 and g['correct']>=411,promoted=False)


def assess():
    inputs();check(read(REPORT/'fit.json'));torch.set_num_threads(4);windows,maps=prior.prior.base.heading.original.load()
    for split in ('fit','evaluation'):
        b=torch.load(prior.WORK/(split+'.pt'),weights_only=False);bykey={w['key']:i for i,w in enumerate(windows)};queries=[dict(r,window=bykey[r['key']],candidates=prior.prior.candidates(windows[bykey[r['key']]]['steps'][r['position']]['input'],maps[windows[bykey[r['key']]]['payload']])) for r in b['records']];gs=predicted(queries,b['context'][:,56:],windows,maps,['full']*len(queries));b['records']=[dict(r,**{k:v for k,v in g.items() if k!='goal'}) for r,g in zip(b['records'],gs)];b['goal']=torch.stack([g['goal'] for g in gs]);torch.save(b,WORK/(split+'.pt'))
    r=assessment();immutable_json(REPORT/'result.json',dict(**r,bindings=bindings([WORK/'fit.pt',WORK/'evaluation.pt',*(WORK/(a+'-selected.pt') for a in ARMS)])));print('RESULT',r['checks'],{a:(v['correct'],v['rows'],v['nll_sum']/v['rows']) for a,v in r['results']['evaluation'].items()},flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('command',choices=('freeze','prepare','selectors','assemble','fit','assess'));globals()[parser.parse_args().command]()
