import copy,unittest
import torch
from .test_joint_movement import JointMovementTests
from .heading_movement import HeadingCorrection
from .command_movement import CommandCorrection
from .trajectory_movement_weights import TrajectoryMovement,inference
from .joint_movement_weights import losses


class TrajectoryMovementTests(unittest.TestCase):
    def test_cached_forward_gradients_and_frozen_weights(self):
        base,item,args=JointMovementTests().fixture();h=HeadingCorrection(0);c=CommandCorrection(16)
        with torch.no_grad():h.weights.weight.normal_(std=.02);c.weights[-1].weight.normal_(std=.02)
        n=len(args['observed']);item['heading']=torch.randn(1,n,9,4);item['command_heading']=torch.randn(1,n,9,8)
        args=dict(args,heading=item['heading'][0],command_heading=item['command_heading'][0])
        net=TrajectoryMovement(base.backbone,base.correction,h,c);before=copy.deepcopy(net.state_dict());reference=inference(copy.deepcopy(net))
        with torch.no_grad():a=net(item);b=reference(**args)
        for k in ('move','code'):torch.testing.assert_close(a[k][0],b[k],atol=2e-6,rtol=2e-5)
        parameters=[p for p in net.parameters() if p.requires_grad];self.assertEqual(sum(p.numel() for p in parameters),25569)
        loss,_,_=losses(net(item),item,1.);loss.backward();self.assertTrue(all(p.grad is not None and torch.isfinite(p.grad).all() for p in parameters))
        torch.optim.AdamW(parameters,lr=.001).step()
        for name,p in net.named_parameters():
            if not p.requires_grad:self.assertTrue(torch.equal(p,before[name]))


if __name__=='__main__':unittest.main()
