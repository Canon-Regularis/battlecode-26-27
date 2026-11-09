import unittest
from unittest.mock import patch
import numpy as np
import torch
from .action_priority_head import ActionPriorityHead,classifier_features,routed_coordinates,assemble_predictions

class ActionPriorityTests(unittest.TestCase):
    def test_exact_initial_logits_and_rng(self):
        old=torch.nn.Linear(128,15);state=torch.get_rng_state()
        a=ActionPriorityHead(old,False);b=ActionPriorityHead(old,True)
        self.assertTrue(torch.equal(state,torch.get_rng_state()))
        x=torch.randn(23,128);features=torch.randn(23,41)
        self.assertTrue(torch.equal(a(x,features),old(x)))
        self.assertTrue(torch.equal(a(x,features),b(x,features)))
        self.assertEqual(sum(p.numel() for p in a.parameters()),2550)

    def test_loaded_nonzero_control_weights_still_masked(self):
        old=torch.nn.Linear(128,15);model=ActionPriorityHead(old,False)
        with torch.no_grad():model.extra.weight.fill_(100)
        x=torch.randn(2,128)
        self.assertTrue(torch.equal(model(x,torch.randn(2,41)),old(x)))

    def test_exact_derived_bits_and_missing(self):
        values=torch.zeros(4,7,dtype=torch.int64);values[:3,1]=1;values[:2,3]=1
        values[0,0]=2**31-1;values[0,2]=2**31-2
        output=classifier_features(torch.zeros(4,39),values)
        self.assertTrue(torch.equal(output[:,-2:],torch.tensor([[0.,1.],[0.,0.],[1.,0.],[1.,0.]])))

    def test_routing_uses_prediction(self):
        class Model:
            def parameter_logits(self,c,g,v,f,r):return f
        logits=torch.zeros(2,15);logits[0,14]=1;logits[1,2]=1
        result=routed_coordinates(Model(),None,None,None,logits,None)
        self.assertTrue(torch.equal(result,torch.tensor([14,2])))

    def test_arguments_unchanged_and_priority_precision(self):
        baseline=dict(prediction=np.zeros(2,int),type_nll=np.zeros(2,np.float32),param_nll=np.array([1.,2.],np.float32),nll=np.zeros(2,np.float32),coordinate=np.array([4,8]),priority=np.array([37,42]))
        result=assemble_predictions(baseline,torch.zeros(2,15),torch.tensor([9,10]),torch.tensor([9,2]),9,np.array([1.00000004,2.]))
        for key in ('param_nll','coordinate','priority'):np.testing.assert_array_equal(result[key],baseline[key])
        self.assertTrue(np.isfinite(result['nll']).all())

    def test_fitter_rejects_before_data_consumption(self):
        from . import action_priority_fit as entry
        with patch.object(entry,'verify_protocol',side_effect=AssertionError('reject')),patch.object(entry,'data') as load:
            with self.assertRaisesRegex(AssertionError,'reject'):entry.fit('C01')
            load.assert_not_called()

    def test_roundtrip_rejects_before_model_loading(self):
        from . import action_priority_roundtrip as entry
        with patch.object(entry,'verify_protocol',side_effect=AssertionError('reject')),patch.object(entry,'load_base') as load:
            with self.assertRaisesRegex(AssertionError,'reject'):entry.run()
            load.assert_not_called()

if __name__=='__main__':unittest.main()
