"""Six-fit maximum matched experiment; non-history inputs, heads and losses fixed."""
import copy
import json
import random
import sys
import time
import traceback

import numpy as np
import torch
import torch.nn.functional as F
from torch import nn

from . import reliable_train as rt
from .reliable_model import JointModel,priority_log_mass
from .observation_model import ObservationHistoryModel
from .observation_inputs import ObservationInputs
from .observation_study import ROOT,WORK,REPORTS,OLD,MORE,freeze_plan,log_command
from .more_replays import frozen,sha
from .more_train import combined_data
from .observation_metrics import compare,targeting_regressions
from .development import gates


def atomic_json(path,value):
    temporary=path.with_suffix('.tmp');temporary.write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8');temporary.replace(path)


def infer(model,data,bank,batch_size=256):
    from collections import defaultdict
    output=defaultdict(list);model.eval();n=len(data['y'])
    with torch.no_grad():
        for a in range(0,n,batch_size):
            b=min(n,a+batch_size);idx=torch.arange(a,b);observations,gaps=bank.batch(idx)
            logits,context=model(data['x'][a:b],data['history'][a:b],observations,gaps)
            lp=logits.log_softmax(-1);y,py=data['y'][a:b],data['py'][a:b];prediction=lp.argmax(-1)
            grid=data['grid'][a:b].float();valid=data['valid'][a:b];rules=data['rules'][a:b]
            conditional=model.parameter_logits(context,grid,valid,y,rules).log_softmax(-1)
            proposed=model.parameter_logits(context,grid,valid,prediction,rules).argmax(-1)
            priority=model.priority(context);type_nll=-lp.gather(1,y[:,None])[:,0];param_nll=torch.zeros(b-a)
            selected=py>=0;param_nll[selected]=-conditional[selected].gather(1,py[selected,None])[:,0]
            ispriority=y==rt.LABELS.index('priority');priority_nll=-priority_log_mass(priority,data['priority'][a:b])
            param_nll[ispriority]=priority_nll[ispriority]
            values=dict(prediction=prediction,nll=type_nll+param_nll,type_nll=type_nll,param_nll=param_nll,
                        coordinate=conditional.argmax(-1),proposed_coordinate=proposed,top5=conditional.topk(5,-1).indices,
                        priority=(priority[:,0]*100).round())
            for key,value in values.items():output[key].append(value.numpy())
    return {key:np.concatenate(value) for key,value in output.items()}


def rng_state():
    n=np.random.get_state()
    return dict(torch=torch.get_rng_state(),python=random.getstate(),numpy=[n[0],n[1].tolist(),*n[2:]])


def restore_rng(state):
    torch.set_rng_state(state['torch']);random.setstate(state['python'])
    n=state['numpy'];np.random.set_state((n[0],np.array(n[1],dtype=np.uint32),*n[2:]))


def reserve_fit(identifier,seed,config):
    path=WORK/'fit-ledger.json';ledger=json.loads(path.read_text()) if path.exists() else {}
    if identifier not in ledger:
        if len(ledger)>=6:raise RuntimeError('Six substantive fits exhausted, including failed fits')
        ledger[identifier]=dict(seed=seed,config=config,status='reserved',reserved_at=time.time())
    else:assert ledger[identifier]['seed']==seed and ledger[identifier]['config']==config
    atomic_json(path,ledger)


def update_fit(identifier,**fields):
    path=WORK/'fit-ledger.json';ledger=json.loads(path.read_text());ledger[identifier].update(fields);atomic_json(path,ledger)


