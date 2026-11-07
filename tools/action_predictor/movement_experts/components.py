"""Prospectively declared fixed-checkpoint component diagnostic; no intent labels."""
import json
import numpy as np
import torch
from .protocol import ROOT,BASE,WORK,REPORT
from .data import load,batch,read
from .model import MovementExpert
from ..audit import immutable_json
from ..data import digest

@torch.no_grad()
def run():
    torch.set_num_threads(4);plan=REPORT/'X00-component-diagnostic-plan.json';assert plan.exists();info=json.loads((REPORT/'X00.json').read_text());path=WORK/f"runs/X00/round-{info['selected_round']:02d}.pt";saved=torch.load(path,weights_only=False);model=MovementExpert(True,saved['counts']);model.load_state_dict(saved['state']);model.eval();captured=[];gate_raw=[]
    hooks=[h.register_forward_hook(lambda module,args,out:captured.append(out.detach().clone())) for h in model.heads];hooks.append(model.gate.register_forward_hook(lambda module,args,out:gate_raw.append(out.detach().clone())));results={};artifacts={};maxdiff=0
    for split in ('train','validation'):
        d=load(split);y=d['raw']['y'];ids=np.flatnonzero(np.isin(y,[3,8])&(np.load(BASE.parent/'v9/frequency/natural-mask.npy') if split=='train' else True));archive=read(WORK/f'runs/X00/{split}-predictions.npz');mode_rows=[];mixture_rows=[];weight_rows=[];js_rows=[]
        for a in range(0,len(ids),256):
            ix=ids[a:a+256];inputs=batch(d,ix,saved['mean'],saved['std']);captured.clear();gate_raw.clear();lp,gate=model(*inputs);grid=inputs[1];valid=inputs[2];family=inputs[-1];allowed=valid&torch.where((family==8)[:,None],grid[:,:,5]>0,torch.ones_like(valid));complete=torch.cat((allowed,torch.zeros((len(ix),2),dtype=torch.bool)),1);complete[~allowed.any(-1)]=True;parts=[]
            for logits in captured:
                logits[:,:289]=logits[:,:289].masked_fill(~valid,-1e4);full=logits.log_softmax(-1);restricted=logits.masked_fill(~complete,-1e4).log_softmax(-1);parts.append(torch.logaddexp(restricted+np.log(.9999),full+np.log(.0001)))
            parts=torch.stack(parts,1);reconstructed=torch.logsumexp(parts+gate_raw[0].log_softmax(-1)[:,:,None],1);maxdiff=max(maxdiff,float((lp-reconstructed).abs().max()));torch.testing.assert_close(lp,reconstructed,atol=1e-6,rtol=0);mix=lp.argmax(-1).numpy();np.testing.assert_array_equal(mix,archive['coordinate'][ix]);mode_rows.append(parts.argmax(-1).numpy());mixture_rows.append(mix);weight_rows.append(gate.numpy());double=parts.double();middle=torch.logsumexp(double,1)-np.log(2);js_rows.append((.5*(double.exp()*(double-middle[:,None])).sum((1,2))).numpy())
        modes=np.concatenate(mode_rows);mixture=np.concatenate(mixture_rows);weights=np.concatenate(weight_rows);js=np.concatenate(js_rows);target=d['raw']['py'][ids];head_correct=(modes==target[:,None])&(target[:,None]<289);correct=(mixture==target)&(target<289);union=head_correct.any(-1);typed=archive['prediction'][ids]==y[ids];contexts={'all':np.ones(len(ids),bool),'move':y[ids]==8,'blocked':y[ids]==3,'continue':(y[ids]==8)&(d['direction'][ids]==2),'change':(y[ids]==8)&(d['direction'][ids]==3)};summary={}
        for name,m in contexts.items():
            n=int(m.sum());summary[name]=dict(rows=n,head_mode_exact=head_correct[m].sum(0).tolist(),head_mode_union_exact=int((union&m).sum()),head_mode_agreement=int(((modes[:,0]==modes[:,1])&m).sum()),mixture_MAP_exact=int((correct&m).sum()),union_correct_but_mixture_wrong=int((union&~correct&m).sum()),mixture_correct_outside_both_modes=int((correct&~union&m).sum()),head_union_joint=int((union&typed&m).sum()),mixture_joint=int((correct&typed&m).sum()),gate_mean=weights[m].mean(0).tolist() if n else None,gate_entropy=float((-weights[m]*np.log(np.clip(weights[m],1e-30,1))).sum(1).mean()) if n else None,head_JS_divergence_mean=float(js[m].mean()) if n else None)
        dest=WORK/f'runs/X00/{split}-components.npz';assert not dest.exists();np.savez_compressed(dest,index=ids,head_modes=modes,mixture_mode=mixture,gate=weights,JS_divergence=js);artifacts[str(dest.relative_to(ROOT))]=digest(dest);results[split]=summary;print('X00 components',split,summary,flush=True)
    for hook in hooks:hook.remove()
    immutable_json(REPORT/'X00-components.json',dict(results=results,artifacts=artifacts,checkpoint_sha256=digest(path),fit_report_sha256=digest(REPORT/'X00.json'),plan_sha256=digest(plan),source_sha256=digest(__file__),max_reconstruction_logp_difference=maxdiff,command='python -m tools.action_predictor.movement_experts.components',interpretation='Oracle union only of two CURRENT conditional head modes, not all output support or architecture ceiling. Mixture MAP can be outside either mode. Recorded family/answer only for evaluation after constructing distributions; no pseudo-intent supervision, oracle routing, smoothing or fit. No threshold/checkpoint changes.',new_fits=0,reserved_opened=0));print('X00 component diagnostic complete',flush=True)

if __name__=='__main__':run()
