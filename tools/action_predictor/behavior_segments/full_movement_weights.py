"""Full-map weight fine-tuning without changing the policy architecture."""
import torch
from torch import nn

FROZEN=('code.','embeddings','query.','goal.')


class FullMovement(nn.Module):
    def __init__(self,backbone,correction):
        super().__init__();self.backbone=backbone;self.correction=correction
        for name,p in backbone.named_parameters():p.requires_grad_(not name.startswith(FROZEN))
        correction.requires_grad_(True)

    def forward(self,args):
        states=[];hook=self.backbone.code.register_forward_pre_hook(lambda module,values:states.append(values[0]))
        try:output=self.backbone(**{k:v for k,v in args.items() if k!='geometry'})
        finally:hook.remove()
        combined=torch.cat((states[0],args['geometry'].flatten(-2)),-1)
        move=self.correction(combined,output['code'].softmax(-1),output['move'])
        return dict(move=move,code=output['code'])
