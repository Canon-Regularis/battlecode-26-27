import unittest
import numpy as np
import torch
from .previous_dropout import build,corrupt_grid,initial_parity,MASK_SEED
from .neutral_bias import build as control
from .gradient_routing.engine import update_window
from .gradient_routing.test_contract import mixed


class PreviousDropoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):torch.set_num_threads(1)

    def test_group_scope_and_input_preservation(self):
        grid=torch.ones(3,289,20);before=grid.clone();family=torch.tensor([8,2,8])
        changed=corrupt_grid(grid,family,torch.tensor([False,True]))
        self.assertTrue(torch.equal(grid,before))
        self.assertTrue(torch.equal(changed[:,:,:18],grid[:,:,:18]))
        self.assertTrue((changed[0,:,18:20]==0).all())
        self.assertTrue((changed[2,:,18:20]==2).all())
        self.assertTrue(torch.equal(changed[1],grid[1]))

    def test_eval_parity_rng_and_clean_repeated_calls(self):
        torch.manual_seed(27);a=control();rng=torch.get_rng_state()
        torch.manual_seed(27);b=build();initial_parity(b,a.state_dict())
        self.assertTrue(torch.equal(rng,torch.get_rng_state()))
        ctx=torch.randn(4,128);g=torch.randn(4,289,20);v=torch.ones(4,289,dtype=torch.bool)
        rules=torch.ones(4,5);family=torch.tensor([8,2,8,5]);b.eval()
        saved=b.mask_generator.get_state().clone()
        with torch.no_grad():
            expected=a.spatial(dict(context=ctx),g,v,rules,family)
            for _ in range(2):self.assertTrue(torch.equal(b.spatial(dict(context=ctx),g,v,rules,family),expected))
        self.assertTrue(torch.equal(saved,b.mask_generator.get_state()));self.assertEqual(b.mask_draws,0)

    def test_train_mask_stream_and_other_families(self):
        torch.manual_seed(27);a=control();torch.manual_seed(27);b=build()
        ctx=torch.randn(4,128);g=torch.randn(4,289,20);v=torch.ones(4,289,dtype=torch.bool)
        rules=torch.ones(4,5);family=torch.tensor([8,2,8,5]);b.train()
        generator=torch.Generator().manual_seed(MASK_SEED);keep=torch.rand(2,generator=generator)>=.5
        global_rng=torch.get_rng_state().clone()
        with torch.no_grad():
            expected=a.spatial(dict(context=ctx),corrupt_grid(g,family,keep),v,rules,family)
            actual=b.spatial(dict(context=ctx),g,v,rules,family)
            clean=a.spatial(dict(context=ctx),g,v,rules,family)
        self.assertTrue(torch.equal(actual,expected));self.assertTrue(torch.equal(actual[family!=8],clean[family!=8]))
        self.assertTrue(torch.equal(global_rng,torch.get_rng_state()))
        self.assertTrue(torch.equal(generator.get_state(),b.mask_generator.get_state()))
        self.assertEqual(b.mask_draws,2);self.assertEqual(b.mask_dropped,int((~keep).sum()))

    def test_synthetic_training_counts_and_finite_gradients(self):
        torch.manual_seed(27);model=build();data=mixed(64);rows=np.arange(64).reshape(2,32).T
        before=data['arrays']['grid'].copy();model.train()
        opt=torch.optim.AdamW(model.parameters(),lr=.0003,weight_decay=.01)
        _,records=update_window(model,data,rows,opt,'R00')
        self.assertEqual(len(records),1);self.assertFalse(records[0]['projected'])
        self.assertEqual(model.mask_draws,int((data['arrays']['y']==8).sum()))
        self.assertTrue(all(p.grad is None or torch.isfinite(p.grad).all() for p in model.parameters()))
        np.testing.assert_array_equal(before,data['arrays']['grid'])


if __name__=='__main__':unittest.main()
