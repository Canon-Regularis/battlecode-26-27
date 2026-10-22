"""Run a drawing-only self-match and print the draft planner's ranked loops.

Usage: uv run python bots/economy-bot/inspect_loops.py --map packs
"""

import argparse
import ast
import json
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile


ROOT = Path(__file__).resolve().parents[2]
# Import only SDK-free settings; the host cannot load cambc's WASM bindings.
sys.path.insert(0, str(ROOT / "bots" / "economy-bot" / "src"))
from settings import LOOP_COLORS, REPORT_MARKER, ROUNDS_PER_LOOP


def extract_report(data):
    text = data.decode("utf-8", errors="replace")
    if "bot error:" in text:
        message = text[text.index("bot error:"):].splitlines()[0]
        raise ValueError(message)
    index = text.find(REPORT_MARKER)
    if index < 0:
        raise ValueError("draft did not produce a loop report: " + text.replace("\0", "")[:2000])
    payload = text[index + len(REPORT_MARKER):].splitlines()[0]
    return ast.literal_eval(payload)


def print_report(report, side):
    print(f"\nTeam {side.upper()} | squad body types {report['roster']} | "
          f"risk tolerance {report['risk_tolerance']:.2f}")
    if not report["loops"]:
        print("No feasible scoring loop found within the search budget.")
    for rank, loop in enumerate(report["loops"], 1):
        order = " -> ".join(str(tuple(p)) for p in loop["camps"])
        color = LOOP_COLORS[(rank - 1) % len(LOOP_COLORS)][0]
        print(f"#{rank} ({color}): altar {tuple(loop['altar'])} -> {order} -> altar")
        print(f"  {loop['gems']} gems, {loop['gold']} gold | "
              f"{loop['gems_per_turn']:.3f} gems/turn | adjusted score {loop['score']:.3f}")
        print(f"  travel {loop['travel']}, clear/capture {loop['clear_capture']}, "
              f"tribute {loop['tribute']}, wait {loop['respawn_wait']} | "
              f"period {loop['period']}, first deposit ~{loop['first_deposit']}")
        print(f"  positional risk {loop['risk']:.1%} | multiplier {loop['risk_multiplier']:.3f} | "
              f"base score {loop['base_score']:.3f}")


def argument_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--map", default="packs", help="Map name or .map26a path")
    parser.add_argument("--side", choices=("a", "b", "both"), default="a")
    parser.add_argument("--fuel", type=int, help="Override per-turn fuel for deeper local searches")
    parser.add_argument("--json", action="store_true", help="Print just the extracted JSON report")
    parser.add_argument("--view", action="store_true", help="Open the replay with loop drawing overlays")
    return parser


def run_inspection_match(cli, map_name, fuel=None):
    """Build/run a drawing-only match and return its newly created replay."""
    output = ROOT / "replays" / "loop-inspection" / Path(map_name).stem
    output.mkdir(parents=True, exist_ok=True)
    before = set(output.glob("*.repl26a"))
    command = [*cli, "run", "economy-bot", "economy-bot", "--map", map_name,
               "--rounds", str(len(LOOP_COLORS) * ROUNDS_PER_LOOP), "--out-dir", str(output)]
    if fuel is not None:
        command.extend(("--fuel", str(fuel)))
    result = subprocess.run(
        command, cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
    )
    if result.returncode:
        raise subprocess.CalledProcessError(result.returncode, command, output=result.stdout)
    bundles = set(output.glob("*.repl26a")) - before
    if not bundles:
        raise ValueError("Runner did not produce a replay:\n" + result.stdout)
    return max(bundles, key=lambda path: path.stat().st_mtime_ns)


def read_replay_reports(bundle, sides):
    with zipfile.ZipFile(bundle) as replay:
        return {side: extract_report(replay.read(f"team-{side}.stdout")) for side in sides}


def open_replay(cli, bundle):
    subprocess.Popen([*cli, "view", str(bundle)], cwd=ROOT,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def main(argv=None):
    parser = argument_parser()
    args = parser.parse_args(argv)
    if args.fuel is not None and args.fuel <= 0:
        parser.error("--fuel must be positive")
    uv = shutil.which("uv")
    if uv is None:
        parser.error("uv not found; install uv and run this script with uv run")
    cli = [uv, "run", "cambc"]
    sides = ("a", "b") if args.side == "both" else (args.side,)
    bundle = None
    try:
        bundle = run_inspection_match(cli, args.map, args.fuel)
        reports = read_replay_reports(bundle, sides)
    except subprocess.CalledProcessError as error:
        print(error.output, file=sys.stderr)
        return error.returncode
    except (ValueError, KeyError, zipfile.BadZipFile) as error:
        print(str(error) + (f"\nReplay: {bundle}" if bundle else ""), file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(reports, indent=2))
    else:
        for side, report in reports.items():
            print_report(report, side)
        print(f"\nReplay: {bundle.relative_to(ROOT)}")
        print("Enable debug drawings for a champion on your chosen team. "
              f"The overlay cycles through loops every {ROUNDS_PER_LOOP} rounds.")
    if args.view:
        open_replay(cli, bundle)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
