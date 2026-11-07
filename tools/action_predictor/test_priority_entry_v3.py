import unittest
from unittest.mock import patch
from . import priority_fit_v3 as fit
from . import priority_roundtrip_v3 as roundtrip
from . import reliable_train as rt

class PriorityEntryTests(unittest.TestCase):
    def test_runtime_label_swap_rejected_before_full_gate(self):
        swapped=list(rt.LABELS);a=swapped.index('priority');b=swapped.index('recall');swapped[a],swapped[b]=swapped[b],swapped[a]
        with patch.object(rt,'LABELS',swapped),patch('tools.action_predictor.priority_verify.verify') as downstream:
            with self.assertRaisesRegex(AssertionError,'Runtime label order'):fit.gate()
            downstream.assert_not_called()

    def test_roundtrip_dependency_rejection_precedes_model_consumption(self):
        with patch.object(roundtrip,'verify_dependencies',side_effect=AssertionError('changed executable')),patch.object(roundtrip,'load_base') as load:
            with self.assertRaisesRegex(AssertionError,'changed executable'):roundtrip.run()
            load.assert_not_called()

    def test_roundtrip_input_rejection_precedes_model_consumption(self):
        with patch.object(roundtrip,'verify_dependencies'),patch.object(roundtrip,'verify_roundtrip_bindings',side_effect=AssertionError('changed input')),patch.object(roundtrip,'load_base') as load:
            with self.assertRaisesRegex(AssertionError,'changed input'):roundtrip.run()
            load.assert_not_called()

if __name__=='__main__':unittest.main()
