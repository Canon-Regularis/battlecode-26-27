"""One reviewed fit per invocation; NEVER auto-run a second experiment."""
import argparse
import copy
import json
from pathlib import Path
import sys
import time
import traceback
import numpy as np
import torch

from . import reliable_train as rt
from .reliable_model import JointModel,priority_log_mass
from .category_study import ROOT,WORK,REPORTS
from .more_replays import frozen,sha
from .priority_head import PriorityHead,flatten,normalizer
from .priority_dependencies import MANIFEST,freeze_dependencies,verify_dependencies,baseline_binding
from .observation_metrics import correctness

BASE=ROOT/'.cambc/action-predictor/v5'
VAL=ROOT/'.cambc/action-predictor/v4/validation.npz'

def context_directory():return WORK/'priority-context'/sha(__file__)[:16]

def read(path):return json.loads(Path(path).read_text(encoding='utf-8'))
def write(path,value):
    temp=path.with_suffix('.tmp');temp.write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8');temp.replace(path)
def log(argv):
    with (WORK/'commands.jsonl').open('a') as f:f.write(json.dumps(dict(argv=list(map(str,argv))))+'\n')
def code_hashes():
    return {str(Path(__file__).with_name(name)):sha(Path(__file__).with_name(name)) for name in
        ('priority_fit_v2.py','priority_head.py','priority_predictor.py','priority_roundtrip_v2.py','test_priority_head.py','priority_dependencies.py','test_priority_dependencies.py')}

def gate():
    verify_dependencies() # Current executable closure and frozen baseline predictions.
    # Revalidate live full evidence, not just a saved passed=True or probe report.
    from .priority_verify import verify
    verify()
    audit=read(REPORTS/'priority-recovery-audit.json');approval=read(REPORTS/'priority-data-review-approval.json')
    assert audit['passed'] and audit['chain_verification_sha256']==sha(REPORTS/'priority-chain-verification.json')
    assert audit['data_ready_sha256']==sha(REPORTS/'priority-data-ready.json')
    assert audit['plan_sha256']==sha(REPORTS/'priority-extraction-plan.json')
    assert audit['audit_source_sha256']==sha(Path(__file__).with_name('priority_audit.py'))
    assert audit['validator_source_sha256']==sha(Path(__file__).with_name('priority_verify.py'))
    for name,digest in audit['test_source_sha256'].items():assert sha(Path(__file__).with_name(name))==digest
    for path,digest in audit['input_hashes'].items():assert sha(path)==digest
    assert approval['verdict']=='APPROVE' and approval['audit_sha256']==sha(REPORTS/'priority-recovery-audit.json')
    assert approval['chain_sha256']==sha(REPORTS/'priority-chain-verification.json')
    from .observation_study import freeze_plan
    from .observation_validate import sealed_audit
    freeze_plan();sealed_audit()
    member=read(ROOT/'tools/action_predictor/experiments/v5/membership.json')
    for r in member['records']:
        if r['split']!='train':assert not (WORK/'priority'/r['raw_sha256']).exists()
    original=read(ROOT/'tools/action_predictor/experiments/v5/M01.json')
    assert sha(BASE/'runs/M01/model.pt')==original['checkpoint_sha256']
    return audit

