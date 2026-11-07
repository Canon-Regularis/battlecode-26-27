"""Sequential forward policy evaluation; answers consumed only after prediction."""
import numpy as np
import torch
from .data import chunks,causal_inputs,geometry,targets

def select_state(previous,current,mask):
    return {key:torch.where(mask.reshape((-1,)+(1,)*(value.ndim-1)),value,previous[key]) for key,value in current.items()}

@torch.no_grad()
def infer(model,d,decode=True):
    model.eval();n=len(d['raw']['y']);state=model.empty(32);out={key:np.full(n,-1,np.int64) for key in ('prediction','coordinate','proposed_coordinate')};out.update(priority=d['priority_mode'].copy(),top5=np.full((n,5),-1,np.int64),nll=np.zeros(n,np.float64),type_nll=np.zeros(n,np.float64),param_nll=np.zeros(n,np.float64));goals=dict(prior=np.zeros((n,4),np.float32),world=np.zeros((n,4,2),np.float32),retention=np.zeros(n,np.float32),achievement_nll=np.full(n,np.nan,np.float32));seen=np.zeros(n,np.uint8)
    for rows in chunks(d['sequences']):
        for ids in rows:
            valid=ids>=0;ix=np.maximum(ids,0);mask=torch.from_numpy(valid);step=model.begin(**causal_inputs(d,ix),state=state);geo=geometry(d,ix)
            # Decode before reading the current answer or future achieved target.
            if decode:
                pred=model.decode(step,**geo,priority_mode=torch.from_numpy(d['priority_mode'][ix]),priority_mode_logp=torch.from_numpy(d['priority_mode_logp'][ix]));out['prediction'][ids[valid]]=pred['prediction'].numpy()[valid];out['proposed_coordinate'][ids[valid]]=pred['coordinate'].numpy()[valid]
            target=targets(d,ix);loss,post=model.observed(step,**geo,**{k:target[k] for k in ('y','py','priority_parameter_nll')});out['nll'][ids[valid]]=loss.numpy()[valid];goals['prior'][ids[valid]]=step['logprior'].exp().numpy()[valid];goals['world'][ids[valid]]=step['world'].numpy()[valid];goals['retention'][ids[valid]]=step['retain'].numpy()[valid];gmask=target['achievement_available'].numpy()&valid;gnll=model.achieved_goal_loss(step,target['achieved'],target['achievement_available']).numpy();goals['achievement_nll'][ids[gmask]]=gnll[gmask]
            if decode:
                y=target['y'].numpy();t=-pred['type_logp'][torch.arange(32),target['y']].numpy();out['type_nll'][ids[valid]]=t[valid];out['param_nll'][ids[valid]]=loss.numpy()[valid]-t[valid]
                for family,lp in pred['parameter_logp'].items():
                    m=valid&(y==family)
                    if m.any():out['coordinate'][ids[m]]=lp.argmax(-1).numpy()[m];out['top5'][ids[m]]=lp.topk(5,-1).indices.numpy()[m]
            state=select_state(state,post,mask);seen[ids[valid]]+=1
    assert np.all(seen==1),'Each original row predicted once, no easier denominator'
    if decode:
        typed=(out['prediction']==d['raw']['y'])&(d['raw']['py']>=0);np.testing.assert_array_equal(out['coordinate'][typed],out['proposed_coordinate'][typed])
    return out,goals
