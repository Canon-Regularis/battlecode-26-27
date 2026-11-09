import copy
import unittest
import torch
from . import model
from .code_weight_fit import code_forward,configure,loss
from .test_model import CausalPolicyTests


class CodeWeightFitTests(unittest.TestCase):
    def fixture(self):
        w,r,k=CausalPolicyTests().fixture();w['steps'][2]['observed']=False
        w['steps'][1]['previous'][0]=.7
        args,_=model.encode_window(w,r,k);torch.manual_seed(4);net=model.SegmentPolicy(k)
        capture={};h=net.context.register_forward_pre_hook(lambda module,args:capture.update(context=args[0].detach()))
        net(**args);h.remove()
        item=dict(context=capture['context'][None],**{key:args[key][None] for key in ('previous','previous_mask','rounds','observed')},
                  labels=torch.tensor([[0,4,7,2]]))
        return net,args,item

    def test_cached_forward_and_gradient_parity(self):
        net,args,item=self.fixture();configure(net);other=copy.deepcopy(net)
        a=net(**args)['code'];b=code_forward(other,item)[0]
        torch.testing.assert_close(a,b,atol=1e-6,rtol=1e-5)
        mask=args['observed'].bool()
        torch.nn.functional.cross_entropy(a[mask],item['labels'][0,mask]).backward()
        loss(b[None],item).backward()
        for (name,p),(other_name,q) in zip(net.named_parameters(),other.named_parameters()):
            self.assertEqual(name,other_name)
            if p.requires_grad:torch.testing.assert_close(p.grad,q.grad,atol=1e-6,rtol=1e-4)
            else:self.assertIsNone(p.grad);self.assertIsNone(q.grad)

    def test_independent_windows_and_future_causality(self):
        net,args,item=self.fixture()
        doubled={k:torch.cat((v,v),0) for k,v in item.items()}
        first=code_forward(net,doubled)
        torch.testing.assert_close(first[0],first[1])
        doubled['context'][1,3]+=5;doubled['previous'][1,3]+=5
        doubled['labels'][:]=7
        changed=code_forward(net,doubled)
        torch.testing.assert_close(first[0],changed[0]);torch.testing.assert_close(first[1,:3],changed[1,:3])

    def test_only_existing_training_path_changes(self):
        net,args,item=self.fixture();original={k:v.clone() for k,v in net.state_dict().items()}
        opt=torch.optim.AdamW(configure(net),lr=.01)
        opt.zero_grad();loss(code_forward(net,item),item).backward();opt.step()
        changed={k for k,v in net.state_dict().items() if not torch.equal(v,original[k])}
        self.assertEqual(changed,{k for k in original if k.startswith(('context.','memory.','code.'))})
        altered={k:v.clone() for k,v in item.items()};altered['labels'][~altered['observed'].bool()]=1
        torch.testing.assert_close(loss(code_forward(net,item),item),loss(code_forward(net,altered),altered))


if __name__=='__main__':unittest.main()