def freeze_design():
    settings=rt.BENCH['training']
    frozen(REPORTS/'priority-logistic-design-v2.json',dict(
        revision=2,prior_design_sha256=sha(REPORTS/'priority-logistic-design.json'),dependencies_sha256=sha(MANIFEST),
        hypothesis='Recovering omitted causal priority inputs may improve integer prediction; no benefit assumed.',
        fits=[dict(id='P01',seed=26,use_inputs=False),dict(id='P02',seed=26,use_inputs=True)],
        replication='Do not auto-repeat. After both individually reviewed seed26 fits, preregister seed27/28 matched repeats if measured benefit and original guards justify them. No claim of three-seed consistency before repeats.',
        architecture='Frozen M01 context128 and every action/spatial path. Matched Linear(167,2) logistic priority heads,336 trainable parameters each;39 extra fields:7 current/latest values+masks/gap and16x2 earlier argument/mask. Control zeroes normalized extra channels.',
        initialization='Both warm-start identical M01 priority weights/bias; added columns zero; preserve shuffle RNG. No shared-model fine-tuning.',
        normalization='Retained M01 normalization for original paths; float64 mean/sample std of all433071 TRAIN recovered input rows only, floor0.01, storedfloat32. No validation-fitted statistics.',
        losses='Original integer-bin logistic NLL only for priority rows, SUM divided by FULL minibatch length. Frozen action/spatial terms have zero gradients and are omitted from backprop, but all terms retained for checkpoint/evaluation joint NLL.',
        training=settings,checkpoint='Minimum unweighted observed joint NLL over all14439 validation rows; improvement0.0001, patience6,35epoch cap. Same rule botharms; no selection on exact accuracy. Epoch0 is reported only, not a candidate.',
        rows=dict(train=433071,validation=14439),sampler='Original augmented full-row random permutation, batch256; no class/sample changes.',
        accounting='Replace only priority forecasts and priority conditional NLL in frozen M01 predictions; keep action/coordinate/ability paths identical. Retain all rows,43shopsunassessed, all categories and originalguards. Parameter-only priority joint ceiling343/576.',
        inputs=dict(train_sha256=sha(BASE/'combined-train.npz'),validation_sha256=sha(VAL),
                    recovered_ready_sha256=sha(REPORTS/'priority-data-ready.json'),baseline_sha256=sha(BASE/'runs/M01/model.pt'),baseline_predictions_sha256=baseline_binding()['predictions_sha256']),
        success_definition_sha256=sha(REPORTS/'success-definition.json'),code=code_hashes(),
        review='Code/design approval bound to exact hashes required before fit. Exactly one fit per command; fresh requested Sol xhigh review after every completed fit before another command. Failed/resumed states retained.',
        reserved='75newval+75finaltest sealed, oldtestunused; no matches/botchanges/downloads/deployments/PR from this runner.'))

def load_base():
    saved=torch.load(BASE/'runs/M01/model.pt',weights_only=True,map_location='cpu')
    model=JointModel(len(saved['mean']),24,len(rt.LABELS),saved['config']);model.load_state_dict(saved['state_dict'])
    model.requires_grad_(False);model.eval();return model,saved

def cached_context(split,model,saved):
    source=BASE/'combined-train.npz' if split=='train' else VAL
    directory=context_directory();directory.mkdir(parents=True,exist_ok=True)
    path=directory/(split+'.npy');receipt=directory/(split+'.json')
    binding=dict(data_sha256=sha(source),checkpoint_sha256=sha(BASE/'runs/M01/model.pt'),
        encoder_sha256=sha(Path(__file__).with_name('reliable_model.py')),preprocessing_sha256=sha(Path(__file__).with_name('reliable_train.py')),
        context_builder_sha256=sha(__file__))
    if receipt.exists():
        info=read(receipt);assert info['binding']==binding and sha(path)==info['sha256']
    else:
        assert not path.exists(),'Partial context cache retained; inspect before retry'
        with np.load(source) as z:raw={k:z[k] for k in z.files}
        data,_=rt.model_data(raw,saved['config'],(saved['mean'],saved['std']))
        table=np.lib.format.open_memmap(path,mode='w+',dtype=np.float32,shape=(len(raw['y']),128))
        with torch.no_grad():
            for start in range(0,len(table),256):
                stop=min(len(table),start+256);_,context=model(data['x'][start:stop],data['history'][start:stop]);table[start:stop]=context.numpy()
        table.flush();del table
        frozen(receipt,dict(binding=binding,sha256=sha(path),rows=len(raw['y'])))
    return torch.from_numpy(np.load(path,mmap_mode='c'))

def prepare():
    freeze_dependencies();gate();freeze_design();rt.setup(26);model,saved=load_base()
    for split in ('train','validation'):cached_context(split,model,saved)
    with np.load(WORK/'priority-train.npz') as z:extra=flatten(z['values'],z['history'])
    mean,std=normalizer(extra)
    path=context_directory()/'extra-normalization.npz'
    if path.exists():
        with np.load(path) as z:assert np.array_equal(mean,z['mean']) and np.array_equal(std,z['std'])
    else:np.savez_compressed(path,mean=mean,std=std)
    frozen(REPORTS/'priority-context-ready-v2.json',dict(
        contexts={s:sha(context_directory()/(s+'.npy')) for s in ('train','validation')},directory=str(context_directory()),
        normalizer_sha256=sha(path),design_sha256=sha(REPORTS/'priority-logistic-design-v2.json'),new_fits=0))
    print('Frozen contexts and training-only normalization prepared; no optimizer steps.',flush=True)

