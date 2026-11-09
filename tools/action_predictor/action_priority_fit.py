"""C01/C02: matched classifier-only soft-priority-input comparison."""
import argparse,copy,sys,time,traceback
from pathlib import Path
import numpy as np
import torch
import torch.nn.functional as F
from . import reliable_train as rt
from .category_study import WORK,REPORTS,ROOT
from .more_replays import frozen,sha
from .priority_fit_v3 import BASE,VAL,read,log,gate,load_base,context_directory
from .priority_modes_fit import data as parent_data
from .priority_residual_fit import verify_protocol as verify_parent,head as priority_head
from .action_priority_head import ActionPriorityHead,classifier_features,routed_coordinates,assemble_predictions
from .event_semantics import PLAN as SEMANTICS,sources as semantics_sources
from .observation_metrics import correctness

PLAN=REPORTS/'action-priority-plan.json';SOURCES=REPORTS/'action-priority-sources.json'
WEIGHTS=REPORTS/'action-priority-weights.json';PREFIT=REPORTS/'action-priority-prefit.json'
PRIORITY=WORK/'runs/P05'
NAMES=('action_priority_head.py','action_priority_fit.py','action_priority_predictor.py','action_priority_roundtrip.py','test_action_priority.py')

def sources():return {str(Path(__file__).with_name(n)):sha(Path(__file__).with_name(n)) for n in NAMES}

def parent_bindings():
    verify_parent();review=read(REPORTS/'D01-review.json');assert review['verdict']=='APPROVE'
    for file,key in (('D01.json','report_sha256'),('D01-analysis.json','analysis_sha256'),('D01-completion.json','completion_sha256')):assert sha(REPORTS/file)==review[key]
    assert read(SEMANTICS)['source_hashes']==semantics_sources()
    review=read(REPORTS/'P05-review.json');assert review['verdict']=='APPROVE'
    assert review['fit_report_sha256']==sha(REPORTS/'P05.json')
    info=read(REPORTS/'P05.json')
    for file,key in (('model.pt','checkpoint_sha256'),('validation-predictions.npz','predictions_sha256'),('priority-outputs.npy','priority_outputs_sha256')):assert sha(PRIORITY/file)==info[key]

def weights(y,balance):
    counts=torch.bincount(y,minlength=len(rt.LABELS)).float()
    result=(counts.max()/counts.clamp_min(1)).pow(balance).clamp_max(20)
    return counts,result/result[y].mean()

def verify_protocol():
    parent_bindings();manifest=read(SOURCES);plan=read(PLAN)
    assert manifest['sources']==sources() and manifest['D01_plan_sha256']==sha(SEMANTICS)
    assert plan['sources_sha256']==sha(SOURCES) and plan['weights_sha256']==sha(WEIGHTS)
    assert plan['D01_review_sha256']==sha(REPORTS/'D01-review.json') and plan['P05_report_sha256']==sha(REPORTS/'P05.json')
    assert plan['success_definition_sha256']==sha(REPORTS/'success-definition.json')
    assert plan['train_sha256']==sha(BASE/'combined-train.npz') and plan['validation_sha256']==sha(VAL)
    assert plan['normalization_sha256']==sha(context_directory()/'extra-normalization.npz')
    for split in ('train','validation'):
        assert plan['priority_'+split+'_sha256']==sha(WORK/('priority-'+split+'.npz'))
        assert plan['context_'+split+'_sha256']==sha(context_directory()/(split+'.npy'))
    with np.load(BASE/'combined-train.npz') as z:y=torch.from_numpy(z['y']).long()
    counts,w=weights(y,plan['balance']);assert read(WEIGHTS)==dict(counts=counts.tolist(),weights=w.tolist(),balance=plan['balance'],normalization='Mean weight over all original augmented TRAIN rows equals one')
    return plan

def head(original,use_inputs):return ActionPriorityHead(original,use_inputs)

