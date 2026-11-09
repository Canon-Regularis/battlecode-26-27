import copy,unittest
import torch
from torch.nn import functional as F
from . import model
from .full_movement_weights import FullMovement,FROZEN
from .joint_movement_weights import inference
from .code_path_movement import PathCorrection,candidate_features
from .test_model import CausalPolicyTests


class FullMovementTests(unittest.TestCase):
    def fixture(self):
        w,r,k=CausalPolicyTests().fixture();args,_=model.encode_window(w,r,k)
        args['geometry']=torch.stack([candidate_features(s['input'],r) for s in w['steps']])
        net=FullMovement(model.SegmentPolicy(k),PathCorrection(torch.ones(8)/8));support,labels=model.move_support(w)
        return net,args,support,labels

    def test_inference_parity_and_encoder_gradients(self):
        net,args,support,labels=self.fixture();reference=inference(copy.deepcopy(net));before=copy.deepcopy(net.state_dict())
        with torch.no_grad():a=net(args);b=reference(**args)
        for key in ('move','code'):self.assertTrue(torch.equal(a[key],b[key]))
        out=net(args);F.cross_entropy(out['move'].masked_fill(~support,-1e9),labels).backward()
        active=[p for p in net.parameters() if p.requires_grad]
        self.assertTrue(all(p.grad is not None and torch.isfinite(p.grad).all() for p in active))
        torch.optim.AdamW(active,lr=.001).step()
        for name,p in net.backbone.named_parameters():
            if name.startswith(FROZEN):self.assertTrue(torch.equal(p,before['backbone.'+name]),name)
        self.assertFalse(torch.equal(net.backbone.maps.input.weight,before['backbone.maps.input.weight']))

    def test_window_gradient_accumulation_matches_combined_objective(self):
        net,args,support,labels=self.fixture();reference=copy.deepcopy(net);denominator=len(labels)*2
        for _ in range(2):
            out=net(args);loss=F.cross_entropy(out['move'].masked_fill(~support,-1e9),labels,reduction='sum')/denominator;loss.backward()
        losses=[]
        for _ in range(2):losses.append(F.cross_entropy(reference(args)['move'].masked_fill(~support,-1e9),labels,reduction='sum'))
        (sum(losses)/denominator).backward()
        for (name,p),(name2,q) in zip(net.named_parameters(),reference.named_parameters()):
            if p.requires_grad:torch.testing.assert_close(p.grad,q.grad,atol=2e-7,rtol=1e-5)


if __name__=='__main__':unittest.main()