def predict(head,context,extra,raw,baseline):
    result={key:value.copy() for key,value in baseline.items()};outputs=[];head.eval()
    with torch.no_grad():
        for start in range(0,len(context),256):outputs.append(head(context[start:start+256],extra[start:start+256]))
    output=torch.cat(outputs);result['priority']=(output[:,0]*100).round().numpy()
    mask=raw['y']==rt.LABELS.index('priority')
    conditional=-priority_log_mass(output[mask],torch.from_numpy(raw['priority'][mask])).numpy()
    result['param_nll'][mask]=conditional
    result['nll'][mask]=result['type_nll'][mask]+conditional
    return result

def report_metrics(raw,pred,baseline,extra_values,outside):
    score=rt.summarize(raw,pred);_,joint=correctness(raw,pred)
    score['joint_per_action']={name:dict(support=int((raw['y']==i).sum()),correct=int(joint[raw['y']==i].sum()),
        accuracy=float(joint[raw['y']==i].mean()) if (raw['y']==i).any() else None,
        false_positives=int(((pred['prediction']==i)&(raw['y']!=i)).sum())) for i,name in enumerate(rt.LABELS)}
    mask=raw['y']==rt.LABELS.index('priority');target=raw['priority']
    vocab=set(read(REPORTS/'priority-training-vocabulary.json')['values'])
    unseen=np.array([int(v) not in vocab for v in target])
    score['priority_strata']={}
    for name,selected in [('all',mask),('no_previous',mask&(extra_values[:,5]==0)),
        ('latest_outside16',mask&outside),('unseen_value',mask&unseen)]:
        n=int(selected.sum());score['priority_strata'][name]=dict(support=n,exact=int((pred['priority'][selected]==target[selected]).sum()),
            joint=int(joint[selected].sum()),nll=float(pred['param_nll'][selected].mean()) if n else None)
    for key in ('prediction','coordinate','proposed_coordinate','top5','type_nll'):
        assert np.array_equal(pred[key],baseline[key]),'Frozen path changed: '+key
    nonpriority=~mask;assert np.array_equal(pred['nll'][nonpriority],baseline['nll'][nonpriority])
    score['parameters']['priority']['exact_accuracy']=float((pred['priority'][mask]==target[mask]).mean())
    score['priority_conditional_nll']=float(pred['param_nll'][mask].mean())
    rng=np.random.default_rng(20261106);groups=np.unique(raw['group']);g=len(groups)
    draws=np.stack([np.bincount(rng.integers(0,g,size=g),minlength=g) for _ in range(2000)])
    _,old_joint=correctness(raw,baseline);intervals={}
    for name in rt.LABELS:
        selected=raw['y']==rt.LABELS.index(name)
        n=np.array([(selected&(raw['group']==group)).sum() for group in groups])
        a=np.array([(selected&joint&(raw['group']==group)).sum() for group in groups])
        b=np.array([(selected&old_joint&(raw['group']==group)).sum() for group in groups])
        denominator=draws@n;ok=denominator>0
        intervals[name]=dict(valid_draws=int(ok.sum()),support=int(selected.sum()))
        if ok.any():
            absolute=(draws@a)[ok]/denominator[ok];delta=(draws@(a-b))[ok]/denominator[ok]
            intervals[name].update(joint_interval=list(map(float,np.quantile(absolute,[.025,.975]))),
                                  delta_vs_M01_interval=list(map(float,np.quantile(delta,[.025,.975]))))
    score['paired_group_joint_intervals']=intervals
    return score

