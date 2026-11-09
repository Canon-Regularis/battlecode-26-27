"""Preregister and run ONE reviewed absolute-mode priority experiment."""
import argparse,copy,json,sys,time,traceback
from pathlib import Path
import numpy as np
import torch
from . import reliable_train as rt
from .category_study import ROOT,WORK,REPORTS
from .more_replays import frozen,sha
from .priority_head import flatten
from .priority_modes import AbsolutePriorityModes
from .priority_dependencies_v3 import verify_dependencies,verify_roundtrip_bindings,baseline_binding,MANIFEST
from .priority_fit_v3 import BASE,VAL,read,write,log,gate,load_base,cached_context,context_directory,report_metrics

PLAN=REPORTS/'priority-absolute-modes-plan.json'
SOURCES=REPORTS/'priority-absolute-modes-sources.json'
VOCAB=REPORTS/'priority-absolute-modes-vocabulary.json'
PREFIT=REPORTS/'priority-absolute-modes-prefit.json'
NAMES=('priority_modes.py','priority_modes_fit.py','priority_modes_predictor.py','priority_modes_roundtrip.py','test_priority_modes.py')

def source_hashes():return {str(Path(__file__).with_name(n)):sha(Path(__file__).with_name(n)) for n in NAMES}

def verify_protocol():
    # Fail closed before consuming model/data even in standalone inference checks.
    verify_dependencies();manifest=read(SOURCES)
    assert manifest['legacy_manifest_sha256']==sha(MANIFEST)
    assert manifest['sources']==source_hashes()
    plan=read(PLAN)
    assert plan['sources_sha256']==sha(SOURCES) and plan['vocabulary_sha256']==sha(VOCAB)
    assert plan['context_ready_sha256']==sha(REPORTS/'priority-context-ready-v3.json')
    assert plan['success_definition_sha256']==sha(REPORTS/'success-definition.json')
    assert sha(BASE/'combined-train.npz')==plan['train_sha256']
    assert sha(VAL)==plan['validation_sha256']
    assert sha(REPORTS/'P02.json')==plan['P02_report_sha256']==read(REPORTS/'P02-review.json')['fit_report_sha256']
    assert read(REPORTS/'P02-review.json')['verdict']=='APPROVE'
    assert sha(WORK/'runs/P02/validation-predictions.npz')==read(REPORTS/'P02.json')['predictions_sha256']
    assert baseline_binding()['predictions_sha256']==plan['baseline_predictions_sha256']
    verify_roundtrip_bindings()
    return plan

def head(original):
    vocab=read(VOCAB)
    return AbsolutePriorityModes(original,vocab['values'],vocab['counts'],True)

def data():
    model,saved=load_base()
    contexts={s:cached_context(s,model,saved) for s in ('train','validation')}
    with np.load(context_directory()/'extra-normalization.npz') as z:mean,std=z['mean'],z['std']
    extra={};values={};outside={}
    for split in contexts:
        with np.load(WORK/('priority-'+split+'.npz')) as z:
            values[split]=z['values'];outside[split]=z['last_outside_window']
            extra[split]=torch.from_numpy((flatten(z['values'],z['history']).astype(np.float32)-mean)/std)
    with np.load(BASE/'combined-train.npz') as z:train_y=torch.from_numpy(z['y']).long();train_priority=torch.from_numpy(z['priority']).long()
    with np.load(VAL) as z:raw={k:z[k] for k in z.files}
    with np.load(BASE/'runs/M01/validation-predictions.npz') as z:baseline={k:z[k] for k in z.files}
    return model,contexts,extra,values,outside,mean,std,train_y,train_priority,raw,baseline

@torch.no_grad()
def predict(branch,context,extra,raw,baseline):
    result={k:v.copy() for k,v in baseline.items()};outputs=[];integers=[];nll=[];branch.eval()
    for start in range(0,len(context),256):
        stop=min(start+256,len(context));out=branch(context[start:stop],extra[start:stop]);outputs.append(out)
        integers.append(branch.integer(out));nll.append(-branch.log_mass(out,torch.from_numpy(raw['priority'][start:stop]).long()))
    output=torch.cat(outputs);result['priority']=torch.cat(integers).numpy()
    mask=raw['y']==rt.LABELS.index('priority');conditional=torch.cat(nll).numpy()
    result['param_nll'][mask]=conditional[mask];result['nll'][mask]=result['type_nll'][mask]+conditional[mask]
    return result,output

