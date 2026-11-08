"""Decompose saved control movement errors without fitting or tuning anything."""
import json
import numpy as np
import torch
from ..history_horizon.data import load,input_batch,geometry,targets,chunks
from ..history_horizon.engine import take,put
from ..history_horizon.model import Policy
from ..history_horizon.protocol import ROOT,WORK as HISTORY_WORK,REPORT as HISTORY_REPORT,SEED
from ..reliable_train import setup
from ..audit import immutable_json
from ..data import digest

REPORT=ROOT/'tools/action_predictor/experiments/v34'
WORK=ROOT/'.cambc/action-predictor/v34'


def decomposition(logp,gold,last):
    """Partition probability by exact previous displacement versus its complement.

    Complement includes every other tile and the two special buckets. This is
    a probability identity, not an inferred semantic intent label.
    """
    n=len(gold);index=np.arange(n)
    if not np.all((gold>=0)&(gold<289)&(last>=0)&(last<289)):raise ValueError('Known tiles required')
    if not np.allclose(np.logaddexp.reduce(logp,axis=1),0,atol=1e-8):raise ValueError('Unnormalized probabilities')
    repeat=gold==last;rest=logp.copy();rest[index,last]=-np.inf
    other_logp=np.logaddexp.reduce(rest,axis=1)
    group_logp=np.where(repeat,logp[index,last],other_logp)
    gold_logp=logp[index,gold]
    return dict(repeat_gold=repeat,p_repeat=np.exp(logp[index,last]),
        coordinate_nll=-gold_logp,group_nll=-group_logp,within_group_nll=group_logp-gold_logp,
        gold_rank=1+(logp>gold_logp[:,None]).sum(1),
        gold_rank_without_repeat=1+(rest>gold_logp[:,None]).sum(1),
        conditional_mode=logp.argmax(1),forced_nonrepeat_mode=rest.argmax(1))


def discrimination(probability,positive):
    """Tie-aware empirical AUC, fixed threshold and reliability bins."""
    probability=np.asarray(probability);positive=np.asarray(positive,dtype=bool)
    _,inverse,count=np.unique(probability,return_inverse=True,return_counts=True)
    ends=count.cumsum();ranks=ends-(count-1)/2
    pos=int(positive.sum());neg=len(positive)-pos
    auc=(ranks[inverse][positive].sum()-pos*(pos+1)/2)/(pos*neg) if pos and neg else None
    bins=[]
    for i in range(10):
        mask=(probability>=i/10)&((probability<(i+1)/10) if i<9 else (probability<=1))
        bins.append(dict(low=i/10,high=(i+1)/10,rows=int(mask.sum()),
            predicted=float(probability[mask].mean()) if mask.any() else None,
            observed=float(positive[mask].mean()) if mask.any() else None))
    return dict(rows=len(positive),positive=pos,AUC=float(auc) if auc is not None else None,
        Brier=float(np.mean((probability-positive)**2)),
        threshold_half_accuracy=float(np.mean((probability>=.5)==positive)),reliability=bins)


