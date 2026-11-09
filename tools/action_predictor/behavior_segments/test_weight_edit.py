import unittest
import torch
from .weight_edit import edit
from . import model


class EditTests(unittest.TestCase):
    def test_history_weight_edit_equals_input_scaling(self):
        from .test_model import CausalPolicyTests
        w,r,k=CausalPolicyTests().fixture();w['steps'][1]['previous'][0]=.7
        args,_=model.encode_window(w,r,k);torch.manual_seed(2);net=model.SegmentPolicy(k).eval()
        modified=model.SegmentPolicy(k).eval();modified.load_state_dict(edit(net.state_dict(),[.5,.5,0,0,0,0,0,0],5,0))
        with torch.no_grad():a=net(**dict(args,previous=args['previous']*5));b=modified(**args)
        for name in ('goal','move','code'):torch.testing.assert_close(a[name],b[name],atol=1e-6,rtol=1e-5)

    def test_bias_edit_and_original_preservation(self):
        state={'memory.weight_ih':torch.ones(144,80),'code.bias':torch.zeros(8),'untouched':torch.ones(3)}
        result=edit(state,[.75,.25,0,0,0,0,0,0],5,.5)
        self.assertTrue(torch.all(state['memory.weight_ih']==1));self.assertTrue(torch.all(state['code.bias']==0))
        self.assertTrue(torch.all(result['memory.weight_ih'][:,32:55]==5))
        self.assertTrue(torch.equal(result['memory.weight_ih'][:,:32],state['memory.weight_ih'][:,:32]))
        self.assertTrue(torch.equal(result['memory.weight_ih'][:,55:],state['memory.weight_ih'][:,55:]))
        self.assertGreater(float(result['code.bias'][1]),float(result['code.bias'][0]));self.assertTrue(torch.all(result['code.bias'][2:]==0))


if __name__=='__main__':unittest.main()
