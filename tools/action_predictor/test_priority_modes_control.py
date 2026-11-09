"""Guard against inadvertently enabling the recovered channels in P04."""
import unittest
from unittest import mock
from types import SimpleNamespace
from .priority_modes_control_predictor import PriorityModesControlPredictor
from .priority_modes_predictor import PriorityModesPredictor


class PriorityModeControlTests(unittest.TestCase):
    def test_treatment_checkpoint_rejected_before_model_loading(self):
        with mock.patch('torch.load',return_value={'config':{'id':'P03','use_inputs':True}}),mock.patch.object(PriorityModesPredictor,'__init__',return_value=None) as parent:
            with self.assertRaisesRegex(AssertionError,'Not a P04'):
                PriorityModesControlPredictor(None,None,[],[],head_checkpoint='ignored')
            parent.assert_not_called()

    def test_control_masks_channels_after_checkpoint_construction(self):
        def parent(instance,*args,**kwargs):instance.head=SimpleNamespace(use_inputs=True)
        with mock.patch('torch.load',return_value={'config':{'id':'P04','use_inputs':False}}),mock.patch.object(PriorityModesPredictor,'__init__',new=parent):
            predictor=PriorityModesControlPredictor(None,None,[],[],head_checkpoint='ignored')
            self.assertIs(predictor.head.use_inputs,False)

    def test_fit_rejection_precedes_consumption(self):
        from . import priority_modes_control as runner
        with mock.patch.object(runner,'verify_protocol',side_effect=AssertionError('forced rejection')),mock.patch.object(runner,'gate') as gate:
            with self.assertRaisesRegex(AssertionError,'forced rejection'):runner.fit()
            gate.assert_not_called()

    def test_roundtrip_rejection_precedes_consumption(self):
        from . import priority_modes_control_roundtrip as runner
        with mock.patch.object(runner,'verify_protocol',side_effect=AssertionError('forced rejection')),mock.patch.object(runner,'load_base') as load:
            with self.assertRaisesRegex(AssertionError,'forced rejection'):runner.run()
            load.assert_not_called()

if __name__=='__main__':unittest.main()