def data():
    model,contexts,extra,values,outside,mean,std,y,_,raw,_=parent_data()
    features={split:classifier_features(extra[split],torch.from_numpy(values[split])) for split in contexts}
    saved=torch.load(PRIORITY/'model.pt',weights_only=True,map_location='cpu')
    assert torch.equal(saved['extra_mean'],torch.from_numpy(mean)) and torch.equal(saved['extra_std'],torch.from_numpy(std))
    arguments=priority_head(model.priority);arguments.load_state_dict(saved['head_state']);arguments.requires_grad_(False);arguments.eval()
    with np.load(PRIORITY/'validation-predictions.npz') as z:baseline={k:z[k] for k in z.files}
    fixed_nll=baseline['param_nll'].astype(np.float64)
    mask=raw['y']==rt.LABELS.index('priority')
    with torch.no_grad():
        out=torch.from_numpy(np.asarray(np.load(PRIORITY/'priority-outputs.npy',mmap_mode='r')[mask]).copy())
        fixed_nll[mask]=-arguments.log_mass(out,torch.from_numpy(raw['priority'][mask]).long(),torch.from_numpy(values['validation'][mask])).numpy()
    saved_base=torch.load(BASE/'runs/M01/model.pt',weights_only=True,map_location='cpu')
    spatial,_=rt.model_data(raw,saved_base['config'],(saved_base['mean'],saved_base['std']))
    return model,arguments,contexts,features,extra,values,mean,std,y,raw,baseline,fixed_nll,spatial

@torch.no_grad()
def predict(branch,model,context,features,raw,baseline,fixed_nll,spatial):
    branch.eval();outputs=[];proposed=[]
    for start in range(0,len(context),256):
        stop=min(start+256,len(context));out=branch(context[start:stop],features[start:stop]);outputs.append(out)
        proposed.append(routed_coordinates(model,context[start:stop],spatial['grid'][start:stop].float(),spatial['valid'][start:stop],out,spatial['rules'][start:stop]).argmax(-1))
    logits=torch.cat(outputs)
    result=assemble_predictions(baseline,logits,torch.cat(proposed),torch.from_numpy(raw['y']).long(),rt.LABELS.index('priority'),fixed_nll)
    for key in ('coordinate','top5','priority','param_nll'):assert np.array_equal(result[key],baseline[key]),key
    matched=result['prediction']==raw['y'];assert np.array_equal(result['coordinate'][matched],result['proposed_coordinate'][matched])
    return result,logits

def summarize(raw,pred):
    result=rt.summarize(raw,pred);_,joint=correctness(raw,pred)
    result['joint_per_action']={name:dict(support=int((raw['y']==i).sum()),correct=int(joint[raw['y']==i].sum())) for i,name in enumerate(rt.LABELS)}
    return result

