"""V9 entity-input pilot: train classifier/GRU/movement, retain target baselines."""
import argparse,copy,json,sys,time,traceback
from pathlib import Path
import numpy as np
import torch
import torch.nn.functional as F
from . import reliable_train as rt
from .fundamental_audit import WORK,REPORTS,dependencies,arrays,metrics,log
from .priority_fit_v3 import BASE,VAL,read,load_base,context_directory
from .priority_residual_fit import head as priority_head
from .priority_head import flatten
from .action_priority_head import classifier_features
from .entity_cache import build,DIRECTORY
from .entity_set import EntityBank
from .entity_model import EntityMovementModel
from .more_replays import frozen,sha
from .observation_metrics import correctness,group_samples,interval
from .priority_dependencies_v3 import verify_label_schema
from .entity_set import encode_entities
from .rich_data import read_turns

NAMES=('entity_set.py','entity_cache.py','entity_model.py','entity_experiment.py','test_entity_set.py','fundamental_audit.py','action_priority_head.py')

def source_hashes():return {str(Path(__file__).with_name(n)):sha(Path(__file__).with_name(n)) for n in NAMES}

def validated_inputs():
    _,metadata=verify_label_schema();receipt=read(REPORTS/'D02-completion.json')
    for path,digest in receipt['files'].items():assert sha(path)==digest,'D02 evidence changed: '+path
    for path,digest in receipt['supplemental_inputs'].items():assert sha(path)==digest,'Diagnostic input changed: '+path
    original=read(REPORTS/'D02.json')
    for name,digest in original['train_predictions_sha256'].items():assert sha(WORK/name)==digest,'Diagnostic prediction changed'
    return dict(completion_sha256=sha(REPORTS/'D02-completion.json'),labels=metadata)

def priority_strata(raw,pred,training):
    code=rt.LABELS.index('priority');v,c=np.unique(training['priority'][training['y']==code],return_counts=True);counts=dict(zip(v,c))
    support=np.array([counts.get(x,0) for x in raw['priority']]);parameter,joint=correctness(raw,pred);out={}
    for name,condition in [('all',support>=0),('unseen',support==0),('rare_1_to_19',(support>0)&(support<20)),('seen_20_to_99',(support>=20)&(support<100)),('seen_100_plus',support>=100)]:
        mask=(raw['y']==code)&condition;n=int(mask.sum());error=np.abs(pred['priority'][mask].astype(np.int64)-raw['priority'][mask].astype(np.int64))
        out[name]=dict(support=n,exact=int(parameter[mask].sum()),joint=int(joint[mask].sum()),parameter_nll=float(pred['param_nll'][mask].mean()) if n else None,mean_absolute_error=float(error.mean()) if n else None,maximum_error=int(error.max()) if n else None)
    return out

def target_deltas(raw,new,old):
    a,j=correctness(raw,new);b,k=correctness(raw,old);out={}
    for name in ('attack','cast_0','cast_1','ward','move','blocked','priority'):
        mask=raw['y']==rt.LABELS.index(name)
        out[name]=dict(support=int(mask.sum()),parameter_change=float(a[mask].mean()-b[mask].mean()),joint_change=float(j[mask].mean()-k[mask].mean()))
    return out

