import unittest,copy
import numpy as np
import torch
from .entity_set import encode_entities
from .entity_model import EntityMovementModel
from .reliable_model import JointModel

def own():
    return dict(entity=dict(kind=1,index=0),known=15,team=0,type=1,position=dict(x=3,y=4),health=1000,maxHealth=1000,alive=True,buffs=[],abilities=[1,6],cooldowns=[0,0],charges=[0,0],abilityProps=[{},{}])

class EntityTests(unittest.TestCase):
    def test_hidden_state_and_ids_excluded(self):
        observation=dict(own=own(),entities=[]);reference=encode_entities(observation)
        observation['own']['entity']['index']=42
        observation['entities']=[dict(entity=dict(kind=1,index=9),known=0,type=12,health=123456,position=dict(x=70,y=80))]
        np.testing.assert_array_equal(reference,encode_entities(observation))

    def test_no_nearest_cap_and_dead_entities_retained(self):
        me=own();entities=[]
        for i in range(20):
            e=copy.deepcopy(me);e['entity']['index']=i+1;e['health']=0 if i==0 else 10;entities.append(e)
        values=encode_entities(dict(own=me,entities=entities))
        self.assertEqual(values.shape,(21,119));self.assertTrue(np.isfinite(values).all())

    def test_observable_cooldown_and_buffs_change_token(self):
        a=dict(own=own(),entities=[]);b=copy.deepcopy(a);b['own']['cooldowns'][1]=7;b['own']['buffs']=[dict(type=1,timer=3,magnitude=100)]
        self.assertFalse(np.array_equal(encode_entities(a),encode_entities(b)))

    def model(self,use=True):
        base=JointModel(253,24,15,dict(history=16,rich=True,spatial=True,constrain=False))
        return EntityMovementModel(base,torch.nn.Linear(167,2),119,use)

    def test_permutation_invariance_after_nonzero_fusion(self):
        torch.manual_seed(26);torch.set_num_threads(4);model=self.model().eval()
        with torch.no_grad():
            model.action_fusion[-1].weight.normal_(0,.01);model.movement_fusion[-1].weight.normal_(0,.01)
            x=torch.randn(2,253);history=torch.randn(2,32,24);tokens=torch.randn(2,7,119);mask=torch.ones(2,7,dtype=torch.bool);extra=torch.randn(2,41)
            a=model(x,history,tokens,mask,extra);p=torch.tensor([3,0,6,1,5,2,4]);b=model(x,history,tokens[:,p],mask[:,p],extra)
            torch.testing.assert_close(a[0],b[0],rtol=0,atol=2e-6);torch.testing.assert_close(a[1],b[1],rtol=0,atol=2e-6)

    def test_classifier_trainable_and_frozen_target_paths(self):
        model=self.model();self.assertTrue(model.student.action.weight.requires_grad)
        self.assertTrue(model.student.history.weight_ih_l0.requires_grad)
        self.assertFalse(any(p.requires_grad for p in model.teacher.parameters()))
        self.assertNotEqual(model.teacher.action.weight.data_ptr(),model.student.action.weight.data_ptr())
        context=torch.randn(3,128);movement=torch.randn(3,128);grid=torch.randn(3,289,20);valid=torch.ones(3,289,dtype=torch.bool);family=torch.tensor([2,5,6]);rules=torch.zeros(3,5)
        with torch.no_grad():
            actual=model.parameter_logits(movement,context,grid,valid,family,rules)
            expected=model.teacher.parameter_logits(context,grid,valid,family,rules)
        self.assertTrue(torch.equal(actual,expected))

if __name__=='__main__':unittest.main()
