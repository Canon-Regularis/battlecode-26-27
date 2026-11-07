"""Training-derived integer point modes plus a normalized full-support fallback."""
import torch
from torch import nn
import torch.nn.functional as F
from .priority_head import EXTRA


def logistic_log_mass(raw, target):
    """Integer-bin logistic mass in float64, with arbitrary candidate dimensions.

    The identity avoids subtracting nearly equal CDFs. Scale bounds are the
    retained M01 bounds; targets/locations are never clipped to a vocabulary.
    """
    raw=raw.double();target=target.double()
    mean=raw[...,0];scale=raw[...,1].clamp(-6,5).exp()
    while mean.ndim<target.ndim:mean=mean.unsqueeze(-1);scale=scale.unsqueeze(-1)
    hi=(target/100+.005-mean)/scale;lo=(target/100-.005-mean)/scale
    return F.logsigmoid(hi)+F.logsigmoid(-lo)+torch.log(-torch.expm1(-.01/scale))


class AbsolutePriorityModes(nn.Module):
    """One linear output redesign; no new hidden layers or context encoder."""
    def __init__(self,original,values,counts,use_inputs=True):
        super().__init__()
        values=torch.as_tensor(values,dtype=torch.int64);counts=torch.as_tensor(counts,dtype=torch.float64)
        assert values.ndim==1 and len(values)>0 and len(values)==len(counts)
        assert bool((values[1:]>values[:-1]).all()) and bool((counts>0).all())
        self.register_buffer('values',values);self.use_inputs=use_inputs
        state=torch.get_rng_state();self.linear=nn.Linear(128+EXTRA,len(values)+3)
        with torch.no_grad():
            self.linear.weight.zero_();self.linear.bias.zero_()
            prior=torch.cat((.95*counts/counts.sum(),torch.tensor([.05],dtype=torch.float64)))
            self.linear.bias[:-2].copy_(prior.log().float())
            self.linear.weight[-2:,:128].copy_(original.weight);self.linear.bias[-2:].copy_(original.bias)
        torch.set_rng_state(state)

    def forward(self,context,features):
        if not self.use_inputs:features=torch.zeros_like(features)
        return self.linear(torch.cat((context,features),-1))

    def log_mass(self,raw,target):
        target=target.to(torch.int64)
        assert raw.ndim==2 and target.shape==(len(raw),)
        mix=raw[:,:-2].double().log_softmax(-1)
        index=torch.searchsorted(self.values,target);safe=index.clamp(max=len(self.values)-1)
        present=(index<len(self.values))&(self.values[safe]==target)
        point=mix.gather(1,safe[:,None]).squeeze(1).masked_fill(~present,-torch.inf)
        fallback=mix[:,-1]+logistic_log_mass(raw[:,-2:],target)
        return torch.logaddexp(point,fallback)

    def candidate_log_masses(self,raw):
        # A logistic integer distribution is maximized at the rounded location.
        # Every non-vocabulary integer has only fallback mass, so the global
        # mixture argmax lies in vocabulary UNION {rounded fallback location}.
        mix=raw[:,:-2].double().log_softmax(-1)
        center=(raw[:,-2].double()*100).round().to(torch.int64)
        candidates=torch.cat((self.values[None].expand(len(raw),-1),center[:,None]),-1)
        fallback=mix[:,-1,None]+logistic_log_mass(raw[:,-2:],candidates)
        point=torch.full_like(fallback,-torch.inf);point[:,:len(self.values)]=mix[:,:-1]
        index=torch.searchsorted(self.values,center);safe=index.clamp(max=len(self.values)-1)
        present=(index<len(self.values))&(self.values[safe]==center)
        point[:,-1]=mix.gather(1,safe[:,None]).squeeze(1).masked_fill(~present,-torch.inf)
        return candidates,torch.logaddexp(point,fallback)

    def integer(self,raw):
        candidates,logp=self.candidate_log_masses(raw)
        # Sorted vocabulary first, then fallback candidate; ties are deterministic.
        return candidates.gather(1,logp.argmax(-1)[:,None]).squeeze(1)
