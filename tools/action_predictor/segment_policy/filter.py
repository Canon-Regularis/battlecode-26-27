"""Differentiable causal explicit-duration filter with conservative gap resets."""
import torch
from torch import nn
import torch.nn.functional as F


class NeuralSemiMarkov(nn.Module):
    def __init__(self,context_size,states=4,max_age=32):
        super().__init__()
        if states<3 or max_age<2:raise ValueError('At least three states and two ages required for learned non-self transitions')
        self.states,self.max_age=states,max_age
        self.initial=nn.Linear(context_size,states*max_age)
        self.transition=nn.Linear(context_size,states*(states-1))
        self.termination=nn.Linear(context_size,states)
        self.age_logits=nn.Parameter(torch.zeros(states,max_age-1))
        self.register_buffer('destinations',torch.tensor([[j for j in range(states) if j!=i] for i in range(states)]))

    def initial_logp(self,context):
        # Unknown segment prefix is a distribution over age, not a fabricated
        # segment start or a claim that every prior own root was observed.
        return self.initial(context).double().log_softmax(-1).reshape(-1,self.states,self.max_age)

    def factors(self,context):
        n=len(context)
        logits=self.transition(context).double().reshape(n,self.states,self.states-1).log_softmax(-1)
        transition=torch.full((n,self.states,self.states),-torch.inf,dtype=logits.dtype,device=context.device)
        transition=transition.scatter(2,self.destinations[None].expand(n,-1,-1),logits)
        hazard=self.termination(context).double()[:,:,None]+self.age_logits.double()[None]
        log_end=F.logsigmoid(hazard)
        # A declared finite duration truncation, not a Fish duration rule.
        log_end=torch.cat((log_end,torch.zeros_like(log_end[:,:,-1:])),2)
        log_stay=F.logsigmoid(-hazard)
        return transition,log_end,log_stay

    def predict(self,context,previous_logp,root_gap,prefix_unavailable):
        n=len(context)
        if previous_logp.shape!=(n,self.states,self.max_age):raise ValueError('State/age shape changed')
        if root_gap.shape!=(n,) or root_gap.dtype!=torch.int64 or bool((root_gap<1).any()):raise ValueError('Exact positive own-root gaps required')
        if prefix_unavailable.shape!=(n,) or prefix_unavailable.dtype!=torch.bool:raise ValueError('Explicit unavailable prefix required')
        transition,log_end,log_stay=self.factors(context)
        ending=torch.logsumexp(previous_logp+log_end,2)
        new_segment=torch.logsumexp(ending[:,:,None]+transition,1)
        continuing=previous_logp[:,:,:-1]+log_stay
        advanced=torch.cat((new_segment[:,:,None],continuing),2)
        reset=prefix_unavailable|(root_gap!=1)
        prior=torch.where(reset[:,None,None],self.initial_logp(context),advanced)
        # Never reuse current context to invent transitions in unobserved roots.
        # A reset marginalizes an unknown prefix instead of asserting continuity.
        return dict(logp=prior,unknown_prefix=reset,transition=transition,
                    termination_logp=log_end)

    def observe(self,prior,recorded_command_logp):
        """Call only AFTER this command occurred; no answer enters predict()."""
        if recorded_command_logp.shape!=prior['logp'].shape[:2]:raise ValueError('State-conditioned command likelihood required')
        joint=prior['logp']+recorded_command_logp[:,:,None]
        mass=torch.logsumexp(joint.flatten(1),1)
        return -mass,joint-mass[:,None,None]


class StateExecutionCondition(nn.Module):
    """Learned multiplicative/additive execution conditioning, no intent names.

    The caller must train its observation encoder and actual action/spatial heads
    jointly. This module is not a selector over frozen component distributions.
    """
    def __init__(self,context_size=128,states=4,code_size=32):
        super().__init__()
        self.codes=nn.Parameter(torch.randn(states,code_size)*.1)
        self.condition=nn.Linear(code_size,2*context_size)

    def forward(self,context):
        scale,shift=self.condition(self.codes).chunk(2,-1)
        return context[:,None]*(1+scale.tanh()[None])+shift[None]
