"""Bounded fitting-only coordinate search of nine existing movement biases."""
import argparse,time
from pathlib import Path
import numpy as np
import torch
from . import joint_movement_fit as base,code_path_fit as old,code_weight_fit as first,expanded_code_fit as expanded
from . import data as original
from .study import evaluate
from ..audit import immutable_json
from ..data import digest

ROOT=original.ROOT;REPORT=ROOT/'tools/action_predictor/experiments/v55';WORK=ROOT/'.cambc/action-predictor/v55'
read=base.read;check=base.check;bindings=base.bindings


def freeze():
    REPORT.mkdir(parents=True,exist_ok=True);plan,_,_,_=base.inputs();check(read(base.REPORT/'selection.json'));check(read(base.REPORT/'result.json'))
    paths=[base.REPORT/n for n in ('plan.json','selection.json','refit.json','result.json','verification.json')]
    immutable_json(REPORT/'plan.json',dict(sources=bindings([Path(__file__),Path(__file__).with_name('movement_bias_predictor.py'),Path(__file__).with_name('test_movement_bias.py')]),
        inputs=bindings(paths),bounds=[.1,.3,.6],step=.02,passes=4,seconds_cap=600,target_accuracy=.8,
        intervention='Edit only nine entries of the existing base movement bias, starting at selected V54 '
        'weights. At each coordinate evaluate a fixed0.02 grid within the bound. Prefer fitting correct '
        'count,then NLL,then smaller absolute bias. Four passes,ascending direction order,including stay. '
        'No new layers or feature/support/decoder changes; no model optimizer updates.',
        selection='Each fitting fold calibrates its matching V54 selected checkpoint on all other24games '
        'and scores original held64windows. Select pooled correct count,then NLL,then smaller bound. '
        'Identity eligible. Refit one selected bound on full fitting data. No evaluation-dependent choice.',
        limits='Repeatedly exposed research games and inherited backbone/fold exposure. '
        'This tests a bounded direction correction,not strategy or a guarantee of80percent. '
        'Code and goals must remain unchanged. No subagents or runtime promotion.'))


def inputs():
    plan=read(REPORT/'plan.json');check(plan);parent,architecture,cache,ids=base.inputs()
    return plan,parent,architecture,cache,ids


@torch.no_grad()
def forecasts(name,parent,architecture,cache):
    data=base.dataset(name,cache);net=base.new_model(name,parent,architecture);selected=read(base.REPORT/'selection.json')['selected']
    path=base.WORK/'selected.pt' if name=='full' else base.WORK/'tuning'/f"kl{selected['coefficient']:g}-fold{name[-1]}"/f"epoch-{selected['epoch']:03d}.pt"
    net.load_state_dict(torch.load(path,weights_only=False)['model']);rows=[]
    for begin in range(0,len(data['observed']),16):rows.append(net(first.take(data,slice(begin,begin+16)))['move'].clone())
    return dict(logits=torch.cat(rows),labels=data['movement_labels'],support=data['support'])


def subset(data,indices):
    mask=data['labels'][indices]>=0
    return data['logits'][indices][mask].numpy(),data['labels'][indices][mask].numpy(),data['support'][indices][mask].numpy()


def statistics(logits,labels,support,bias):
    z=np.where(support,logits+bias[None,:],-1e9).astype(np.float64)
    predicted=z.argmax(1);maximum=z.max(1);loss=maximum+np.log(np.exp(z-maximum[:,None]).sum(1))-z[np.arange(len(labels)),labels]
    return dict(rows=len(labels),correct=int((predicted==labels).sum()),nll=float(loss.mean()),predictions=predicted.tolist())


def calibrate(logits,labels,support,bound,plan):
    bias=np.zeros(9,np.float32);trace=[]
    if bound==0:return bias,trace
    grid=np.linspace(-bound,bound,round(2*bound/plan['step'])+1,dtype=np.float32)
    for iteration in range(plan['passes']):
        for direction in range(9):
            candidates=[]
            for value in grid:
                trial=bias.copy();trial[direction]=value;score=statistics(logits,labels,support,trial)
                candidates.append(((-score['correct'],score['nll'],abs(float(value)),float(value)),value))
            _,value=min(candidates,key=lambda v:v[0]);bias[direction]=value
            score=statistics(logits,labels,support,bias)
            trace.append(dict(iteration=iteration,direction=direction,bias=bias.tolist(),correct=score['correct'],nll=score['nll']))
    return bias,trace