def measures(raw,ids,lp,type_lp):
    grid=raw['grid'][ids];gold=raw['py'][ids];previous=grid[:,:,18]
    known=previous.max(1)>0;last=previous.argmax(1);safe=(gold>=0)&(gold<289)&known
    rows=np.flatnonzero(safe);detail=decomposition(lp[safe],gold[safe],last[safe]);source=ids[safe]
    result={};direction=raw['direction'][source];i=np.arange(len(source))
    strata={'all_known_previous':np.ones(len(source),bool),'change':direction==3,'continue':direction==2,
        'change_full16':(direction==3)&(raw['history_gaps'][source,:,1].sum(1)==16),
        'change_missing_frames':(direction==3)&(raw['history_gaps'][source,:,1].sum(1)<16)}
    supported=raw['valid'][source,gold[safe]]&(grid[safe][i,gold[safe],5]>0)
    for name,mask in strata.items():
        result[name]=dict(rows=int(mask.sum()),current_support=int(supported[mask].sum()),
            coordinate_correct=int((detail['conditional_mode'][mask]==gold[safe][mask]).sum()),
            type_argmax_move=int((type_lp[safe][mask].argmax(1)==8).sum()),
            type_nll=float(-type_lp[safe][mask,8].mean()) if mask.any() else None,
            coordinate_nll=float(detail['coordinate_nll'][mask].mean()) if mask.any() else None,
            repeat_vs_other_nll=float(detail['group_nll'][mask].mean()) if mask.any() else None,
            within_chosen_group_nll=float(detail['within_group_nll'][mask].mean()) if mask.any() else None,
            average_repeat_probability=float(detail['p_repeat'][mask].mean()) if mask.any() else None,
            gold_rank_median=float(np.median(detail['gold_rank'][mask])) if mask.any() else None,
            gold_top3=int((detail['gold_rank'][mask]<=3).sum()),
            gold_is_exact_repeat=int(detail['repeat_gold'][mask].sum()),
            mode_repeats_previous=int((detail['conditional_mode'][mask]==last[safe][mask]).sum()),
            forced_nonrepeat_correct=int((detail['forced_nonrepeat_mode'][mask]==gold[safe][mask]).sum()))
    if not np.allclose(detail['coordinate_nll'],detail['group_nll']+detail['within_group_nll'],atol=1e-10):
        raise ValueError('Loss decomposition failed')
    return dict(total_movement_rows=len(ids),known_previous_tile_rows=len(source),
        unassessed_previous_or_gold=int((~safe).sum()),strata=result,
        nonrepeat_discrimination=discrimination(1-detail['p_repeat'],~detail['repeat_gold']),
        interpretation='Conditional head diagnostics, not achieved full commands. Forced-nonrepeat mode is an oracle intervention, not available policy accuracy or a complete ceiling. No causal shortcut or observation-sufficiency inference.')


@torch.no_grad()
def forecast(model,data):
    raw=data['arrays'];ids=np.flatnonzero(raw['y']==8);index=np.full(len(raw['y']),-1,np.int64);index[ids]=np.arange(len(ids))
    lp=np.full((len(ids),291),np.nan);type_lp=np.full((len(ids),15),np.nan)
    seen=np.zeros(len(raw['y']),np.uint8);state=model.empty(32);model.eval()
    for batch in chunks(data['sequences'],unroll=32):
        for row in batch:
            active=torch.from_numpy(np.flatnonzero(row>=0));at=row[row>=0]
            if not len(at):continue
            step=model.begin(**input_batch(data,at),state=take(state,active),reset8=True)
            geo=geometry(data,at)
            # Compute the movement conditional for every row BEFORE loading its
            # target; only archive the true-movement subset after this forecast.
            spatial=model.spatial(step,**geo,family=torch.full((len(at),),8,dtype=torch.long))
            typ=model.execution.action(step['context']).double().log_softmax(-1)
            target=targets(data,at);loss,post=model.observed(step,**geo,**target)
            if not torch.isfinite(loss).all():raise ValueError('Nonfinite checkpoint loss')
            state=put(state,active,post);seen[at]+=1
            move=target['y']==8;where=index[at[move.numpy()]]
            lp[where]=spatial[move].numpy();type_lp[where]=typ[move].numpy()
    if not np.all(seen==1) or not np.isfinite(lp).all() or not np.isfinite(type_lp).all():raise ValueError('Incomplete forecast')
    return dict(ids=ids,move_logp=lp,type_logp=type_lp)


