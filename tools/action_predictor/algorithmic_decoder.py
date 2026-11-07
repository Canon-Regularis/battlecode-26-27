"""D00 fixed non-fitting bounded mixture decoder diagnostic; no promotion."""
import json
import numpy as np
import torch
from .algorithmic.study import ROOT,WORK,REPORT
from .algorithmic_fit import load,evaluate
from .movement_predictor import MovementMixturePredictor
from .priority_fit_v3 import BASE,VAL,context_directory
from .priority_residual_fit import VOCAB
from .priority_head import flatten
from .audit import immutable_json
from .data import digest
from . import reliable_train as rt

@torch.no_grad()
def run():
    rt.setup(26);d=load('validation');n=len(d['x']);directory=WORK/'runs/A00';saved=np.load(directory/'validation-predictions.npz')
    immutable_json(REPORT/'D00-plan.json',dict(source_sha256=digest(__file__),fit='none;A00round17fixed',candidates='All C00simple emitted commands plus G00 existing hard forecast. Rank exact stochastic mixture probability for each unique command in this bounded set. This is not global MAP, particularly priority, nor an optimal action-first G00 decoder.',selection='Diagnostic evaluated once on all original DEV. Retain hard decoder for A01 paired architecture study regardless of D00 result. No threshold or retrospectively chosen decoder.',reserved_opened=0))
    g=json.loads((REPORT.parent/'v9/G00.json').read_text());predictor=MovementMixturePredictor(BASE/'runs/M01/model.pt',context_directory()/'extra-normalization.npz',json.loads(VOCAB.read_text()),BASE.parent/'v8/runs/P05/model.pt',BASE.parent/'v9/runs/G00/model.pt',g['checkpoint_sha256'])
    with np.load(VAL) as z:raw={k:z[k] for k in z.files}
    data,_=rt.model_data(raw,predictor.config,(predictor.mean,predictor.std))
    with np.load(BASE.parent/'v8/priority-validation.npz') as z:values=torch.from_numpy(z['values']);extra=torch.from_numpy((flatten(z['values'],z['history']).astype(np.float32)-predictor.extra_mean.numpy())/predictor.extra_std.numpy())
    c=d['c'];base=d['baseline'];fallback=np.stack((base['prediction'],base['proposed_coordinate'],base['priority']),-1)
    spatial={rt.LABELS.index(x) for x in ('move','blocked','attack','cast_0','cast_1','ward','submit','altar','teleport')}
    commands=np.concatenate((fallback[:,None],c),1).copy()
    for i,row in enumerate(commands):
        for command in row:
            if command[0] not in spatial:command[1]=-1
            if command[0]!=9:command[2]=0
    probability=np.zeros(commands.shape[:2],np.float64)
    for a in range(0,n,256):
        b=min(n,a+256);x=data['x'][a:b];h=data['history'][a:b];grid=data['grid'][a:b].float();valid=data['valid'][a:b];rules=data['rules'][a:b];logits,context=predictor.model(x,h);types=logits.softmax(-1).double();encoded=predictor.movement.encode(x,h,context);pr=predictor.head(context,extra[a:b])
        for family in range(1,len(rt.LABELS)):
            rows,cols=np.where(commands[a:b,:,0]==family)
            if not len(rows):continue
            mass=types[rows,family].numpy()
            if family in spatial:
                codes=torch.full((b-a,),family,dtype=torch.int64)
                lp=predictor.movement.parameter_log_probs(encoded,grid,valid,codes,rules)[0] if family in (8,3) else predictor.model.parameter_logits(context,grid,valid,codes,rules).log_softmax(-1)
                coordinates=commands[a+rows,cols,1];mass*=lp[rows,coordinates].exp().double().numpy()
            elif family==9:
                target=torch.from_numpy(commands[a+rows,cols,2]);mass*=predictor.head.log_mass(pr[rows],target,values[a:b][rows]).exp().numpy()
            probability[a+rows,cols]=mass
    np.save(WORK/'validation-G00-candidate-probability.npy',probability)
    weights=saved['selector_weights'];pred=dict(prediction=base['prediction'].copy(),coordinate=base['proposed_coordinate'].copy(),priority=base['priority'].copy(),nll=saved['nll'].copy());confidence=[]
    for i in range(n):
        point={}
        for k,command in enumerate(commands[i,1:]):
            if command[0]>=0:point[tuple(command)]=point.get(tuple(command),0.)+float(weights[i,k+1])
        options={tuple(command):weights[i,0]*probability[i,k]+point.get(tuple(command),0.) for k,command in enumerate(commands[i]) if command[0]>=0}
        winner=max(options,key=options.get);confidence.append(options[winner]);pred['prediction'][i],pred['coordinate'][i],pred['priority'][i]=winner
    np.savez_compressed(directory/'D00-validation-predictions.npz',**pred,command_confidence=confidence)
    result=evaluate(d['raw'],pred,np.load(BASE.parent/'v7/validation-direction.npy'))
    immutable_json(REPORT/'D00.json',dict(plan_sha256=digest(REPORT/'D00-plan.json'),result=result,G00_candidate_probability_sha256=digest(WORK/'validation-G00-candidate-probability.npy'),prediction_sha256=digest(directory/'D00-validation-predictions.npz'),changed_commands=int(((pred['prediction']!=saved['prediction'])|(pred['coordinate']!=saved['coordinate'])|(pred['priority']!=saved['priority'])).sum()),new_fits=0,reserved_opened=0,not_promoted=True))
    print('D00',result['strict_correct'],result['macro_f1'],flush=True)

if __name__=='__main__':run()
