"""Matched-data GRU/map-CNN fits; all scoring uses the original validation rows."""
from collections import defaultdict
import copy
import json

import numpy as np
import torch
import torch.nn.functional as F
from torch import nn

from . import reliable_train as rt
from .map_model import MapJointModel
from .reliable_model import priority_log_mass
from .spatial_data import WORK, REPORTS, MapInputs
from .more_replays import ROOT, WORK as MORE, REPORTS as MORE_REPORTS, frozen, sha
from .more_train import OLD, OLD_REPORTS, combined_data
from .development import gates
from .group_uncertainty import bootstrap, paired


def infer(model, data, maps, batch_size=256):
    result = defaultdict(list); n = len(data['y']); model.eval()
    with torch.no_grad():
        for a in range(0, n, batch_size):
            b = min(n, a+batch_size); indices = torch.arange(a, b)
            local, global_map = maps.batch(indices)
            logits, context, spatial = model(data['x'][a:b], data['history'][a:b], local, global_map)
            lp = logits.log_softmax(-1); y, py = data['y'][a:b], data['py'][a:b]
            prediction = lp.argmax(-1)
            grid, valid, rules = data['grid'][a:b].float(), data['valid'][a:b], data['rules'][a:b]
            conditional = model.parameter_logits(context,grid,valid,y,rules,spatial).log_softmax(-1)
            proposed = model.parameter_logits(context,grid,valid,prediction,rules,spatial).argmax(-1)
            priority = model.priority(context)
            type_nll = -lp.gather(1,y[:,None])[:,0]; param_nll = torch.zeros(b-a)
            selected = py >= 0
            param_nll[selected] = -conditional[selected].gather(1,py[selected,None])[:,0]
            ispriority = y == rt.LABELS.index('priority')
            priority_nll = -priority_log_mass(priority,data['priority'][a:b])
            param_nll[ispriority] = priority_nll[ispriority]
            for key,value in dict(prediction=prediction,nll=type_nll+param_nll,type_nll=type_nll,
                                  param_nll=param_nll,coordinate=conditional.argmax(-1),proposed_coordinate=proposed,
                                  top5=conditional.topk(5,-1).indices,priority=(priority[:,0]*100).round()).items():
                result[key].append(value.numpy())
    return {key:np.concatenate(value) for key,value in result.items()}


