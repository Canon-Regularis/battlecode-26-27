"""Matched P03 output head with recovered priority channels zeroed: P04 only."""
import argparse,copy,json,sys,time,traceback,inspect
from pathlib import Path
import numpy as np
import torch
from . import reliable_train as rt
from .category_study import ROOT,WORK,REPORTS
from .more_replays import frozen,sha
from .priority_modes import AbsolutePriorityModes
from .priority_fit_v3 import read,log,gate,load_base,BASE,report_metrics
from . import priority_modes_fit as treatment
from .priority_modes_fit import data,predict,VOCAB

PLAN=REPORTS/'priority-modes-control-plan.json'
SOURCES=REPORTS/'priority-modes-control-sources.json'
PREFIT=REPORTS/'priority-modes-control-prefit.json'
NAMES=('priority_modes_control.py','priority_modes_control_predictor.py','priority_modes_control_roundtrip.py','test_priority_modes_control.py')

def source_hashes():return {str(Path(__file__).with_name(n)):sha(Path(__file__).with_name(n)) for n in NAMES}

def verify_parent():
    treatment.verify_protocol()
    review=read(REPORTS/'P03-review.json');assert review['verdict']=='APPROVE'
    for name,key in (('P03.json','fit_report_sha256'),('P03-analysis.json','analysis_sha256'),('P03-tail-and-coverage-amendment.json','tail_amendment_sha256')):
        assert sha(REPORTS/name)==review[key]
    info=read(REPORTS/'P03.json')
    for name,key in (('model.pt','checkpoint_sha256'),('validation-predictions.npz','predictions_sha256'),('priority-outputs.npy','priority_outputs_sha256')):
        assert sha(WORK/'runs/P03'/name)==info[key]
    approval=read(REPORTS/'priority-absolute-modes-code-approval.json')
    assert approval['completion_sha256']==sha(REPORTS/'priority-absolute-modes-prefit-completion.json')
    assert approval['evaluation_addendum_sha256']==sha(REPORTS/'priority-absolute-modes-evaluation-addendum.json')

def verify_protocol():
    verify_parent();manifest=read(SOURCES);plan=read(PLAN)
    assert manifest['sources']==source_hashes()
    assert manifest['parent_sources_sha256']==sha(treatment.SOURCES)
    assert plan['sources_sha256']==sha(SOURCES) and plan['parent_plan_sha256']==sha(treatment.PLAN)
    assert plan['P03_report_sha256']==sha(REPORTS/'P03.json') and plan['P03_review_sha256']==sha(REPORTS/'P03-review.json')
    assert plan['evaluation_addendum_sha256']==sha(REPORTS/'priority-absolute-modes-evaluation-addendum.json')
    assert plan['training']==read(treatment.PLAN)['training']
    return plan

def head(original):
    vocab=read(VOCAB)
    return AbsolutePriorityModes(original,vocab['values'],vocab['counts'],False)

def canonical_treatment_fit():
    return inspect.getsource(treatment.fit).replace('P03','P04').replace('priority-absolute-modes-code-approval.json','priority-modes-control-code-approval.json').replace('use_inputs=True','use_inputs=False')

