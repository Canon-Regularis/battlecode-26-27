"""A00: causal marginal command-agreement selector with stochastic G00 fallback.

Training uses sum of all matching point experts plus fallback likelihood, never
an invented intent label. Serving hard-routes the most probable equivalent point
expert group or opaque fallback slot. This decoder is deliberately not claimed
to be the exact MAP command of the stochastic mixture.
"""
import json,sys,time
from pathlib import Path
import numpy as np
import torch
from torch import nn
from .algorithmic.study import ROOT,WORK,REPORT,matches
from .algorithmic.library import NAMES
from .audit import immutable_json
from .data import digest
from . import reliable_train as rt

def evaluate(raw,pred,direction):
    y=raw['y'];p=pred['prediction'];matrix=np.bincount(y*len(rt.LABELS)+p,minlength=len(rt.LABELS)**2).reshape(len(rt.LABELS),-1)
    joint=matches(np.stack((p,pred['coordinate'],pred['priority']),-1)[:,None],y,raw['py'],raw['priority']).any(1)
    diag=matrix.diagonal();f1=2*diag/np.maximum(matrix.sum(0)+matrix.sum(1),1);rows=[]
    for k,label in enumerate(rt.LABELS):
        n=int((y==k).sum());g=int((p==k).sum());tp=int(diag[k]);j=int(joint[y==k].sum())
        rows.append(dict(action=label,support=n,joint_correct=j,joint_accuracy=j/n if n else None,type_precision=tp/g if g else 0,type_recall=tp/n if n else None,type_f1=float(f1[k]),type_FP=g-tp,joint_FP=g-j,parameter_given_correct_type=j/tp if tp and label!='shop' else None,all_true_family_parameter_accuracy=None))
    groups=np.unique(raw['group']);counts=np.array([(raw['group']==g).sum() for g in groups]);correct=np.array([joint[raw['group']==g].sum() for g in groups]);rng=np.random.default_rng(20261107);draws=np.stack([np.bincount(rng.integers(len(groups),size=len(groups)),minlength=len(groups)) for _ in range(2000)]);boot=draws@correct/(draws@counts)
    return dict(strict_correct=int(joint.sum()),accuracy=float(joint.mean()),macro_f1=float(f1[1:].mean()),observed_joint_nll=float(pred['nll'].mean()),per_category=rows,confusion=matrix.tolist(),group_bootstrap_accuracy95=np.quantile(boot,[.025,.975]).tolist(),per_group={str(int(g)):dict(rows=int((raw['group']==g).sum()),correct=int(joint[raw['group']==g].sum())) for g in groups},movement_contexts={name:dict(rows=int(((y==rt.LABELS.index('move'))&(direction==code)).sum()),joint_correct=int(joint[(y==rt.LABELS.index('move'))&(direction==code)].sum())) for name,code in [('continuing',2),('change',3),('no_previous',1)]})

class Selector(nn.Module):
    def __init__(self,features):
        super().__init__();self.net=nn.Sequential(nn.Linear(features,64),nn.Tanh(),nn.Dropout(.1),nn.Linear(64,len(NAMES)+1))
        nn.init.zeros_(self.net[-1].weight);nn.init.constant_(self.net[-1].bias,-4);self.net[-1].bias.data[0]=4
    def forward(self,x,available):
        return self.net(x).masked_fill(~available,-1e9).log_softmax(-1)