def fit(config,seed,train_raw,val_raw,train_maps,val_maps,normalizer):
    rt.setup(seed)
    identifier = config['id']; directory = WORK / 'runs' / identifier
    directory.mkdir(parents=True,exist_ok=True)
    if (directory/'model.pt').exists() or (REPORTS/(identifier+'.json')).exists():
        raise FileExistsError('Preserve existing spatial experiment/checkpoint')
    train,_ = rt.model_data(train_raw,config,normalizer)
    val,_ = rt.model_data(val_raw,config,normalizer)
    model = MapJointModel(train['x'].shape[1],train['history'].shape[-1],len(rt.LABELS),config)
    settings = rt.BENCH['training']
    optimizer = torch.optim.AdamW(model.parameters(),lr=settings['lr'],weight_decay=settings['weight_decay'])
    counts = torch.bincount(train['y'],minlength=len(rt.LABELS)).float()
    weights = (counts.max()/counts.clamp_min(1)).pow(config['balance']).clamp_max(20)
    weights /= weights[train['y']].mean()
    frozen(directory/'config.json',dict(config=config,seed=seed,training_settings=settings,
        train_sha256=sha(MORE/'combined-train.npz'),validation_sha256=sha(OLD/'validation.npz'),
        maps_sha256=sha(WORK/'maps.npz'),plan_sha256=sha(REPORTS/'plan.json'),
        benchmark_sha256=sha(REPORTS/'benchmark.json')))
    best=float('inf');best_epoch=0;best_state=None;log=[]
    for epoch in range(1,settings['max_epochs']+1):
        model.train();order=torch.randperm(len(train['y']));total=0.
        for a in range(0,len(order),settings['batch_size']):
            idx=order[a:a+settings['batch_size']];y=train['y'][idx];py=train['py'][idx]
            local,global_map=train_maps.batch(idx)
            optimizer.zero_grad(set_to_none=True)
            logits,context,spatial=model(train['x'][idx],train['history'][idx],local,global_map)
            loss=(weights[y]*F.cross_entropy(logits,y,reduction='none')).mean()
            selected=py>=0
            if selected.any():
                parameter_logits=model.parameter_logits(context[selected],train['grid'][idx[selected]].float(),
                    train['valid'][idx[selected]],y[selected],train['rules'][idx[selected]],spatial[selected])
                loss+=F.cross_entropy(parameter_logits,py[selected],reduction='sum')/len(idx)
            priority=y==rt.LABELS.index('priority')
            if priority.any():
                loss-=priority_log_mass(model.priority(context[priority]),train['priority'][idx[priority]]).sum()/len(idx)
            loss.backward();nn.utils.clip_grad_norm_(model.parameters(),settings['gradient_clip']);optimizer.step()
            total+=float(loss.detach())*len(idx)
        prediction=infer(model,val,val_maps);score=rt.summarize(val_raw,prediction)
        row=dict(epoch=epoch,train_objective=total/len(train['y']),validation_nll=score['joint_nll'],
                 macro_f1=score['macro_f1'],movement_exact=score['parameters']['move']['exact_accuracy'],
                 movement_joint=score['parameters']['move']['joint_accuracy'])
        log.append(row)
        with (directory/'epochs.jsonl').open('a') as stream:
            stream.write(json.dumps(row)+'\n')
        print(identifier,row,flush=True)
        if score['joint_nll']<best-.0001:
            best=score['joint_nll'];best_epoch=epoch;best_state=copy.deepcopy(model.state_dict())
            torch.save(dict(state_dict=best_state,epoch=epoch,validation_nll=best),directory/'best-state.pt')
        elif epoch-best_epoch>=settings['patience']:
            break
    model.load_state_dict(best_state)
    prediction=infer(model,val,val_maps);score=rt.summarize(val_raw,prediction)
    torch.save(dict(state_dict=best_state,config=config,seed=seed,mean=normalizer[0],std=normalizer[1],
                    labels=rt.LABELS,architecture='public-map-cnn-gru-v1',
                    benchmark_sha256=sha(REPORTS/'benchmark.json')),directory/'model.pt')
    np.savez_compressed(directory/'validation-predictions.npz',**prediction)
    info=dict(config=config,seed=seed,best_epoch=best_epoch,history=log,validation=score,
              parameters=sum(p.numel() for p in model.parameters()),
              checkpoint_sha256=sha(directory/'model.pt'),predictions_sha256=sha(directory/'validation-predictions.npz'))
    frozen(REPORTS/(identifier+'.json'),info)
    return info


def load_prediction(work,identifier,info):
    path=work/'runs'/identifier/'validation-predictions.npz'
    assert sha(path)==info['predictions_sha256']
    with np.load(path,allow_pickle=False) as archive:
        return {key:archive[key] for key in archive.files}