def prepare():
    verify_parent();gate()
    snapshots=WORK/'mode-control-sources';snapshots.mkdir(exist_ok=True)
    for path,digest in source_hashes().items():
        p=snapshots/(digest+'_'+Path(path).name)
        if not p.exists():p.write_bytes(Path(path).read_bytes())
        assert sha(p)==digest
    frozen(SOURCES,dict(sources=source_hashes(),parent_sources_sha256=sha(treatment.SOURCES)))
    parent=read(treatment.PLAN)
    frozen(PLAN,dict(id='P04',seed=26,use_inputs=False,hypothesis='Do the39 recovered causal priority channels improve the P03 multimodal head? No benefit assumed.',
        sources_sha256=sha(SOURCES),parent_plan_sha256=sha(treatment.PLAN),P03_report_sha256=sha(REPORTS/'P03.json'),P03_review_sha256=sha(REPORTS/'P03-review.json'),
        evaluation_addendum_sha256=sha(REPORTS/'priority-absolute-modes-evaluation-addendum.json'),training=parent['training'],rows=parent['rows'],
        comparison='Same87528parameter head, training-only518value vocabulary, initialization, M01 fallback warmstart, seed26, context128, normalizedextra39, data/groups, loss, sampler, optimizer, compute path and checkpoint rule as P03. ONLY zero all normalized extra39 channels within head.forward.',
        implementation='Reuse immutable P03 data/predict helpers and exact fit function after declared ID/artifact-name/use_inputs substitutions; verify canonical source equivalence. Original P03 sources/checkpoints/reports remain unchanged.',
        checkpoint=parent['checkpoint'],budget='ONE substantive P04 control fit only; code/protocol proof reviewed before optimizer, completed fit freshly reviewed before any subsequent study or repeat.',
        exploratory_input_gate='P03 at least5 percentage points higher exact priority than P04, lower priority NLL and higher joint priority correctness, identical nonpriority paths. This only supports proposing separately preregistered matched head-seed repeats; original goals/guards unchanged.',
        reporting='Compare both arms against P01/P02/frequency/M01; show exact/joint/NLL, completecategoryPRF/support/FP, rare/unseen/missing/outside-window/history-length/tail errors, paired whole-group uncertainty, parameter/compute counts. No causal contribution claim before measured control.',
        ultimate_goal=parent['ultimate_goal'],reserved=parent['reserved'],replication='No auto-repeat. Any later matched head-seed repeats keep the same frozen M01 representation and cannot certify independent full-GRU training or category-wide reliability.'))
    verify_protocol()
    assert inspect.getsource(fit)==canonical_treatment_fit(),'Matched optimization loop differs unexpectedly'
    rt.setup(26);model,contexts,extra,*_=data()
    control=head(model.priority);active=treatment.head(model.priority)
    assert all(torch.equal(control.state_dict()[k],v) for k,v in active.state_dict().items())
    maximum=0.;compared=0
    with torch.no_grad():
        for split in contexts:
            for a in range(0,len(contexts[split]),256):
                c=contexts[split][a:a+256];e=extra[split][a:a+256]
                difference=float((control(c,e)-active(c,e)).abs().max());maximum=max(maximum,difference);compared+=len(c)
    assert maximum==0
    from .priority_modes_control_roundtrip import run
    run()
    frozen(PREFIT,dict(plan_sha256=sha(PLAN),sources_sha256=sha(SOURCES),parent_prefit_sha256=sha(treatment.PREFIT),
        roundtrip_sha256=sha(REPORTS/'priority-modes-control-initial-roundtrip.json'),initial_rows_compared=compared,initial_maximum_difference=maximum,
        optimizer_loop_canonical_equivalent=True,trainable_parameters=sum(p.numel() for p in control.parameters()),frozen_parameters=sum(p.numel() for p in model.parameters()),new_optimizer_steps=0))
    print('P04 matched-control pre-fit proof complete. STOP for fresh Sol xhigh review.',flush=True)

