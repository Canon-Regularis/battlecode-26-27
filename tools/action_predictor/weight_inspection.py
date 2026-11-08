"""Read saved weights and causal fitting activations; never construct an optimizer."""
import json
from pathlib import Path
import numpy as np
import torch
from .neighborhood_movement.protocol import ROOT, build
from .neighborhood_movement.model import terrain_patch
from .gradient_routing.data import load_subset
from .history_horizon.data import chunks,input_batch,geometry,targets
from .history_horizon.engine import take,put
from .reliable_train import setup
from .data import digest
from .audit import immutable_json

REPORT=ROOT/'tools/action_predictor/experiments/v39'
WORK=ROOT/'.cambc/action-predictor/v39'


def stats(x):
    x=np.asarray(x,dtype=np.float64).ravel()
    if not len(x):return dict(n=0)
    if not np.isfinite(x).all():raise ValueError('Nonfinite statistic')
    return dict(n=len(x),mean=float(x.mean()),rms=float(np.sqrt(np.mean(x*x))),
        minimum=float(x.min()),p10=float(np.quantile(x,.1)),median=float(np.median(x)),
        p90=float(np.quantile(x,.9)),maximum=float(x.max()))


def distribution(tile,special,valid,support):
    """Original movement support mixture, including special buckets/fallback."""
    logits=torch.cat((tile.masked_fill(~valid,-1e4),special),-1)
    allowed=valid&support
    complete=torch.cat((allowed,torch.zeros(len(tile),2,dtype=torch.bool)),1)
    complete[~allowed.any(-1)]=True
    return torch.logaddexp(logits.masked_fill(~complete,-1e4).log_softmax(-1)+torch.log(logits.new_tensor(.9999)),
        logits.log_softmax(-1)+torch.log(logits.new_tensor(.0001))).double().log_softmax(-1)


def diagnostics(lp,gold,direction):
    result={};p=lp.numpy();gold=np.asarray(gold);index=np.arange(len(gold))
    for name,mask in [('all',np.ones(len(gold),bool)),('change',direction==3),('continue',direction==2)]:
        result[name]=dict(rows=int(mask.sum()),conditional_correct=int((p.argmax(1)[mask]==gold[mask]).sum()),
            coordinate_nll=float(-p[index,gold][mask].mean()))
    return result


