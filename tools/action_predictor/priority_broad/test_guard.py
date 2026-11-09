"""Exercise failure paths without constructing a model or optimizer."""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from .guard import checked_execution, committed_sources


class ExecutionGuardTests(unittest.TestCase):
    def test_failed_prerequisite_prevents_later_commands_and_fit(self):
        called = []
        with tempfile.TemporaryDirectory() as directory:
            marker = Path(directory) / 'incorrectly-reached'
            with self.assertRaises(subprocess.CalledProcessError):
                checked_execution([
                    [sys.executable, '-c', 'raise SystemExit(17)'],
                    [sys.executable, '-c', f'from pathlib import Path; Path({str(marker)!r}).touch()']],
                    lambda receipts: called.append('fit'), Path(directory))
            self.assertFalse(marker.exists())
            self.assertEqual(called, [])

    def test_successful_sequence_reaches_operation_once(self):
        called = []
        result = checked_execution([[sys.executable, '-c', 'print("passed")']],
            lambda receipts: called.append(receipts) or 'complete', Path.cwd())
        self.assertEqual(result, 'complete')
        self.assertEqual(len(called), 1)
        self.assertEqual(called[0][0]['returncode'], 0)

    def test_uncommitted_source_prevents_operation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'source.py'
            source.write_bytes(b'executed bytes')
            replies = [subprocess.CompletedProcess([], 0, stdout='abc123\n'),
                       subprocess.CompletedProcess([], 0, stdout=b'committed bytes')]
            reached = []
            with patch('subprocess.run', side_effect=replies):
                with self.assertRaises(RuntimeError):
                    committed_sources(root, [source])
                    reached.append('fit')
            self.assertEqual(reached, [])


if __name__ == '__main__':
    unittest.main()