def fit():
    plan=verify_protocol()
    approval=read(REPORTS/'priority-modes-control-code-approval.json')
    assert approval['verdict']=='APPROVE' and approval['plan_sha256']==sha(PLAN)
    assert approval['sources_sha256']==sha(SOURCES) and approval['prefit_sha256']==sha(PREFIT)
    gate();verify_protocol();rt.setup(plan['seed'])
    model,contexts,extra,values,outside,mean,std,train_y,train_priority,raw,baseline=data()
    branch=head(model.priority);settings=plan['training'];optimizer=torch.optim.AdamW(branch.parameters(),lr=settings['lr'],weight_decay=settings['weight_decay'])
    directory=WORK/'runs/P04';directory.mkdir(exist_ok=True)
    assert not (REPORTS/'P04.json').exists(),'Completed fit immutable'
    fingerprint=dict(plan_sha256=sha(PLAN),sources_sha256=sha(SOURCES),prefit_sha256=sha(PREFIT),approval_sha256=sha(REPORTS/'priority-modes-control-code-approval.json'))
    frozen(directory/'config.json',fingerprint)
    initial,_=predict(branch,contexts['validation'],extra['validation'],raw,baseline)
    frozen(directory/'epoch-zero.json',rt.summarize(raw,initial))
    best=float('inf');best_epoch=0;best_state=None;history=[];start_epoch=1;elapsed=0.
    latest=directory/'latest-state.pt'
    if latest.exists():
        state=torch.load(latest,weights_only=True);assert state['fingerprint']==fingerprint
        branch.load_state_dict(state['head']);optimizer.load_state_dict(state['optimizer']);torch.set_rng_state(state['rng'])
        best,best_epoch,best_state,history,start_epoch,elapsed=state['best'],state['best_epoch'],state['best_state'],state['history'],state['epoch']+1,state['elapsed']
    start=time.perf_counter()
    try:
        if not (history and history[-1]['epoch']-best_epoch>=settings['patience']):
            for epoch in range(start_epoch,settings['max_epochs']+1):
                epoch_start=time.perf_counter();calls=0;updates=0;supervised=0;total=0.;branch.train();order=torch.randperm(len(train_y))
                for a in range(0,len(order),settings['batch_size']):
                    idx=order[a:a+settings['batch_size']];selected=train_y[idx]==rt.LABELS.index('priority');optimizer.zero_grad(set_to_none=True)
                    if selected.any():
                        chosen=idx[selected];out=branch(contexts['train'][chosen],extra['train'][chosen])
                        loss=-branch.log_mass(out,train_priority[chosen]).sum()/len(idx)
                        loss.backward();torch.nn.utils.clip_grad_norm_(branch.parameters(),settings['gradient_clip']);updates+=1;supervised+=len(chosen);total+=float(loss.detach())*len(idx)
                    optimizer.step();calls+=1
                prediction,_=predict(branch,contexts['validation'],extra['validation'],raw,baseline);score=rt.summarize(raw,prediction)
                row=dict(epoch=epoch,optimizer_calls=calls,head_updates=updates,supervised_examples=supervised,priority_train_objective_fullrow_mean=total/len(train_y),joint_nll=score['joint_nll'],seconds=time.perf_counter()-epoch_start)
                history.append(row)
                if score['joint_nll']<best-.0001:best=score['joint_nll'];best_epoch=epoch;best_state=copy.deepcopy(branch.state_dict())
                state=dict(head=branch.state_dict(),optimizer=optimizer.state_dict(),rng=torch.get_rng_state(),best=best,best_epoch=best_epoch,best_state=best_state,history=history,epoch=epoch,elapsed=elapsed+time.perf_counter()-start,fingerprint=fingerprint)
                torch.save(state,directory/('epoch-'+str(epoch)+'.pt'));torch.save(state,directory/'latest.tmp.pt');(directory/'latest.tmp.pt').replace(latest)
                print('P04',row,flush=True)
                if epoch-best_epoch>=settings['patience']:break
        branch.load_state_dict(best_state);pred,output=predict(branch,contexts['validation'],extra['validation'],raw,baseline)
        score=report_metrics(raw,pred,baseline,values['validation'],outside['validation'])
        torch.save(dict(head_state=best_state,architecture='frozen-M01-priority-absolute-modes-v1',config=dict(id='P04',seed=26,use_inputs=False),
            extra_mean=torch.from_numpy(mean),extra_std=torch.from_numpy(std),baseline_sha256=sha(BASE/'runs/M01/model.pt'),fingerprint=fingerprint),directory/'model.pt')
        np.savez_compressed(directory/'validation-predictions.npz',**pred);np.save(directory/'priority-outputs.npy',output.numpy())
        frozen(REPORTS/'P04.json',dict(config=dict(id='P04',seed=26,use_inputs=False),validation=score,best_epoch=best_epoch,history=history,
            trainable_parameters=sum(p.numel() for p in branch.parameters()),frozen_baseline_parameters=sum(p.numel() for p in model.parameters()),
            optimizer_calls=sum(r['optimizer_calls'] for r in history),head_updates=sum(r['head_updates'] for r in history),supervised_examples=sum(r['supervised_examples'] for r in history),
            resume_accounting='Only completed epochs/time counted; any discarded partial work remains in failure logs. Calls include no-gradient batches; head updates exclude them.',
            elapsed_seconds=elapsed+time.perf_counter()-start,checkpoint_sha256=sha(directory/'model.pt'),predictions_sha256=sha(directory/'validation-predictions.npz'),
            priority_outputs_sha256=sha(directory/'priority-outputs.npy'),epoch_zero_sha256=sha(directory/'epoch-zero.json'),fingerprint=fingerprint,
            nonpriority_paths_unchanged=True,three_seed_confirmed=False,all_category_goal_met=False))
    except BaseException:
        (directory/('failure-'+str(time.time_ns())+'.txt')).write_text(traceback.format_exc());raise
    print('ONE fit complete. STOP for fresh Sol xhigh review.',flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--prepare',action='store_true');p.add_argument('--fit',choices=['P04']);args=p.parse_args()
    assert args.prepare!=bool(args.fit),'Choose exactly one operation'
    log([sys.executable,'-m','tools.action_predictor.priority_modes_control',*sys.argv[1:]])
    prepare() if args.prepare else fit()
