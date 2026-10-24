import ast
import contextlib
import io
import json
from pathlib import Path
import random
import sys
import tempfile
import textwrap
from types import ModuleType
import unittest
from unittest.mock import patch

from tools.bot_optimizer import Options, optimize_folder, optimize_source
from tools.bot_optimizer.__main__ import main


class Board:
    """Ordered position fake: exposes representation/order mistakes in passes."""

    def __init__(self, values=()):
        self.values = set(values)

    def positions(self):
        return sorted(self.values)

    def count(self):
        return len(self.values)

    def is_empty(self):
        return not self.values

    def is_set(self, position):
        return position in self.values

    def __and__(self, other):
        return Board(self.values & other.values)


class Field:
    def get(self, position):
        return position * position


def fake_sdk():
    sdk = ModuleType("cambc")
    sdk.Bitboard = Board
    sdk.DistanceField = Field
    return sdk


def load(source):
    namespace = {}
    exec(compile(source, "<test-bot>", "exec"), namespace)
    return namespace


class RewriteTests(unittest.TestCase):
    def optimize(self, source, options=None):
        return optimize_source(textwrap.dedent(source), options)

    def equivalent(self, source, inputs, options=None):
        source = textwrap.dedent(source)
        result = optimize_source(source, options)
        with patch.dict(sys.modules, {"cambc": fake_sdk()}):
            original, generated = load(source), load(result.source)
            for args in inputs:
                self.assertEqual(original["run"](*args), generated["run"](*args))
        return result

    def test_exact_integer_square(self):
        result = self.equivalent("""
            def run(n):
                total = 0
                for x in range(n):
                    total += x**2
                return total
        """, [(0,), (1,), (100,)])
        self.assertEqual([c.pass_name for c in result.changes], ["integer-square"])

    def test_unknown_float_and_bool_not_treated_as_exact_int(self):
        for expression in ("value", "1.5", "True"):
            result = self.optimize(f"def run(value):\n    x = {expression}\n    return x**2\n")
            self.assertFalse(result.changes)

    def test_annotations_are_explicit_opt_in(self):
        source = "def run(x: int):\n    return x**2\n"
        self.assertFalse(self.optimize(source).changes)
        self.assertTrue(self.optimize(source, Options(trust_annotations=True)).changes)

    def test_sum_range_native_map(self):
        result = self.equivalent("def run():\n    return sum(abs(x) for x in range(-64, 64))", [()])
        self.assertEqual(result.changes[-1].pass_name, "native-map")
        self.assertIn("map(abs, range", result.source)

    def test_bounded_integer_sum(self):
        result = self.equivalent("def run():\n    return sum(x*x + 1 for x in range(128))", [()])
        self.assertEqual(result.changes[-1].pass_name, "bounded-sum")

    def test_empty_sum_and_negative_step(self):
        for expression in ("range(0)", "range(10, -20, -2)", "range(2, 1)"):
            self.equivalent(f"def run():\n    return sum(x*x for x in {expression})", [()])

    def test_unbounded_and_effectful_generators_left_alone(self):
        for expression in ("sum(x*x for x in range(n))", "sum(x*x for x in range(10000))",
                           "sum(x*x for x in range(10) if f(x))",
                           "sum(f(x) for x in range(10))", "any(x*x for x in range(10))",
                           "sum(1/x for x in range(10))"):
            result = self.optimize(f"def run(n, f):\n    return {expression}")
            self.assertFalse(result.changes)

    def test_shadowed_builtins_and_imports(self):
        cases = [
            "def run(sum):\n    return sum(x*x for x in range(10))",
            "sum = lambda x: x\ndef run():\n    return sum(x*x for x in range(10))",
            "def run(range):\n    return sum(x*x for x in range(10))",
            "def run(map):\n    return sum(abs(x) for x in range(10))",
            "def run(abs):\n    return sum(abs(x) for x in range(10))",
            "import cambc\ndef run(cambc):\n    b = cambc.Bitboard()\n    return len(b.positions())",
            "import cambc\ndef run():\n    b = cambc.Bitboard()\n    len = lambda x: 99\n    return len(b.positions())",
        ]
        for source in cases:
            with self.subTest(source=source):
                options = Options(max_materialize=0)
                self.assertFalse(self.optimize(source, options).changes)

    def test_count_existence_and_intersection(self):
        source = """
            import cambc as sdk
            def run(left, right):
                a = sdk.Bitboard(left)
                b = sdk.Bitboard(right)
                return (len(a.positions()), bool(a.positions()),
                        [p for p in a.positions() if b.is_set(p)],
                        sum(1 for p in a.positions() if b.is_set(p)))
        """
        rng = random.Random(123)
        inputs = [(rng.sample(range(40), rng.randrange(40)), rng.sample(range(40), rng.randrange(40)))
                  for _ in range(100)] + [((), ())]
        result = self.equivalent(source, inputs)
        self.assertEqual({c.pass_name for c in result.changes}, {
            "mask-count", "mask-empty", "mask-filter", "mask-intersection-count",
        })

    def test_native_field_key(self):
        result = self.equivalent("""
            import cambc
            def run(values):
                board = cambc.Bitboard(values)
                field = cambc.DistanceField()
                return min(board.positions(), key=lambda p: field.get(p), default=None)
        """, [((),), ([3, 1, 7],)])
        self.assertEqual(result.changes[-1].pass_name, "native-key")

    def test_native_key_requires_safe_iterable_and_no_shadowed_receiver(self):
        for body in ("min(values, key=lambda p: field.get(p))",
                     "min(board.positions(), key=lambda field: field.get(field))"):
            result = self.optimize(f"import cambc\ndef run(values):\n    board = cambc.Bitboard()\n    field = cambc.DistanceField()\n    return {body}")
            self.assertFalse(result.changes)

    def test_itemgetter_preserves_calls_exceptions_and_stable_ties(self):
        source = "def run(rows):\n    return sorted(rows, key=lambda row: row[1])"
        result = self.equivalent(source, [([],), ([(4, 1), (3, 1), (2, 0)],)])
        self.assertEqual(result.changes[-1].pass_name, "native-itemgetter")
        calls = []

        class Record:
            def __getitem__(self, index):
                calls.append(index)
                return 1

        for version in (source, result.source):
            calls.clear()
            load(version)["run"]([Record(), Record()])
            self.assertEqual(calls, [1, 1])

    def test_attrgetter_nested_path_and_methods(self):
        result = self.equivalent("""
            class Bot:
                def choose(self, values):
                    return min(values, key=lambda row: row.real)
            def run(values):
                return Bot().choose(values)
        """, [([3, 1, 2],)])
        self.assertEqual(result.changes[-1].pass_name, "native-attrgetter")

    def test_helper_hoisting_preserves_docstring_and_future_import(self):
        result = self.optimize('"doc"\nfrom __future__ import annotations\ndef run(rows):\n    return min(rows, key=lambda row: row[1])')
        namespace = load(result.source)
        self.assertEqual(namespace["__doc__"], "doc")
        self.assertTrue(result.changes)

    def test_helper_names_avoid_local_global_and_definition_collisions(self):
        result = self.equivalent("""
            def _bcopt_key_0():
                return 9
            def run(rows):
                _bcopt_key_1 = 10
                return min(rows, key=lambda row: row[1]), _bcopt_key_0(), _bcopt_key_1
        """, [([(1, 2), (2, 1)],)])
        self.assertIn("_bcopt_key_2", result.source)

    def test_control_flow_reassignment_does_not_leak_types(self):
        sources = [
            "x=2\nif flag:\n    x=1.5\nreturn x**2",
            "x=2\nfor i in range(2):\n    y=x**2\n    x=1.5\nreturn x",
            "x=2\nwhile flag:\n    y=x**2\n    x=1.5\n    break\nreturn x",
            "x=2\n[(x:=1.5) for i in range(2)]\nreturn x**2",
            "try:\n    raise ValueError()\nexcept TypeError:\n    x=2\nexcept ValueError:\n    x=flag\n    return x**2",
        ]
        for source in sources:
            with self.subTest(source=source):
                result = self.optimize("def run(flag):\n" + textwrap.indent(source, "    "))
                self.assertFalse(result.changes)

    def test_definition_and_target_side_effects_invalidate_facts(self):
        sources = [
            "x=2\ndef x():\n    return 3\nreturn x**2",
            "x=2\nclass x:\n    pass\nreturn x**2",
            "x=2\ndef inner(a=(x:=1.1)):\n    return a\nreturn x**2",
            "x=2\ninner=lambda a=(x:=1.1): a\nreturn x**2",
            "x=2\na=[1,2]\na[int(x:=1.1)]=5\nreturn x**2",
            "x=2\na=[1,2]\na[int(x:=1.1)]+=5\nreturn x**2",
            "x=2\na=[1,2]\ndel a[int(x:=1.1)]\nreturn x**2",
        ]
        for source in sources:
            with self.subTest(source=source):
                result = self.optimize("def run():\n" + textwrap.indent(source, "    "))
                self.assertFalse(result.changes)

    def test_global_and_nonlocal_mutation(self):
        for source in ("""
            x=2
            def mutate():
                global x
                x=1.5
            mutate()
            y=x**2
        """, """
            def run():
                x=2
                def mutate():
                    nonlocal x
                    x=1.5
                mutate()
                return x**2
        """):
            self.assertFalse(self.optimize(source).changes)

    def test_delayed_generator_does_not_assume_captured_types(self):
        result = self.equivalent("""
            def run():
                x = 2
                result = (x**2 for i in range(3))
                x = 1.1
                return list(result)
        """, [()])
        self.assertFalse(result.changes)

    def test_mutable_sequence_elements_not_assumed_exact_ints(self):
        result = self.equivalent("""
            def run():
                values = [1, 2]
                values[0] = 1.1
                result = []
                for x in values:
                    result.append(x**2)
                return result
        """, [()])
        self.assertFalse(result.changes)

    def test_nested_nonlocal_import_mutation(self):
        result = self.optimize("""
            def outer():
                import cambc
                def mutate(value):
                    nonlocal cambc
                    cambc = value
                def run():
                    b = cambc.Bitboard()
                    return len(b.positions())
                return mutate, run
        """)
        self.assertFalse(result.changes)

    def test_private_attribute_mangling_not_replaced(self):
        result = self.equivalent("""
            class Record:
                def __init__(self, value):
                    self.__value = value
                def choose(self, rows):
                    return min(rows, key=lambda row: row.__value)
            def run():
                rows = [Record(2), Record(1)]
                return rows[0].choose(rows) is rows[1]
        """, [()])
        self.assertFalse(result.changes)

    def test_comprehension_binding_does_not_inherit_outer_fact(self):
        result = self.optimize("""
            def run():
                x = 2
                return [(x**2, y) for y in range(2) if x**2 for x in [1.1]]
        """)
        self.assertFalse(result.changes)

    def test_pattern_capture_cannot_shadow_generated_helper(self):
        result = self.equivalent("""
            def run(rows):
                match rows:
                    case _bcopt_key_0:
                        return min(rows, key=lambda row: row[1])
        """, [([(1, 2), (2, 1)],)])
        self.assertIn("_bcopt_key_1", result.source)

    def test_key_exception_type_preserved(self):
        for expression in ("row[1]", "row.missing"):
            source = f"def run(rows):\n    return min(rows, key=lambda row: {expression})"
            result = self.optimize(source)
            errors = []
            for version in (source, result.source):
                try:
                    load(version)["run"]([object()])
                except Exception as error:
                    errors.append(type(error))
            self.assertEqual(len(errors), 2)
            self.assertEqual(errors[0], errors[1])

    def test_reflection_monkeypatch_and_star_import_skip(self):
        for hazard in ("globals()", "eval('1')", "import cambc\ncambc.Bitboard = object", "from math import *"):
            result = self.optimize(hazard + "\ndef run():\n    return sum(x*x for x in range(10))")
            self.assertFalse(result.changes)
            self.assertTrue(result.warnings)

    def test_no_argument_methods_only(self):
        result = self.optimize("import cambc\ndef run():\n    b=cambc.Bitboard()\n    return len(b.positions(42))")
        self.assertFalse(result.changes)

    def test_generic_type_parameter_scopes_left_unchanged(self):
        for source in ("""
            import cambc
            def run[len]():
                b = cambc.Bitboard()
                return len(b.positions())
        """, """
            import cambc
            class Bot[len]:
                def run(self):
                    b = cambc.Bitboard()
                    return len(b.positions())
        """):
            self.assertFalse(self.optimize(source).changes)

    def test_disabled_passes_and_idempotence(self):
        source = "def run():\n    return sum(x**2 for x in range(10))"
        result = self.optimize(source, Options(disabled=frozenset({"integer-square", "bounded-sum"})))
        self.assertFalse(result.changes)
        result = self.optimize(source)
        self.assertFalse(self.optimize(result.source).changes)


class FolderTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.bot = self.root / "bot"
        (self.bot / "src").mkdir(parents=True)
        (self.bot / "src/main.py").write_text("import kernel\n")
        (self.bot / "src/kernel.py").write_text("def run():\n    return sum(x*x for x in range(10))\n")

    def test_folder_assets_exclusions_report_and_no_source_modification(self):
        (self.bot / "asset.bin").write_bytes(b"\x00\xff")
        (self.bot / ".cambc").mkdir()
        (self.bot / ".cambc/cache").write_text("old")
        before = (self.bot / "src/kernel.py").read_bytes()
        output = self.root / "out"
        report = optimize_folder(self.bot, output)
        self.assertEqual((self.bot / "src/kernel.py").read_bytes(), before)
        self.assertEqual((output / "asset.bin").read_bytes(), b"\x00\xff")
        self.assertFalse((output / ".cambc").exists())
        self.assertEqual(report["pass_counts"], {"bounded-sum": 1})
        self.assertEqual(json.loads((output / "optimizer-report.json").read_text()), report)

    def test_reproducible_reports_and_output(self):
        first = optimize_folder(self.bot, self.root / "one")
        second = optimize_folder(self.bot, self.root / "two")
        self.assertEqual(first, second)
        self.assertEqual((self.root / "one/src/kernel.py").read_bytes(),
                         (self.root / "two/src/kernel.py").read_bytes())

    def test_build_named_source_package_is_not_a_root_build_cache(self):
        package = self.bot / "src/build"
        package.mkdir()
        (package / "__init__.py").write_text("VALUE=1\n")
        optimize_folder(self.bot, self.root / "out")
        self.assertEqual((self.root / "out/src/build/__init__.py").read_text(), "VALUE=1\n")

    def test_reject_overwrite_overlap_missing_entry_and_symlink(self):
        for output in (self.bot, self.bot / "out", self.root):
            with self.subTest(output=output), self.assertRaises(ValueError):
                optimize_folder(self.bot, output)
        (self.bot / "link").symlink_to(self.bot / "src/kernel.py")
        with self.assertRaises(ValueError):
            optimize_folder(self.bot, self.root / "out")
        self.assertFalse((self.root / "out").exists())

    def test_failed_parse_does_not_create_output(self):
        (self.bot / "src/kernel.py").write_text("def invalid(")
        with self.assertRaises(SyntaxError):
            optimize_folder(self.bot, self.root / "out")
        self.assertFalse((self.root / "out").exists())

    def test_folder_wide_dynamic_import_barrier(self):
        (self.bot / "src/main.py").write_text("exec('import kernel')")
        report = optimize_folder(self.bot, self.root / "out")
        self.assertFalse(report["pass_counts"])
        self.assertTrue(report["files"]["src/kernel.py"]["warnings"])

    def test_cli(self):
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(main([str(self.bot), "--output", str(self.root / "out")]), 0)
            with self.assertRaises(SystemExit):
                main([str(self.bot), "--output", str(self.root / "other"), "--maps", "collision"])

    def test_cli_verification_failure_is_persisted(self):
        output = self.root / "out"
        with patch("tools.bot_optimizer.__main__.verify", side_effect=ValueError("bad build")), \
             contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(main([str(self.bot), "--output", str(output), "--verify"]), 1)
        report = json.loads((output / "optimizer-report.json").read_text())
        self.assertEqual(report["validation"]["runtime"]["status"], "failed")


if __name__ == "__main__":
    unittest.main()
