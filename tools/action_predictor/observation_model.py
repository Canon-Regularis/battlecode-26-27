"""Only history input changes: M01 GRU and all non-history paths/heads retained."""
import torch
from torch import nn

from .reliable_model import JointModel


class ObservationHistoryModel(JointModel):
    def __init__(self,inputs,action_features,classes,config):
        super().__init__(inputs,action_features,classes,config)
        assert config['history']==16 and config['rich'] and config['spatial']
        state=torch.get_rng_state()
        original=self.history
        self.observation=nn.Sequential(nn.Linear(inputs,32),nn.ReLU())
        self.history=nn.GRU(action_features+32+5,64,batch_first=True)
        with torch.no_grad():
            self.history.weight_ih_l0.zero_()
            self.history.weight_ih_l0[:,:action_features].copy_(original.weight_ih_l0)
            for name in ('weight_hh_l0','bias_ih_l0','bias_hh_l0'):
                getattr(self.history,name).copy_(getattr(original,name))
        torch.set_rng_state(state)

    def forward(self,x,history,observations,gaps):
        if not self.config['observations']:
            observations=torch.zeros_like(observations)
        encoded=self.observation(observations)*gaps[:,:,1:2]
        sequence=torch.cat((history[:,-16:],encoded,gaps),-1)
        _,h=self.history(sequence)
        context=self.combine(torch.cat((self.current(x),h[-1]),-1))
        return self.action(context),context