def fit(config,seed,train_raw,val_raw,train_bank,val_bank,normalizer):
    identifier=config['id'];directory=WORK/'runs'/identifier;directory.mkdir(parents=True,exist_ok=True)
    report=REPORTS/(identifier+'.json')
    if report.exists():
        info=json.loads(report.read_text());assert info['config']==config and info['seed']==seed
        assert sha(directory/'model.pt')==info['checkpoint_sha256']
        update_fit(identifier,status='complete',report_sha256=sha(report));return info
    reserve_fit(identifier,seed,config)
    rt.setup(seed)
    train,_=rt.model_data(train_raw,config,normalizer);val,_=rt.model_data(val_raw,config,normalizer)
    model=ObservationHistoryModel(train['x'].shape[1],train['history'].shape[-1],len(rt.LABELS),config)
    settings=rt.BENCH['training'];optimizer=torch.optim.AdamW(model.parameters(),lr=settings['lr'],weight_decay=settings['weight_decay'])
    counts=torch.bincount(train['y'],minlength=len(rt.LABELS)).float()
    weights=(counts.max()/counts.clamp_min(1)).pow(config['balance']).clamp_max(20);weights/=weights[train['y']].mean()
    fingerprint=dict(config=config,seed=seed,plan_sha256=sha(REPORTS/'plan.json'),data_ready_sha256=sha(REPORTS/'data-ready.json'),
        train_sha256=sha(MORE/'combined-train.npz'),validation_sha256=sha(OLD/'validation.npz'),
        execution_lock_sha256=sha(REPORTS/'execution-lock.json'),training_settings=settings)
    frozen(directory/'config.json',fingerprint)
    best=float('inf');best_epoch=0;best_state=None;history=[];start_epoch=1;elapsed=0.
    latest=directory/'latest-state.pt'
    if latest.exists():
        state=torch.load(latest,weights_only=True,map_location='cpu');assert state['fingerprint']==fingerprint
        model.load_state_dict(state['model']);optimizer.load_state_dict(state['optimizer']);restore_rng(state['rng'])
        best=state['best'];best_epoch=state['best_epoch'];best_state=state['best_state'];history=state['history']
        start_epoch=state['epoch']+1;elapsed=state['elapsed_seconds']
        print(identifier,'resuming identical fit at epoch',start_epoch,flush=True)
    wall_start=time.perf_counter();update_fit(identifier,status='running')
    try:
        if not (history and history[-1]['epoch']-best_epoch>=settings['patience']):
            for epoch in range(start_epoch,settings['max_epochs']+1):
                epoch_start=time.perf_counter();model.train();order=torch.randperm(len(train['y']));total=0.
                for a in range(0,len(order),settings['batch_size']):
                    idx=order[a:a+settings['batch_size']];y=train['y'][idx];py=train['py'][idx]
                    obs,gaps=train_bank.batch(idx);optimizer.zero_grad(set_to_none=True)
                    logits,context=model(train['x'][idx],train['history'][idx],obs,gaps)
                    loss=(weights[y]*F.cross_entropy(logits,y,reduction='none')).mean()
                    selected=py>=0
                    if selected.any():
                        parameter_logits=model.parameter_logits(context[selected],train['grid'][idx[selected]].float(),
                            train['valid'][idx[selected]],y[selected],train['rules'][idx[selected]])
                        loss+=F.cross_entropy(parameter_logits,py[selected],reduction='sum')/len(idx)
                    priority=y==rt.LABELS.index('priority')
                    if priority.any():loss-=priority_log_mass(model.priority(context[priority]),train['priority'][idx[priority]]).sum()/len(idx)
                    loss.backward();nn.utils.clip_grad_norm_(model.parameters(),settings['gradient_clip']);optimizer.step()
                    total+=float(loss.detach())*len(idx)
                train_seconds=time.perf_counter()-epoch_start;eval_start=time.perf_counter()
                prediction=infer(model,val,val_bank);score=rt.summarize(val_raw,prediction)
                row=dict(epoch=epoch,train_objective=total/len(train['y']),validation_nll=score['joint_nll'],
                    macro_f1=score['macro_f1'],movement_exact=score['parameters']['move']['exact_accuracy'],
                    movement_joint=score['parameters']['move']['joint_accuracy'],train_seconds=train_seconds,
                    evaluation_seconds=time.perf_counter()-eval_start)
                history.append(row)
                if score['joint_nll']<best-.0001:
                    best=score['joint_nll'];best_epoch=epoch;best_state=copy.deepcopy(model.state_dict())
                    torch.save(dict(state_dict=best_state,epoch=epoch),directory/'best-state.pt')
                state=dict(model=model.state_dict(),optimizer=optimizer.state_dict(),rng=rng_state(),best=best,best_epoch=best_epoch,
                    best_state=best_state,history=history,epoch=epoch,fingerprint=fingerprint,
                    elapsed_seconds=elapsed+time.perf_counter()-wall_start)
                temporary=directory/'latest-state.tmp.pt';torch.save(state,temporary);temporary.replace(latest)
                atomic_json(directory/'progress.json',row)
                print(identifier,row,flush=True)
                if epoch-best_epoch>=settings['patience']:break
        model.load_state_dict(best_state)
        prediction=infer(model,val,val_bank);score=rt.summarize(val_raw,prediction)
        bundle=dict(state_dict=best_state,config=config,seed=seed,mean=normalizer[0],std=normalizer[1],labels=rt.LABELS,
                    architecture='personal-observation-history-gru-v1',plan_sha256=sha(REPORTS/'plan.json'))
        checkpoint=directory/'model.pt'
        if checkpoint.exists():
            old=torch.load(checkpoint,weights_only=True,map_location='cpu')
            assert all(torch.equal(old['state_dict'][key],value) for key,value in best_state.items())
        else:torch.save(bundle,checkpoint)
        np.savez_compressed(directory/'validation-predictions.npz',**prediction)
        info=dict(config=config,seed=seed,best_epoch=best_epoch,history=history,validation=score,
            parameters=sum(p.numel() for p in model.parameters()),baseline_parameters=104160,
            elapsed_seconds=elapsed+time.perf_counter()-wall_start,
            training_seconds=sum(r['train_seconds'] for r in history),optimizer_steps=len(history)*int(np.ceil(len(train['y'])/settings['batch_size'])),
            target_rows=len(train['y']),checkpoint_sha256=sha(checkpoint),predictions_sha256=sha(directory/'validation-predictions.npz'))
        frozen(report,info);update_fit(identifier,status='complete',report_sha256=sha(report))
        return info
    except BaseException as error:
        update_fit(identifier,status='failed_or_interrupted',error=repr(error))
        (directory/('failure-'+str(time.time_ns())+'.txt')).write_text(traceback.format_exc())
        raise


