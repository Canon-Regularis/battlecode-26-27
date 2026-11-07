"""Run the frozen V4 benchmark without touching the test split during selection."""
import argparse
from collections import defaultdict
import copy
import json
from pathlib import Path
import random

import numpy as np
import torch
from torch import nn
import torch.nn.functional as F

from .audit import immutable_json
from .benchmark import REPORTS, WORK
from .data import digest
from .reliable_model import JointModel, priority_log_mass
from .targets import OFFSETS
from .train import metrics


def setup(seed):
    random.seed(seed);np.random.seed(seed);torch.manual_seed(seed)
    torch.set_num_threads(4);torch.use_deterministic_algorithms(True)


def load_data(split):
    path=WORK/f'{split}.npz'
    receipt=json.loads((WORK/f'{split}-data.json').read_text())
    if digest(path)!=receipt['sha256']:
        raise ValueError('Frozen prepared data changed')
    with np.load(path,allow_pickle=False) as archive:
        return {k:archive[k] for k in archive.files}


def model_data(raw,config,normalizer=None):
    n=raw['x'].shape[1] if config['rich'] else 200
    x=torch.from_numpy(raw['x'][:,:n]).float()
    if normalizer is None:
        normalizer=(x.mean(0),x.std(0).clamp_min(.01))
    mean,std=normalizer
    history=torch.from_numpy(raw['history']).float().clone()
    # Utility-event coordinates (0,0) are unset transport fields, not prior locations.
    spatial_history=torch.zeros(history.shape[:2],dtype=torch.bool)
    for name in ('move','blocked','attack','cast_0','cast_1','ward','submit','altar','teleport','end'):
        spatial_history|=history[:,:,LABELS.index(name)]>0
    history[:,:,len(LABELS)+1:len(LABELS)+3]*=spatial_history[:,:,None]
    return dict(x=(x-mean)/std,history=history,
                grid=torch.from_numpy(raw['grid']),valid=torch.from_numpy(raw['valid']),
                y=torch.from_numpy(raw['y']).long(),py=torch.from_numpy(raw['py']).long(),
                priority=torch.from_numpy(raw['priority']).float(),
                rules=torch.from_numpy(np.column_stack((raw['attack_range'],raw['ability_range'],raw['ability_mask']))).float()),normalizer


def infer(model,data,batch_size=256):
    n=len(data['y']);result=defaultdict(list)
    model.eval()
    with torch.no_grad():
        for a in range(0,n,batch_size):
            b=min(n,a+batch_size);x=data['x'][a:b];h=data['history'][a:b]
            logits,context=model(x,h);lp=logits.log_softmax(-1);y=data['y'][a:b];py=data['py'][a:b]
            prediction=lp.argmax(-1)
            grid=data['grid'][a:b].float();valid=data['valid'][a:b]
            conditional=model.parameter_logits(context,grid,valid,y,data['rules'][a:b]).log_softmax(-1)
            proposed=model.parameter_logits(context,grid,valid,prediction,data['rules'][a:b]).argmax(-1)
            priority=model.priority(context)
            type_nll=-lp.gather(1,y[:,None])[:,0]
            param_nll=torch.zeros(b-a)
            spatial=py>=0
            param_nll[spatial]=-conditional[spatial].gather(1,py[spatial,None])[:,0]
            ispriority=y==LABELS.index('priority')
            priority_nll=-priority_log_mass(priority,data['priority'][a:b])
            param_nll[ispriority]=priority_nll[ispriority]
            for key,value in dict(prediction=prediction,nll=type_nll+param_nll,type_nll=type_nll,
                                  param_nll=param_nll,coordinate=conditional.argmax(-1),proposed_coordinate=proposed,
                                  top5=conditional.topk(5,-1).indices,priority=(priority[:,0]*100).round()).items():
                result[key].append(value.numpy())
    return {k:np.concatenate(v) for k,v in result.items()}


