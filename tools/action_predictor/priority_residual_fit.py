"""P05 preregistration: one learned absolute/negative-latest-residual output."""
import argparse,copy,sys,time,traceback
from pathlib import Path
import numpy as np
import torch
from . import reliable_train as rt
from .category_study import WORK,REPORTS
from .more_replays import frozen,sha
from .priority_fit_v3 import BASE,VAL,read,log,gate,load_base,report_metrics
from .priority_modes_fit import data
from . import priority_anchor_baselines as parent
from .priority_residual_modes import AnchoredPriorityModes

PLAN=REPORTS/'priority-residual-modes-plan.json'
SOURCES=REPORTS/'priority-residual-modes-sources.json'
VOCAB=REPORTS/'priority-residual-modes-vocabulary.json'
PREFIT=REPORTS/'priority-residual-modes-prefit.json'
NAMES=('priority_residual_modes.py','priority_residual_fit.py','priority_residual_predictor.py','priority_residual_roundtrip.py','test_priority_residual_modes.py')


def source_hashes():
    return {str(Path(__file__).with_name(n)):sha(Path(__file__).with_name(n)) for n in NAMES}


def verify_parent():
    parent.verify_protocol()
    review=read(REPORTS/'A01-review.json');assert review['verdict']=='APPROVE'
    for file,key in (('A01.json','report_sha256'),('A01-analysis.json','analysis_sha256'),('A01-state-and-generalization-diagnostic.json','state_diagnostic_sha256')):
        assert sha(REPORTS/file)==review[key]


def vocabulary():
    priors=read(parent.PRIORS)['priors']
    absolute=priors['global_frequency']['prior'];residual=priors['latest_minus_residual']['prior']
    return dict(absolute=absolute['values'],absolute_counts=absolute['counts'],residual=residual['values'],residual_counts=residual['counts'],
                absolute_support=absolute['fit_support'],residual_support=residual['fit_support'],source_priors_sha256=sha(parent.PRIORS))


def verify_protocol():
    verify_parent();source=read(SOURCES);plan=read(PLAN)
    assert source['sources']==source_hashes() and source['parent_sources_sha256']==sha(parent.SOURCES)
    assert plan['sources_sha256']==sha(SOURCES) and plan['vocabulary_sha256']==sha(VOCAB)
    assert plan['A01_review_sha256']==sha(REPORTS/'A01-review.json')
    assert read(VOCAB)==vocabulary(),'Vocabulary must reconstruct from bound TRAIN-only priors'
    assert plan['train_sha256']==sha(BASE/'combined-train.npz') and plan['validation_sha256']==sha(VAL)
    for split in ('train','validation'):
        assert plan['priority_'+split+'_sha256']==sha(WORK/('priority-'+split+'.npz'))
    assert plan['P03_report_sha256']==sha(REPORTS/'P03.json')
    assert plan['success_definition_sha256']==sha(REPORTS/'success-definition.json')
    return plan


def head(original):
    v=read(VOCAB)
    return AnchoredPriorityModes(original,v['absolute'],v['absolute_counts'],v['residual'],v['residual_counts'])


@torch.no_grad()
def predict(branch,context,extra,raw,baseline,values):
    result={k:v.copy() for k,v in baseline.items()};outputs=[];integers=[];nll=[];branch.eval()
    for start in range(0,len(context),256):
        stop=min(start+256,len(context));out=branch(context[start:stop],extra[start:stop]);v=torch.from_numpy(values[start:stop])
        outputs.append(out);integers.append(branch.integer(out,v))
        nll.append(-branch.log_mass(out,torch.from_numpy(raw['priority'][start:stop]).long(),v))
    output=torch.cat(outputs);result['priority']=torch.cat(integers).numpy()
    mask=raw['y']==rt.LABELS.index('priority');conditional=torch.cat(nll).numpy()
    result['param_nll'][mask]=conditional[mask];result['nll'][mask]=result['type_nll'][mask]+conditional[mask]
    return result,output


