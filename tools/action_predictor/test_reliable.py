import tempfile
from pathlib import Path
import unittest
import numpy as np
import torch

from .reliable_model import JointModel,priority_log_mass
from .reliable_train import model_data,LABELS
from .group_uncertainty import bootstrap,paired


class ReliableTests(unittest.TestCase):
    def test_stateless_cannot_use_history_or_persistence_channels(self):
        model=JointModel(8,24,15,dict(history=0,spatial=True)).eval()
        x=torch.randn(2,8);h=torch.randn(2,32,24)
        a,c=model(x,h);b,d=model(x,h*0)
        torch.testing.assert_close(a,b)
        grid=torch.randn(2,289,20);valid=torch.ones(2,289,dtype=torch.bool);family=torch.tensor([8,2])
        first=model.parameter_logits(c,grid,valid,family)
        grid[:,:,18:]=999
        torch.testing.assert_close(first,model.parameter_logits(d,grid,valid,family))

    def test_pre_mask_restricts_choice_but_retains_all_label_mass(self):
        model=JointModel(8,24,15,dict(history=4,spatial=True,constrain=True)).eval()
        grid=torch.zeros(2,289,20);grid[:,:,2]=1;grid[:,144,2]=0;grid[:,144,17]=1
        grid[0,145,5]=1 # Only personally reachable movement destination.
        rules=torch.tensor([[1,4,4,8,16],[1,4,4,8,16]],dtype=torch.float32)
        p=model.parameter_logits(torch.zeros(2,128),grid,torch.ones(2,289,dtype=torch.bool),torch.tensor([8,5]),rules).softmax(-1)
        self.assertEqual(p.argmax(-1).tolist(),[145,144])
        self.assertTrue(torch.isfinite(p.log()).all())
        torch.testing.assert_close(p.sum(-1),torch.ones(2))

    def test_discrete_priority_distribution_has_finite_gradients(self):
        raw=torch.tensor([[5.,0.],[1.,-5.]],requires_grad=True)
        loss=-priority_log_mass(raw,torch.tensor([500.,105.])).mean()
        self.assertTrue(torch.isfinite(loss));loss.backward()
        self.assertTrue(torch.isfinite(raw.grad).all())

    def test_group_bootstrap_is_paired_and_deterministic(self):
        n=8;raw=dict(y=np.array([8,8,2,2,8,8,2,2]),py=np.full(n,144),priority=np.zeros(n),group=np.array([1]*4+[2]*4))
        pred=dict(prediction=raw['y'].copy(),coordinate=raw['py'].copy(),priority=np.zeros(n),top5=np.tile(np.arange(144,149),(n,1)),nll=np.ones(n))
        ci,_,_=bootstrap(raw,pred)
        self.assertEqual(ci['joint_accuracy'],{'low':1.,'high':1.})
        self.assertEqual(paired(raw,pred,pred)['joint_loss_reduction'],{'low':0.,'high':0.})


if __name__=='__main__':unittest.main()