def summarize(raw,pred):
    y=raw['y'];p=pred['prediction'];py=raw['py'];classes=len(LABELS)
    matrix=np.bincount(y*classes+p,minlength=classes**2).reshape(classes,classes)
    report=metrics(torch.from_numpy(matrix))
    # Keep the named action set fixed even when a resampled group lacks a rare class.
    report['macro_f1']=float(np.mean([c['f1'] for c in report['per_class'][1:]]))
    type_correct=y==p
    param_correct=np.ones(len(y),dtype=bool)
    spatial=py>=0
    param_correct[spatial]=(pred['coordinate'][spatial]==py[spatial])&(py[spatial]<289)
    priority=y==LABELS.index('priority')
    param_correct[priority]=pred['priority'][priority]==raw['priority'][priority]
    observable_joint=type_correct&param_correct
    full_joint=observable_joint&(y!=LABELS.index('shop'))
    report.update(joint_nll=float(pred['nll'].mean()),joint_observable_accuracy=float(observable_joint.mean()),
                  strict_full_command_accuracy=float(full_joint.mean()),strict_unassessed_shop=int((y==LABELS.index('shop')).sum()))
    parameterized=spatial|priority|(y==LABELS.index('shop'))
    report['parameterized_support']=int(parameterized.sum())
    report['joint_parameterized_accuracy']=float(full_joint[parameterized].mean()) if parameterized.any() else None
    families={}
    for name in ('move','blocked','attack','cast_0','cast_1','ward','submit','altar','teleport','priority','shop'):
        mask=y==LABELS.index(name);support=int(mask.sum())
        row=dict(support=support,joint_accuracy=float(full_joint[mask].mean()) if support else None)
        if name not in ('priority','shop') and support:
            known=mask&(py<289)&(py>=0)
            top=pred['top5'];correct=(top==py[:,None])&(py[:,None]<289)
            row.update(exact_accuracy=float(param_correct[mask].mean()),
                       top3_accuracy=float(correct[mask,:3].any(-1).mean()),
                       top5_accuracy=float(correct[mask].any(-1).mean()),
                       joint_top3_accuracy=float((correct[mask,:3].any(-1)&type_correct[mask]).mean()),
                       unassessable_coordinates=int((mask&~known).sum()))
            decoded=known&(pred['coordinate']<289)
            row['destination_error_coverage']=int(decoded.sum())
            row['mean_chebyshev_error']=float(np.abs(OFFSETS[pred['coordinate'][decoded]]-OFFSETS[py[decoded]]).max(-1).mean()) if decoded.any() else None
            # Error includes unknown predictions at a fixed 16-cell penalty, declared explicitly.
            error=np.full(support,16.)
            idx=np.flatnonzero(mask);ok=(py[idx]<289)&(py[idx]>=0)&(pred['coordinate'][idx]<289)
            error[ok]=np.abs(OFFSETS[pred['coordinate'][idx[ok]]]-OFFSETS[py[idx[ok]]]).max(-1)
            row['penalized_mean_chebyshev_error']=float(error.mean())
        families[name]=row
    report['parameters']=families
    report['observable_invalid_commands']=invalid_rate(raw,pred)
    return report


def invalid_rate(raw,pred):
    p=pred['prediction'];c=pred['proposed_coordinate'];n=len(p)
    assessed=np.zeros(n,bool);invalid=np.zeros(n,bool)
    for i,name in enumerate(LABELS):
        selected=p==i
        if name in ('move','blocked'):
            assessed|=selected
            idx=np.flatnonzero(selected);ok=c[idx]<289
            invalid[idx[~ok]]=True
            invalid[idx[ok]]=~raw['move_mask'][idx[ok],c[idx[ok]]]
        elif name in ('attack','cast_0','cast_1','ward','submit','recall','shop'):
            assessed|=selected
            alive=raw['hp_alive'];channel=raw['channel']==0;flags=raw['flags'];restr=raw['restrictions']
            if name=='attack':
                ok=alive&channel&((flags&2)!=0)&((restr&2)==0)
            elif name.startswith('cast_'):
                slot=int(name[-1]);ok=alive&channel&raw['ability_ready'][:,slot]&((flags&1024)!=0)&((restr&4)==0)
            elif name=='ward':
                ok=alive&channel&(raw['ward_charges']>0)
            elif name=='submit':
                ok=alive&channel&(raw['gems']>0)
            elif name=='recall':
                ok=alive&channel
            else:
                ok=raw['shop']
            invalid|=selected&~ok
    return dict(assessed=int(assessed.sum()),invalid=int((invalid&assessed).sum()),
                rate=float(invalid[assessed].mean()) if assessed.any() else None,
                all_command_fraction=float((invalid&assessed).mean()),
                full_engine_illegal_action_rate=None,
                meaning='Partial observable violations: exact personal movement mask; other families readiness/resource checks only. Does not certify complete legality.')


