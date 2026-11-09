"""P05: absolute modes and learned residuals around a causal negative anchor."""
import torch
from torch import nn
from .priority_head import EXTRA
from .priority_modes import logistic_log_mass


class AnchoredPriorityModes(nn.Module):
    def __init__(self, original, absolute, absolute_counts, residual, residual_counts):
        super().__init__()
        for name, values, counts in (('absolute', absolute, absolute_counts), ('residual', residual, residual_counts)):
            values=torch.as_tensor(values,dtype=torch.int64)
            counts=torch.as_tensor(counts,dtype=torch.float64)
            assert values.ndim==1 and len(values)>0 and values.shape==counts.shape
            assert bool((values[1:]>values[:-1]).all()) and bool((counts>0).all())
            self.register_buffer(name,values)
        state=torch.get_rng_state()
        self.linear=nn.Linear(128+EXTRA,len(absolute)+len(residual)+3)
        with torch.no_grad():
            self.linear.weight.zero_()
            a=torch.as_tensor(absolute_counts,dtype=torch.float64)
            r=torch.as_tensor(residual_counts,dtype=torch.float64)
            prior=torch.cat((.475*a/a.sum(),.475*r/r.sum(),torch.tensor([.05],dtype=torch.float64)))
            self.linear.bias[:-2].copy_(prior.log().float())
            self.linear.weight[-2:,:128].copy_(original.weight)
            self.linear.bias[-2:].copy_(original.bias)
        torch.set_rng_state(state)

    def forward(self,context,features):
        return self.linear(torch.cat((context,features),-1))

    def components(self,raw,values):
        assert raw.ndim==2 and values.dtype==torch.int64 and values.shape==(len(raw),7)
        assert bool(((values[:,5]==0)|(values[:,5]==1)).all())
        assert bool((values[values[:,5]==0,4]==0).all())
        # Replay priorities are signed int32. Use checked int64 arithmetic;
        # arbitrary output integers are not clipped to this input domain.
        assert bool(((values[:,4]>=-(2**31))&(values[:,4]<2**31)).all())
        anchor=-values[:,4]
        assert int(self.residual.min())>=-(2**32) and int(self.residual.max())<=2**32
        points=torch.cat((self.absolute[None].expand(len(raw),-1),anchor[:,None]+self.residual[None]),-1)
        logits=raw[:,:-2].double().clone()
        logits[:,len(self.absolute):-1]=logits[:,len(self.absolute):-1].masked_fill(values[:,5,None]==0,-torch.inf)
        return points,logits.log_softmax(-1)

    def log_mass(self,raw,target,values):
        assert target.dtype==torch.int64 and target.shape==(len(raw),)
        points,mix=self.components(raw,values)
        mass=mix[:,:-1].masked_fill(points!=target[:,None],-torch.inf).logsumexp(-1)
        fallback=mix[:,-1]+logistic_log_mass(raw[:,-2:],target)
        return torch.logaddexp(mass,fallback)

    @torch.no_grad()
    def candidate_log_masses(self,raw,values):
        points,mix=self.components(raw,values)
        center=raw[:,-2].double()*100
        assert bool(torch.isfinite(center).all()) and bool((center.abs()<2**62).all())
        candidates=torch.cat((points,center.floor().long()[:,None],center.ceil().long()[:,None]),-1)
        weights=torch.cat((mix[:,:-1],torch.full((len(raw),2),-torch.inf,dtype=torch.float64,device=raw.device)),-1)
        candidates,order=candidates.sort(-1)
        weights=weights.gather(1,order)
        first=torch.ones_like(candidates,dtype=torch.bool)
        first[:,1:]=candidates[:,1:]!=candidates[:,:-1]
        groups=first.long().cumsum(-1)-1
        maxima=torch.full_like(weights,-torch.inf).scatter_reduce(1,groups,weights,reduce='amax',include_self=True)
        safe=maxima.masked_fill(~torch.isfinite(maxima),0)
        sums=torch.zeros_like(weights).scatter_add(1,groups,(weights-safe.gather(1,groups)).exp())
        point=(sums.log()+safe).gather(1,groups)
        fallback=mix[:,-1,None]+logistic_log_mass(raw[:,-2:],candidates)
        return candidates,torch.logaddexp(point,fallback)

    def integer(self,raw,values):
        candidates,mass=self.candidate_log_masses(raw,values)
        # Sorted coordinates: equal-probability maxima choose the smaller integer.
        return candidates.gather(1,mass.argmax(-1)[:,None]).squeeze(1)
