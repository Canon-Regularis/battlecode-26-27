"""Frozen nonfitting Q-only and fixed-mixture controls for V13."""
import json
import numpy as np
import torch
from .consistent_data import ROOT,BASE,WORK,REPORT
from .consistent_study import load,predictions
from .command_mixture import log_mass,decode
from .algorithmic_fit import evaluate
from .algorithmic.study import matches
from .audit import immutable_json
from .data import digest

@torch.no_grad()
def legacy_probabilities(commands):
    from .proposal_predictor import load_proposal_predictor
    from .command_mixture import FallbackDistribution
    from .priority_head import flatten
    from . import reliable_train as rt
    rt.setup(20261110);p=load_proposal_predictor().frozen
    with np.load(BASE.parent/'v4/validation.npz') as z:raw={k:z[k] for k in z.files}
    data,_=rt.model_data(raw,p.config,(p.mean,p.std))
    with np.load(BASE.parent/'v8/priority-validation.npz') as z:values=torch.from_numpy(z['values']);extra=torch.from_numpy((flatten(z['values'],z['history']).astype(np.float32)-p.extra_mean.numpy())/p.extra_std.numpy())
    result=[]
    for a in range(0,len(commands),256):
        b=a+256;inputs={k:data[k][a:b] for k in ('x','history','valid','rules')};inputs.update(grid=data['grid'][a:b].float(),priority_values=values[a:b],extra=extra[a:b]);result.append(FallbackDistribution(p,inputs).log_prob(commands[a:b]))
    return np.concatenate(result)

def run(split):
    d=load(split);n=len(d['x']);directory=WORK/'controls';directory.mkdir(exist_ok=True);reports={}
    for name in ('Q00','U00'):
        weights=np.zeros((n,58),np.float64)
        if name=='Q00':weights[:,0]=1
        else:
            available=d['c'][:,:,0]>=0;counts=available.sum(1);weights[:,0]=.9;weights[:,1:]=.1*available/np.maximum(counts[:,None],1);weights[counts==0,0]=1
        with np.errstate(divide='ignore'):scores=np.log(weights)
        nll=-log_mass(torch.from_numpy(scores),torch.from_numpy(np.array(d['matches'])),torch.from_numpy(np.array(d['target-logq']))).numpy();pred=predictions(scores,nll,d);path=directory/f'{name}-{split}.npz';assert not path.exists();np.savez_compressed(path,**pred);reports[name]=dict(result=evaluate(d['raw'],pred,np.load(BASE.parent/f'v7/{split}-direction.npy')),prediction_sha256=digest(path))
        print('Control',split,name,reports[name]['result']['strict_correct'],flush=True)
    if split=='validation':
        # Also fix the old A00 decoder without a refit or silently changing its
        # point library. Reuse shared Q modes and query its existing point slots.
        from .algorithmic_fit import load as oldload
        old=oldload(split);oldc=old['c'];saved=np.load(BASE.parent/'v10/runs/A00/validation-predictions.npz');oldlogq=legacy_probabilities(oldc)
        from .command_mixture import agreement,target_commands
        with np.errstate(divide='ignore'):lw=np.log(saved['selector_weights'].astype(np.float64))
        nll=-log_mass(torch.from_numpy(lw),torch.from_numpy(agreement(oldc,target_commands(d['raw']['y'],d['raw']['py'],d['raw']['priority']))),torch.from_numpy(np.array(d['target-logq']))).numpy()
        command,confidence,fraction=decode(lw,oldc,oldlogq,d['modes'],d['mode-logq']);p=dict(prediction=command[:,0],coordinate=command[:,1],priority=command[:,2],nll=nll,command_log_probability=confidence,point_probability_fraction=fraction)
        path=directory/'D01-validation.npz';assert not path.exists();np.savez_compressed(path,**p);reports['D01']=dict(result=evaluate(d['raw'],p,np.load(BASE.parent/'v7/validation-direction.npy')),prediction_sha256=digest(path),max_old_A00_nll_difference=float(np.max(np.abs(nll-saved['nll']))),qualification='No-refit A00 consistency correction with unchanged weights and point library. The shared FallbackDistribution computes both old point probabilities and observed likelihood. All-family modes remove bounded-D00 search omission; observed-representation qualification applies.')
        print('A00 consistent decoder',reports['D01']['result']['strict_correct'],flush=True)
    immutable_json(REPORT/f'{split}-controls.json',dict(reports=reports,protocol_sha256=digest(REPORT/'protocol-r2.json'),source_sha256=digest(__file__),new_fits=0,reserved_opened=0))

if __name__=='__main__':
    import sys
    run(sys.argv[1])