def prepare():
    parent_bindings();gate();rt.setup(26);model,saved=load_base()
    with np.load(BASE/'combined-train.npz') as z:y=torch.from_numpy(z['y']).long()
    balance=saved['config']['balance'];assert not saved['config'].get('focal')
    counts,w=weights(y,balance)
    frozen(WEIGHTS,dict(counts=counts.tolist(),weights=w.tolist(),balance=balance,normalization='Mean weight over all original augmented TRAIN rows equals one'))
    directory=WORK/'action-priority-sources';directory.mkdir(exist_ok=True)
    for path,digest in sources().items():
        p=directory/(digest+'_'+Path(path).name)
        if not p.exists():p.write_bytes(Path(path).read_bytes())
        assert sha(p)==digest
    frozen(SOURCES,dict(sources=sources(),D01_plan_sha256=sha(SEMANTICS)))
    bindings={}
    for split in ('train','validation'):
        bindings['priority_'+split+'_sha256']=sha(WORK/('priority-'+split+'.npz'))
        bindings['context_'+split+'_sha256']=sha(context_directory()/(split+'.npy'))
    frozen(PLAN,dict(id='C01-C02',fits=[dict(id='C01',seed=26,use_inputs=False),dict(id='C02',seed=26,use_inputs=True)],sources_sha256=sha(SOURCES),weights_sha256=sha(WEIGHTS),
        D01_review_sha256=sha(REPORTS/'D01-review.json'),P05_report_sha256=sha(REPORTS/'P05.json'),success_definition_sha256=sha(REPORTS/'success-definition.json'),
        train_sha256=sha(BASE/'combined-train.npz'),validation_sha256=sha(VAL),normalization_sha256=sha(context_directory()/'extra-normalization.npz'),**bindings,
        hypothesis='Direct causal priority-state/history channels plus two fixed PRE indicators may improve action discrimination in a frozen GRU representation. Benefit is not assumed; compare against a fresh matched zeroed-classifier-input control.',
        architecture='Same two affine terms in both arms: Linear128to15 warmed M01 action logits plus bias-free Linear41to15 initializedzero. No new hidden activation/GRU/map/argument change.2550 nominal parameters;615 extra weights inactive in control.104160 M01 plus207816 P05 argument parameters frozen.',
        feature_schema='Existing39 flattened causal priority inputs in original order, normalized by unchanged TRAIN-only mean/std; append unnormalized pair_unavailable=!(current_available&&scheduled_available) and changed=(both_available&&current!=scheduled), computed from exact int64 personal PRE values. No current target/header/POST/future/intent inputs. Unknown pair sets unavailable1 and changed0; original masks retained. Pair_unavailable is0 on all current TRAIN/dev rows, avoiding a redundant treatment-only constant bias.',
        control='Zero all41 classifier extra channels in forward even after load; retain correlated M01 context and P05 argument predictor with its original priority inputs. This isolates direct classifier access to an input package, not whole-model absence of priority information or arithmetic-only attribution.',
        balance=balance,training=rt.BENCH['training'],loss='Retain M01 augmented-row sampling/shuffle and exact TRAIN class-weight formula capped20, normalized by mean TRAIN row weight. Optimize mean(weight[y]*actionCE) over FULL minibatch; focalzero. Frozen argument losses have no gradients; validation unweighted full observed joint NLL retains exact P05 argument losses/rounding. No frequency or weight correction in this study.',
        checkpoint='Original full-development observed joint NLL, improvement0.0001,patience6,max35epochs. Epochzero reported not selectable. Preserve all epochs/failure/resume accounting. No selection on exactness/macroF1.',
        routing='Runtime coordinate probabilities always use PREDICTED action family. Retain true-family coordinates/top5 and original argument losses for parameter metrics. Recompute proposed coordinates for changed types. Priority arguments remain P05. All43shops strict unassessed failures.',
        membership='Same433071TRAIN targets470games94groups;14439originaldevtargets25games5groups. Both75reservedpartitions sealed,oldexposedtestunused. No new rows, no action constraints or label changes.',
        exploratory_progress_gate=dict(action_macro_f1_minimum=.65,macro_f1_gain_vs_control=.02,priority_joint_gain_vs_control_minimum=18,priority_joint_minimum=71,ward_type_correct_minimum=35,ward_joint_minimum=7,ward_type_false_positives_maximum=282,move_joint_minimum=1287,recall_joint_minimum=2472,targeting_joint_regression_maximum=.02,observed_joint_loss_below_control=True,strict_joint_above_control=True,meaning='All conditions required; priority+18 is a fixed count gate. Also require no ward/move/recall joint decline vs control and no >2pp attack/cast0/cast1 joint decline vs EITHER control or P05. Original conditional targeting guards unchanged. Exploratory follow-up only, not reliability/replacement.'),
        reporting='Per-action type/joint PRF/support/FP, true-family vs correct-type parameter accuracy, all targeting/joint regressions, top-k/destination errors, loss and partial legality decomposition with assessed support.2000 paired whole-group resamples vs P05 and matched control, missing/outside16/priority-state strata. Actual rows retained; five reused groups and checkpoint-selection limitations explicit.',
        budget='TWO substantive fits C01thenC02 seed26 only, separate CLI invocations and fresh review after each. C01 code/pre-fit review approval required; C02 also needs actual completed-C01 review. If all frozen progress gates pass, propose separately reviewed seeds27/28 matched repeats; none automatic or authorized under this plan. Head seeds under fixed M01/P05 are not independent full-GRU seed consistency.',
        goals='Original >=90%joint EVERYcategory EACHof3seeds and all original macroF1,movement+10pp,strongest-baselineloss-10%,targeting guards unchanged. Frozen parameter ceilings include priority109/576,move1404/2362,ward24/112,cast1 146/243; this isolation cannot satisfy the full category goal.',
        prohibited='No matches,botchanges,deployment,downloads,reserved behavior,PR/merge operations from runner. No hard equality/channel/after-priority masks.'))
    verify_protocol();model,arguments,contexts,features,extra,values,mean,std,y,raw,baseline,fixed_nll,spatial=data()
    a=head(model.action,False);b=head(model.action,True);maximum=0.
    with torch.no_grad():
        for split in contexts:
            for start in range(0,len(contexts[split]),256):
                c=contexts[split][start:start+256];f=features[split][start:start+256]
                assert torch.equal(a(c,f),b(c,f)) and torch.equal(a(c,f),model.action(c))
        initial,outputs=predict(a,model,contexts['validation'],features['validation'],raw,baseline,fixed_nll,spatial)
        for key in baseline:assert np.array_equal(initial[key],baseline[key]),key
    from .action_priority_roundtrip import run
    run();run(use_inputs=True)
    zero_columns=(features['train']==0).all(0).nonzero().flatten().tolist()
    frozen(PREFIT,dict(plan_sha256=sha(PLAN),sources_sha256=sha(SOURCES),weights_sha256=sha(WEIGHTS),all447510_initial_logits_exact=True,all8_initial_prediction_arrays_exact=True,
        trainable_parameters=sum(p.numel() for p in a.parameters()),inactive_control_weights=615,frozen_parameters=sum(p.numel() for p in model.parameters())+sum(p.numel() for p in arguments.parameters()),
        all_zero_TRAIN_extra_columns=zero_columns,inactive_treatment_weights_on_current_TRAIN=15*len(zero_columns),
        control_roundtrip_sha256=sha(REPORTS/'action-priority-initial-control-roundtrip.json'),treatment_roundtrip_sha256=sha(REPORTS/'action-priority-initial-treatment-roundtrip.json'),new_fits=0))
    print('C01/C02 preregistration and pre-fit proof complete. STOP for fresh Sol xhigh review before C01.',flush=True)

