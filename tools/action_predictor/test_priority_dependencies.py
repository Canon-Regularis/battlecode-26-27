import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch
import json
from .priority_dependencies import check_hashes,baseline_binding
from .more_replays import sha

class PriorityDependencyTests(unittest.TestCase):
    def test_changed_executable_dependency_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'correctness.py';path.write_text('original')
            binding={str(path):sha(path)};check_hashes(binding)
            path.write_text('changed')
            with self.assertRaisesRegex(AssertionError,'Dependency'):check_hashes(binding)

    def test_mismatched_baseline_archive_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            predictions=Path(directory)/'predictions.npz';predictions.write_bytes(b'original')
            report=Path(directory)/'M01.json';report.write_text(json.dumps(dict(predictions_sha256=sha(predictions))))
            with patch('tools.action_predictor.priority_dependencies.BASE_REPORT',report),patch('tools.action_predictor.priority_dependencies.BASE_PREDICTIONS',predictions):
                self.assertEqual(baseline_binding()['predictions_sha256'],sha(predictions))
                predictions.write_bytes(b'replaced')
                with self.assertRaisesRegex(AssertionError,'Baseline prediction'):baseline_binding()

if __name__=='__main__':unittest.main()