def run_experiment():
    plan=json.loads((REPORTS/'plan.json').read_text())
    assert sha(ROOT/'tools/action_predictor/map_model.py')==plan['model_source_sha256']
    ready=json.loads((REPORTS/'data-ready.json').read_text())
    assert sha(WORK/'maps.npz')==ready['maps_sha256']
    assert sha(MORE/'combined-train.npz')==plan['train_sha256']
    assert sha(OLD/'validation.npz')==plan['validation_sha256']
    assert sha(REPORTS/'benchmark.json')==plan['benchmark_sha256']
    baselines={name:json.loads((MORE_REPORTS/(name+'.json')).read_text()) for name in ('M01','M02','M03')}
    for name,info in baselines.items():
        assert sha(MORE/'runs'/name/'model.pt')==plan['baseline_checkpoints'][name]==info['checkpoint_sha256']
    train=combined_data()
    with np.load(OLD/'validation.npz',allow_pickle=False) as archive:
        val={key:archive[key] for key in archive.files}
    with np.load(WORK/'maps.npz',allow_pickle=False) as archive:
        maps={key:archive[key] for key in archive.files}
    train_maps,val_maps=MapInputs(maps,'train'),MapInputs(maps,'validation')
    saved=torch.load(MORE/'runs/M01/model.pt',weights_only=True,map_location='cpu')
    normalizer=(saved['mean'],saved['std'])
    for identifier in ('M02','M03'):
        other=torch.load(MORE/'runs'/identifier/'model.pt',weights_only=True,map_location='cpu')
        assert torch.equal(other['mean'],normalizer[0]) and torch.equal(other['std'],normalizer[1])
    references=json.loads((OLD_REPORTS/'selection-lock.json').read_text())['references']
    fixed=json.loads((OLD_REPORTS/'validation-evaluation.json').read_text())['models']
    infos={}
    def run_one(identifier,seed,zero_map):
        config=plan['base_config']|dict(id=identifier,name='gru-public-map-cnn',zero_map=zero_map)
        path=REPORTS/(identifier+'.json')
        if path.exists():
            info=json.loads(path.read_text())
            assert info['config']==config and info['seed']==seed
            assert sha(WORK/'runs'/identifier/'model.pt')==info['checkpoint_sha256']
        else:
            info=fit(config,seed,train,val,train_maps,val_maps,normalizer)
        infos[identifier]=info
        return info['validation']
    spatial=run_one('S01',26,False)
    control=run_one('S02',26,True)
    original=baselines['M01']['validation']
    target_gates=gates(spatial,references,fixed)
    regressions={family:original['parameters'][family]['exact_accuracy']-spatial['parameters'][family]['exact_accuracy']
                 for family in ('attack','cast_0','cast_1')}
    conditions=dict(
        movement_above_current=spatial['parameters']['move']['exact_accuracy']>original['parameters']['move']['exact_accuracy'],
        movement_above_capacity_control=spatial['parameters']['move']['exact_accuracy']>control['parameters']['move']['exact_accuracy'],
        movement_joint_no_regression=spatial['parameters']['move']['joint_accuracy']>=original['parameters']['move']['joint_accuracy'],
        joint_loss_guard=spatial['joint_nll']<=original['joint_nll']*1.02,
        macro_f1_guard=spatial['macro_f1']>=original['macro_f1']-.02,
        targeting_guard=target_gates['passed']['targeting'] and all(value<=.02 for value in regressions.values()))
    promising=all(conditions.values()) or all(target_gates['passed'].values())
    frozen(REPORTS/'repeat-decision.json',dict(conditions=conditions,promising=promising,
        target_gates=target_gates,plan_sha256=sha(REPORTS/'plan.json'),additional_fits=2 if promising else 0))
    if promising:
        run_one('S03',27,False);run_one('S04',28,False)
    evidence=[]
    for identifier,old_id in [('S01','M01'),('S02','M01'),('S03','M02'),('S04','M03')]:
        if identifier not in infos:continue
        info=infos[identifier];prediction=load_prediction(WORK,identifier,info)
        old_prediction=load_prediction(MORE,old_id,baselines[old_id])
        intervals,_,_=bootstrap(val,prediction)
        evidence.append(dict(id=identifier,seed=info['seed'],zero_map=info['config']['zero_map'],
            validation=info['validation'],baseline_id=old_id,baseline_validation=baselines[old_id]['validation'],
            group_intervals=intervals,paired_changes=paired(val,prediction,old_prediction),
            original_target_gates=gates(info['validation'],references,fixed),checkpoint_sha256=info['checkpoint_sha256']))
    map_runs=[item for item in evidence if not item['zero_map']]
    consistent=len(map_runs)==3 and all(
        r['validation']['parameters']['move']['exact_accuracy']>r['baseline_validation']['parameters']['move']['exact_accuracy']
        and r['validation']['parameters']['move']['joint_accuracy']>=r['baseline_validation']['parameters']['move']['joint_accuracy']
        and r['validation']['joint_nll']<=1.02*r['baseline_validation']['joint_nll']
        and r['validation']['macro_f1']>=r['baseline_validation']['macro_f1']-.02
        and r['original_target_gates']['passed']['targeting']
        and all(r['baseline_validation']['parameters'][family]['exact_accuracy']-r['validation']['parameters'][family]['exact_accuracy']<=.02
                for family in ('attack','cast_0','cast_1')) for r in map_runs)
    capacity=paired(val,load_prediction(WORK,'S01',infos['S01']),load_prediction(WORK,'S02',infos['S02']))
    frozen(REPORTS/'validation-comparison.json',dict(runs=evidence,spatial_vs_zero_map=capacity,
        repeated_map_seeds=len(map_runs),consistent_movement_improvement=consistent,
        all_targets_met_consistently=len(map_runs)==3 and all(all(r['original_target_gates']['passed'].values()) for r in map_runs),
        selection='S01 is a promising validation candidate' if consistent else 'Keep current M01 baseline; no consistent spatial improvement established',
        new_validation_games_opened=0,final_test_games_opened=0,old_test_games_scored=0,
        plan_sha256=sha(REPORTS/'plan.json')))
    print('Spatial experiment complete; final test remains sealed.',flush=True)


if __name__=='__main__':
    run_experiment()
