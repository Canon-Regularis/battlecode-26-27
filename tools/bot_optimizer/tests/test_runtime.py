import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from tools.bot_optimizer.benchmark import summarize
from tools.bot_optimizer.runtime import check_logs, executable, replay_logs, run_command, verify


class RuntimeTests(unittest.TestCase):
    def test_reject_old_and_empty_cli_version(self):
        for version in ("cambc 1.0.1", ""):
            with patch("tools.bot_optimizer.runtime.subprocess.run", return_value=
                       subprocess.CompletedProcess([], 0, stdout=version)), self.assertRaises(ValueError):
                executable("/fake/cambc")

    def test_accept_pinned_cli(self):
        with patch("tools.bot_optimizer.runtime.subprocess.run", return_value=
                   subprocess.CompletedProcess([], 0, stdout="cambc 3.0.4\n")):
            self.assertEqual(executable("/fake/cambc"), "/fake/cambc")

    def test_process_failure_is_not_hidden(self):
        with patch("tools.bot_optimizer.runtime.subprocess.run", return_value=
                   subprocess.CompletedProcess([], 7, stdout="out", stderr="failure")), self.assertRaisesRegex(ValueError, "failure"):
            run_command(["cambc", "build", "bot"])

    def test_failure_markers(self):
        for message in ("FATAL probe", "bot error: failed", "Traceback (most recent call last):"):
            with self.assertRaises(ValueError):
                check_logs({"team-a.stdout": message})
        check_logs({"team-a.stdout": "normal log"})

    def test_verify_build_only_is_reported_as_build_only(self):
        with patch("tools.bot_optimizer.runtime.executable", return_value="/fake/cambc"), \
             patch("tools.bot_optimizer.runtime.run_command") as run:
            report = verify("/fake/bot")
        self.assertEqual(report["build"], "passed")
        self.assertFalse(report["smoke"])
        self.assertEqual(run.call_args.args[0], ["/fake/cambc", "build", "/fake/bot", "--release"])


class ReplayTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "match.repl26a"

    def write_replay(self, a, b=None):
        with zipfile.ZipFile(self.path, "w") as archive:
            archive.writestr("team-a.stdout", a)
            archive.writestr("team-b.stdout", a if b is None else b)
            archive.writestr("team-a.stderr", "")

    def record(self, *, done=True, cost=10):
        pair = json.dumps({"name": "kernel", "baseline": 20, "optimized": cost, "ratio": 20 / cost})
        return 'BCOPT_META {"width": 41, "height": 41}\nBCOPT_PAIR ' + pair + ('\nBCOPT_DONE\n' if done else '\n')

    def test_complete_paired_replay(self):
        self.write_replay(self.record())
        self.assertEqual(set(replay_logs(self.path)), {"team-a.stdout", "team-b.stdout", "team-a.stderr"})
        result = summarize(self.path, ("kernel",))
        self.assertEqual(result["minimum_ratio"], 2)
        self.assertEqual(len(result["pairs"]["kernel"]), 2)

    def test_missing_duplicate_failed_or_unexpected_case_rejected(self):
        for text in (self.record(done=False), self.record() * 2, self.record() + "FATAL failed", ""):
            with self.subTest(text=text):
                self.write_replay(text)
                with self.assertRaises(ValueError):
                    summarize(self.path, ("kernel",))
        self.write_replay(self.record())
        with self.assertRaises(ValueError):
            summarize(self.path, ("kernel", "missing"))

    def test_both_teams_required(self):
        self.write_replay(self.record(), "")
        with self.assertRaises(ValueError):
            summarize(self.path, ("kernel",))

    def test_losing_optimisation_is_reported_not_hidden(self):
        self.write_replay(self.record(cost=40))
        self.assertEqual(summarize(self.path, ("kernel",))["minimum_ratio"], 0.5)


if __name__ == "__main__":
    unittest.main()
