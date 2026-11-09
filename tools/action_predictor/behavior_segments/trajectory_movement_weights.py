"""Jointly adapt existing recurrent and movement weights with causal direction inputs."""
import torch
from torch import nn
from . import code_weight_fit as recurrent
from .joint_movement_weights import ACTIVE
from .code_path_movement import PathMovementPolicy
from .heading_movement import HeadingPolicy
from .command_movement import CommandPolicy


class TrajectoryMovement(nn.Module):
    def __init__(self,backbone,correction,heading,commands):
        super().__init__();self.backbone=backbone;self.correction=correction;self.heading=heading;self.commands=commands
        for name,p in backbone.named_parameters():p.requires_grad_(name.startswith(ACTIVE))
        for m in (correction,heading,commands):m.requires_grad_(True)

    def forward(self,item):
        states=[];hook=self.backbone.code.register_forward_pre_hook(lambda module,args:states.append(args[0]))
        try:code=recurrent.code_forward(self.backbone,item)
        finally:hook.remove()
        probabilities=code.softmax(-1);context=torch.cat((states[0],probabilities),-1)
        move=self.backbone.movement(torch.cat((states[0],probabilities@self.backbone.embeddings),-1))
        move=self.correction(torch.cat((states[0],item['geometry'].flatten(-2)),-1),probabilities,move)
        move=self.heading(context,item['heading'],move)
        return dict(move=self.commands(context,item['command_heading'],move),code=code)


def inference(net):return CommandPolicy(HeadingPolicy(PathMovementPolicy(net.backbone,net.correction),net.heading),net.commands).eval()
