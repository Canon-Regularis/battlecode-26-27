"""Bounded G00/G01 movement mixture comparison; fixed retained classifier."""
import argparse,copy,json,sys,time,traceback
from pathlib import Path
import numpy as np
import torch
import torch.nn.functional as F
from . import reliable_train as rt
from .fundamental_audit import WORK,REPORTS,dependencies,arrays,metrics,log
from .priority_fit_v3 import BASE,VAL,read,load_base,context_directory
from .entity_experiment import validated_inputs,group_comparison,legality
from .movement_mixture import MovementMixture,previous_direction
from .targets import OFFSETS
from .more_replays import frozen,sha

NAMES=('movement_mixture.py','movement_study.py','test_movement_mixture.py')
AUXILIARY_WEIGHT=.05

def sources():return {str(Path(__file__).with_name(n)):sha(Path(__file__).with_name(n)) for n in NAMES}

def load():
    binding=dependencies();diagnostics=validated_inputs()
    for path,digest in read(REPORTS/'E01-plan.json')['source_hashes'].items():
        assert sha(path)==digest,'Changed imported V9 dependency: '+path
        binding[path]=digest
    rt.setup(26);teacher,saved=load_base();raw={};data={};baseline={};contexts={};direction={}
    for split,path in [('train',BASE/'combined-train.npz'),('validation',VAL)]:
        print('Load movement inputs',split,flush=True);raw[split]=arrays(path);data[split],_=rt.model_data(raw[split],saved['config'],(saved['mean'],saved['std']))
        baseline[split]=arrays(WORK/'D02-P05-train.npz' if split=='train' else BASE.parent/'v8/runs/P05/validation-predictions.npz')
        contexts[split]=torch.from_numpy(np.load(context_directory()/(split+'.npy')))
        direction[split]=np.load(BASE.parent/'v7'/(split+'-direction.npy'))
    return teacher,saved,raw,data,baseline,contexts,direction,binding,diagnostics

def alignment(raw,data,direction):
    output={}
    for split in raw:
        grid=data[split]['grid'];known=[];matches=[]
        for a in range(0,len(grid),8192):
            offset,available,_=previous_direction(grid[a:a+8192]);known.append(available.numpy());label=data[split]['py'][a:a+8192];inside=(label>=0)&(label<289)
            actual=torch.as_tensor(OFFSETS)[label.clamp(0,288)];same=(actual.sign()==offset.sign()).all(-1);matches.append(same.numpy())
        known=np.concatenate(known);same=np.concatenate(matches);move=raw[split]['y']==rt.LABELS.index('move');nonzero=np.isin(direction[split],[2,3]);assessed=move&known&nonzero
        assert np.array_equal(same[assessed],direction[split][assessed]==2),'Causal last-move partition does not match frozen direction evidence'
        output[split]=dict(rows=len(known),move_rows=int(move.sum()),move_with_known_last_offset=int((move&known).sum()),move_without_known_last_offset=int((move&~known).sum()),supervised_gate_rows=int(assessed.sum()),direction_agreements=int(assessed.sum()),blocked_rows=int((raw[split]['y']==rt.LABELS.index('blocked')).sum()),scope='Previous successful offset comes only from existing causal grid channel18; missing/outside-window earlier offsets explicitly unavailable. Direction target checked for supervised rows only; all rows retained.')
    return output

