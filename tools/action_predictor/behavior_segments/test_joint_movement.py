import copy,unittest
import torch
from . import model
from .joint_movement_weights import JointMovement,losses,inference,ACTIVE
from .joint_movement_fit import choose
from .code_path_movement import PathCorrection,candidate_features
from .test_model import CausalPolicyTests


class JointMovementTests(unittest.TestCase):
    def fixture(self):
        w,r,k=CausalPolicyTests().fixture();args,_=model.encode_window(w,r,k);backbone=model.SegmentPolicy(k)
        captured=[];hook=backbone.context.register_forward_pre_hook(lambda module,values:captured.append(values[0]))
        with torch.no_grad():out=backbone(**args)
        hook.remove();support,labels=model.move_support(w);geometry=torch.stack([candidate_features(s['input'],r) for s in w['steps']])
        item=dict(context=captured[0][None],**{name:args[name][None] for name in ('previous','previous_mask','rounds','observed')},
            geometry=geometry[None],support=support[None],movement_labels=labels[None],teacher=out['code'].softmax(-1)[None],labels=out['code'].argmax(-1)[None])
        head=PathCorrection(torch.ones(8)/8)
        with torch.no_grad():head.coefficients.weight.normal_(std=.05)
        return JointMovement(backbone,head),item,dict(args,geometry=geometry)

    def test_full_forward_cache_parity_and_frozen_tensors(self):
        net,item,args=self.fixture();before=copy.deepcopy(net.state_dict());reference=inference(copy.deepcopy(net))
        with torch.no_grad():a=net(item);b=reference(**args)
        for key in ('move','code'):torch.testing.assert_close(a[key][0],b[key],atol=1e-6,rtol=1e-5)
        params=[p for p in net.parameters() if p.requires_grad];self.assertEqual(sum(p.numel() for p in params),24293)
        loss,move,kl=losses(net(item),item,.2);loss.backward();self.assertLess(abs(float(kl.detach())),1e-6)
        self.assertTrue(all(p.grad is not None and torch.isfinite(p.grad).all() for p in params))
        torch.optim.AdamW(params,lr=.001).step()
        for name,p in net.named_parameters():
            if not p.requires_grad:self.assertTrue(torch.equal(p,before[name]),name)
        self.assertFalse(torch.equal(before['backbone.memory.weight_ih'],net.state_dict()['backbone.memory.weight_ih']))

    def test_future_inputs_and_targets_do_not_affect_prefix(self):
        net,item,args=self.fixture();changed=copy.deepcopy(item)
        changed['context'][:,-1]=100;changed['previous'][:,-1]=100
        changed['movement_labels'].fill_(0);changed['labels'].fill_(7);changed['teacher'].fill_(1/8)
        with torch.no_grad():a=net(item);b=net(changed)
        for name in ('move','code'):torch.testing.assert_close(a[name][:,:-1],b[name][:,:-1])

    def test_selection_rejects_code_regression(self):
        base=dict(epoch=0,coefficient=.2,rows=100,correct=45,nll=1.5,code_rows=100,code_correct=80)
        bad=dict(base,epoch=8,correct=90,code_correct=78)
        good=dict(base,epoch=16,correct=50,code_correct=79)
        self.assertEqual(choose([base,bad,good],.01),good)


if __name__=='__main__':unittest.main()
