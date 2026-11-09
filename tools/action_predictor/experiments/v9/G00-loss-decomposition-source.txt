"""Selected-checkpoint gate/destination loss decomposition; no fitting."""
from pathlib import Path
import sys
import numpy as np
import torch
import torch.nn.functional as F
from . import reliable_train as rt
from .fundamental_audit import WORK,REPORTS,arrays,log
from .priority_fit_v3 import BASE,VAL,read,load_base,context_directory
from .movement_mixture import MovementMixture,previous_direction,log_partition
from .more_replays import frozen,sha

@torch.no_grad()
def run(identifier):
    rt.setup(26);report=read(REPORTS/(identifier+'.json'));cp=WORK/'runs'/identifier/'model.pt';assert sha(cp)==report['checkpoint_sha256'];saved=torch.load(cp,weights_only=True,map_location='cpu');teacher,base=load_base();model=MovementMixture(teacher,saved['specialized']);model.load_state_dict(saved['state_dict']);model.eval();result={}
    for split,path in [('train',BASE/'combined-train.npz'),('validation',VAL)]:
        raw=arrays(path);data,_=rt.model_data(raw,base['config'],(saved['mean'],saved['std']));direction=np.load(BASE.parent/'v7'/(split+'-direction.npy'));context=torch.from_numpy(np.load(context_directory()/(split+'.npy')));indices=np.flatnonzero((raw['y']==8)&np.isin(direction,[2,3]));losses=[];gates=[];destinations=[];maximum=0.
        for a in range(0,len(indices),256):
            idx=indices[a:a+256];grid=data['grid'][idx].float();family=data['y'][idx];valid=data['valid'][idx];rules=data['rules'][idx];enc=model.encode(data['x'][idx],data['history'][idx],context[idx]);lp,gate,available=model.parameter_log_probs(enc,grid,valid,family,rules);offset,known,mask=previous_direction(grid)
            eligible=available;py=data['py'][idx];assert ((py>=0)&(py<289)).all();target=torch.from_numpy(direction[idx]==2);assert torch.equal(mask.gather(1,py[:,None])[:,0][eligible],target[eligible])
            bce=F.binary_cross_entropy_with_logits(gate,target.float(),reduction='none');nll=-lp.gather(1,py[:,None])[:,0]
            if model.specialized:
                p=model.continuation.parameter_logits(enc[1],grid,valid,family,rules).log_softmax(-1);q=model.change.parameter_logits(enc[2],grid,valid,family,rules).log_softmax(-1)
                p=p.masked_fill(~mask,-torch.inf)-log_partition(p,mask)[:,None];q=q.masked_fill(mask,-torch.inf)-log_partition(q,~mask)[:,None]
                within=-torch.where(target,p.gather(1,py[:,None])[:,0],q.gather(1,py[:,None])[:,0]);error=(nll-bce-within)[eligible].abs();maximum=max(maximum,float(error.max()))
                assert maximum<=2e-5;destinations.extend(within[eligible].tolist())
            losses.extend(nll[eligible].tolist());gates.extend(bce[eligible].tolist())
        result[split]=dict(eligible_move_support=len(losses),selected_checkpoint_mixture_move_nll=float(np.mean(losses)),gate_BCE=float(np.mean(gates)),within_partition_destination_NLL=float(np.mean(destinations)) if destinations else None,decomposition_max_error=maximum if model.specialized else None,extra_auxiliary_weight=.05 if model.specialized else 0.,effective_gate_coefficient_on_eligible_rows=1.05 if model.specialized else None,scope='Selected checkpoint, all eligible true move rows. G01 directional support makes primary NLL = gateBCE+within-partition NLL; auxiliary adds0.05gateBCE. G00 unrestricted mixture has no such semantic decomposition or gate supervision. Means are per eligible row, not the full-minibatch training denominator.')
    evidence=dict(report_sha256=sha(REPORTS/(identifier+'.json')),source_sha256=sha(__file__),splits=result,interpretation='Architecture/support/optimization and extra gate weighting package; not proof that a new independent auxiliary task alone helped. No future-direction input, oracle routing or checkpoint reselection.',new_fits=0,reserved_opened=0)
    frozen(REPORTS/(identifier+'-loss-decomposition.json'),evidence);(REPORTS/(identifier+'-loss-decomposition-source.txt')).write_bytes(Path(__file__).read_bytes());print(result)

if __name__=='__main__':log([sys.executable,'-m','tools.action_predictor.movement_loss_diagnostics',*sys.argv[1:]]);run(sys.argv[1])
