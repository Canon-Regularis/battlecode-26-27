"""Conditional placement uncertainty and bounded TRAIN-only input-use probe."""
import json,sys
import numpy as np
import torch
from .protocol import BASE,WORK,REPORT
from .fit import load,inputs
from .model import Placement,placement_modes,placement_target
from ..observation_metrics import interval
from ..audit import immutable_json
from ..data import digest
from .. import reliable_train as rt

@torch.no_grad()
def run(identifier):
    assert identifier.startswith('P');rt.setup(20261112);info=json.loads((REPORT/f'{identifier}.json').read_text());checkpoint=WORK/f"runs/{identifier}/round-{info['selected_round']:02d}.pt";saved=torch.load(checkpoint,weights_only=False);model=Placement(saved['counts']);model.load_state_dict(saved['state']);model.eval();results={}
    for split in ('train','validation'):
        d=load(split);ward=d['raw']['y']==14;out=np.load(WORK/f'runs/{identifier}/{split}-outputs.npz');correct=out['coordinate']==d['raw']['py'];old=np.asarray(d['ward-mode'])==d['raw']['py'];masks={'all':ward}
        if split=='train':masks['natural']=ward&np.load(BASE.parent/'v9/frequency/natural-mask.npy')
        rows={}
        for name,m in masks.items():rows[name]=dict(rows=int(m.sum()),new_exact=int(correct[m].sum()),old_exact=int(old[m].sum()),rescues=int((correct&~old&m).sum()),regressions=int((~correct&old&m).sum()),new_conditional_nll=float((-np.array(d['ward-target-logp'][m])+out['nll'][m]-d['base_nll'][m]).mean()),old_conditional_nll=float(-np.array(d['ward-target-logp'][m]).mean()))
        results[split]=rows
        if split=='validation':
            groups=np.unique(d['raw']['group']);rng=np.random.default_rng(20261106);draws=np.stack([np.bincount(rng.integers(len(groups),size=len(groups)),minlength=len(groups)) for _ in range(2000)]);counts=np.array([(ward&(d['raw']['group']==g)).sum() for g in groups]);delta=np.array([((correct.astype(int)-old.astype(int))*ward*(d['raw']['group']==g)).sum() for g in groups]);den=draws@counts;rows['paired_conditional_accuracy95']=interval(np.divide(draws@delta,den,out=np.full(len(den),np.nan),where=den>0))
        else:
            # Fixed selected model; corrupt only the frozen context on TRAIN.
            # This probes functional reliance, not Fish intent or information
            # sufficiency; no optimization or game action is performed.
            ids=np.flatnonzero(ward);permutation=np.random.default_rng(20261112).permutation(ids);corrupt={};newcorrect=[];loss=[]
            for a in range(0,len(ids),512):
                ix=ids[a:a+512];x,tile,mask=inputs(d,ix,saved['mean'],saved['std'],identifier);x[:,:128]=torch.from_numpy(np.clip((np.array(d['global'][permutation[a:a+512],:128])-saved['mean'][:128])/saved['std'][:128],-10,10));lp=model(x,tile,mask);c,_=placement_modes(lp,mask,torch.from_numpy(np.array(d['ward-local-logp'][ix])),torch.from_numpy(np.array(d['ward-mode'][ix])).long(),torch.from_numpy(np.array(d['ward-mode-logp'][ix])));newcorrect.append(c.numpy()==d['raw']['py'][ix]);loss.append(-placement_target(lp,mask,d['raw']['py'][ix],torch.from_numpy(np.array(d['ward-target-logp'][ix]))).numpy())
            rows['TRAIN_shuffled_context_probe']=dict(rows=len(ids),exact=int(np.concatenate(newcorrect).sum()),conditional_nll=float(np.concatenate(loss).mean()),meaning='Only existing128frozenneuralcontext shuffled;currenttilefeatures/mask retained. Measures fittedmodeldependence, not availableinformationcausalvalue. No newfit.')
    immutable_json(REPORT/f'{identifier}-placement-diagnosis.json',dict(results=results,source_sha256=digest(__file__),checkpoint_sha256=digest(checkpoint),new_fits=0,reserved_opened=0));print(identifier,results,flush=True)

if __name__=='__main__':run(sys.argv[1])
