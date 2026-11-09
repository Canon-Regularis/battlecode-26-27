import unittest
import numpy as np
import torch
from .rare_code_edit import solve_head, make_state, metrics, folds, select


class RareCodeEditTests(unittest.TestCase):
    def test_rare_class_and_folded_normalization(self):
        rng = np.random.default_rng(2)
        y = np.array([0]*200+[3]*5+[7]*5)
        x = np.eye(8)[y] * np.arange(1,9) + rng.normal(0,.01,(len(y),8))
        weight,bias = solve_head(x,y,.1,[0,3,7])
        pred = (x @ weight.T+bias).argmax(1)
        self.assertEqual(metrics(y,pred)['minimum_recall'],1.)
        # Independent weighted ridge first-order optimality in normalized space.
        mean,scale=x.mean(0),x.std(0).clip(1e-4)
        z=np.column_stack(((x-mean)/scale,np.ones(len(x))))
        coef=np.vstack(((weight[[0,3,7]]*scale).T/4,
                        (bias[[0,3,7]]+weight[[0,3,7]]@mean)/4))
        counts=np.bincount(y,minlength=8);w=len(y)/(3*counts[y])
        gradient=z.T@(w[:,None]*(z@coef-np.eye(8)[y][:,[0,3,7]]))
        gradient[:-1] += .1*coef[:-1]
        np.testing.assert_allclose(gradient,0,atol=1e-10)
        self.assertTrue(np.all(bias[[1,2,4,5,6]] == -30))

    def test_scope_and_missing_class_rejection(self):
        base={'memory.weight_ih':torch.ones(144,80),'code.weight':torch.ones(8,48),
              'code.bias':torch.ones(8),'other':torch.ones(3)}
        state=make_state(base,5,np.zeros((8,48)),np.zeros(8))
        self.assertTrue(torch.all(base['memory.weight_ih']==1))
        self.assertTrue(torch.equal(state['other'],base['other']))
        self.assertTrue(torch.equal(state['memory.weight_ih'][:,:32],base['memory.weight_ih'][:,:32]))
        self.assertTrue(torch.equal(state['memory.weight_ih'][:,55:],base['memory.weight_ih'][:,55:]))
        with self.assertRaises(ValueError): solve_head(np.ones((2,3)),[0,0],1,[0,1])

    def test_group_folds_and_false_positives(self):
        groups=[f'g{i}' for i in range(8) for _ in range(4)]
        mapping=folds(groups)
        self.assertEqual(mapping,folds(list(reversed(groups))))
        y=np.tile([0,0,0,3],8);x=np.eye(8)[y]
        selected,results,_=select({1.:x},y,groups,[.1,1])
        self.assertEqual(results[selected]['metrics']['minimum_recall'],1.)
        self.assertEqual(metrics([0,0,3],[3,3,3])['per_code']['3']['precision'],1/3)


if __name__ == '__main__': unittest.main()