def prepare():
    verify_parent();gate()
    directory=WORK/'residual-modes-sources';directory.mkdir(exist_ok=True)
    for path,digest in source_hashes().items():
        destination=directory/(digest+'_'+Path(path).name)
        if not destination.exists():destination.write_bytes(Path(path).read_bytes())
        assert sha(destination)==digest
    frozen(SOURCES,dict(sources=source_hashes(),parent_sources_sha256=sha(parent.SOURCES)))
    frozen(VOCAB,vocabulary())
    frozen(PLAN,dict(id='P05',seed=26,sources_sha256=sha(SOURCES),vocabulary_sha256=sha(VOCAB),A01_review_sha256=sha(REPORTS/'A01-review.json'),
        train_sha256=sha(BASE/'combined-train.npz'),validation_sha256=sha(VAL),priority_train_sha256=sha(WORK/'priority-train.npz'),priority_validation_sha256=sha(WORK/'priority-validation.npz'),
        P03_report_sha256=sha(REPORTS/'P03.json'),success_definition_sha256=sha(REPORTS/'success-definition.json'),
        hypothesis='A learned mixture of absolute modes and residual modes around negative latest earlier own priority may improve exact commands and tails over P03. This is an output-design package, not assumed benefit or a recovered-input isolation.',
        architecture='Linear(167,1237): 518 absolute points,716 TRAIN-derived residual points shifted by negative latest PRE argument,one absolute logistic fallback gate and two parameters. 207816 trainable parameters versus87528 P03;104160 M01 parameters frozen. No hidden layer, GRU, nonhistory input, action or spatial change.',
        anchor='Exact signed int64 arithmetic on own latest earlier priority argument with explicit availability; earlier_event<=PRE<target_event. Input values verified signed-int32 domain; no label/output range clipping. Same39 causal channels as P03, normalized identically; analytic shift reads exact original integers rather than reversing float normalization.',
        prior='A01 TRAIN-only absolute and latest-minus-residual counts. Initial .475 absolute/.475 residual/.05 fallback; warm M01 fallback location/scale, other weights zero, construction RNG preserved. Missing anchor masks residual logits before softmax; retained absolute/fallback renormalize. No row deletion or invented residual modes.',
        distribution='Sum all duplicate absolute/shifted point masses with logsumexp, plus ONE normalized full-support integer-bin absolute logistic fallback. Decoder compares all point coordinates and floor/ceiling of fallback location, sorted smallest-integer ties. No target-dependent sign/anchor/routing and no private/POST state.',
        interpretation='Capacity2.374x P03 and changed prior are part of this output-design package. Cannot attribute gain only to arithmetic or infer input usefulness. Residual support[-1206,850] is TRAIN-derived for this negative anchor; A01 positive-anchor large residual evidence remains preserved; fallback supports all other integers.',
        normalization='Reuse original train-only M01 and V3 recovered-input normalization unchanged.',
        rows=dict(train=433071,validation=14439),membership='470 TRAIN games94groups;25 original development games5groups. All original targets/support retained;all43 shops unassessed strict failures. Both75-game reserved partitions sealed;old exposed test unused.',
        loss='Same unweighted priority NLL SUM divided by FULL minibatch length, frozen action/spatial loss accounting; no sampler, augmentation, class-weight, optimizer or loss-normalization changes.',
        training=rt.BENCH['training'],checkpoint='Original observed full-development joint NLL, improvement0.0001,patience6,max35epochs;epochzero reported but not selectable. Preserve all epochs,failures and checkpoints.',
        exploratory_progress_gate=dict(priority_exact_minimum=125,priority_joint_minimum=58,priority_nll_below=3.99395084,rare_nll_maximum=8.13333,unseen_nll_maximum=11.90325,errors_over1000_maximum=12,nonpriority_paths_identical=True,meaning='At least29 additional exact values over P03;positive joint gain;lower NLL;no >0.1nat rare/unseen NLL regression or increased >1000 tail. Exploratory continuation criterion only, not original success. No automatic repeats.'),
        reporting='Report all category joint correctness,type/joint PRF,false positives,both parameter denominators,losses,legality coverage,top-k/destination metrics;whole-group paired uncertainty vsP03/P01/M01/strongest A01 metric references;rare/unseen,no-history,outside16,sign,tail strata;compute and inactive masks. Full observed loss excludes unavailable shop args;strict scoring does not.',
        goal='All original >=90%every-category eachof3seeds,macroF1>=.65,movement+10pp,loss-10% vs strongest baseline,targeting guards unchanged. Parameter-only priority type ceiling343/576=59.55%. No strategy labels/percentage.',
        budget='ONE P05 seed26 substantive fit only. Fresh review of code,tests,causal roundtrip and protocol plus bound approval before optimizer. Fresh review after fit before any later experiment. Failed P04 gate does not trigger identical repeats.',
        prohibited='No matches,playing-bot changes,deployment,replay downloads,reserved behavior inspection,PR operations or auto-merging from this runner.'))
    verify_protocol();rt.setup(26)
    from .priority_residual_roundtrip import run
    run()
    model,_=load_base();branch=head(model.priority)
    frozen(PREFIT,dict(plan_sha256=sha(PLAN),sources_sha256=sha(SOURCES),vocabulary_sha256=sha(VOCAB),
        roundtrip_sha256=sha(REPORTS/'priority-residual-modes-initial-roundtrip.json'),trainable_parameters=sum(p.numel() for p in branch.parameters()),
        frozen_parameters=sum(p.numel() for p in model.parameters()),fits_started=0,new_optimizer_steps=0))
    print('P05 protocol and causal inference proof frozen. STOP for fresh Sol xhigh review before fitting.',flush=True)