@torch.no_grad()
def infer(model,data,baseline,contexts):
    model.eval();result={k:v.copy() for k,v in baseline.items()};gates=np.full(len(result['prediction']),np.nan,np.float32);available=np.zeros(len(gates),bool)
    for a in range(0,len(gates),256):
        b=min(a+256,len(gates));y=data['y'][a:b];grid=data['grid'][a:b].float();valid=data['valid'][a:b];rules=data['rules'][a:b]
        context=model.encode(data['x'][a:b],data['history'][a:b],contexts[a:b]);lp,gate,known=model.parameter_log_probs(context,grid,valid,y,rules)
        selected=(y==8)|(y==3);rows=a+selected.nonzero().flatten().numpy()
        result['coordinate'][rows]=lp[selected].argmax(-1).numpy();result['top5'][rows]=lp[selected].topk(5,-1).indices.numpy()
        result['param_nll'][rows]=-lp[selected].gather(1,data['py'][a:b][selected,None])[:,0].numpy();result['nll'][rows]=result['type_nll'][rows]+result['param_nll'][rows]
        family=torch.from_numpy(result['prediction'][a:b]);proposed,_,_=model.parameter_log_probs(context,grid,valid,family,rules);chosen=(family==8)|(family==3);idx=a+chosen.nonzero().flatten().numpy();result['proposed_coordinate'][idx]=proposed[chosen].argmax(-1).numpy()
        gates[a:b]=gate.sigmoid().numpy();available[a:b]=known.numpy()
    typed=(result['prediction']==data['y'].numpy())&(data['py'].numpy()>=0)
    np.testing.assert_array_equal(result['coordinate'][typed],result['proposed_coordinate'][typed])
    for key in ('prediction','priority','type_nll'):np.testing.assert_array_equal(result[key],baseline[key])
    return result,dict(continuation_probability=gates,available=available)

def gate_metrics(raw,gate,direction):
    eligible=(raw['y']==8)&gate['available']&np.isin(direction,[2,3]);target=direction==2;forecast=gate['continuation_probability']>=.5
    matrix=np.bincount(target[eligible].astype(int)*2+forecast[eligible].astype(int),minlength=4).reshape(2,2)
    return dict(supervised_support=int(eligible.sum()),confusion_change_continue=matrix.tolist(),accuracy=float((target[eligible]==forecast[eligible]).mean()) if eligible.any() else None,missing_move_history=int(((raw['y']==8)&~gate['available']).sum()),scope='True move family conditional gate evaluation on every eligible recorded move; predicted gate from causal inputs, no oracle routing.')

