import contextlib
import io
import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import inspect_loops


class InspectionTests(unittest.TestCase):
    def test_extracts_report_from_binary_framed_stdout(self):
        data = b'\0\x01draft message\nSQUAD_LOOPS_DATA {"roster":[10],"loops":[]}\n\0\xff'
        self.assertEqual(inspect_loops.extract_report(data), {"roster": [10], "loops": []})

    def test_missing_report_explains_draft_error(self):
        with self.assertRaisesRegex(ValueError, "bot error: example"):
            inspect_loops.extract_report(b"\0bot error: example\n")

    def test_playback_error_is_not_hidden_by_successful_draft_report(self):
        with self.assertRaisesRegex(ValueError, "bot error: playback"):
            inspect_loops.extract_report(b"SQUAD_LOOPS_DATA {}\n\0bot error: playback\n")

    def test_cli_keeps_uv_side_json_and_view_options(self):
        bundle = inspect_loops.ROOT / "replays" / "example.repl26a"
        reports = {"a": {"roster": [10], "risk_tolerance": 0.2, "loops": []}}
        output = io.StringIO()
        with patch.object(inspect_loops.shutil, "which", return_value="/usr/bin/uv"), \
                patch.object(inspect_loops, "run_inspection_match", return_value=bundle) as run_match, \
                patch.object(inspect_loops, "read_replay_reports", return_value=reports) as read, \
                patch.object(inspect_loops, "open_replay") as view, \
                contextlib.redirect_stdout(output):
            result = inspect_loops.main(["--map", "packs", "--json", "--view", "--fuel", "123"])
        self.assertEqual(result, 0)
        self.assertEqual(json.loads(output.getvalue()), reports)
        run_match.assert_called_once_with(["/usr/bin/uv", "run", "cambc"], "packs", 123)
        read.assert_called_once_with(bundle, ("a",))
        view.assert_called_once_with(["/usr/bin/uv", "run", "cambc"], bundle)

    def test_runner_failure_preserves_its_exit_code(self):
        failure = subprocess.CalledProcessError(3, ["uv", "run", "cambc"], output="runner failed")
        with patch.object(inspect_loops.shutil, "which", return_value="uv"), \
                patch.object(inspect_loops, "run_inspection_match", side_effect=failure), \
                contextlib.redirect_stderr(io.StringIO()) as output:
            self.assertEqual(inspect_loops.main([]), 3)
        self.assertIn("runner failed", output.getvalue())


if __name__ == "__main__":
    unittest.main()