def fit(config,seed,train_raw,val_raw,*,train_source=None,validation_source=None):
    setup(seed)
    identifier=config['id'];directory=WORK/'runs'/identifier
    directory.mkdir(parents=True,exist_ok=True)
    if (directory/'model.pt').exists() or (REPORTS/f'{identifier}.json').exists():
        raise FileExistsError('Experiment/checkpoint already exists')
    train,normalizer=model_data(train_raw,config)
    val,_=model_data(val_raw,config,normalizer)
    model=JointModel(train['x'].shape[1],train['history'].shape[-1],len(LABELS),config)
    settings=BENCH['training']
    optimizer=torch.optim.AdamW(model.parameters(),lr=settings['lr'],weight_decay=settings['weight_decay'])
    counts=torch.bincount(train['y'],minlength=len(LABELS)).float()
    weights=(counts.max()/counts.clamp_min(1)).pow(config['balance']).clamp_max(20)
    weights/=weights[train['y']].mean()
    best=float('inf');best_epoch=0;best_state=None;log=[]
    immutable_json(directory/'config.json',dict(config=config,seed=seed,benchmark_sha256=digest(REPORTS/'benchmark.json'),
                   train_sha256=digest(train_source or WORK/'train.npz'),
                   validation_sha256=digest(validation_source or WORK/'validation.npz')))
    for epoch in range(1,settings['max_epochs']+1):
        model.train();order=torch.randperm(len(train['y']));total=0.
        for a in range(0,len(order),settings['batch_size']):
            idx=order[a:a+settings['batch_size']];y=train['y'][idx];py=train['py'][idx]
            optimizer.zero_grad(set_to_none=True)
            logits,context=model(train['x'][idx],train['history'][idx])
            action_loss=F.cross_entropy(logits,y,reduction='none')
            if config.get('focal'):
                action_loss=action_loss*(1-torch.exp(-action_loss)).pow(config['focal'])
            loss=(weights[y]*action_loss).mean()
            selected=py>=0
            if selected.any():
                parameter_logits=model.parameter_logits(context[selected],train['grid'][idx[selected]].float(),train['valid'][idx[selected]],y[selected],train['rules'][idx[selected]])
                loss+=F.cross_entropy(parameter_logits,py[selected],reduction='sum')/len(idx)
            priority=y==LABELS.index('priority')
            if priority.any():
                loss-=priority_log_mass(model.priority(context[priority]),train['priority'][idx[priority]]).sum()/len(idx)
            loss.backward();nn.utils.clip_grad_norm_(model.parameters(),settings['gradient_clip']);optimizer.step()
            total+=float(loss.detach())*len(idx)
        predictions=infer(model,val);score=summarize(val_raw,predictions)
        log.append(dict(epoch=epoch,train_objective=total/len(train['y']),validation_nll=score['joint_nll'],
                        macro_f1=score['macro_f1'],movement_exact=score['parameters']['move']['exact_accuracy']))
        if epoch%5==0 or epoch==1:
            print(identifier,log[-1],flush=True)
        if score['joint_nll']<best-.0001:
            best=score['joint_nll'];best_epoch=epoch;best_state=copy.deepcopy(model.state_dict())
        elif epoch-best_epoch>=settings['patience']:
            break
    model.load_state_dict(best_state)
    predictions=infer(model,val);report=summarize(val_raw,predictions)
    torch.save(dict(state_dict=best_state,config=config,seed=seed,mean=normalizer[0],std=normalizer[1],labels=LABELS,
                    benchmark_sha256=digest(REPORTS/'benchmark.json')),directory/'model.pt')
    np.savez_compressed(directory/'validation-predictions.npz',**predictions)
    info=dict(config=config,seed=seed,best_epoch=best_epoch,history=log,parameters=sum(p.numel() for p in model.parameters()),
              validation=report,checkpoint_sha256=digest(directory/'model.pt'),predictions_sha256=digest(directory/'validation-predictions.npz'))
    immutable_json(REPORTS/f'{identifier}.json',info)
    print(identifier,'complete',dict(macro_f1=report['macro_f1'],joint_nll=report['joint_nll'],move=report['parameters']['move']['exact_accuracy']),flush=True)
    return info


BENCH=json.loads((REPORTS/'benchmark.json').read_text()) if (REPORTS/'benchmark.json').exists() else {}
LABELS=json.loads(Path('.cambc/action-predictor/data/dataset.json').read_text())['labels']


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('experiment');p.add_argument('--seed',type=int,default=26)
    args=p.parse_args();config=next(c for c in BENCH['experiments'] if c['id']==args.experiment)
    fit(config,args.seed,load_data('train'),load_data('validation'))
