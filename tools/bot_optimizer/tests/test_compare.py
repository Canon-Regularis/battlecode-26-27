import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
from types import ModuleType
import unittest
from unittest.mock import patch
import zipfile

from tools.bot_optimizer.compare import compare, instrument, observations


class CompareTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.bot = self.root / "bot"
        (self.bot / "src").mkdir(parents=True)
        (self.bot / "src/main.py").write_text('"module doc"\nfrom __future__ import annotations\nclass Worker:\n    def work(self,x):\n        "function doc"\n        return x+1\n')

    def test_instrument_keeps_signature_result_and_docstrings(self):
        instrument(self.bot, "main:Worker.work")
        source = (self.bot / "src/main.py").read_text()
        sdk = ModuleType("cambc")
        fuel = iter((100, 80))
        sdk.fuel_remaining = lambda: next(fuel)
        output = io.StringIO()
        namespace = {}
        with patch.dict(sys.modules, {"cambc": sdk}), contextlib.redirect_stdout(output):
            exec(source, namespace)
            self.assertEqual(namespace["Worker"]().work(3), 4)
        self.assertEqual(namespace["__doc__"], "module doc")
        self.assertEqual(namespace["Worker"].work.__doc__, "function doc")
        self.assertIn("BCOPT_MEASURE (20, 100, 80)", output.getvalue())

    def test_invalid_async_generator_and_yielding_targets_rejected(self):
        for target in ("../main:Worker.work", "main:Missing", "main:Worker"):
            with self.subTest(target=target), self.assertRaises(ValueError):
                instrument(self.bot, target)
        for definition in ("async def f():\n    return 1", "def f():\n    yield 1",
                           "def f():\n    cambc.end_turn()"):
            (self.bot / "src/main.py").write_text(definition)
            with self.assertRaises(ValueError):
                instrument(self.bot, "main:f")

    def write_replay(self, destination, *, spent=10, output="RESULT 1", duplicate=False):
        destination.mkdir(parents=True)
        path = destination / "match.repl26a"
        text = f"BCOPT_MEASURE ({spent}, 100, {100-spent})\n{output}\n"
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr("team-a.stdout", text)
            archive.writestr("team-b.stdout", text if not duplicate else "")
        return path

    def test_replay_requires_valid_intervals_both_teams_and_requested_outputs(self):
        for index, options in enumerate(({"spent": -1}, {"duplicate": True}, {"output": "other"})):
            path = self.write_replay(self.root / f"case-{index}", **options)
            with self.assertRaises(ValueError):
                observations(path, "RESULT ")

    def test_generic_comparison_pipeline_and_reversed_repeat_order(self):
        commands = []

        def run(command, **kwargs):
            commands.append(command)
            variant = Path(command[2]).name
            self.write_replay(Path(command[-1]), spent=10 if variant == "baseline" else 5)

        with patch("tools.bot_optimizer.compare.executable", return_value="fake-cambc"), \
             patch("tools.bot_optimizer.compare.run_command", side_effect=run):
            report = compare(self.bot, self.root / "output", target="main:Worker.work",
                             maps=("map-one", "map-two"), repeats=2, output_prefix="RESULT ")
        self.assertEqual(report["status"], "complete")
        self.assertEqual(len(report["comparisons"]), 8)
        self.assertTrue(all(row["reduction_percent"] == 50 for row in report["comparisons"]))
        self.assertEqual(Path(commands[0][2]).name, "baseline")
        self.assertEqual(Path(commands[4][2]).name, "optimized")
        self.assertEqual(json.loads((self.root / "output/results.json").read_text()), report)
        self.assertNotIn("fuel_remaining", (self.bot / "src/main.py").read_text())

    def test_mismatched_printed_results_are_not_accepted_as_a_fuel_win(self):
        def run(command, **kwargs):
            variant = Path(command[2]).name
            self.write_replay(Path(command[-1]), output=f"RESULT {variant}")

        with patch("tools.bot_optimizer.compare.executable", return_value="fake-cambc"), \
             patch("tools.bot_optimizer.compare.run_command", side_effect=run), self.assertRaises(ValueError):
            compare(self.bot, self.root / "output", target="main:Worker.work", maps=("map-one",),
                    output_prefix="RESULT ")


if __name__ == "__main__":
    unittest.main()