def load(split):
    report=json.loads((REPORT/f'C00-{split}.json').read_text());cp=WORK/f'{split}-candidates.npy';assert digest(cp)==report['candidates_sha256']
    path=ROOT/('.cambc/action-predictor/v5/combined-train.npz' if split=='train' else '.cambc/action-predictor/v4/validation.npz')
    assert digest(path)==report['data_sha256']
    with np.load(path) as z:raw={k:z[k] for k in ('x','history','y','py','priority','group')}
    h=raw['history'][:,-8:].copy();spatial=np.zeros(h.shape[:2],bool)
    for name in ('move','blocked','attack','cast_0','cast_1','ward','submit','altar','teleport','end'):spatial|=h[:,:,rt.LABELS.index(name)]>0
    h[:,:,len(rt.LABELS)+1:len(rt.LABELS)+3]*=spatial[:,:,None]
    x=np.concatenate((raw['x'],h.reshape(len(h),-1)),axis=1).astype(np.float32)
    pp=ROOT/'.cambc/action-predictor/v9/runs/G00'/f'{split}-predictions.npz';assert digest(pp)==report['G00_predictions_sha256']
    with np.load(pp) as z:baseline={k:z[k] for k in z.files}
    c=np.load(cp)[:,1].copy();available=np.column_stack((np.ones(len(c),bool),c[:,:,0]>=0))
    match=matches(c,raw['y'],raw['py'],raw['priority']);mass=np.column_stack((np.exp(-baseline['nll'].astype(np.float64)),match.astype(np.float64)))
    return dict(raw=raw,x=x,c=c,available=torch.from_numpy(available),mass=torch.from_numpy(mass),baseline=baseline)

def infer(model,data,mean,std):
    scores=[];loss=[];model.eval()
    with torch.no_grad():
        for a in range(0,len(data['x']),1024):
            b=a+1024;x=torch.from_numpy(np.clip((data['x'][a:b]-mean)/std,-10,10));lp=model(x,data['available'][a:b]);scores.append(lp.exp().numpy())
            loss.append((-torch.logsumexp(lp.double()+data['mass'][a:b].clamp_min(1e-300).log(),-1)).numpy())
    return np.concatenate(scores),np.concatenate(loss)

def decode(scores,data):
    base=data['baseline'];pred={k:base[k].copy() for k in ('prediction','priority')};pred['coordinate']=base['proposed_coordinate'].copy();n=len(scores);fallback=np.zeros(n,bool)
    # Equivalence classes are exact command triples; duplicate explanations sum.
    for i in range(n):
        groups={}
        for j,c in enumerate(data['c'][i]):
            if c[0]>=0:groups[tuple(map(int,c))]=groups.get(tuple(map(int,c)),0.)+float(scores[i,j+1])
        if not groups or scores[i,0]>=max(groups.values()):fallback[i]=True;continue
        command=max(groups,key=groups.get);pred['prediction'][i],pred['coordinate'][i],pred['priority'][i]=command
    return pred,fallback