@torch.no_grad()
def roundtrip(model,data,bank,features,contexts):
    # New encoding/serving path only. Legacy x/history and teacher were previously
    # proven; compare raw PRE entity extraction with packed cache and full routing.
    jobs=read(BASE.parent/'v7/jobs.json');model.eval();count=0;maximum=0.
    for job in [j for j in jobs if j['split']=='validation']:
        decisions=[d for t in read_turns(job['manifest'],job['record']) for d in t['decisions']]
        for local in sorted({0,len(decisions)//2,len(decisions)-1}):
            row=job['offset']+local;token=encode_entities(decisions[local]['observation']);cached,mask=bank.batch(np.array([row]))
            np.testing.assert_array_equal(token.astype(np.float32),cached[0,mask[0]].numpy())
            direct=torch.from_numpy(token.astype(np.float32))[None];full=torch.ones((1,len(token)),dtype=torch.bool)
            args=(data['x'][row:row+1],data['history'][row:row+1]);tail=(features[row:row+1],contexts[row:row+1])
            first=model(*args,cached,mask,*tail);second=model(*args,direct,full,*tail)
            for x,y in zip(first,second):maximum=max(maximum,float((x-y).abs().max()))
            family=first[0].argmax(-1);p=model.parameter_logits(first[1],first[2],data['grid'][row:row+1].float(),data['valid'][row:row+1],family,data['rules'][row:row+1]).softmax(-1)
            q=model.parameter_logits(second[1],second[2],data['grid'][row:row+1].float(),data['valid'][row:row+1],family,data['rules'][row:row+1]).softmax(-1)
            maximum=max(maximum,float((p-q).abs().max()));count+=1
    assert maximum<=1e-5
    return dict(targets=count,games=25,maximum_error=maximum,tolerance=1e-5,scope='Raw personal PRE entity tokens versus packed float16 cache, full new action and predicted-family coordinate path. No reserved rows.')

def ranked_plan():
    d=read(REPORTS/'D02.json')
    frozen(REPORTS/'ranked-plan.json',dict(D02_sha256=sha(REPORTS/'D02.json'),maximum_pilot_fits=8,conditional_additional_seed_fits=4,
        ranked=[dict(rank=1,ids=['E00','E01'],hypothesis='All personally visible entity details improve action/movement beyond matched zero-entity GRU control; both retrain classifier/representation and preserve ability targeting.',evidence='TRAIN direction changes32.95% vscontinuation93.97%; discarded observable entity types/buffs/cooldowns; nearest3 loses56%of sampled visible camps.'),
        dict(rank=2,hypothesis='Separate continuation/change destination distributions with predicted gate and recorded change supervision.',evidence='Change/continue shared-gradient cosine mean-0.5305, negative12/12; true future direction never input.'),
        dict(rank=3,ids=['T00','T01'],hypothesis='Fresh GRU versus small causal transformer with identical complete earlier observations/actions/gaps, rows, heads and optimizer budget. Start without rich entities; combine only after measured component evidence.'),
        dict(rank=4,hypothesis='Natural-frequency sampling vs legacy augmented+weighted loss; separately augmentation-weight correction. Preserve ward recall, not blanket suppression.'),
        dict(rank=5,hypothesis='Nonlinear conditional priority mixture using recovered state/history, full-support rare/unseen fallback. Current TRAIN exact25.16%,dev18.92% suggests inadequate fit; classifier is retrained in representation studies.')],
        selection='Each fit frozen before training; minimum original-development observed joint NLL, improvement0.0001,patience6,max35epochs; no posthoc peak accuracy selection. Preserve every epoch and negative result.',
        followup='After every substantive completed fit obtain FRESH GPT6.1Sol xhigh review with exact user question. No routine pre-fit review requirement under latest user direction. No further fit before addressing justified completed-fit findings.',
        immutable_reuse='Relevant data/feature/checkpoint/code hashes checked; do not repeat unchanged495-game replay reconstruction. Full causal/extraction checks only when inputs/assumptions change, as for the new entity cache.',
        original_goal='>=90%exact joint action+all recorded required parameters in EVERY adequately supported category, consistent across3seeds. All rows retained;43unknown shops remain strict failures; altar/teleport2examples uncertified. No finaltest/generalization claim from reused development.',
        reserved='All75newvalidation and75final-test games sealed. No oldexposedtest,downloads,matches,playing-bot changes or deployment.',deferred='Unfitted C01/C02 frozen-classifier-input pilot preserved but deferred by latest user request; zero fits/optimizer steps.'))

def load():
    ready=build();model,saved=load_base();priority=priority_head(model.priority)
    state=torch.load(BASE.parent/'v8/runs/P05/model.pt',weights_only=True,map_location='cpu');priority.load_state_dict(state['head_state'])
    normalizer=(saved['mean'],saved['std']);raw={};data={};baseline={};banks={};extras={};values={};features={};contexts={}
    for split,path in [('train',BASE/'combined-train.npz'),('validation',VAL)]:
        print('Load training inputs',split,flush=True);raw[split]=arrays(path);data[split],_=rt.model_data(raw[split],saved['config'],normalizer)
        baseline[split]=arrays(WORK/'D02-P05-train.npz' if split=='train' else BASE.parent/'v8/runs/P05/validation-predictions.npz')
        banks[split]=EntityBank(DIRECTORY,split,ready['dimension'])
        with np.load(BASE.parent/('v8/priority-'+split+'.npz')) as z:
            values[split]=torch.from_numpy(z['values']);extras[split]=torch.from_numpy((flatten(z['values'],z['history']).astype(np.float32)-state['extra_mean'].numpy())/state['extra_std'].numpy())
        features[split]=classifier_features(extras[split],values[split]);contexts[split]=torch.from_numpy(np.load(context_directory()/(split+'.npy')))
    return model,priority,saved,ready,raw,data,baseline,banks,extras,values,features,contexts

@torch.no_grad()
def infer(model,data,baseline,bank,extra,values,features,contexts):
    model.eval();result={key:value.copy() for key,value in baseline.items()};n=len(result['prediction'])
    for a in range(0,n,256):
        b=min(a+256,n);idx=np.arange(a,b);entities,mask=bank.batch(idx)
        logits,movement,teacher=model(data['x'][a:b],data['history'][a:b],entities,mask,features[a:b],contexts[a:b])
        lp=logits.log_softmax(-1);y=data['y'][a:b];prediction=lp.argmax(-1);grid=data['grid'][a:b].float();valid=data['valid'][a:b];rules=data['rules'][a:b]
        conditional=model.student.parameter_logits(movement,grid,valid,y,rules).log_softmax(-1)
        selected=(y==rt.LABELS.index('move'))|(y==rt.LABELS.index('blocked'));global_rows=a+selected.nonzero().flatten().numpy()
        result['coordinate'][global_rows]=conditional[selected].argmax(-1).numpy();result['top5'][global_rows]=conditional[selected].topk(5,-1).indices.numpy()
        result['param_nll'][global_rows]=-conditional[selected].gather(1,data['py'][a:b][selected,None])[:,0].numpy()
        result['prediction'][a:b]=prediction.numpy();result['type_nll'][a:b]=-lp.gather(1,y[:,None])[:,0].numpy()
        result['proposed_coordinate'][a:b]=model.parameter_logits(movement,teacher,grid,valid,prediction,rules).argmax(-1).numpy()
        result['nll'][a:b]=result['type_nll'][a:b]+result['param_nll'][a:b]
        ispriority=y==rt.LABELS.index('priority')
        if ispriority.any():
            # Preserve original 256-row GEMM shape before selecting supervised
            # rows; changing the GEMM to 1-2 rows changes frozen float32 outputs.
            p=model.priority(teacher,extra[a:b])[ispriority];p64=-model.priority.log_mass(p,data['priority'][a:b][ispriority].long(),values[a:b][ispriority]).numpy()
            rows=a+ispriority.nonzero().flatten().numpy();np.testing.assert_array_equal(p64.astype(result['param_nll'].dtype),result['param_nll'][rows])
            result['nll'][rows]=result['type_nll'][rows]+p64
    typed_spatial=(result['prediction']==data['y'].numpy())&(data['py'].numpy()>=0)
    np.testing.assert_array_equal(result['coordinate'][typed_spatial],result['proposed_coordinate'][typed_spatial])
    return result

def group_comparison(raw,new,old):
    groups=np.unique(raw['group']);rng=np.random.default_rng(20261106);draws=np.stack([np.bincount(rng.integers(0,len(groups),len(groups)),minlength=len(groups)) for _ in range(2000)])
    allrows=np.ones(len(raw['y']),bool);a=group_samples(raw,new,allrows,draws,groups);b=group_samples(raw,old,allrows,draws,groups)
    return dict(joint_accuracy_gain=interval(a['joint_accuracy']-b['joint_accuracy']),macro_f1_gain=interval(a['macro_f1']-b['macro_f1']),loss_reduction=interval(1-a['joint_nll']/b['joint_nll']),move_joint_gain=interval(a['move_joint']-b['move_joint']),scope='Five reused groups; pointwise conditional on checkpoint selection, not independent3seed/untouched confirmation')

def legality(raw,pred):
    out={}
    for name in ('move','blocked'):
        selected=pred['prediction']==rt.LABELS.index(name);idx=np.flatnonzero(selected);c=pred['proposed_coordinate'][idx];known=c<289
        out[name]=dict(predicted_support=len(idx),mask_rejections=int((~known).sum())+int((~raw['move_mask'][idx[known],c[known]]).sum()))
    out['legacy_partial']=rt.invalid_rate(raw,pred);out['full_engine_legality']=None;out['meaning']='Successful move-mask rejections separated from blocked-attempt forecasts; blocked mask rejection can be correct outcome prediction.'
    return out

def fit(identifier):
    ranked_plan();binding=dependencies();diagnostics=validated_inputs();rt.setup(26);loaded=load();teacher,priority,saved,ready,raw,data,baseline,banks,extra,values,features,contexts=loaded
    config=dict(id=identifier,seed=26,use_entities=identifier=='E01',dimension=ready['dimension'])
    if identifier=='E01':
        review=read(REPORTS/'E00-review.json');assert review['verdict']=='APPROVE' and review['fit_report_sha256']==sha(REPORTS/'E00.json')
    model=EntityMovementModel(teacher,priority,ready['dimension'],config['use_entities']);rt.setup(26)
    plan=dict(config=config,source_hashes=source_hashes(),dependencies=binding,diagnostic_bindings=diagnostics,entity_cache_sha256=sha(REPORTS/'entity-cache-ready.json'),ranked_plan_sha256=sha(REPORTS/'ranked-plan.json'),
        architecture='Warm M01 trainable current encoder/GRU/classifier and independent entity-conditioned action/movement residual fusions. Frozen separate M01 teacher for all nonmove/nonblocked target distributions, frozen P05 priority parameters. Both arms see41same causal priority channels; zero versus actual entity DETAILS is sole paired change. Both retain padding metadata, run same dense attention and sampler.',
        entities='119float16 token fields per own/known entity, all entity counts retained, no nearest-k or IDs. Buffs aggregate by type; known dead entities included; explicit missing-field indicators. No positional encoding across entity set.',
        loss='Original augmented rows,original class weights balance0.5/clamp20/mean1,weighted actionCE plus move/blocked coordinateCE SUM/FULL minibatch. Other argument losses constant frozen, included in validation observed jointNLL. No direction auxiliary or class-frequency correction yet.',
        checkpoint='Minimum full originaldev observed jointNLL improvement0.0001,max35epochs,patience6; epochzero not selected',training=rt.BENCH['training'],
        exploratory_seed_trigger='Original regression guards required; at least2pp overall strict gain OR5pp joint move gain versus P05 with paired95%gain lower>0. Also no overall joint regression, no macroF1 drop>1pp,no >2pp attack/cast0/cast1 joint drop,ward typeTP>=35 and joint>=7. Compute-allocation criterion only;90%everycategory/3seed originalgoal unchanged.',
        accounting='Every row retained;all43shop arguments unassessed strict failures. Newclassifier changes action distributions, real parameters routed by predictedfamily; true-family parameter metrics separately. No real match or bot changes;reserved75+75sealed.',budget='ONE fit per invocation;freshSolxhigh review after every completed fit. E01needsreviewedE00. No automatic repeats.')
    frozen(REPORTS/(identifier+'-plan.json'),plan);directory=WORK/'runs'/identifier
    assert not directory.exists(),'Existing run preserved; do not overwrite or silently restart an interrupted fit'
    directory.mkdir(parents=True)
    assert not (REPORTS/(identifier+'.json')).exists() and not (directory/'model.pt').exists(),'Never overwrite completed experiment'
    frozen(directory/'config.json',dict(config=config,plan_sha256=sha(REPORTS/(identifier+'-plan.json'))))
    for path,digest in source_hashes().items():
        snapshot=directory/(digest+'_'+Path(path).name)
        snapshot.write_bytes(Path(path).read_bytes())
    initial=infer(model,data['validation'],baseline['validation'],banks['validation'],extra['validation'],values['validation'],features['validation'],contexts['validation'])
    for key in ('prediction','coordinate','proposed_coordinate','top5','priority'):assert np.array_equal(initial[key],baseline['validation'][key]),'Warm initial decode mismatch:'+key
    frozen(directory/'epoch-zero.json',rt.summarize(raw['validation'],initial))
    counts=torch.bincount(data['train']['y'],minlength=len(rt.LABELS)).float();weights=(counts.max()/counts.clamp_min(1)).pow(.5).clamp_max(20);weights/=weights[data['train']['y']].mean()
    optimizer=torch.optim.AdamW([p for p in model.parameters() if p.requires_grad],lr=plan['training']['lr'],weight_decay=plan['training']['weight_decay']);best=float('inf');best_epoch=0;best_state=None;history=[];start=time.perf_counter()
    try:
        for epoch in range(1,plan['training']['max_epochs']+1):
            model.train();order=torch.randperm(len(data['train']['y']));total=0.;calls=0;epoch_start=time.perf_counter()
            for a in range(0,len(order),plan['training']['batch_size']):
                idx=order[a:a+plan['training']['batch_size']];entities,mask=banks['train'].batch(idx.numpy());y=data['train']['y'][idx]
                optimizer.zero_grad(set_to_none=True);logits,movement,_=model(data['train']['x'][idx],data['train']['history'][idx],entities,mask,features['train'][idx],contexts['train'][idx])
                loss=(weights[y]*F.cross_entropy(logits,y,reduction='none')).mean();selected=(y==rt.LABELS.index('move'))|(y==rt.LABELS.index('blocked'))
                if selected.any():
                    chosen=idx[selected];p=model.student.parameter_logits(movement[selected],data['train']['grid'][chosen].float(),data['train']['valid'][chosen],y[selected],data['train']['rules'][chosen])
                    loss+=F.cross_entropy(p,data['train']['py'][chosen],reduction='sum')/len(idx)
                loss.backward();torch.nn.utils.clip_grad_norm_([p for p in model.parameters() if p.requires_grad],plan['training']['gradient_clip']);optimizer.step();calls+=1;total+=float(loss.detach())*len(idx)
            prediction=infer(model,data['validation'],baseline['validation'],banks['validation'],extra['validation'],values['validation'],features['validation'],contexts['validation']);score=rt.summarize(raw['validation'],prediction)
            row=dict(epoch=epoch,train_objective=total/len(order),validation_nll=score['joint_nll'],macro_f1=score['macro_f1'],strict_joint=score['strict_full_command_accuracy'],move_exact=score['parameters']['move']['exact_accuracy'],move_joint=score['parameters']['move']['joint_accuracy'],seconds=time.perf_counter()-epoch_start,calls=calls);history.append(row)
            if score['joint_nll']<best-.0001:best=score['joint_nll'];best_epoch=epoch;best_state=copy.deepcopy(model.state_dict())
            torch.save(dict(state=model.state_dict(),optimizer=optimizer.state_dict(),rng=torch.get_rng_state(),epoch=epoch,history=history,plan_sha256=sha(REPORTS/(identifier+'-plan.json'))),directory/('epoch-'+str(epoch)+'.pt'));print(identifier,row,flush=True)
            if epoch-best_epoch>=plan['training']['patience']:break
        model.load_state_dict(best_state);valpred=infer(model,data['validation'],baseline['validation'],banks['validation'],extra['validation'],values['validation'],features['validation'],contexts['validation']);trainpred=infer(model,data['train'],baseline['train'],banks['train'],extra['train'],values['train'],features['train'],contexts['train'])
        torch.save(dict(state_dict=best_state,config=config,labels=rt.LABELS,mean=saved['mean'],std=saved['std'],plan_sha256=sha(REPORTS/(identifier+'-plan.json')),priority_mean=torch.load(BASE.parent/'v8/runs/P05/model.pt',weights_only=True)['extra_mean'],priority_std=torch.load(BASE.parent/'v8/runs/P05/model.pt',weights_only=True)['extra_std']),directory/'model.pt')
        np.savez_compressed(directory/'validation-predictions.npz',**valpred);np.savez_compressed(directory/'train-predictions.npz',**trainpred)
        direction=BASE.parent/'v7';m01=arrays(BASE/'runs/M01/validation-predictions.npz')
        report=dict(config=config,best_epoch=best_epoch,history=history,train=metrics(raw['train'],trainpred,np.load(direction/'train-direction.npy')),validation=metrics(raw['validation'],valpred,np.load(direction/'validation-direction.npy')),
            comparisons=dict(M01=group_comparison(raw['validation'],valpred,m01),P05=group_comparison(raw['validation'],valpred,baseline['validation'])),legality=legality(raw['validation'],valpred),
            checkpoint_sha256=sha(directory/'model.pt'),predictions_sha256=sha(directory/'validation-predictions.npz'),train_predictions_sha256=sha(directory/'train-predictions.npz'),plan_sha256=sha(REPORTS/(identifier+'-plan.json')),
            trainable_parameters=sum(p.numel() for p in model.parameters() if p.requires_grad),frozen_parameters=sum(p.numel() for p in model.parameters() if not p.requires_grad),seconds=time.perf_counter()-start,optimizer_calls=sum(h['calls'] for h in history),three_seed_confirmed=False,all_category_goal_met=False,reserved_opened=0)
        report['priority_strata']={split:priority_strata(raw[split],pred,raw['train']) for split,pred in [('train',trainpred),('validation',valpred)]}
        report['targeting_changes']={name:target_deltas(raw['validation'],valpred,pred) for name,pred in [('M01',m01),('P05',baseline['validation'])]}
        report['inference_roundtrip']=roundtrip(model,data['validation'],banks['validation'],features['validation'],contexts['validation'])
        frozen(REPORTS/(identifier+'.json'),report);print('Completed ONE substantive fit; obtain freshSolxhigh review before nextfit.',flush=True)
    except BaseException:
        (directory/('failure-'+str(time.time_ns())+'.txt')).write_text(traceback.format_exc());raise

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('identifier',choices=['E00','E01']);args=parser.parse_args();log([sys.executable,'-m','tools.action_predictor.entity_experiment',*sys.argv[1:]]);fit(args.identifier)
