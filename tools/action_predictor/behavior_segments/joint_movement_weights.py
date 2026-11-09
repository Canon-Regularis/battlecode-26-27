"""Weight-only recurrent movement adaptation with frozen-code distillation."""
import torch
from torch import nn
from torch.nn import functional as F
from .code_path_movement import PathCorrection,PathMovementPolicy
from . import code_weight_fit as recurrent

ACTIVE=('context.','memory.','movement.')


class JointMovement(nn.Module):
    def __init__(self,backbone,correction):
        super().__init__();self.backbone=backbone;self.correction=correction
        for name,p in self.backbone.named_parameters():p.requires_grad_(name.startswith(ACTIVE))
        self.correction.requires_grad_(True)

    def forward(self,item):
        captured=[];hook=self.backbone.code.register_forward_pre_hook(lambda module,args:captured.append(args[0]))
        try:code=recurrent.code_forward(self.backbone,item)
        finally:hook.remove()
        states=captured[0];probabilities=code.softmax(-1)
        baseline=self.backbone.movement(torch.cat((states,probabilities@self.backbone.embeddings),-1))
        combined=torch.cat((states,item['geometry'].flatten(-2)),-1)
        return dict(move=self.correction(combined,probabilities,baseline),code=code)


def losses(output,item,coefficient):
    mask=item['movement_labels']>=0;observed=item['observed'].bool()
    logits=output['move'].masked_fill(~item['support'],-1e9)
    movement=F.cross_entropy(logits[mask],item['movement_labels'][mask]) if mask.any() else logits.sum()*0
    distillation=F.kl_div(output['code'][observed].log_softmax(-1),item['teacher'][observed],reduction='batchmean')
    return movement+coefficient*distillation,movement,distillation


def inference(net):return PathMovementPolicy(net.backbone,net.correction).eval()