def fit(identifier):
    gate();freeze_design();design=read(REPORTS/'priority-logistic-design-v2.json')
    approval=read(REPORTS/'priority-fit-code-approval-v2.json')
    assert approval['verdict']=='APPROVE' and approval['design_sha256']==sha(REPORTS/'priority-logistic-design-v2.json')
    assert approval['sources']==code_hashes()
    assert approval['dependencies_sha256']==verify_dependencies()
    config=next(c for c in design['fits'] if c['id']==identifier)
    ledger_path=WORK/'priority-fit-ledger-v2.json';ledger=read(ledger_path) if ledger_path.exists() else {}
    if identifier=='P02':
        review=read(REPORTS/'P01-review.json');assert review['fit_report_sha256']==sha(REPORTS/'P01.json') and review['verdict']=='APPROVE'
    directory=WORK/'runs'/identifier;directory.mkdir(parents=True,exist_ok=True)
    assert not (REPORTS/(identifier+'.json')).exists(),'Completed fit immutable; do not refit under sameID'
    if identifier in ledger:assert ledger[identifier]['config']==config
    else:ledger[identifier]=dict(config=config,status='reserved')
    write(ledger_path,ledger)
    rt.setup(config['seed']);model,saved=load_base();contexts={s:cached_context(s,model,saved) for s in ('train','validation')}
    context_ready=read(REPORTS/'priority-context-ready-v2.json')
    for split in contexts:assert sha(context_directory()/(split+'.npy'))==context_ready['contexts'][split]
    assert context_ready['directory']==str(context_directory())
    with np.load(context_directory()/'extra-normalization.npz') as z:mean,std=z['mean'],z['std']
    assert sha(context_directory()/'extra-normalization.npz')==context_ready['normalizer_sha256']
    assert context_ready['design_sha256']==sha(REPORTS/'priority-logistic-design-v2.json')
    extra={};values={};outside={}
    for split in contexts:
        with np.load(WORK/('priority-'+split+'.npz')) as z:
            values[split]=z['values'];outside[split]=z['last_outside_window'];features=flatten(z['values'],z['history'])
        extra[split]=torch.from_numpy((features.astype(np.float32)-mean)/std)
    with np.load(BASE/'combined-train.npz') as z:train_y=torch.from_numpy(z['y']).long();train_priority=torch.from_numpy(z['priority']).float()
    with np.load(VAL) as z:raw={key:z[key] for key in z.files}
    assert baseline_binding()['predictions_sha256']==design['inputs']['baseline_predictions_sha256']
    with np.load(BASE/'runs/M01/validation-predictions.npz') as z:baseline={key:z[key] for key in z.files}
    head=PriorityHead(model.priority,config['use_inputs']);settings=design['training']
    optimizer=torch.optim.AdamW(head.parameters(),lr=settings['lr'],weight_decay=settings['weight_decay'])
    fingerprint=dict(design_sha256=sha(REPORTS/'priority-logistic-design-v2.json'),config=config,
        context_ready_sha256=sha(REPORTS/'priority-context-ready-v2.json'),approval_sha256=sha(REPORTS/'priority-fit-code-approval-v2.json'),
        dependencies_sha256=sha(MANIFEST),baseline_predictions_sha256=baseline_binding()['predictions_sha256'])
    frozen(directory/'config.json',fingerprint)
    initial_prediction=predict(head,contexts['validation'],extra['validation'],raw,baseline)
    initial_score=rt.summarize(raw,initial_prediction)
    frozen(directory/'epoch-zero.json',initial_score) # Report only; never eligible for selection.
    best=float('inf');best_epoch=0;best_state=None;history=[];start_epoch=1;elapsed=0.
    latest=directory/'latest-state.pt'
    if latest.exists():
        state=torch.load(latest,weights_only=True,map_location='cpu');assert state['fingerprint']==fingerprint
        head.load_state_dict(state['head']);optimizer.load_state_dict(state['optimizer']);torch.set_rng_state(state['rng'])
        best,best_epoch,best_state=state['best'],state['best_epoch'],state['best_state'];history=state['history'];start_epoch=state['epoch']+1;elapsed=state['elapsed']
    start=time.perf_counter();ledger[identifier]['status']='running';write(ledger_path,ledger)
    try:
        if not (history and history[-1]['epoch']-best_epoch>=settings['patience']):
            for epoch in range(start_epoch,settings['max_epochs']+1):
                epoch_start=time.perf_counter();head_updates=0;optimizer_calls=0;head.train();order=torch.randperm(len(train_y));total=0.
                for a in range(0,len(order),settings['batch_size']):
                    idx=order[a:a+settings['batch_size']];selected=train_y[idx]==rt.LABELS.index('priority')
                    optimizer.zero_grad(set_to_none=True)
                    if not selected.any():
                        optimizer.step();optimizer_calls+=1 # None gradients: no priority update/weight decay, as original full model.
                        continue
                    output=head(contexts['train'][idx],extra['train'][idx])
                    loss=-priority_log_mass(output[selected],train_priority[idx[selected]]).sum()/len(idx)
                    loss.backward();torch.nn.utils.clip_grad_norm_(head.parameters(),settings['gradient_clip']);optimizer.step();optimizer_calls+=1;head_updates+=1
                    total+=float(loss.detach())*len(idx)
                prediction=predict(head,contexts['validation'],extra['validation'],raw,baseline);score=rt.summarize(raw,prediction)
                row=dict(epoch=epoch,optimizer_calls=optimizer_calls,head_updates=head_updates,priority_train_objective_fullrow_mean=total/len(train_y),joint_nll=score['joint_nll'],
                    priority_exact=float((prediction['priority'][raw['y']==9]==raw['priority'][raw['y']==9]).mean()),seconds=time.perf_counter()-epoch_start)
                history.append(row)
                if score['joint_nll']<best-.0001:best=score['joint_nll'];best_epoch=epoch;best_state=copy.deepcopy(head.state_dict())
                torch.save(dict(head=head.state_dict(),optimizer=optimizer.state_dict(),rng=torch.get_rng_state(),best=best,best_epoch=best_epoch,
                    best_state=best_state,history=history,epoch=epoch,elapsed=elapsed+time.perf_counter()-start,fingerprint=fingerprint),directory/('epoch-'+str(epoch)+'.pt'))
                temp=directory/'latest.tmp.pt';torch.save(dict(head=head.state_dict(),optimizer=optimizer.state_dict(),rng=torch.get_rng_state(),best=best,best_epoch=best_epoch,
                    best_state=best_state,history=history,epoch=epoch,elapsed=elapsed+time.perf_counter()-start,fingerprint=fingerprint),temp);temp.replace(latest)
                print(identifier,row,flush=True)
                if epoch-best_epoch>=settings['patience']:break
        head.load_state_dict(best_state);pred=predict(head,contexts['validation'],extra['validation'],raw,baseline)
        score=report_metrics(raw,pred,baseline,values['validation'],outside['validation'])
        torch.save(dict(head_state=best_state,config=config,extra_mean=torch.from_numpy(mean),extra_std=torch.from_numpy(std),
            baseline_sha256=sha(BASE/'runs/M01/model.pt'),architecture='frozen-M01-priority-logistic-v1',fingerprint=fingerprint),directory/'model.pt')
        np.savez_compressed(directory/'validation-predictions.npz',**pred)
        frozen(REPORTS/(identifier+'.json'),dict(config=config,validation=score,best_epoch=best_epoch,history=history,
            trainable_parameters=sum(p.numel() for p in head.parameters()),frozen_baseline_parameters=sum(p.numel() for p in model.parameters()),
            optimizer_calls=sum(row['optimizer_calls'] for row in history),head_updates=sum(row['head_updates'] for row in history),
            epoch_zero_sha256=sha(directory/'epoch-zero.json'),
            resume_accounting='Completed epochs only. Discarded partial-epoch work and time after interruption are not included; failure logs and every epoch checkpoint are retained. Optimizer calls include no-gradient batches; head updates exclude them.',elapsed_seconds=elapsed+time.perf_counter()-start,
            checkpoint_sha256=sha(directory/'model.pt'),predictions_sha256=sha(directory/'validation-predictions.npz'),
            nonpriority_paths_unchanged=True,three_seed_confirmed=False,all_category_goal_met=False))
        ledger[identifier]['status']='complete';ledger[identifier]['report_sha256']=sha(REPORTS/(identifier+'.json'));write(ledger_path,ledger)
    except BaseException:
        ledger[identifier]['status']='failed_or_interrupted';write(ledger_path,ledger)
        (directory/('failure-'+str(time.time_ns())+'.txt')).write_text(traceback.format_exc());raise
    print('ONE fit complete. STOP: fresh Sol review required before another experiment.',flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--prepare',action='store_true');parser.add_argument('--fit',choices=['P01','P02']);args=parser.parse_args()
    log([sys.executable,'-m','tools.action_predictor.priority_fit_v2',*sys.argv[1:]])
    if args.prepare:prepare()
    elif args.fit:fit(args.fit)
    else:parser.error('Choose --prepare or --fit; never multiple fits')