def choose(candidates):return min(candidates,key=lambda c:(-c['correct'],c['nll'],c['bound']))


def run():
    start=time.perf_counter();plan,parent,architecture,cache,ids=inputs();WORK.mkdir(parents=True,exist_ok=False);torch.set_num_threads(1)
    scores={};calibrations={}
    for fold in range(4):
        data=forecasts('fold'+str(fold),parent,architecture,cache);torch.save(data,WORK/f'fold{fold}-logits.pt')
        training,held=expanded.partition_indices(ids,fold);a=subset(data,training);b=subset(data,held)
        for bound in [0.,*plan['bounds']]:
            if time.perf_counter()-start>=plan['seconds_cap']:raise TimeoutError('Movement bias budget exceeded')
            bias,trace=calibrate(*a,bound,plan);scores[(fold,bound)]=statistics(*b,bias)
            calibrations[f'{fold}/{bound:g}']=dict(bias=bias.tolist(),trace=trace,validation=scores[(fold,bound)])
        print('Calibrated fitting fold',fold,flush=True)
    candidates=[]
    for bound in [0.,*plan['bounds']]:
        v=[scores[(k,bound)] for k in range(4)];n=sum(x['rows'] for x in v)
        candidates.append(dict(bound=bound,rows=n,correct=sum(x['correct'] for x in v),nll=sum(x['nll']*x['rows'] for x in v)/n))
    chosen=choose(candidates);immutable_json(WORK/'calibration.json',calibrations)
    immutable_json(REPORT/'selection.json',dict(plan_sha256=digest(REPORT/'plan.json'),selected=chosen,candidates=candidates,
        bindings=bindings([WORK/'calibration.json',*(WORK/f'fold{k}-logits.pt' for k in range(4))]),outer_evaluation_used=False))
    data=forecasts('full',parent,architecture,cache);torch.save(data,WORK/'full-logits.pt')
    bias,trace=calibrate(*subset(data,np.arange(len(ids))),chosen['bound'],plan)
    saved=torch.load(base.WORK/'selected.pt',weights_only=False);saved['model']['backbone.movement.bias']=saved['model']['backbone.movement.bias']+torch.from_numpy(bias)
    saved['bias_plan_sha256']=digest(REPORT/'plan.json');saved['bias_selection_sha256']=digest(REPORT/'selection.json')
    torch.save(saved,WORK/'selected.pt');bound_files=bindings([WORK/'full-logits.pt',WORK/'selected.pt']);elapsed=time.perf_counter()-start
    if elapsed>=plan['seconds_cap']:raise TimeoutError('Movement bias publication budget exceeded')
    immutable_json(REPORT/'refit.json',dict(selection_sha256=digest(REPORT/'selection.json'),bias=bias.tolist(),trace=trace,bindings=bound_files,seconds=elapsed))
    print('SELECTED',chosen,'bias',bias.tolist(),flush=True)


def policy(parent,architecture):
    saved=torch.load(WORK/'selected.pt',weights_only=False)
    assert saved['bias_plan_sha256']==digest(REPORT/'plan.json') and saved['bias_selection_sha256']==digest(REPORT/'selection.json')
    net=base.new_model('full',parent,architecture);net.load_state_dict(saved['model']);return base.inference(net)


def assess():
    start=time.perf_counter();plan,parent,architecture,cache,ids=inputs();check(read(REPORT/'refit.json'));torch.set_num_threads(4)
    windows,maps=original.load();encoded=old.encoded_windows(windows,maps,architecture);discovery=read(original.REPORT/'discovery.json');net=policy(parent,architecture);results={};comparisons={}
    for split in ('fit','evaluation'):
        value=evaluate(net,windows,maps,encoded,discovery,split,start+600);baseline=read(base.WORK/(split+'-predictions.json'))
        for a,b in zip(value['records'],baseline['records']):
            assert {k:v for k,v in a.items() if k not in ('move_prediction','movement_nll')}=={k:v for k,v in b.items() if k not in ('move_prediction','movement_nll')}
        immutable_json(WORK/(split+'-predictions.json'),value);results[split]=value['summary'];comparisons[split]=prior_pair(value,baseline);print(split,value['summary'],flush=True)
    bound_files=bindings([WORK/'selected.pt',WORK/'fit-predictions.json',WORK/'evaluation-predictions.json']);elapsed=time.perf_counter()-start
    if elapsed>=600:raise TimeoutError('Movement bias assessment exceeded')
    immutable_json(REPORT/'result.json',dict(refit_sha256=digest(REPORT/'refit.json'),results=results,comparisons=comparisons,
        target_met=results['evaluation']['movement_accuracy']>=.8,bindings=bound_files,seconds=elapsed,promoted=False))


