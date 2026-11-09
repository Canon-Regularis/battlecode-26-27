import copy
import unittest
import torch
from .code_movement import MovementCorrection, CodeMovementPolicy, supported_log_probabilities
from . import code_weight_fit as first, model
from .code_movement_fit import frozen_features, choose
from .test_model import CausalPolicyTests


class CodeMovementTests(unittest.TestCase):
    def test_zero_residual_and_constant_control(self):
        torch.manual_seed(3)
        states=torch.randn(4,48); probabilities=torch.randn(4,8).softmax(-1); baseline=torch.randn(4,9)
        predicted=MovementCorrection(torch.ones(8)/8,True); constant=MovementCorrection(torch.ones(8)/8,False)
        self.assertTrue(torch.equal(predicted(states,probabilities,baseline),baseline))
        with torch.no_grad():predicted.weight.normal_();predicted.bias.normal_()
        constant.load_state_dict(predicted.state_dict())
        changed=probabilities.roll(1,-1)
        self.assertTrue(torch.equal(constant(states,probabilities,baseline),constant(states,changed,baseline)))
        self.assertFalse(torch.equal(predicted(states,probabilities,baseline),predicted(states,changed,baseline)))

    def test_support_and_gradient_isolation(self):
        w,r,k=CausalPolicyTests().fixture();args,_=model.encode_window(w,r,k)
        base=model.SegmentPolicy(k); old=copy.deepcopy(base.state_dict())
        correction=MovementCorrection(torch.ones(8)/8);net=CodeMovementPolicy(base,correction)
        support,labels=model.move_support(w);out=net(**args)
        lp=supported_log_probabilities(out['move'],support)
        self.assertTrue(torch.all(lp.exp()[~support]==0))
        loss=-lp.gather(1,labels[:,None]).mean();loss.backward()
        self.assertTrue(all(p.grad is None for p in base.parameters()))
        self.assertTrue(all(p.grad is not None and torch.isfinite(p.grad).all() for p in correction.parameters()))
        opt=torch.optim.AdamW(correction.parameters(),lr=.01);opt.step()
        self.assertTrue(all(torch.equal(v,base.state_dict()[n]) for n,v in old.items()))

    def test_cached_features_and_nonzero_causal_streaming(self):
        w,r,k=CausalPolicyTests().fixture();args,_=model.encode_window(w,r,k)
        base=model.SegmentPolicy(k);capture=[]
        hook=base.context.register_forward_pre_hook(lambda module,values:capture.append(values[0]))
        with torch.no_grad():original=base(**args)
        hook.remove()
        cache=dict(context=capture[0][None],**{name:args[name][None] for name in ('previous','previous_mask','rounds','observed')})
        features=frozen_features(base,cache)
        torch.testing.assert_close(features['baseline'][0],original['move'])
        torch.testing.assert_close(features['probabilities'][0],original['code'].softmax(-1))
        correction=MovementCorrection(torch.ones(8)/8)
        with torch.no_grad():correction.weight.normal_(std=.1)
        net=CodeMovementPolicy(base,correction)
        with torch.no_grad():expected=net(**args)
        for name in ('goal','code','state'):self.assertTrue(torch.equal(original[name],expected[name]))
        def part(a,b):return {n:({j:v[a:b] for j,v in value.items()} if n=='batch' else value[a:b]) for n,value in args.items()}
        with torch.no_grad():prefix=net(**part(0,2));suffix=net(**part(2,4),state=prefix['state'])
        torch.testing.assert_close(suffix['move'],expected['move'][2:],atol=1e-6,rtol=1e-5)
        w['steps'][-1]['previous'][0]=99
        for s in w['steps']:s['movement']=[-1,0];s['behavior']=[99.]*len(s['behavior'])
        altered,_=model.encode_window(w,r,k)
        with torch.no_grad():actual=net(**altered)
        self.assertTrue(torch.equal(actual['move'][:-1],expected['move'][:-1]))

    def test_shared_selection_includes_zero(self):
        candidates=[dict(epoch=8,arms={'constant':dict(correct=5,nll=1.),'predicted':dict(correct=5,nll=1.)}),
                    dict(epoch=0,arms={'constant':dict(correct=5,nll=1.),'predicted':dict(correct=5,nll=1.)})]
        self.assertEqual(choose(candidates)['epoch'],0)


if __name__=='__main__':unittest.main()