def fit(identifier):
    teacher,saved,raw,data,baseline,contexts,direction,binding,diagnostics=load()
    review=read(REPORTS/'E01-review.json');assert review['verdict']=='APPROVE' and review['fit_report_sha256']==sha(REPORTS/'E01.json')
    if identifier=='G01':
        r=read(REPORTS/'G00-review.json');assert r['verdict']=='APPROVE' and r['fit_report_sha256']==sha(REPORTS/'G00.json')
    agreement=alignment(raw,data,direction);model=MovementMixture(teacher,identifier=='G01');rt.setup(26)
    plan=dict(id=identifier,seed=26,specialized=identifier=='G01',sources=sources(),legacy_dependencies=binding,diagnostics=diagnostics,completed_entity_review_sha256=sha(REPORTS/'E01-review.json'),alignment=agreement,
        hypothesis='Separate continuation/change GRU destination experts plus learned causal gate and recorded-only auxiliary supervision improve net exact movement without losing continuation. G00 is otherwise matched unrestricted two-expert control. This tests an output/support/supervision package, not isolated auxiliary attribution.',
        input='Same frozen M01 current253/action-history16/candidate-grid20 inputs; last successful offset recovered from PRE grid18, availability explicit. Teacher context and all classifier/ability/priority outputs preserved P05. No actual next direction or label passed to forward. No new extraction, entities or geometry redesign.',
        control='Both arms copy two M01 GRU/encoder/coordinate models, same nonlinear gate and teacher-prior offset. Initial experts identical; zero residual gate and normalized partitions reconstruct M01 movement. Same nominal parameters, initialization, all433071rows, batches, optimizer and selection.',
        blocked='All blocked attempts retained; both arms use unrestricted mixture for blocked outcomes. No successful-move mask asserted for blocked. Startup/unavailable prior-offset rows use unrestricted mixture and no gate auxiliary; no rows dropped.',
        loss=dict(primary='Movement/blocked NLL SUM divided by FULL original minibatch256. Original frozen losses constant, included in whole-development observed joint NLL selection. All original augmented rows shuffled, no class/sampling correction.',auxiliary='Only G01: BCEWithLogits predicting continuation on recorded move direction2/3 with causal prior available; SUM/FULL minibatch. Recorded label used only by training loss.',auxiliary_weight=AUXILIARY_WEIGHT),
        training=rt.BENCH['training'],checkpoint='Original whole-development observed jointNLL; improvement0.0001,max35epochs,patience6; epochzero unselectable; all epochs preserved.',
        prospective_guards='Against BOTH matched control and P05: no net strict-command regression, continuation exact drop<=0.5pp, no attack/cast0/cast1 conditional or joint regression, direction-change joint no regression. WardFP<=282,recall->ward<=257,wardtypeTP>=35,joint>=7,typeprecision>=35/317; frozen classifier/arguments should preserve these exactly. Blocked support retained.',
        exploratory_repeat_gate='After BOTH fits only: jointmove>=5pp better than P05 and G00, paired95%gain lower>0, lower jointNLL than both, all prospective guards. Allocation only; original90%eachcategory+3seeds,macro.65,movement+10pp,simple/retainedloss-10%,target guards unchanged. No automatic repeats.',
        budget='G00 and G01 consume pilots3and4 of8; one fit per invocation, freshGPT6.1Solxhigh completed review before nextfit. Bounded movement-only isolation; classifier retraining already done E00/E01 and next sampling/classifier comparison remains separate.',reserved='All75newvalidation/75finaltest sealed; only original TRAIN/development groups; no matches/downloads/botchanges/deploy/merge.')
    frozen(REPORTS/(identifier+'-plan.json'),plan);directory=WORK/'runs'/identifier;assert not directory.exists(),'Never overwrite or silently restart a run';directory.mkdir(parents=True)
    for path,digest in sources().items():(directory/(digest+'_'+Path(path).name)).write_bytes(Path(path).read_bytes())
    initial,_=infer(model,data['validation'],baseline['validation'],contexts['validation'])
    for key in ('prediction','priority','coordinate','proposed_coordinate'):np.testing.assert_array_equal(initial[key],baseline['validation'][key],err_msg='Initial warm decode '+key)
    frozen(directory/'epoch-zero.json',rt.summarize(raw['validation'],initial))
    optimizer=torch.optim.AdamW([p for p in model.parameters() if p.requires_grad],lr=plan['training']['lr'],weight_decay=plan['training']['weight_decay']);history=[];best=float('inf');best_epoch=0;best_state=None;start=time.perf_counter()
    try:
        for epoch in range(1,plan['training']['max_epochs']+1):
            model.train();order=torch.randperm(len(data['train']['y']));total=0.;aux_total=0.;calls=0;updates=0;epoch_start=time.perf_counter()
            for a in range(0,len(order),plan['training']['batch_size']):
                rows=order[a:a+plan['training']['batch_size']];y=data['train']['y'][rows];selected=(y==8)|(y==3);idx=rows[selected];optimizer.zero_grad(set_to_none=True);calls+=1
                if not len(idx):optimizer.step();continue
                lp,gate,available=model(data['train']['x'][idx],data['train']['history'][idx],data['train']['grid'][idx].float(),data['train']['valid'][idx],data['train']['y'][idx],data['train']['rules'][idx],contexts['train'][idx])
                loss=F.nll_loss(lp,data['train']['py'][idx],reduction='sum')/len(rows);primary=float(loss.detach());aux=torch.zeros(())
                eligible=(data['train']['y'][idx]==8)&available&torch.from_numpy(np.isin(direction['train'][idx.numpy()],[2,3]))
                if model.specialized and eligible.any():
                    target=torch.from_numpy(direction['train'][idx.numpy()][eligible.numpy()]==2).float();aux=F.binary_cross_entropy_with_logits(gate[eligible],target,reduction='sum')/len(rows);loss+=AUXILIARY_WEIGHT*aux
                loss.backward();torch.nn.utils.clip_grad_norm_([p for p in model.parameters() if p.requires_grad],plan['training']['gradient_clip']);optimizer.step();updates+=1;total+=primary*len(rows);aux_total+=float(aux.detach())*len(rows)
            pred,gate=infer(model,data['validation'],baseline['validation'],contexts['validation']);score=rt.summarize(raw['validation'],pred)
            row=dict(epoch=epoch,train_primary=total/len(order),train_gate_auxiliary=aux_total/len(order),validation_nll=score['joint_nll'],strict_joint=score['strict_full_command_accuracy'],move_exact=score['parameters']['move']['exact_accuracy'],move_joint=score['parameters']['move']['joint_accuracy'],seconds=time.perf_counter()-epoch_start,optimizer_calls=calls,head_updates=updates);history.append(row)
            if score['joint_nll']<best-.0001:best=score['joint_nll'];best_epoch=epoch;best_state=copy.deepcopy(model.state_dict())
            torch.save(dict(state=model.state_dict(),optimizer=optimizer.state_dict(),rng=torch.get_rng_state(),history=history,epoch=epoch,plan_sha256=sha(REPORTS/(identifier+'-plan.json'))),directory/('epoch-'+str(epoch)+'.pt'));print(identifier,row,flush=True)
            if epoch-best_epoch>=plan['training']['patience']:break
        model.load_state_dict(best_state);predictions={};gates={}
        for split in data:predictions[split],gates[split]=infer(model,data[split],baseline[split],contexts[split]);np.savez_compressed(directory/(split+'-predictions.npz'),**predictions[split]);np.savez_compressed(directory/(split+'-gates.npz'),**gates[split])
        torch.save(dict(state_dict=best_state,specialized=model.specialized,labels=rt.LABELS,mean=saved['mean'],std=saved['std'],plan_sha256=sha(REPORTS/(identifier+'-plan.json'))),directory/'model.pt')
        m01=arrays(BASE/'runs/M01/validation-predictions.npz');report=dict(id=identifier,best_epoch=best_epoch,history=history,train=metrics(raw['train'],predictions['train'],direction['train']),validation=metrics(raw['validation'],predictions['validation'],direction['validation']),gate={split:gate_metrics(raw[split],gates[split],direction[split]) for split in raw},comparisons=dict(M01=group_comparison(raw['validation'],predictions['validation'],m01),P05=group_comparison(raw['validation'],predictions['validation'],baseline['validation'])),legality=legality(raw['validation'],predictions['validation']),alignment=agreement,checkpoint_sha256=sha(directory/'model.pt'),predictions_sha256=sha(directory/'validation-predictions.npz'),train_predictions_sha256=sha(directory/'train-predictions.npz'),plan_sha256=sha(REPORTS/(identifier+'-plan.json')),nominal_trainable_parameters=sum(p.numel() for p in model.parameters() if p.requires_grad),frozen_model_parameters=sum(p.numel() for p in model.parameters() if not p.requires_grad),seconds=time.perf_counter()-start,optimizer_calls=sum(h['optimizer_calls'] for h in history),head_updates=sum(h['head_updates'] for h in history),three_seed_confirmed=False,reserved_opened=0)
        if identifier=='G01':report['comparisons']['G00']=group_comparison(raw['validation'],predictions['validation'],arrays(WORK/'runs/G00/validation-predictions.npz'))
        frozen(REPORTS/(identifier+'.json'),report);print('Completed ONE fit; fresh Sol xhigh review required before another fit.',flush=True)
    except BaseException:(directory/('failure-'+str(time.time_ns())+'.txt')).write_text(traceback.format_exc());raise

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('identifier',choices=['G00','G01']);arg=p.parse_args();log([sys.executable,'-m','tools.action_predictor.movement_study',*sys.argv[1:]]);fit(arg.identifier)
