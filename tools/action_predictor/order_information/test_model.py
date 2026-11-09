import unittest
import torch
from ..priority_residual_modes import AnchoredPriorityModes
from .model import OrderHead


class OrderModelTests(unittest.TestCase):
    def test_initial_output_and_rng_preserved(self):
        torch.manual_seed(34)
        base=AnchoredPriorityModes(torch.nn.Linear(128,2),[-3,1],[1,1],[-1,0],[1,1])
        before=torch.get_rng_state().clone()
        wrapper=OrderHead(base,True)
        self.assertTrue(torch.equal(before,torch.get_rng_state()))
        context=torch.randn(3,128);extra=torch.randn(3,39);order=torch.randn(3,32)
        torch.testing.assert_close(wrapper(context,extra,order),base(context,extra),rtol=0,atol=0)
        self.assertEqual(int(torch.count_nonzero(wrapper.order.weight)),0)

    def test_control_mask_remains_effective_with_nonzero_loaded_weights(self):
        base=AnchoredPriorityModes(torch.nn.Linear(128,2),[-3,1],[1,1],[-1,0],[1,1])
        wrapper=OrderHead(base,False)
        with torch.no_grad():wrapper.order.weight.fill_(.3)
        context=torch.randn(4,128);extra=torch.randn(4,39)
        a=wrapper(context,extra,torch.randn(4,32))
        b=wrapper(context,extra,torch.full((4,32),1000.))
        torch.testing.assert_close(a,base(context,extra),rtol=0,atol=0)
        torch.testing.assert_close(a,b,rtol=0,atol=0)


if __name__=='__main__':unittest.main()