def run():
    rt.setup(20261107);WORK.mkdir(exist_ok=True);directory=WORK/'runs/A00';directory.mkdir(parents=True,exist_ok=True)
    assert not (directory/'round-01.pt').exists(),'Never overwrite an attempted fit'
    train_report=json.loads((REPORT/'C00-train.json').read_text());r=train_report['libraries']['simple'];assert r['per_family']['move']['coverage']>=.60 or r['rescues_beyond_G00']/train_report['rows']>=.03
    from .fundamental_audit import dependencies
    from .priority_dependencies_v3 import verify_label_schema
    dependencies();verify_label_schema()
    g=json.loads((REPORT.parent/'v9/G00.json').read_text());assert digest(ROOT/'.cambc/action-predictor/v9/runs/G00/model.pt')==g['checkpoint_sha256']
    plan=dict(id='A00',source_sha256=digest(__file__),selected_library='C00 simple,mode1; selected by TRAIN movement coverage68.42% vs58.30%field library, before reading DEV coverage. Slot suffixes field_yx/field_xy in this control mean squared-distance-yx/xy geometric ties, as implemented in library.py.',library_plan_sha256=digest(REPORT/'C00-plan-r1.json'),coverage_reports={s:digest(REPORT/f'C00-{s}.json') for s in ('train','validation')},
        inputs='253 frozen personal PRE features plus last8 actual own-action encodings, sanitized utility coordinates. No game/group/map IDs, sampled-row recurrence, current answer, future evidence or oracle routing. Missing history remains explicit in frozen vectors.',
        model='445->64tanh->32logits;dropout.1;masked absent candidates;zero output weights,fallback bias4,other bias-4',
        loss='Unweighted original augmented TRAIN. Negative log(sum weights of all exact command matches + fallback weight*G00 observed joint probability). Marginalizes duplicate intent explanations. Shop argument likelihood remains unobserved;strict shop alwaysfails.',
        decoder='Sum weights of identical point commands; compare largest to opaque fallback weight; emit point or G00 predicted-family command. Approximate hard routing, not mixture command MAP. Action selection and fallback routing are trainable.',
        optimizer=dict(name='AdamW',lr=.001,weight_decay=.01,batch=512,gradient_clip=5),seed=20261107,selection=dict(max_rounds=35,patience=6,improvement=.0001,criterion='full original DEV observed joint NLL'),
        limitations='No goal persistence yet. C00 uses terrain-only route costs, not verified full historical path semantics. Point experts have no novel shop arguments or nonzero priority. Conditional all-family parameter predictions unavailable for this joint command decoder; correctly typed conditional metrics and full predictions reported; do not mislabel its single output as true-family argument accuracy.',
        promotion='Original targets binding; no promotion from oracle coverage. Three seeds only if joint improvement>=.005, no attack/cast joint or conditional loss>.02, macroF1>=.65 and DEV NLL improves. Maximum2 pilot fits frozen in C00; no automatic reuse after review.')
    immutable_json(REPORT/'A00-plan.json',plan)
    data={s:load(s) for s in ('train','validation')};t=data['train'];v=data['validation'];mean=t['x'].mean(0);std=np.maximum(t['x'].std(0),.01);x=torch.from_numpy(np.clip((t['x']-mean)/std,-10,10));model=Selector(x.shape[1]);opt=torch.optim.AdamW(model.parameters(),lr=.001,weight_decay=.01)
    best=float('inf');selected=0;trace=[];rng=np.random.default_rng(20261107)
    for epoch in range(1,36):
        model.train();losses=[]
        for indices in np.array_split(rng.permutation(len(x)),int(np.ceil(len(x)/512))):
            idx=torch.from_numpy(indices);opt.zero_grad();lp=model(x[idx],t['available'][idx]);loss=-torch.logsumexp(lp.double()+t['mass'][idx].clamp_min(1e-300).log(),-1).mean();loss.backward();torch.nn.utils.clip_grad_norm_(model.parameters(),5);opt.step();losses.append(float(loss.detach()))
        scores,nll=infer(model,v,mean,std);value=float(nll.mean());torch.save(dict(state=model.state_dict(),mean=mean,std=std,epoch=epoch,plan_sha256=digest(REPORT/'A00-plan.json')),directory/f'round-{epoch:02d}.pt')
        trace.append(dict(round=epoch,training_loss=float(np.mean(losses)),dev_nll=value));print(trace[-1],flush=True)
        if value<best-.0001:best=value;selected=epoch
        if epoch-selected>=6:break
    saved=torch.load(directory/f'round-{selected:02d}.pt',weights_only=False);model.load_state_dict(saved['state']);reports={}
    for split,d in data.items():
        scores,nll=infer(model,d,mean,std);pred,fallback=decode(scores,d);pred['nll']=nll;np.savez_compressed(directory/f'{split}-predictions.npz',**pred,fallback=fallback,selector_weights=scores)
        direction=np.load(ROOT/'.cambc/action-predictor/v7'/f'{split}-direction.npy');report=evaluate(d['raw'],pred,direction)
        base=evaluate(d['raw'],d['baseline'],direction);report['G00']=base
        joint=matches(np.stack((pred['prediction'],pred['coordinate'],pred['priority']),-1)[:,None],d['raw']['y'],d['raw']['py'],d['raw']['priority']).any(1)
        report['fallback']=dict(rows=int(fallback.sum()),accuracy=float(joint[fallback].mean()) if fallback.any() else None,point_rows=int((~fallback).sum()),point_accuracy=float(joint[~fallback].mean()) if (~fallback).any() else None)
        reports[split]=report
    immutable_json(REPORT/'A00.json',dict(plan_sha256=digest(REPORT/'A00-plan.json'),selected_round=selected,trace=trace,reports=reports,reserved_opened=0,checkpoint_sha256=digest(directory/f'round-{selected:02d}.pt')))
    print('Completed A00 selected',selected,flush=True)

if __name__=='__main__':run()
