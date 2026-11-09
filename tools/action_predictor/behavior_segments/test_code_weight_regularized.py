import unittest
import torch
from .code_weight_regularized import training_forward
from .code_weight_fit import code_forward
from .test_code_weight_fit import CodeWeightFitTests


class RegularizedCodeTests(unittest.TestCase):
    def test_zero_dropout_matches_original_path(self):
        net,args,item=CodeWeightFitTests().fixture()
        a=training_forward(net,item,dict(context_dropout=0.,state_dropout=0.))
        torch.testing.assert_close(a,code_forward(net,item),rtol=0,atol=0)

    def test_seeded_dropout_and_causal_prefix(self):
        net,args,item=CodeWeightFitTests().fixture();config=dict(context_dropout=.25,state_dropout=.1)
        torch.manual_seed(3);a=training_forward(net,item,config)
        torch.manual_seed(3);b=training_forward(net,item,config);torch.testing.assert_close(a,b,rtol=0,atol=0)
        item['context'][:,3]+=5;item['previous'][:,3]+=5;item['labels'][:]=7
        torch.manual_seed(3);changed=training_forward(net,item,config)
        torch.testing.assert_close(a[:,:3],changed[:,:3],rtol=0,atol=0)
        self.assertTrue(torch.isfinite(changed).all())


if __name__=='__main__':unittest.main()
