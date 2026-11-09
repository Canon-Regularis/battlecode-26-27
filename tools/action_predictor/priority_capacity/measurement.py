"""Exact modes, bounded distinct-candidate ranks and marginalized credits."""
import torch
from ..priority_modes import logistic_log_mass


def distinct_candidate_rank(candidates, logmass, target, target_logmass):
    # P05 returns sorted candidates. Count each integer once; ties choose lower.
    first=torch.ones_like(candidates,dtype=torch.bool)
    first[:,1:]=candidates[:,1:]!=candidates[:,:-1]
    same=candidates==target[:,None]
    # Reuse the candidate arithmetic for a present target, avoiding a tiny
    # regrouping discrepancy that could otherwise rank an integer above itself.
    at=same.long().argmax(-1)
    reference=torch.where(same.any(-1),logmass.gather(1,at[:,None])[:,0],target_logmass)
    better=(candidates!=target[:,None])&((logmass>reference[:,None])|
        ((logmass==reference[:,None])&(candidates<target[:,None])))
    return 1+(first&better).sum(-1)


@torch.no_grad()
def target_credits(model,raw,values,target):
    points,mix=model.components(raw,values)
    count=len(model.absolute)
    absolute=mix[:,:count].masked_fill(points[:,:count]!=target[:,None],-torch.inf).logsumexp(-1)
    residual=mix[:,count:-1].masked_fill(points[:,count:]!=target[:,None],-torch.inf).logsumexp(-1)
    fallback=mix[:,-1]+logistic_log_mass(raw[:,-2:],target)
    source=torch.stack((absolute,residual,fallback),-1)
    total=source.logsumexp(-1)
    return total,(source-total[:,None]).exp()


@torch.no_grad()
def measure(model,raw,values,target):
    candidates,masses=model.candidate_log_masses(raw,values)
    mode=candidates.gather(1,masses.argmax(-1)[:,None])[:,0]
    total,credit=target_credits(model,raw,values,target)
    torch.testing.assert_close(total,model.log_mass(raw,target,values),rtol=1e-12,atol=1e-12)
    rank=distinct_candidate_rank(candidates,masses,target,total)
    error=(mode-target).abs()
    return dict(integer=mode,nll=-total,rank=rank,credit=credit),dict(
        rows=len(target),exact=int((mode==target).sum()),accuracy=float((mode==target).double().mean()),
        mean_NLL=float((-total).mean()),mean_absolute_integer_error=float(error.double().mean()),
        integer_error_quantiles=error.double().quantile(torch.tensor([0,.25,.5,.75,.9,1.],dtype=torch.float64)).tolist(),
        mean_rank_among_distinct_point_and_fallback_mode_candidates=float(rank.double().mean()),
        mean_target_probability_source_shares=credit.mean(0).tolist(),
        rank_scope='Existing distinct P05 points and floor/ceil fallback modes; not rank over all integers.',
        explanation_scope='Absolute/residual/fallback posterior shares of recorded-target mass, '
                          'not Fish intent or unique true explanation.')
