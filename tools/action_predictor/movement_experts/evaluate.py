"""Joint forecasts and matched conditional diagnostics on original rows."""
import numpy as np
import torch
from .. import reliable_train as rt
from ..observation_metrics import correctness,point_metrics,group_samples,interval
from .data import batch

@torch.no_grad()
def infer(model,d,mean,std):
    model.eval();raw=d['raw'];out={k:v.copy() for k,v in d['baseline'].items()};out['nll']=out['nll'].astype(np.float64);out['param_nll']=out['param_nll'].astype(np.float64);gates=np.full((len(raw['y']),2 if model.mixture else 1),np.nan,np.float32)
    # Recorded family is used only for conditional evaluation/loss. Production
    # coordinates below always use the unchanged predicted family.
    for diagnostic in (True,False):
        family=raw['y'] if diagnostic else out['prediction'];ids=np.flatnonzero(np.isin(family,[3,8]))
        for a in range(0,len(ids),256):
            ix=ids[a:a+256];lp,gate=model(*batch(d,ix,mean,std,family[ix]));coordinate=lp.argmax(-1).numpy()
            if diagnostic:
                out['coordinate'][ix]=coordinate;out['top5'][ix]=lp.topk(5,-1).indices.numpy();out['param_nll'][ix]=-lp[torch.arange(len(ix)),torch.from_numpy(raw['py'][ix]).long()].numpy();out['nll'][ix]=out['type_nll'][ix]+out['param_nll'][ix];gates[ix]=gate.numpy()
            else:out['proposed_coordinate'][ix]=coordinate
    typed=np.isin(raw['y'],[3,8])&(raw['y']==out['prediction']);np.testing.assert_array_equal(out['coordinate'][typed],out['proposed_coordinate'][typed]);np.testing.assert_array_equal(out['prediction'],d['baseline']['prediction'])
    return out,gates

def masks(d,natural=None):
    r=d['raw'];move=r['y']==8;n=len(move);out={'all':np.ones(n,bool),'move':move,'blocked':r['y']==3,'continue':move&(d['direction']==2),'change':move&(d['direction']==3),'startup':move&(d['direction']==1),'zero_displacement':move&(d['direction']==4),'move_history16':move&(d['available']==16),'move_history_lt16':move&(d['available']<16),'move_near_obstacle':move&d['near'],'move_away_obstacle':move&~d['near']}
    if natural is not None:out.update({f'natural/{k}':v&natural for k,v in list(out.items())})
    return out

def summary(d,p,mask):
    r=d['raw'];out=point_metrics(r,p,mask);parameter,joint=correctness(r,p);rows=[]
    for k,name in enumerate(rt.LABELS):
        true=mask&(r['y']==k);guess=mask&(p['prediction']==k);typed=true&guess;n=int(true.sum());g=int(guess.sum());tp=int(typed.sum());correct=int((joint&true).sum());den=n+g
        rows.append(dict(action=name,support=n,joint_correct=correct,joint_accuracy=correct/n if n else None,type_TP=tp,type_FP=g-tp,type_precision=tp/g if g else None,type_recall=tp/n if n else None,type_F1=2*tp/den if den else None,joint_FP=g-correct,all_true_family_parameter_accuracy=float(parameter[true].mean()) if n and name in ('move','blocked','attack','cast_0','cast_1','ward','submit','altar','teleport','priority') else None,correctly_typed_support=tp,correctly_typed_parameter_accuracy=float(joint[typed].mean()) if tp and name!='shop' else None))
    out['per_category']=rows;out['strict_correct']=int((joint&mask).sum());out['confusion']=np.bincount(r['y'][mask]*15+p['prediction'][mask],minlength=225).reshape(15,15).tolist();return out

def paired(d,p,old):
    raw=d['raw'];groups=np.unique(raw['group']);rng=np.random.default_rng(20261106);draws=np.stack([np.bincount(rng.integers(len(groups),size=len(groups)),minlength=len(groups)) for _ in range(2000)]);_,j=correctness(raw,p);_,o=correctness(raw,old);out={}
    for name,m in masks(d).items():
        a=group_samples(raw,p,m,draws,groups);b=group_samples(raw,old,m,draws,groups);out[name]=dict(rows=int(m.sum()),rescues=int((j&~o&m).sum()),regressions=int((~j&o&m).sum()),paired95={k:interval(a[k]-b[k]) for k in ('joint_accuracy','joint_nll','macro_f1','move_exact','move_joint','blocked_exact','blocked_joint')},group_net={str(int(g)):int(((j.astype(int)-o.astype(int))*m*(raw['group']==g)).sum()) for g in groups})
    return out

def support(d,p):
    r=d['raw'];coord=r['py'];inside=(coord>=0)&(coord<289);ix=np.clip(coord,0,288);valid=r['valid'][np.arange(len(coord)),ix]&inside;mask=r['move_mask'][np.arange(len(coord)),ix]&inside;out={}
    for code,name in [(8,'move'),(3,'blocked')]:
        m=r['y']==code;out[name]=dict(rows=int(m.sum()),recorded_in_window=int((m&inside).sum()),recorded_inmap=int((m&valid).sum()),recorded_success_mask=int((m&mask).sum()),interpretation='Blocked rejection is an attempted-outcome diagnostic, never an illegal successful move.')
    forecast=np.asarray(p['proposed_coordinate']);inside=(forecast>=0)&(forecast<289);mask=inside&r['move_mask'][np.arange(len(forecast)),np.clip(forecast,0,288)];out['forecast_mask_rejections']={name:int(((p['prediction']==code)&~mask).sum()) for code,name in [(8,'successful_move'),(3,'blocked_attempt')]};out['full_legality']='unassessed';return out