def run():
    if WORK.exists():raise FileExistsError('Preserve prior diagnostic attempt')
    result_path=HISTORY_REPORT/'A.json';result=json.loads(result_path.read_text());epoch=result['selected']['movement']
    review_path=HISTORY_REPORT/'C-review.json';review=json.loads(review_path.read_text())
    if review['verdict']!='APPROVE' or review['result_sha256']!=digest(HISTORY_REPORT/'C.json'):
        raise ValueError('Completed study review not bound')
    bindings={str(p.relative_to(ROOT)):digest(p) for p in (result_path,review_path,HISTORY_REPORT/'protocol.json')}
    protocol=json.loads((HISTORY_REPORT/'protocol.json').read_text())
    if result['protocol_sha256']!=digest(HISTORY_REPORT/'protocol.json'):raise ValueError('Protocol changed')
    for key,expected in protocol['sources'].items():
        if digest(ROOT/key)!=expected:raise ValueError('Inference dependency changed: '+key)
    for path in (ROOT/'tools/action_predictor/experiments/v32/assembly.json',
                 ROOT/'.cambc/action-predictor/v32/features-v1/normalizer.npz'):
        key=str(path.relative_to(ROOT))
        if digest(path)!=protocol['inputs'][key]:raise ValueError('Feature manifest or normalizer changed')
        bindings[key]=digest(path)
    saved_path=HISTORY_WORK/'runs/A'/f'selected-{epoch:02d}-fit.npz'
    saved_key=str(saved_path.relative_to(ROOT))
    if digest(saved_path)!=result['bindings'][saved_key]:raise ValueError('Reference forecast changed')
    bindings[saved_key]=digest(saved_path)
    checkpoints={'initial':HISTORY_WORK/'runs/A/initial.pt','selected':HISTORY_WORK/'runs/A'/f'round-{epoch:02d}.pt'}
    for path in checkpoints.values():
        key=str(path.relative_to(ROOT))
        if digest(path)!=result['bindings'][key]:raise ValueError('Checkpoint changed')
        bindings[key]=digest(path)
    immutable_json(REPORT/'diagnostic-plan.json',dict(source_sha256=digest(__file__),bindings=bindings,
        checkpoint_policy='Only A initial and its frozen primary selected checkpoint; no retrospective model/selector selection.',
        partition='Only all65465fittingrows,10400recordedmoves. Causal replay of existinginputs; no tuning/assessment loading.',
        metrics='Type/coordinate NLL; exact-repeat/complement decomposition; conditional gold rank; oracle forced-nonrepeat mode; fixedthreshold.5,AUC,Brier and10equalwidth reliability bins; full16/missingframe strata.',
        restrictions='No optimizer, training, fitted recalibration, new labels, deployment, reservedgames or matches. No repeats or modelpromotion.',new_fits=0))
    WORK.mkdir(parents=True);setup(SEED);data=load('fit');summaries={};archives={}
    with np.load(saved_path) as z:saved={k:z[k] for k in z.files}
    for name,path in checkpoints.items():
        model=Policy();model.load_state_dict(torch.load(path,map_location='cpu',weights_only=False)['state'])
        output=forecast(model,data);archive=WORK/f'{name}.npz';np.savez_compressed(archive,**output);archives[str(archive.relative_to(ROOT))]=digest(archive)
        if name=='selected':
            ids=output['ids'];gold=data['arrays']['py'][ids];nll=-output['type_logp'][:,8]-output['move_logp'][np.arange(len(ids)),gold]
            if not np.array_equal(output['move_logp'].argmax(1),saved['coordinate'][ids]):raise ValueError('Selected modes changed')
            error=float(np.max(np.abs(nll-saved['nll'][ids])))
            if error>1e-6:raise ValueError('Selected likelihood changed')
        summaries[name]=measures(data['arrays'],output['ids'],output['move_logp'],output['type_logp'])
        print(name,json.dumps(summaries[name]['strata']['change']),flush=True)
    immutable_json(REPORT/'diagnostic.json',dict(plan_sha256=digest(REPORT/'diagnostic-plan.json'),
        source_sha256=digest(__file__),bindings=bindings,archives=archives,results=summaries,
        selected_forecast_nll_max_difference=error,new_fits=0,optimizer_updates=0,reserved_opened=0))


if __name__=='__main__':run()
