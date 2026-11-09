"""No-fit placement controls on the exact same recorded ward rows."""
import json
import numpy as np
import torch
from .protocol import BASE,WORK,REPORT
from .features import INDICES,OFFSETS
from .fit import load
from .model import placement_target,placement_modes,target_local
from ..audit import immutable_json
from ..data import digest

def run():
    train=load('train');y=train['raw']['y'];at,valid=target_local(train['raw']['py']);counts=np.bincount(at[(y==14)&valid],minlength=25)+1;prior=counts/counts.sum();results={}
    for split in ('train','validation'):
        d=train if split=='train' else load(split);ward=np.flatnonzero(d['raw']['y']==14);mask=np.array(d['mask'][ward]);old=torch.from_numpy(np.array(d['ward-local-logp'][ward]));scores={'uniform':np.zeros((len(ward),25)), 'TRAIN_offset_prior':np.broadcast_to(np.log(prior),(len(ward),25)).copy(),'masked_G00':old.numpy().copy()};reports={}
        for name,score in scores.items():
            lp=torch.from_numpy(score).masked_fill(~torch.from_numpy(mask),-1e9).log_softmax(-1);coordinate,_=placement_modes(lp,torch.from_numpy(mask),old,torch.from_numpy(np.array(d['ward-mode'][ward])).long(),torch.from_numpy(np.array(d['ward-mode-logp'][ward])));target=placement_target(lp,torch.from_numpy(mask),d['raw']['py'][ward],torch.from_numpy(np.array(d['ward-target-logp'][ward])));correct=coordinate.numpy()==d['raw']['py'][ward];reports[name]=dict(rows=len(ward),exact=int(correct.sum()),accuracy=float(correct.mean()),conditional_nll=float(-target.mean()))
            if split=='train':
                m=np.load(BASE.parent/'v9/frequency/natural-mask.npy')[ward];reports[name]['natural']=dict(rows=int(m.sum()),exact=int(correct[m].sum()),accuracy=float(correct[m].mean()))
        exact=np.array(d['ward-mode'][ward])==d['raw']['py'][ward];reports['original_G00']=dict(rows=len(ward),exact=int(exact.sum()),accuracy=float(exact.mean()),conditional_nll=float(-np.array(d['ward-target-logp'][ward]).mean()));results[split]=reports
    immutable_json(REPORT/'placement-baselines.json',dict(results=results,source_sha256=digest(__file__),interpretation='All truewardrows retained; oracleprovided-family diagnostic only. Mode tie deterministic coordinateindex; noneofthese are learned specialist accuracy. MaskedG00isolatescandidate-domaincorrection from newhead fitting.',new_fits=0,reserved_opened=0));print(results['validation'],flush=True)

if __name__=='__main__':run()