def prior_pair(a,b):return base.prior.paired(a['records'],b['records'])


def verify():
    start=time.perf_counter();plan,parent,architecture,cache,ids=inputs();selection=read(REPORT/'selection.json');refit=read(REPORT/'refit.json');result=read(REPORT/'result.json')
    for r in (selection,refit,result):check(r)
    assert selection['plan_sha256']==digest(REPORT/'plan.json') and refit['selection_sha256']==digest(REPORT/'selection.json') and result['refit_sha256']==digest(REPORT/'refit.json')
    torch.set_num_threads(1);saved_calibration=read(WORK/'calibration.json');scores={}
    for fold in range(4):
        data=forecasts('fold'+str(fold),parent,architecture,cache);saved=torch.load(WORK/f'fold{fold}-logits.pt',weights_only=True)
        assert all(torch.equal(v,saved[k]) for k,v in data.items());training,held=expanded.partition_indices(ids,fold)
        for bound in [0.,*plan['bounds']]:
            bias,trace=calibrate(*subset(data,training),bound,plan);s=statistics(*subset(data,held),bias)
            assert dict(bias=bias.tolist(),trace=trace,validation=s)==saved_calibration[f'{fold}/{bound:g}'];scores[(fold,bound)]=s
    for c in selection['candidates']:
        v=[scores[(k,c['bound'])] for k in range(4)];assert c['correct']==sum(x['correct'] for x in v) and c['rows']==sum(x['rows'] for x in v)
        assert c['nll']==sum(x['nll']*x['rows'] for x in v)/c['rows']
    assert selection['selected']==choose(selection['candidates'])
    data=forecasts('full',parent,architecture,cache);saved=torch.load(WORK/'full-logits.pt',weights_only=True);assert all(torch.equal(v,saved[k]) for k,v in data.items())
    bias,trace=calibrate(*subset(data,np.arange(len(ids))),selection['selected']['bound'],plan);assert bias.tolist()==refit['bias'] and trace==refit['trace']
    original_weights=torch.load(base.WORK/'selected.pt',weights_only=False)['model'];weights=torch.load(WORK/'selected.pt',weights_only=False)['model']
    for k,v in weights.items():assert torch.equal(v,original_weights[k]+torch.from_numpy(bias) if k=='backbone.movement.bias' else original_weights[k]),k
    torch.set_num_threads(4);windows,maps=original.load();encoded=old.encoded_windows(windows,maps,architecture);discovery=read(original.REPORT/'discovery.json');net=policy(parent,architecture);exact={}
    for split in ('fit','evaluation'):
        actual=evaluate(net,windows,maps,encoded,discovery,split,time.perf_counter()+300);assert actual==read(WORK/(split+'-predictions.json'))
        assert actual['summary']==result['results'][split] and prior_pair(actual,read(base.WORK/(split+'-predictions.json')))==result['comparisons'][split]
        exact[split]=len(actual['records'])
    assert result['target_met']==(result['results']['evaluation']['movement_accuracy']>=.8)
    from .movement_bias_predictor import MovementBiasPredictor
    from .model import move_support
    predictor=MovementBiasPredictor();w=next(w for w in windows if w['partition']=='evaluation');state=None
    with torch.no_grad():expected=net(**encoded[w['key']])
    support,_=move_support(w)
    for i,s in enumerate(w['steps']):
        value=predictor.predict(s['input'] if s['observed'] else None,maps[w['payload']],s['round'],s['previous'],s['previous_mask'],state);state=value['state']
        assert value['code']==int(expected['code'][i].argmax())
        if value['movement_probabilities'] is not None:
            p=expected['move'][i].masked_fill(~support[i],-1e9).softmax(-1)
            torch.testing.assert_close(torch.tensor(value['movement_probabilities']),p,atol=2e-6,rtol=2e-5)
    immutable_json(REPORT/'verification.json',dict(result_sha256=digest(REPORT/'result.json'),exact_forecasts=exact,calibrations_reproduced=17,
        only_base_movement_bias_changed=True,streaming_turns=32,seconds=time.perf_counter()-start));print('VERIFIED movement bias',exact,flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('command',choices=('freeze','run','assess','verify'));globals()[p.parse_args().command]()
