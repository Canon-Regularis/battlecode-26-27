"""Compare any bot's specified function before/after optimisation in Wasm.

This is a measurement tool, not an equivalence prover or automatic strategy
tuner. It instruments separate copies and never changes the supplied bot.
"""

import argparse
import ast
import json
from pathlib import Path
import subprocess
import sys
import tokenize

from .compiler import optimize_folder
from .model import Options, PASS_DESCRIPTIONS
from .records import used_names
from .runtime import check_logs, executable, replay_logs, run_command


PREFIX = "BCOPT_MEASURE "


def instrument(bot, target):
    module, separator, qualified = target.partition(":")
    parts, names = module.split("."), qualified.split(".")
    if not separator or not all(part.isidentifier() for part in [*parts, *names]):
        raise ValueError("Target must be module:Function or module:Class.method")
    root = bot / "src" if (bot / "src/main.py").is_file() else bot
    path = root.joinpath(*parts).with_suffix(".py")
    if not path.is_file():
        path = root.joinpath(*parts, "__init__.py")
    if not path.is_file():
        raise ValueError(f"Target module not found: {module}")
    with tokenize.open(path) as stream:
        tree = ast.parse(stream.read())
    node = tree
    for name in names:
        matches = [child for child in node.body if isinstance(child, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
                   and child.name == name]
        if len(matches) != 1:
            raise ValueError(f"Target not found or ambiguous: {target}")
        node = matches[0]
    if not isinstance(node, ast.FunctionDef):
        raise ValueError("Target must be a synchronous function or method")

    class Suspension(ast.NodeVisitor):
        def __init__(self):
            self.found = False

        def visit_Yield(self, child):
            self.found = True

        visit_YieldFrom = visit_Yield

        def visit_Call(self, child):
            if ((isinstance(child.func, ast.Name) and child.func.id == "end_turn")
                    or (isinstance(child.func, ast.Attribute) and child.func.attr == "end_turn")):
                self.found = True
            self.generic_visit(child)

        def visit_FunctionDef(self, child):
            pass

        visit_AsyncFunctionDef = visit_FunctionDef
        visit_Lambda = visit_FunctionDef

    check = Suspension()
    for statement in node.body:
        check.visit(statement)
    if check.found:
        raise ValueError("Generator functions or explicit end_turn calls cannot be timed as ordinary calls")
    taken = used_names(tree)

    def fresh(stem):
        index = 0
        while f"_bcopt_measure_{stem}_{index}" in taken:
            index += 1
        name = f"_bcopt_measure_{stem}_{index}"
        taken.add(name)
        return name

    sdk, start, end = fresh("sdk"), fresh("start"), fresh("end")
    body = node.body
    doc = []
    if (body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant)
            and isinstance(body[0].value.value, str)):
        doc, body = [body[0]], body[1:]
    enter = ast.parse(f"{start} = {sdk}.fuel_remaining()").body
    finish = ast.parse(f"{end} = {sdk}.fuel_remaining()\n"
                       f"print({'\n' + PREFIX!r} + repr(({start} - {end}, {start}, {end})), flush=True)").body
    node.body = [*doc, *enter, ast.Try(body=body, handlers=[], orelse=[], finalbody=finish)]
    index = 1 if (tree.body and isinstance(tree.body[0], ast.Expr)
                  and isinstance(tree.body[0].value, ast.Constant) and isinstance(tree.body[0].value.value, str)) else 0
    while (index < len(tree.body) and isinstance(tree.body[index], ast.ImportFrom)
           and tree.body[index].module == "__future__"):
        index += 1
    tree.body.insert(index, ast.Import(names=[ast.alias(name="cambc", asname=sdk)]))
    emitted = ast.unparse(ast.fix_missing_locations(tree)) + "\n"
    compile(emitted, str(path), "exec")
    path.write_text(emitted)


def observations(path, output_prefix=None):
    logs = replay_logs(path)
    check_logs(logs)
    result = {}
    for side in ("a", "b"):
        samples, outputs = [], []
        for line in logs.get(f"team-{side}.stdout", "").splitlines():
            if line.startswith(PREFIX):
                record = ast.literal_eval(line[len(PREFIX):])
                if (not isinstance(record, tuple) or len(record) != 3
                        or any(type(value) is not int for value in record)):
                    raise ValueError("Malformed fuel record")
                spent, before, after = record
                if not 0 < spent == before - after or after < 0:
                    raise ValueError("Invalid fuel interval; check for suspension or fuel replenishment")
                samples.append(spent)
            if output_prefix and line.startswith(output_prefix):
                outputs.append(line)
        if not samples or output_prefix and not outputs:
            raise ValueError(f"Missing measurement/output records for team {side} in {path}")
        result[side] = {"samples": samples, "outputs": outputs}
    return result


