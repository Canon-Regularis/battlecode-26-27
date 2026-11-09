"""Same P05 probability head with a zero-initialized information interface."""
import torch
from torch import nn
from .schema_asinh import FIELDS


class OrderHead(nn.Module):
    def __init__(self,base,use_order):
        super().__init__()
        self.base=base
        self.use_order=bool(use_order)
        rng=torch.get_rng_state()
        self.order=nn.Linear(len(FIELDS),base.linear.out_features,bias=False)
        nn.init.zeros_(self.order.weight)
        torch.set_rng_state(rng)

    def forward(self,context,features,order):
        if not self.use_order:
            order=torch.zeros_like(order)
        return self.base(context,features)+self.order(order)

    @property
    def absolute(self):return self.base.absolute
    @property
    def residual(self):return self.base.residual
    def components(self,raw,values):return self.base.components(raw,values)
    def log_mass(self,raw,target,values):return self.base.log_mass(raw,target,values)
    def candidate_log_masses(self,raw,values):return self.base.candidate_log_masses(raw,values)
    def integer(self,raw,values):return self.base.integer(raw,values)