def fit():
    plan=verify_protocol()
    approval=read(REPORTS/'priority-residual-modes-code-approval.json')
    assert approval['verdict']=='APPROVE' and approval['plan_sha256']==sha(PLAN)
    assert approval['sources_sha256']==sha(SOURCES) and approval['prefit_sha256']==sha(PREFIT)
    gate();verify_protocol();rt.setup(plan['seed'])
    model,contexts,extra,values,outside,mean,std,train_y,train_priority,raw,baseline=data()
    train_values=torch.from_numpy(values['train']);branch=head(model.priority);settings=plan['training'];optimizer=torch.optim.AdamW(branch.parameters(),lr=settings['lr'],weight_decay=settings['weight_decay'])
    directory=WORK/'runs/P05';directory.mkdir(exist_ok=True)
    assert not (REPORTS/'P05.json').exists(),'Completed fit immutable'
    fingerprint=dict(plan_sha256=sha(PLAN),sources_sha256=sha(SOURCES),prefit_sha256=sha(PREFIT),approval_sha256=sha(REPORTS/'priority-residual-modes-code-approval.json'))
    frozen(directory/'config.json',fingerprint)
    initial,_=predict(branch,contexts['validation'],extra['validation'],raw,baseline,values['validation'])
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
                        loss=-branch.log_mass(out,train_priority[chosen],train_values[chosen]).sum()/len(idx)
                        loss.backward();torch.nn.utils.clip_grad_norm_(branch.parameters(),settings['gradient_clip']);updates+=1;supervised+=len(chosen);total+=float(loss.detach())*len(idx)
                    optimizer.step();calls+=1
                prediction,_=predict(branch,contexts['validation'],extra['validation'],raw,baseline,values['validation']);score=rt.summarize(raw,prediction)
                row=dict(epoch=epoch,optimizer_calls=calls,head_updates=updates,supervised_examples=supervised,priority_train_objective_fullrow_mean=total/len(train_y),joint_nll=score['joint_nll'],seconds=time.perf_counter()-epoch_start)
                history.append(row)
                if score['joint_nll']<best-.0001:best=score['joint_nll'];best_epoch=epoch;best_state=copy.deepcopy(branch.state_dict())
                state=dict(head=branch.state_dict(),optimizer=optimizer.state_dict(),rng=torch.get_rng_state(),best=best,best_epoch=best_epoch,best_state=best_state,history=history,epoch=epoch,elapsed=elapsed+time.perf_counter()-start,fingerprint=fingerprint)
                torch.save(state,directory/('epoch-'+str(epoch)+'.pt'));torch.save(state,directory/'latest.tmp.pt');(directory/'latest.tmp.pt').replace(latest)
                print('P05',row,flush=True)
                if epoch-best_epoch>=settings['patience']:break
        branch.load_state_dict(best_state);pred,output=predict(branch,contexts['validation'],extra['validation'],raw,baseline,values['validation'])
        score=report_metrics(raw,pred,baseline,values['validation'],outside['validation'])
        torch.save(dict(head_state=best_state,architecture='frozen-M01-priority-anchored-modes-v1',config=dict(id='P05',seed=26,use_inputs=True),
            extra_mean=torch.from_numpy(mean),extra_std=torch.from_numpy(std),baseline_sha256=sha(BASE/'runs/M01/model.pt'),fingerprint=fingerprint),directory/'model.pt')
        np.savez_compressed(directory/'validation-predictions.npz',**pred);np.save(directory/'priority-outputs.npy',output.numpy())
        frozen(REPORTS/'P05.json',dict(config=dict(id='P05',seed=26,use_inputs=True),validation=score,best_epoch=best_epoch,history=history,
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
    p=argparse.ArgumentParser();p.add_argument('--prepare',action='store_true');p.add_argument('--fit',choices=['P05']);args=p.parse_args()
    assert args.prepare!=bool(args.fit),'Choose exactly one operation'
    log([sys.executable,'-m','tools.action_predictor.priority_residual_fit',*sys.argv[1:]])
    prepare() if args.prepare else fit()