def compare(bot, output, *, target, maps=("collision", "corners"), repeats=2,
            rounds=1, fuel=1_000_000_000, output_prefix=None, cambc=None, options=None):
    output = Path(output).resolve()
    if output.exists():
        raise ValueError(f"Output already exists: {output}")
    if repeats < 1 or rounds < 1 or fuel < 1 or not maps:
        raise ValueError("Positive repeats, rounds, fuel and at least one map are required")
    cli = executable(cambc)
    options = options or Options()
    baseline, candidate = output / "baseline", output / "optimized"
    original = optimize_folder(bot, baseline, Options(disabled=frozenset(PASS_DESCRIPTIONS)))
    generated = optimize_folder(bot, candidate, options)
    if original["input_sha256"] != generated["input_sha256"]:
        raise ValueError("Input changed between baseline and candidate compilation")
    for staged in (baseline, candidate):
        instrument(staged, target)
    report = {"status": "running", "optimizer_version": "0.2.0", "input_sha256": generated["input_sha256"],
              "target": target, "options": options.to_dict(), "pass_counts": generated["pass_counts"],
              "fuel_quantum_argument": fuel, "rounds": rounds, "repeats": repeats,
              "output_prefix": output_prefix, "comparisons": [],
              "limitations": ["Measures the named call, not an entire match or win rate.",
                              "Target must not yield/end turns or exhaust its fuel quantum.",
                              "Equal printed outputs/call counts do not prove behavioural equivalence.",
                              "Fuel-aware decisions may change; ensure comparable work before interpreting savings."]}
    for run in range(repeats):
        for map_index, game_map in enumerate(maps):
            data = {}
            order = (("baseline", baseline), ("optimized", candidate))
            if run % 2:
                order = tuple(reversed(order))
            for name, staged in order:
                destination = output / f"run-{run}-map-{map_index}-{name}"
                run_command([cli, "run", str(staged), str(staged), "--release", "--rounds", str(rounds),
                             "--fuel", str(fuel), "--map", game_map, "--out-dir", str(destination)], timeout=300)
                paths = list(destination.glob("*.repl26a"))
                if len(paths) != 1:
                    raise ValueError(f"Expected one replay in {destination}")
                data[name] = observations(paths[0], output_prefix)
            for side in ("a", "b"):
                old, new = data["baseline"][side], data["optimized"][side]
                if len(old["samples"]) != len(new["samples"]):
                    raise ValueError(f"Different measured call counts: {game_map}, team {side}")
                if output_prefix and old["outputs"] != new["outputs"]:
                    raise ValueError(f"Different {output_prefix!r} outputs: {game_map}, team {side}")
                before, after = sum(old["samples"]), sum(new["samples"])
                report["comparisons"].append({"run": run, "map": game_map, "side": side,
                    "baseline_fuel": old["samples"], "optimized_fuel": new["samples"],
                    "ratio": before / after, "reduction_percent": 100 * (1 - after / before),
                    "printed_outputs_equal": True if output_prefix else None})
            (output / "results.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    report["status"] = "complete"
    (output / "results.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bot", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--target", required=True, help="module:Function or module:Class.method")
    parser.add_argument("--maps", default="collision,corners")
    parser.add_argument("--repeats", type=int, default=2)
    parser.add_argument("--rounds", type=int, default=1)
    parser.add_argument("--fuel", type=int, default=1_000_000_000)
    parser.add_argument("--require-equal-prefix", dest="output_prefix")
    parser.add_argument("--cambc")
    parser.add_argument("--disable", action="append", choices=sorted(PASS_DESCRIPTIONS), default=[])
    parser.add_argument("--trust-annotations", action="store_true")
    args = parser.parse_args(argv)
    try:
        report = compare(args.bot, args.output, target=args.target,
                         maps=[name.strip() for name in args.maps.split(",") if name.strip()],
                         repeats=args.repeats, rounds=args.rounds, fuel=args.fuel,
                         output_prefix=args.output_prefix, cambc=args.cambc,
                         options=Options(disabled=frozenset(args.disable), trust_annotations=args.trust_annotations))
        for row in report["comparisons"]:
            print(f"run {row['run'] + 1}, {row['map']} team {row['side']}: {row['reduction_percent']:.2f}% less target fuel")
        print(f"Results: {args.output / 'results.json'}")
        return 0
    except (ValueError, OSError, SyntaxError, subprocess.SubprocessError) as error:
        print(f"compare: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
