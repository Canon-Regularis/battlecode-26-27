import unittest
import numpy as np
from .evaluate import semantic_equal,priority_diagnostics,competition


class AssessmentContracts(unittest.TestCase):
    def test_unused_slots_are_not_semantic_changes(self):
        a=dict(prediction=np.array([10,9,8,5]),priority=np.array([1,2,3,4]),proposed_coordinate=np.array([5,6,7,8]))
        b={k:v.copy() for k,v in a.items()};b['priority'][:]=[9,2,9,9];b['proposed_coordinate'][:]=[99,99,7,8]
        np.testing.assert_array_equal(semantic_equal(a,b),[True,True,True,True])
        b['priority'][1]=3;b['proposed_coordinate'][2]=8;b['prediction'][3]=6
        np.testing.assert_array_equal(semantic_equal(a,b),[True,False,False,False])

    def test_priority_errors_separate_all_family_from_typed(self):
        raw=dict(y=np.array([9,9,10]),priority=np.array([2,4,0]))
        p=dict(prediction=np.array([9,10,9]),priority=np.array([3,100,0]))
        out=priority_diagnostics(raw,p,dict(fallback_weight=np.array([.1,.2,.3])),np.ones(3,bool),np.array([2,4]),[1,10])
        self.assertEqual(out['all']['conditional_MAE'],48.5);self.assertEqual(out['all']['typed_MAE'],1)
        self.assertEqual(out['all']['typed_rows'],1);self.assertEqual(out['false_positives']['type'],1)
        self.assertEqual(out['absolute_frequency_at_most5']['rows'],1)
        empty=priority_diagnostics(raw,p,dict(fallback_weight=np.ones(3)),np.zeros(3,bool),np.array([2,4]),[1,10])
        self.assertIsNone(empty['all']['typed_MAE'])

    def test_competition_bound_is_separate_from_correct_integer(self):
        raw=dict(y=np.array([9,9,9]),priority=np.array([20,20,20]))
        p=dict(prediction=np.array([2,2,9]),priority=np.array([20,20,20]))
        types=np.full((3,15),-100.);types[:,9]=np.log([.2,.6,.6]);types[:,2]=np.log([.8,.4,.4])
        modes=np.full((3,15),-100.);modes[:,2]=np.log(.4)
        out=competition(raw,p,dict(mode_logp=np.log([.5,.5,.9])),types,modes)
        self.assertEqual(out['conditional_mode_correct'],3);self.assertEqual(out['joint_correct'],1)
        self.assertEqual(out['correct_integer_loses_family_competition'],2)
        self.assertEqual(out['optimistic_fixed_type_and_other_heads_priority_joint_ceiling'],2)
        self.assertEqual(out['priority_unreachable_even_with_unit_conditional_mass'],1)


if __name__=='__main__':unittest.main()
