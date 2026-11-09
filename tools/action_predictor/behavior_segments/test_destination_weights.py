import copy,unittest
import torch
from . import model
from .destination_weights import DestinationHead,install,pack
from .destination_weight_fit import choose
from .test_model import CausalPolicyTests


class DestinationWeightTests(unittest.TestCase):
    def test_factored_logits_loss_and_gradients_match_convolutions(self):
        torch.manual_seed(5);w,r,k=CausalPolicyTests().fixture();net=model.SegmentPolicy(k)
        head=DestinationHead(net);reference=copy.deepcopy(head)
        spatial=torch.randn(3,25,16);whole=torch.randn(3,16);shared=torch.randn(3,64);valid=torch.ones(3,25,dtype=torch.bool);valid[:,23:]=False
        q=torch.tanh(reference.query(shared));full=torch.cat((spatial.transpose(1,2),q[:,:,None].expand(-1,-1,25),whole[:,:,None].expand(-1,-1,25)),1)[:,:,:,None]
        expected=reference.goal(full).flatten(1).masked_fill(~valid,-1e9)
        actual=head(spatial,whole,shared,valid);torch.testing.assert_close(actual,expected,atol=5e-7,rtol=1e-5)
        labels=torch.tensor([0,5,10]);a=torch.nn.functional.cross_entropy(actual,labels);b=torch.nn.functional.cross_entropy(expected,labels)
        a.backward();b.backward()
        for (name,p),(name2,q) in zip(head.named_parameters(),reference.named_parameters()):
            if p.requires_grad:torch.testing.assert_close(p.grad,q.grad,atol=2e-7,rtol=1e-4)
        self.assertTrue(torch.all(actual.softmax(-1)[~valid]==0))

    def test_updates_do_not_change_code_or_movement_and_bias_is_fixed(self):
        w,r,k=CausalPolicyTests().fixture();args,_=model.encode_window(w,r,k);net=model.SegmentPolicy(k).eval()
        with torch.no_grad():original=net(**args)
        head=DestinationHead(net);before=copy.deepcopy(net.state_dict());p=[p for p in head.parameters() if p.requires_grad]
        self.assertEqual(sum(x.numel() for x in p),1840)
        opt=torch.optim.AdamW(p,lr=.01)
        loss=torch.nn.functional.cross_entropy(head(torch.randn(2,10,16),torch.randn(2,16),torch.randn(2,64),torch.ones(2,10,dtype=torch.bool)),torch.tensor([2,3]))
        loss.backward();opt.step();install(net,head)
        with torch.no_grad():actual=net(**args)
        for key in ('code','move','state'):self.assertTrue(torch.equal(original[key],actual[key]))
        self.assertTrue(torch.equal(before['goal.2.bias'],net.state_dict()['goal.2.bias']))
        self.assertFalse(torch.equal(original['goal'],actual['goal']))

    def test_packing_padding_and_zero_epoch_selection(self):
        rows=[dict(spatial=torch.ones(n,16),whole=torch.zeros(16),target=n-1) for n in (2,5)]
        args,labels=pack(rows,torch.zeros(2,64),[0,1]);self.assertEqual(labels.tolist(),[1,4])
        self.assertEqual(args['valid'].sum(1).tolist(),[2,5])
        base=dict(within2=2,exact=1,error_sum=4,rows=5,nll=1.,learning_rate=.001)
        self.assertEqual(choose([dict(base,epoch=4),dict(base,epoch=0)])['epoch'],0)


if __name__=='__main__':unittest.main()