def read_prediction(work,identifier,info):
    path=work/'runs'/identifier/'validation-predictions.npz';assert sha(path)==info['predictions_sha256']
    with np.load(path) as archive:return {key:archive[key] for key in archive.files}


def repeat_decision(rich,control,retained,analysis):
    a,b=rich['validation'],control['validation'];move=a['parameters']['move'];base=b['parameters']['move']
    gains=dict(loss_reduction=1-a['joint_nll']/b['joint_nll'],movement_exact=move['exact_accuracy']-base['exact_accuracy'],
               movement_joint=move['joint_accuracy']-base['joint_accuracy'])
    context_triggers={}
    for name in ('direction_change','near_static_obstacle'):
        ar,br=analysis[name]['observations']['parameters']['move'],analysis[name]['control']['parameters']['move']
        context_triggers[name]=bool(ar['support']>=200 and ar['exact_accuracy']-br['exact_accuracy']>=.03)
    trigger=gains['loss_reduction']>=.02 or gains['movement_exact']>=.01 or gains['movement_joint']>=.01 or any(context_triggers.values())
    guards={}
    for name,reference in [('matched_control',b),('retained_M01',retained)]:
        target_changes=targeting_regressions(a,reference)
        guards[name]=dict(loss=a['joint_nll']<=reference['joint_nll']*1.01,
            movement_exact=move['exact_accuracy']>=reference['parameters']['move']['exact_accuracy']-.005,
            movement_joint=move['joint_accuracy']>=reference['parameters']['move']['joint_accuracy']-.005,
            macro_f1=a['macro_f1']>=reference['macro_f1']-.01,
            targeting=all(target_changes[family][metric]>=-.02 for family in ('attack','cast_0','cast_1') for metric in ('exact_accuracy','joint_accuracy')))
    return dict(exploratory_trigger=bool(trigger),gains=gains,context_triggers=context_triggers,regression_guards=guards,
                promising=bool(trigger and all(all(value.values()) for value in guards.values())),
                meaning='Exploratory repetition allocation only. Original success targets remain unchanged.')


