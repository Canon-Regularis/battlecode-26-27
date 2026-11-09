import copy
import unittest
import torch
from .code_weight_full import backward_batch,configure
from . import model
from .test_model import CausalPolicyTests


class FullCodeWeightTests(unittest.TestCase):
    def test_accumulation_denominator_and_gradients(self):
        fixture=CausalPolicyTests();w,r,k=fixture.fixture()
        a,_=model.encode_window(w,r,k);w['steps'][1]['observed']=False
        b,_=model.encode_window(w,r,k);y=torch.tensor([0,4,2,0])
        torch.manual_seed(8);net=model.SegmentPolicy(k);configure(net);other=copy.deepcopy(net)
        actual,n=backward_batch(net,[(a,y),(b,y)])
        self.assertEqual(n,7)
        logits=[];labels=[]
        for args in (a,b):
            mask=args['observed'].bool();logits.append(other(**args)['code'][mask]);labels.append(y[mask])
        expected=torch.nn.functional.cross_entropy(torch.cat(logits),torch.cat(labels));expected.backward()
        self.assertAlmostEqual(actual,float(expected.detach()),places=6)
        for (name,p),(other_name,q) in zip(net.named_parameters(),other.named_parameters()):
            self.assertEqual(name,other_name)
            if p.requires_grad:
                self.assertTrue(torch.isfinite(p.grad).all())
                torch.testing.assert_close(p.grad,q.grad,atol=1e-6,rtol=1e-4)
            else:self.assertIsNone(p.grad);self.assertIsNone(q.grad)
        before={k:v.clone() for k,v in net.state_dict().items()}
        optimizer=torch.optim.AdamW(configure(net),lr=.001);optimizer.step()
        changed=[k for k,v in net.state_dict().items() if not torch.equal(v,before[k])]
        self.assertTrue(any(k.startswith('maps.') for k in changed))
        self.assertTrue(all(k.startswith(('maps.','context.','memory.','code.')) for k in changed))


if __name__=='__main__':unittest.main()