@torch.no_grad()
def run():
    plan_path=REPORT/'plan.json';plan=json.loads(plan_path.read_text())
    for k,v in plan['bindings'].items():
        if digest(ROOT/k)!=v:raise ValueError('Bound artifact changed: '+k)
    WORK.mkdir(parents=True,exist_ok=False)
    setup(27);data=load_subset();raw=data['arrays']
    paths={a:ROOT/f'.cambc/action-predictor/{v}/runs/{a}' for a,v in [('R00','v36'),('N00','v38'),('N01','v38')]}
    states={a:torch.load(p/'round-08.pt',map_location='cpu',weights_only=False)['state'] for a,p in paths.items()}
    initials={a:torch.load(p/'initial.pt',map_location='cpu',weights_only=False)['state'] for a,p in paths.items()}
    model=build('N01');model.load_state_dict(states['N01']);model.eval()
    control=build('N00');control.load_state_dict(states['N00']);control.eval()
    ids=np.flatnonzero(raw['y']==8);reverse=np.full(len(raw['y']),-1);reverse[ids]=np.arange(len(ids))
    contexts=np.full((len(ids),128),np.nan,np.float32);memory_part=np.zeros_like(contexts)
    history_part=np.zeros_like(contexts);state=model.empty(32);seen=np.zeros(len(raw['y']),np.uint8)
    # Forecast context is collected before the current command is assimilated.
    for batch in chunks(data['sequences'],unroll=32):
        for row in batch:
            at=row[row>=0];active=torch.from_numpy(np.flatnonzero(row>=0))
            if not len(at):continue
            inputs=input_batch(data,at);step=model.begin(**inputs,state=take(state,active),reset8=True)
            move=raw['y'][at]==8;ix=reverse[at[move]]
            contexts[ix]=step['context'][move].numpy()
            memory_part[ix]=model.memory_projection(step['hidden'])[move].numpy()
            _,direct=model.execution(inputs['x'],inputs['history'])
            history_part[ix]=(step['base']-direct)[move].numpy()
            _,post=model.observed(step,**geometry(data,at),**targets(data,at))
            state=put(state,active,post);seen[at]+=1
    assert np.all(seen==1) and np.isfinite(contexts).all()
    np.savez_compressed(WORK/'contexts.npz',ids=ids,context=contexts,memory=memory_part,observation_history_and_priority=history_part)
    saved={}
    for a,p in paths.items():
        with np.load(p/'final-movement.npz') as z:
            assert np.array_equal(z['ids'],ids);saved[a]=torch.from_numpy(z['move_logp'].copy())
    weights={}
    for arm,state_dict in states.items():
        weights[arm]={}
        for name,value in state_dict.items():
            start=initials[arm][name];a=value.double();delta=a-start.double()
            weights[arm][name]=dict(shape=list(a.shape),rms=float(a.square().mean().sqrt()),
                update_rms=float(delta.square().mean().sqrt()),finite=bool(torch.isfinite(a).all()))
    bias=states['R00']['execution.offset_bias.weight'][8];init_bias=initials['R00']['execution.offset_bias.weight'][8]
    bias_stats=dict(initial=stats(init_bias[:289]),final=stats(bias[:289]),update=stats(bias[:289]-init_bias[:289]),
        correlation=float(np.corrcoef(init_bias[:289],bias[:289])[0,1]))
    names=['R00','N00','N01','R00_cancel_initial_offset','R00_zero_final_offset','R00_zero_previous_channels',
        'R00_without_memory_projection','R00_without_observation_history_priority_projection']
    scores={name:[] for name in names};activation={k:[] for k in ('candidate_derivative','N00_derivative','N01_derivative',
        'candidate_score_span','offset_span','N00_residual_span','N01_residual_span','N00_common_context_rms','N01_common_context_rms')}
    pair={};n=len(ids)
    for start in range(0,n,128):
        stop=min(start+128,n);at=ids[start:stop];ctx=torch.from_numpy(contexts[start:stop]);g=geometry(data,at)
        grid=g['grid'];valid=g['valid'];allowed=valid&(grid[:,:,5]>0);family=torch.full((len(at),),8,dtype=torch.long)
        ex=model.execution;query=ex.query(ctx)+ex.family(family)
        emb=ex.candidate(grid);dynamic=(emb*query[:,None]).sum(-1)/5.657
        special=ex.special(ctx)+bias[289:]
        residuals={'N00':control.residual(ctx,grid),'N01':model.residual(ctx,grid)}
        base=dynamic+bias[:289]
        tile_scores={'R00':base,**{a:base+res for a,res in residuals.items()}}
        tile_scores['R00_cancel_initial_offset']=base-init_bias[:289]
        tile_scores['R00_zero_final_offset']=dynamic
        altered=grid.clone();altered[:,:,18:20]=0
        tile_scores['R00_zero_previous_channels']=(ex.candidate(altered)*query[:,None]).sum(-1)/5.657+bias[:289]
        for name,part in [('R00_without_memory_projection',memory_part),('R00_without_observation_history_priority_projection',history_part)]:
            changed=ctx-torch.from_numpy(part[start:stop]);q=ex.query(changed)+ex.family(family)
            tile_scores[name]=(emb*q[:,None]).sum(-1)/5.657+bias[:289]
        for name,tile in tile_scores.items():
            sp=special
            if name=='R00_cancel_initial_offset':sp=sp-init_bias[289:]
            elif name=='R00_zero_final_offset':sp=sp-bias[289:]
            elif name.startswith('R00_without_'):
                part=memory_part if name=='R00_without_memory_projection' else history_part
                sp=ex.special(ctx-torch.from_numpy(part[start:stop]))+bias[289:]
            scores[name].append(distribution(tile,sp,valid,grid[:,:,5]>0))
        derivative=1-ex.candidate[1](ex.candidate[0](grid)).square()
        activation['candidate_derivative'].append(derivative[allowed].numpy())
        for a,m in [('N00',control),('N01',model)]:
            pre=m.tile_projection(torch.cat((grid,terrain_patch(grid,m.use_neighborhood)),-1))+m.context_projection(ctx)[:,None]
            activation[a+'_derivative'].append((1-torch.tanh(pre).square())[allowed].numpy())
            activation[a+'_common_context_rms'].append(m.context_projection(ctx).square().mean(-1).sqrt().numpy())
        for key,value in [('candidate_score_span',dynamic),('offset_span',bias[:289].expand(len(at),-1)),
                          ('N00_residual_span',residuals['N00']),('N01_residual_span',residuals['N01'])]:
            span=value.masked_fill(~allowed,-float('inf')).max(-1).values-value.masked_fill(~allowed,float('inf')).min(-1).values
            activation[key].append(span[allowed.any(-1)].numpy())
        # Exact additive logit accounting for gold versus the baseline's strongest wrong tile.
        gold=raw['py'][at];direction=raw['direction'][at]
        baseline=saved['R00'][start:stop].clone();ix=torch.arange(len(at));baseline[ix,gold]=-float('inf')
        rival=baseline.argmax(-1);last=grid[:,:,18].argmax(-1)
        for cohort,rv in [('strongest_wrong',rival),('strongest_wrong_nonrepeat',baseline.scatter(1,last[:,None],-float('inf')).argmax(-1))]:
            mask=(direction==3)&(gold<289)&(rv.numpy()<289)
            rr=rv.clamp_max(288);gg=torch.from_numpy(gold).clamp_max(288)
            mask &= (allowed[ix,rr]&allowed[ix,gg]).numpy()
            values=dict(ids=at,gold=gold,rival=rv.numpy(),is_repeat=(rv==last).numpy(),
                baseline_margin=(saved['R00'][start:stop][ix,rv]-saved['R00'][start:stop][ix,gold]).numpy(),
                dynamic_margin=(dynamic[ix,rr]-dynamic[ix,gg]).numpy(),
                initial_bias_margin=(init_bias[rr]-init_bias[gg]).numpy(),
                learned_bias_update_margin=((bias-init_bias)[rr]-(bias-init_bias)[gg]).numpy(),
                N01_correction_margin=(residuals['N01'][ix,rr]-residuals['N01'][ix,gg]).numpy())
            for k,v in values.items():pair.setdefault(cohort+'_'+k,[]).append(np.asarray(v)[mask])
    scores={k:torch.cat(v) for k,v in scores.items()};pair={k:np.concatenate(v) for k,v in pair.items()}
    parity={}
    for arm in ('R00','N00','N01'):
        error=float((scores[arm]-saved[arm]).abs().max());modes=int((scores[arm].argmax(1)!=saved[arm].argmax(1)).sum())
        assert error<1e-5 and modes==0,(arm,error,modes)
        parity[arm]=dict(max_log_probability_error=error,mode_disagreements=modes)
    np.savez_compressed(WORK/'diagnostics.npz',**{k:v.numpy() for k,v in scores.items()},**pair)
    act={}
    for key,pieces in activation.items():
        value=np.concatenate(pieces);act[key]=stats(value)
        if key.endswith('derivative'):
            act[key]['fraction_below_001']=float((value<.01).mean())
            act[key]['fraction_below_01']=float((value<.1).mean())
            act[key]['per_unit_mean']=value.mean(0).tolist()
    pairs={}
    for cohort in ('strongest_wrong','strongest_wrong_nonrepeat'):
        prefix=cohort+'_';margin=pair[prefix+'baseline_margin'];bad=margin>0
        total=pair[prefix+'dynamic_margin']+pair[prefix+'initial_bias_margin']+pair[prefix+'learned_bias_update_margin']
        assert np.max(np.abs(total-margin))<1e-5
        pairs[cohort]=dict(supported_pairs=len(margin),wrong=int(bad.sum()),
            wrong_repeat=int(pair[prefix+'is_repeat'][bad].sum()),
            wrong_initial_bias_favors_rival=int((pair[prefix+'initial_bias_margin'][bad]>0).sum()),
            wrong_dynamic_favors_gold=int((pair[prefix+'dynamic_margin'][bad]<0).sum()),
            wrong_N01_correction_favors_gold=int((pair[prefix+'N01_correction_margin'][bad]<0).sum()),
            wrong_N01_correction_exceeds_original_margin=int((pair[prefix+'N01_correction_margin'][bad]<-margin[bad]).sum()),
            components={k:stats(v[bad]) for k,v in pair.items() if k.startswith(prefix) and k.endswith('margin')},
            max_decomposition_error=float(np.max(np.abs(total-margin))))
    result=dict(plan_sha256=digest(plan_path),weights=weights,movement_offset_bias=bias_stats,
        causal_rows=len(raw['y']),movement_rows=n,parity=parity,activations=act,pair_decomposition=pairs,
        conditional_interventions={k:diagnostics(v,raw['py'][ids],raw['direction'][ids]) for k,v in scores.items()},
        residual_global_pairwise_bound={a:float(2*states[a]['residual_readout.weight'].abs().sum()) for a in ('N00','N01')},
        bindings={str(p.relative_to(ROOT)):digest(p) for p in WORK.iterdir() if p.is_file()},
        interpretation='Checkpoint-local counterfactuals, not retrained models or achievable policy results. Ablations may be out of distribution; no checkpoint selection, optimization or generalization claim.',new_fits=0,optimizer_updates=0)
    immutable_json(REPORT/'audit.json',result)
    print(json.dumps({k:v for k,v in result.items() if k not in ('weights','activations','bindings')},indent=2))


if __name__=='__main__':run()
