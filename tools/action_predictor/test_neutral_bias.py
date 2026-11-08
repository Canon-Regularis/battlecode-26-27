import unittest
import torch
from .neutral_bias import build,initial_parity
from .history_horizon.model import Policy


class NeutralBiasTests(unittest.TestCase):
    def test_only_movement_tile_bias_changes_and_rng_matches(self):
        torch.manual_seed(27);reference=Policy();rng=torch.get_rng_state()
        torch.manual_seed(27);treatment=build()
        initial_parity(treatment,reference.state_dict())
        self.assertTrue(torch.equal(rng,torch.get_rng_state()))
        self.assertTrue((treatment.execution.offset_bias.weight[8,:289]==0).all())
        self.assertEqual(sum(p.numel() for p in treatment.parameters() if p.requires_grad),139292)

    def test_other_family_probabilities_unchanged(self):
        torch.manual_seed(27);a=Policy();torch.manual_seed(27);b=build()
        context=torch.randn(8,128);grid=torch.randn(8,289,20)
        valid=torch.ones(8,289,dtype=torch.bool);rules=torch.ones(8,5)
        family=torch.tensor([1,2,3,5,6,12,13,14])
        with torch.no_grad():
            x=a.spatial(dict(context=context),grid,valid,rules,family)
            y=b.spatial(dict(context=context),grid,valid,rules,family)
        self.assertTrue(torch.equal(x,y))

    def test_mismatch_rejected(self):
        torch.manual_seed(27);a=Policy();torch.manual_seed(27);b=build()
        with torch.no_grad():b.execution.query.bias[0]+=1
        with self.assertRaises(ValueError):initial_parity(b,a.state_dict())


if __name__=='__main__':unittest.main()
