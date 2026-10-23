"""Compile research kernels and measure their actual generated Wasm fuel costs."""

import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

from .compiler import optimize_source
from .model import Options, PASS_DESCRIPTIONS
from .runtime import check_logs, executable, replay_logs, run_command


def summarize(replay, expected_names):
    logs = replay_logs(replay)
    check_logs(logs)
    pairs = defaultdict(list)
    metadata = []
    runtime = []
    for team in ("team-a.stdout", "team-b.stdout"):
        text = logs.get(team, "")
        completed = 0
        names = Counter()
        metas = []
        for line in text.splitlines():
            if line.startswith("BCOPT_META "):
                metas.append(json.loads(line[len("BCOPT_META "):]))
            elif line.startswith("BCOPT_RUNTIME "):
                runtime.append(json.loads(line[len("BCOPT_RUNTIME "):]))
            elif line.startswith("BCOPT_PAIR "):
                record = json.loads(line[len("BCOPT_PAIR "):])
                names[record["name"]] += 1
                if record["baseline"] <= 0 or record["optimized"] <= 0:
                    raise ValueError("Nonpositive fuel measurement")
                pairs[record["name"]].append(record)
            elif line == "BCOPT_DONE":
                completed += 1
        if completed != 1 or len(metas) != 1 or names != Counter(expected_names):
            raise ValueError(f"Incomplete benchmark in {team}: done={completed}, pairs={dict(names)}")
        metadata.extend(metas)
    return {"replay": Path(replay).name, "metadata": metadata, "runtime": runtime,
            "pairs": dict(pairs), "minimum_ratio": min(r["ratio"] for rs in pairs.values() for r in rs)}


def benchmark(output, *, maps=("collision", "corners"), cambc=None, suite="core", options=None,
              baseline_source=None):
    output = Path(output).resolve()
    if output.exists():
        raise ValueError(f"Output already exists: {output}")
    maps = list(maps)
    if not maps:
        raise ValueError("At least one map is required")
    cli = executable(cambc)
    fixtures = Path(__file__).resolve().parents[2] / "benchmarks/bot-optimizer/src"
    if suite not in {"core", "specialization", "advanced", "lifetimes", "wrappers", "deferred", "reductions", "shortcircuit", "thirty"}:
        raise ValueError(f"Unknown benchmark suite: {suite}")
    options = options or Options()
    source = (fixtures / {"core": "kernels.py", "specialization": "specialization.py",
                         "advanced": "advanced.py", "lifetimes": "lifetimes.py",
                         "wrappers": "wrappers.py", "deferred": "deferred.py",
                         "reductions": "reductions.py", "shortcircuit": "shortcircuit.py",
                         "thirty": "thirty.py"}[suite]).read_text()
    result = optimize_source(source, options)
    baseline = Path(baseline_source).read_text() if baseline_source is not None else source
    # Read the literal case inventory without executing SDK-dependent bot code.
    import ast
    tree = ast.parse(source)
    names = next(ast.literal_eval(n.value) for n in tree.body
                 if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "CASES" for t in n.targets))
    bot = output / "bot"
    src = bot / "src"
    src.mkdir(parents=True)
    shutil.copy2(fixtures / "main.py", src / "main.py")
    (src / "original.py").write_text(baseline)
    (src / "optimized.py").write_text(result.source)
    report = {"status": "running", "target": "cambc 3.0.4", "suite": suite, "options": options.to_dict(),
              "source_sha256": hashlib.sha256(source.encode()).hexdigest(),
              "baseline_source_sha256": hashlib.sha256(baseline.encode()).hexdigest(),
              "baseline": str(baseline_source) if baseline_source is not None else "unmodified source",
              "compiler": result.diagnostics(), "datasets": []}
    (output / "results.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    for index, game_map in enumerate(maps):
        destination = output / f"replays-{index}"
        run_command([cli, "run", str(bot), str(bot), "--release", "--rounds", "1",
                     "--fuel", "1000000000", "--map", game_map, "--out-dir", str(destination)])
        replays = sorted(destination.glob("*.repl26a"))
        if len(replays) != 1:
            raise ValueError(f"Expected one replay in {destination}")
        dataset = summarize(replays[0], names)
        dataset["map"] = game_map
        report["datasets"].append(dataset)
        # Retain completed maps even if a later map fails.
        (output / "results.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    report["status"] = "complete"
    (output / "results.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--maps", default="collision,corners")
    parser.add_argument("--cambc")
    parser.add_argument("--baseline-source", type=Path,
                        help="Use an existing equivalent kernel implementation as baseline (not re-optimised)")
    parser.add_argument("--disable", action="append", choices=sorted(PASS_DESCRIPTIONS), default=[])
    parser.add_argument("--suite", choices=("core", "specialization", "advanced", "lifetimes", "wrappers", "deferred", "reductions", "shortcircuit", "thirty"), default="core")
    args = parser.parse_args(argv)
    try:
        report = benchmark(args.output, maps=[m.strip() for m in args.maps.split(",") if m.strip()],
                           cambc=args.cambc, suite=args.suite, baseline_source=args.baseline_source,
                           options=Options(disabled=frozenset(args.disable)))
        for dataset in report["datasets"]:
            print(dataset["map"] + ":")
            for name, records in dataset["pairs"].items():
                ratios = [r["ratio"] for r in records]
                print(f"  {name}: {min(ratios):.2f}–{max(ratios):.2f}x baseline/optimized fuel")
        print(f"Results: {args.output / 'results.json'}")
        return 0
    except (ValueError, OSError, subprocess.SubprocessError) as error:
        print(f"benchmark: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