def fit(identifier):
    plan=verify_protocol();approval=read(REPORTS/'action-priority-code-approval.json')
    assert approval['verdict']=='APPROVE' and approval['plan_sha256']==sha(PLAN) and approval['sources_sha256']==sha(SOURCES) and approval['prefit_sha256']==sha(PREFIT)
    if identifier=='C02':
        reviewed=read(REPORTS/'C01-review.json');assert reviewed['verdict']=='APPROVE' and reviewed['fit_report_sha256']==sha(REPORTS/'C01.json')
    gate();verify_protocol();config=next(c for c in plan['fits'] if c['id']==identifier);rt.setup(config['seed'])
    model,arguments,contexts,features,extra,values,mean,std,y,raw,baseline,fixed_nll,spatial=data()
    branch=head(model.action,config['use_inputs']);w=torch.tensor(read(WEIGHTS)['weights']);settings=plan['training']
    optimizer=torch.optim.AdamW(branch.parameters(),lr=settings['lr'],weight_decay=settings['weight_decay'])
    directory=WORK/'runs'/identifier;directory.mkdir(exist_ok=True);assert not (REPORTS/(identifier+'.json')).exists(),'Completed fit immutable'
    fingerprint=dict(plan_sha256=sha(PLAN),sources_sha256=sha(SOURCES),prefit_sha256=sha(PREFIT),approval_sha256=sha(REPORTS/'action-priority-code-approval.json'),config=config)
    if identifier=='C02':fingerprint['C01_review_sha256']=sha(REPORTS/'C01-review.json')
    frozen(directory/'config.json',fingerprint)
    initial,_=predict(branch,model,contexts['validation'],features['validation'],raw,baseline,fixed_nll,spatial);frozen(directory/'epoch-zero.json',summarize(raw,initial))
    best=float('inf');best_epoch=0;best_state=None;history=[];start_epoch=1;elapsed=0.;latest=directory/'latest-state.pt'
    if latest.exists():
        state=torch.load(latest,weights_only=True);assert state['fingerprint']==fingerprint
        branch.load_state_dict(state['head']);optimizer.load_state_dict(state['optimizer']);torch.set_rng_state(state['rng'])
        best,best_epoch,best_state,history,start_epoch,elapsed=state['best'],state['best_epoch'],state['best_state'],state['history'],state['epoch']+1,state['elapsed']
    start=time.perf_counter()
    try:
        if not(history and history[-1]['epoch']-best_epoch>=settings['patience']):
            for epoch in range(start_epoch,settings['max_epochs']+1):
                epoch_start=time.perf_counter();branch.train();order=torch.randperm(len(y));calls=0;total=0.
                for offset in range(0,len(order),settings['batch_size']):
                    index=order[offset:offset+settings['batch_size']];optimizer.zero_grad(set_to_none=True)
                    out=branch(contexts['train'][index],features['train'][index]);loss=(w[y[index]]*F.cross_entropy(out,y[index],reduction='none')).mean()
                    loss.backward();torch.nn.utils.clip_grad_norm_(branch.parameters(),settings['gradient_clip']);optimizer.step();calls+=1;total+=float(loss.detach())*len(index)
                pred,_=predict(branch,model,contexts['validation'],features['validation'],raw,baseline,fixed_nll,spatial);score=summarize(raw,pred)
                row=dict(epoch=epoch,optimizer_calls=calls,head_updates=calls,supervised_examples=len(y),weighted_action_train_mean=total/len(y),joint_nll=score['joint_nll'],seconds=time.perf_counter()-epoch_start);history.append(row)
                if score['joint_nll']<best-.0001:best=score['joint_nll'];best_epoch=epoch;best_state=copy.deepcopy(branch.state_dict())
                state=dict(head=branch.state_dict(),optimizer=optimizer.state_dict(),rng=torch.get_rng_state(),best=best,best_epoch=best_epoch,best_state=best_state,history=history,epoch=epoch,elapsed=elapsed+time.perf_counter()-start,fingerprint=fingerprint)
                torch.save(state,directory/('epoch-'+str(epoch)+'.pt'));torch.save(state,directory/'latest.tmp.pt');(directory/'latest.tmp.pt').replace(latest)
                print(identifier,row,flush=True)
                if epoch-best_epoch>=settings['patience']:break
        branch.load_state_dict(best_state);pred,outputs=predict(branch,model,contexts['validation'],features['validation'],raw,baseline,fixed_nll,spatial)
        torch.save(dict(head_state=best_state,architecture='frozen-M01-P05-action-priority-v1',config=config,labels=rt.LABELS,extra_mean=torch.from_numpy(mean),extra_std=torch.from_numpy(std),baseline_sha256=sha(BASE/'runs/M01/model.pt'),priority_sha256=sha(PRIORITY/'model.pt'),fingerprint=fingerprint),directory/'model.pt')
        np.savez_compressed(directory/'validation-predictions.npz',**pred);np.save(directory/'action-logits.npy',outputs.numpy())
        frozen(REPORTS/(identifier+'.json'),dict(config=config,validation=summarize(raw,pred),best_epoch=best_epoch,history=history,trainable_parameters=sum(p.numel() for p in branch.parameters()),inactive_control_weights=0 if config['use_inputs'] else 615,
            frozen_parameters=sum(p.numel() for p in model.parameters())+sum(p.numel() for p in arguments.parameters()),optimizer_calls=sum(r['optimizer_calls'] for r in history),head_updates=sum(r['head_updates'] for r in history),supervised_examples=sum(r['supervised_examples'] for r in history),elapsed_seconds=elapsed+time.perf_counter()-start,
            checkpoint_sha256=sha(directory/'model.pt'),predictions_sha256=sha(directory/'validation-predictions.npz'),action_logits_sha256=sha(directory/'action-logits.npy'),fingerprint=fingerprint,
            argument_paths_unchanged=True,predicted_family_routing=True,resume_accounting='Completed epochs/time only; discarded partial work retained in failure logs. Every classifier batch has gradients; calls equal updates.',three_seed_confirmed=False,all_category_goal_met=False))
    except BaseException:
        (directory/('failure-'+str(time.time_ns())+'.txt')).write_text(traceback.format_exc());raise
    print('ONE classifier fit complete. STOP for fresh Sol xhigh review.',flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--prepare',action='store_true');parser.add_argument('--fit',choices=['C01','C02']);args=parser.parse_args()
    assert args.prepare!=bool(args.fit);log([sys.executable,'-m','tools.action_predictor.action_priority_fit',*sys.argv[1:]])
    prepare() if args.prepare else fit(args.fit)