def prepare():
    verify_dependencies();gate()
    snapshots=WORK/'absolute-modes-sources';snapshots.mkdir(exist_ok=True)
    sources=source_hashes()
    for path,digest in sources.items():
        destination=snapshots/(digest+'_'+Path(path).name)
        if not destination.exists():destination.write_bytes(Path(path).read_bytes())
        assert sha(destination)==digest
    frozen(SOURCES,dict(legacy_manifest_sha256=sha(MANIFEST),sources=sources))
    with np.load(BASE/'combined-train.npz') as z:
        labels=z['priority'][z['y']==rt.LABELS.index('priority')]
    assert np.isfinite(labels).all() and np.array_equal(labels,labels.astype(np.int64))
    values,counts=np.unique(labels.astype(np.int64),return_counts=True)
    assert values.tolist()==read(REPORTS/'priority-training-vocabulary.json')['values']
    frozen(VOCAB,dict(values=values.tolist(),counts=counts.tolist(),support=int(counts.sum()),train_sha256=sha(BASE/'combined-train.npz')))
    frozen(PLAN,dict(id='P03',seed=26,use_inputs=True,hypothesis='A multimodal integer output may improve exact priority over single-logistic P02; benefit is not assumed.',
        sources_sha256=sha(SOURCES),vocabulary_sha256=sha(VOCAB),legacy_manifest_sha256=sha(MANIFEST),
        context_ready_sha256=sha(REPORTS/'priority-context-ready-v3.json'),success_definition_sha256=sha(REPORTS/'success-definition.json'),
        P02_report_sha256=sha(REPORTS/'P02.json'),baseline_predictions_sha256=baseline_binding()['predictions_sha256'],
        train_sha256=sha(BASE/'combined-train.npz'),validation_sha256=sha(VAL),rows=dict(train=433071,validation=14439),
        architecture='Linear(167,K+3): K training-only exact absolute-value point masses, one mixture fallback weight, two learned logistic parameters. Same frozen M01 context and causal39 extra channels; no hidden-layer or GRU change.',
        normalization='Reuse original train-only M01 and V3 recovered-input normalization unchanged.',
        initialization='Mode weights zero, bias log(.95*training_frequency); fallback gate .05; fallback location/scale warm-start M01, extra columns zero. Preserve RNG so seed26 shuffles match P01/P02.',
        distribution='Normalized categorical mixture over K integer point masses and a normalized integer-bin logistic fallback over all integers; stable float64 log masses, no label/range clipping. Decode global maximum over vocabulary union rounded fallback location.',
        loss='Unweighted observed priority NLL SUM divided by FULL minibatch length, same frozen action/spatial loss accounting; no augmentation, sampling or class-weight changes.',
        training=rt.BENCH['training'],checkpoint='Original observed full-development joint NLL, minimum improvement0.0001, patience6, max35epochs; epochzero reported but not selectable. No exact-accuracy selection.',
        compute='Compute gradients only for priority rows, with original full-minibatch denominator. Linear outputs K+3 versus2; report trainable parameters, calls/updates, supervised examples, epochs and elapsed time. No automatic repeats.',
        exploratory_progress_gate='At least5 percentage points higher exact priority than P02, lower priority NLL, positive joint-priority change, and identical nonpriority paths. Exploratory next-study criterion only, not replacement or original success threshold.',
        ultimate_goal='All immutable category-wise90%, original macroF1/movement/loss/targeting guards and three-seed requirements remain unchanged. Shops retain unassessed strict failures. Frozen priority actions cap joint at343/576.',
        budget='ONE substantive fit P03 only. Fresh pre-fit review and bound approval required; fresh review after fit. No immediate repeat or residual-branch test authorized by this plan.',
        reserved='Both75-game partitions sealed; old exposed test unused; no downloads/matches/botchanges/deployments/PR from this runner.'))
    verify_protocol();rt.setup(26)
    from .priority_modes_roundtrip import run
    run()
    model,_=load_base();branch=head(model.priority)
    frozen(PREFIT,dict(plan_sha256=sha(PLAN),sources_sha256=sha(SOURCES),vocabulary_sha256=sha(VOCAB),
        roundtrip_sha256=sha(REPORTS/'priority-absolute-modes-initial-roundtrip.json'),trainable_parameters=sum(p.numel() for p in branch.parameters()),
        frozen_parameters=sum(p.numel() for p in model.parameters()),fits_started=0,new_optimizer_steps=0))
    print('P03 preregistration and causal inference proof complete; STOP for fresh Sol xhigh review before fitting.',flush=True)

def fit():
    plan=verify_protocol()
    approval=read(REPORTS/'priority-absolute-modes-code-approval.json')
    assert approval['verdict']=='APPROVE' and approval['plan_sha256']==sha(PLAN)
    assert approval['sources_sha256']==sha(SOURCES) and approval['prefit_sha256']==sha(PREFIT)
    gate();verify_protocol();rt.setup(plan['seed'])
    model,contexts,extra,values,outside,mean,std,train_y,train_priority,raw,baseline=data()
    branch=head(model.priority);settings=plan['training'];optimizer=torch.optim.AdamW(branch.parameters(),lr=settings['lr'],weight_decay=settings['weight_decay'])
    directory=WORK/'runs/P03';directory.mkdir(exist_ok=True)
    assert not (REPORTS/'P03.json').exists(),'Completed fit immutable'
    fingerprint=dict(plan_sha256=sha(PLAN),sources_sha256=sha(SOURCES),prefit_sha256=sha(PREFIT),approval_sha256=sha(REPORTS/'priority-absolute-modes-code-approval.json'))
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
                print('P03',row,flush=True)
                if epoch-best_epoch>=settings['patience']:break
        branch.load_state_dict(best_state);pred,output=predict(branch,contexts['validation'],extra['validation'],raw,baseline)
        score=report_metrics(raw,pred,baseline,values['validation'],outside['validation'])
        torch.save(dict(head_state=best_state,architecture='frozen-M01-priority-absolute-modes-v1',config=dict(id='P03',seed=26,use_inputs=True),
            extra_mean=torch.from_numpy(mean),extra_std=torch.from_numpy(std),baseline_sha256=sha(BASE/'runs/M01/model.pt'),fingerprint=fingerprint),directory/'model.pt')
        np.savez_compressed(directory/'validation-predictions.npz',**pred);np.save(directory/'priority-outputs.npy',output.numpy())
        frozen(REPORTS/'P03.json',dict(config=dict(id='P03',seed=26,use_inputs=True),validation=score,best_epoch=best_epoch,history=history,
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
    p=argparse.ArgumentParser();p.add_argument('--prepare',action='store_true');p.add_argument('--fit',choices=['P03']);args=p.parse_args()
    assert args.prepare!=bool(args.fit),'Choose exactly one operation'
    log([sys.executable,'-m','tools.action_predictor.priority_modes_fit',*sys.argv[1:]])
    prepare() if args.prepare else fit()
