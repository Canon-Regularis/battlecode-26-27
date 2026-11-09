import copy,unittest
import numpy as np
import torch
from .predictor import BehaviorPredictor
from .persistence import forecast
from .model import SegmentPolicy


class InferenceTests(unittest.TestCase):
    def test_actor_switch_resets_state_and_history(self):
        from .test_model import CausalPolicyTests
        w,route,keys=CausalPolicyTests().fixture();predictor=BehaviorPredictor.__new__(BehaviorPredictor)
        predictor.plan=dict(schema=keys);predictor.net=SegmentPolicy(keys).eval()
        row=w['steps'][0]['input'];first=predictor.predict(row,route,1)
        other=copy.deepcopy(row);other['observation']['own']['entity']['index']=3
        actual=predictor.predict(other,route,2,[5.]*23,[1.]*23,first['state'])
        expected=predictor.predict(other,route,2)
        self.assertEqual(actual['state']['turns'],1);self.assertEqual(actual['code_probabilities'],expected['code_probabilities'])

    def test_persistence_uses_only_available_previous_features(self):
        fitted=dict(mean=[0,0],scale=[1,1],centers=[[0,0],[4,4]])
        self.assertEqual(forecast([100,100],[0,0],fitted,0),0)
        self.assertEqual(forecast([4,-1000],[1,0],fitted,0),1)
        self.assertEqual(forecast([4,1000],[1,0],fitted,0),1)


if __name__=='__main__':unittest.main()
