"""Real entry + real review validator; no optimizer or dataset construction."""
import copy
import json
import unittest
from unittest.mock import patch
from . import amendment, hierarchy_fit, fit
from .data import REPORT


def records():
    return {name: json.loads((REPORT/name).read_text(encoding='utf-8')) for name in
        ('H00-review.json', 'H00-review-delegation.json', 'H00-review-delegation-launch.json', 'H00-review-request.json')}


class HierarchyEntryContracts(unittest.TestCase):
    def test_actual_fresh_review_is_valid(self):
        amendment.validate_review(records())

    def test_legacy_known_mismatched_entry_is_disabled(self):
        with patch.object(fit, 'preflight', side_effect=AssertionError('legacy preflight reached')):
            with patch.object(fit.torch.optim, 'AdamW', side_effect=AssertionError('optimizer reached')) as optimizer:
                with self.assertRaisesRegex(RuntimeError, 'known history mismatch'): fit.run('H01')
                optimizer.assert_not_called()

    def test_review_and_matching_faults_stop_real_entry(self):
        expected = dict(initial_features=128, dynamics_features=149, previous_command_fields=21,
            extra_nominal_trainable_weights=336, command_written_after_prediction=True, reset_at_same_gaps=True)
        for fault in ('incomplete', 'wrong_checkpoint', 'wrong_model', 'wrong_effort',
                      'unresolved', 'empty_resolution', 'wrong_parent', 'active_run',
                      'wrong_matching', 'missing_amendment'):
            with self.subTest(fault=fault):
                record = records()
                plan = dict(sources={}, matching_contract=copy.deepcopy(expected), inputs={})
                response = dict(reviewed_checkpoint_sha256=amendment.H00_CHECKPOINT,
                    findings_resolved={k: True for k in ('history_path', 'exit_timepoint',
                        'combined_architecture_attribution', 'sequence_limits', 'review_entry_gate')}, review_bindings={})
                if fault == 'incomplete': record['H00-review-delegation.json']['status'] = 'running'
                if fault == 'wrong_checkpoint': record['H00-review-request.json']['checkpoint_sha256'] = 'wrong'
                if fault == 'wrong_model': record['H00-review-delegation.json']['model'] = 'wrong'
                if fault == 'wrong_effort': record['H00-review-delegation.json']['options'] = []
                if fault == 'wrong_parent': record['H00-review.json']['thread']['parentThreadId'] = 'wrong'
                if fault == 'active_run': record['H00-review.json']['thread']['activeRunId'] = 'still-running'
                if fault == 'unresolved': response['findings_resolved']['history_path'] = False
                if fault == 'empty_resolution': response['findings_resolved'] = {}
                if fault == 'wrong_matching': plan['matching_contract']['dynamics_features'] = 128
                def read(path):
                    if path == amendment.PLAN:
                        if fault == 'missing_amendment': raise FileNotFoundError('Amendment absent')
                        return plan
                    if path.name == 'H00-review-response.json': return response
                    return record[path.name]
                # Replace only external committed-byte/data scope in this fixture.
                # Actual preflight, review validation, matching checks and run()
                # execute; every injected fault occurs before datasets or Adam.
                with patch.object(amendment, 'source_gate', return_value=('fixture', {})), \
                     patch.object(amendment, 'read_checked', side_effect=read), \
                     patch.object(hierarchy_fit.torch.optim, 'AdamW', side_effect=AssertionError('optimizer reached')) as optimizer:
                    with self.assertRaises((RuntimeError, FileNotFoundError)):
                        hierarchy_fit.run('H01')
                    optimizer.assert_not_called()


if __name__ == '__main__': unittest.main()
