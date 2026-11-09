"""Adapt existing map and trajectory weights; retain the forecast architecture."""
import torch
from torch import nn
from .full_movement_weights import FROZEN


class MapTrajectory(nn.Module):
    def __init__(self,net):
        super().__init__();self.backbone=net.backbone;self.correction=net.correction;self.heading=net.heading;self.commands=net.commands
        for name,p in self.backbone.named_parameters():p.requires_grad_(not name.startswith(FROZEN))
        for m in (self.correction,self.heading,self.commands):m.requires_grad_(True)

    def forward(self,args):
        states=[];hook=self.backbone.code.register_forward_pre_hook(lambda module,values:states.append(values[0]))
        try:out=self.backbone(**{k:v for k,v in args.items() if k not in ('geometry','heading','command_heading')})
        finally:hook.remove()
        prob=out['code'].softmax(-1);context=torch.cat((states[0],prob),-1)
        move=self.correction(torch.cat((states[0],args['geometry'].flatten(-2)),-1),prob,out['move'])
        move=self.heading(context,args['heading'],move);move=self.commands(context,args['command_heading'],move)
        return dict(move=move,code=out['code'],context=context)