def run():
    freeze_plan();assert (REPORTS/'recovery-audit.json').exists() and (REPORTS/'data-ready.json').exists()
    plan=json.loads((REPORTS/'plan.json').read_text());ready=json.loads((REPORTS/'data-ready.json').read_text())
    lock=json.loads((REPORTS/'execution-lock.json').read_text())
    for path,digest in lock['training_sources'].items():assert sha(path)==digest,path
    for name,digest in ready['files'].items():assert sha(WORK/name)==digest,name
    assert sha(MORE/'combined-train.npz')==plan['train_sha256'] and sha(OLD/'validation.npz')==plan['validation_sha256']
    train=combined_data()
    with np.load(OLD/'validation.npz') as archive:val={key:archive[key] for key in archive.files}
    saved=torch.load(MORE/'runs/M01/model.pt',weights_only=True,map_location='cpu');assert sha(MORE/'runs/M01/model.pt')==plan['baseline_checkpoint_sha256']
    normalizer=(saved['mean'],saved['std']);rt.setup(26)
    original=JointModel(len(saved['mean']),train['history'].shape[-1],len(rt.LABELS),saved['config']);original.load_state_dict(saved['state_dict'])
    val_data,_=rt.model_data(val,saved['config'],normalizer)
    original_prediction=rt.infer(original,val_data);original_score=rt.summarize(val,original_prediction)
    retained_info=json.loads((ROOT/'tools/action_predictor/experiments/v5/M01.json').read_text())
    for key in ('accuracy','macro_f1','joint_nll','strict_full_command_accuracy'):
        assert abs(original_score[key]-retained_info['validation'][key])<1e-6
    frozen(REPORTS/'retained-M01-reproduction.json',dict(checkpoint_sha256=sha(MORE/'runs/M01/model.pt'),
        validation_sha256=sha(OLD/'validation.npz'),measured_validation=original_score,reproduced=True))
    del original,val_data
    train_bank,val_bank=ObservationInputs('train',normalizer),ObservationInputs('validation',normalizer)
    aux={key:np.load(WORK/('validation-'+key+'.npy'),mmap_mode='r') for key in ('available','gaps','direction','near_obstacle','visible_change')}
    infos={}
    def one(identifier,seed,observations):
        config=plan['base_config']|dict(id=identifier,name='gru-personal-observation-history',observations=observations)
        info=fit(config,seed,train,val,train_bank,val_bank,normalizer);infos[identifier]=info;return info
    control=one('H01',26,False);rich=one('H02',26,True)
    rich_prediction=read_prediction(WORK,'H02',rich);control_prediction=read_prediction(WORK,'H01',control)
    analysis=compare(val,rich_prediction,control_prediction,aux)
    for arm,info in [('observations',rich),('control',control)]:
        point=analysis['overall'][arm];assert point['rows']==len(val['y'])
        assert abs(point['joint_accuracy']-info['validation']['strict_full_command_accuracy'])<1e-7
        assert abs(point['macro_f1']-info['validation']['macro_f1'])<1e-6
        assert sum(point['per_action_support'].values())==len(val['y'])
    frozen(REPORTS/'seed26-context-comparison.json',analysis)
    decision=repeat_decision(rich,control,original_score,analysis)
    frozen(REPORTS/'repeat-decision.json',decision)
    if decision['promising']:
        one('H03',27,False);one('H04',27,True);one('H05',28,False);one('H06',28,True)
    original_refs=ROOT/'tools/action_predictor/experiments/v4'
    references=json.loads((original_refs/'selection-lock.json').read_text())['references']
    fixed=json.loads((original_refs/'validation-evaluation.json').read_text())['models']
    evidence=[]
    for control_id,rich_id,retained_id in [('H01','H02','M01'),('H03','H04','M02'),('H05','H06','M03')]:
        if rich_id not in infos:continue
        r,c=infos[rich_id],infos[control_id]
        rp,cp=read_prediction(WORK,rich_id,r),read_prediction(WORK,control_id,c)
        analysis=compare(val,rp,cp,aux)
        frozen(REPORTS/(rich_id+'-context-comparison.json'),analysis)
        old_info=json.loads((ROOT/'tools/action_predictor/experiments/v5'/(retained_id+'.json')).read_text())
        old_prediction=read_prediction(MORE,retained_id,old_info)
        vs_retained=compare(val,rp,old_prediction,aux)
        frozen(REPORTS/(rich_id+'-versus-retained-contexts.json'),vs_retained)
        evidence.append(dict(seed=r['seed'],control=control_id,observations=rich_id,
            control_score=c['validation'],observation_score=r['validation'],retained_id=retained_id,
            original_target_gates=gates(r['validation'],references,fixed),
            loss_reduction_vs_control=1-r['validation']['joint_nll']/c['validation']['joint_nll'],
            loss_reduction_vs_retained=1-r['validation']['joint_nll']/old_info['validation']['joint_nll'],
            regressions_vs_control=targeting_regressions(r['validation'],c['validation']),
            regressions_vs_retained=targeting_regressions(r['validation'],old_info['validation']),
            overall_paired_intervals=analysis['overall']['paired_intervals'],
            retained_paired_intervals=vs_retained['overall']['paired_intervals']))
    strongest_loss=min([fixed[references['loss']]['joint_nll']]+[
        json.loads((ROOT/'tools/action_predictor/experiments/v5'/(identifier+'.json')).read_text())['validation']['joint_nll']
        for identifier in ('M01','M02','M03')]+[e['control_score']['joint_nll'] for e in evidence])
    historical_success=len(evidence)==3 and all(all(e['original_target_gates']['passed'].values()) for e in evidence)
    stronger_success=historical_success and all(e['observation_score']['joint_nll']<=.9*strongest_loss and
        all(change>=-.02 for family in ('attack','cast_0','cast_1') for metric,change in e['regressions_vs_control'][family].items()) and
        all(change>=-.02 for family in ('attack','cast_0','cast_1') for metric,change in e['regressions_vs_retained'][family].items()) for e in evidence)
    frozen(REPORTS/'validation-comparison.json',dict(pairs=evidence,substantive_fits=len(infos),
        budget=6,repeat_decision=decision,all_target_rows_retained=True,new_validation_games_opened=0,final_test_games_opened=0,
        selection=('Observation history meets the fixed development targets across three matched seeds; retain M01 as archived baseline. No final-test evaluation or deployed selection.' if stronger_success else
                   'Retain M01. The bounded observation-history experiment does not meet all fixed development targets consistently; no final-test selection.'),
        original_targets_met_in_three_pairs=historical_success,strongest_available_baseline_joint_nll=strongest_loss,
        stronger_baseline_loss_target=.9*strongest_loss,all_targets_including_stronger_controls_met=bool(stronger_success)))
    print('Bounded observation-history experiment complete; reserved games remain unopened.',flush=True)


if __name__=='__main__':
    log_command([sys.executable,'-m','tools.action_predictor.observation_train'],purpose='Bounded matched observation-history fits and measurements')
    run()
