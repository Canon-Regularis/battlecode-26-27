"""Optimise a bot folder without modifying the original."""

import argparse
import json
from pathlib import Path
import subprocess
import sys

from .compiler import REPORT_NAME, optimize_folder
from .model import Options, PASS_DESCRIPTIONS
from .runtime import verify


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bot", nargs="?", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--list-passes", action="store_true")
    parser.add_argument("--disable", action="append", choices=sorted(PASS_DESCRIPTIONS), default=[])
    parser.add_argument("--trust-annotations", action="store_true",
                        help="Opt into exact supported SDK/int parameter types from annotations")
    parser.add_argument("--max-materialize", type=int, default=4096,
                        help="Maximum statically bounded integer sum list size (0 disables nonempty lists)")
    parser.add_argument("--min-bulk-fields", type=int, default=4,
                        help="Minimum frozen-record field count for native bulk initialisation")
    parser.add_argument("--verify", action="store_true", help="Build generated bot with cambc --release")
    parser.add_argument("--maps", help="Comma-separated smoke-test maps (requires --verify)")
    parser.add_argument("--rounds", type=int, default=3, help="Smoke-test rounds (default: 3)")
    parser.add_argument("--cambc", help="Path to the cambc 3.0.4 executable")
    args = parser.parse_args(argv)
    if args.list_passes:
        for name, description in PASS_DESCRIPTIONS.items():
            print(f"{name}: {description}")
        return 0
    if not args.bot or not args.output:
        parser.error("bot and --output are required")
    if args.maps and not args.verify:
        parser.error("--maps requires --verify")
    if args.rounds <= 0:
        parser.error("--rounds must be positive")
    try:
        options = Options(trust_annotations=args.trust_annotations,
                          max_materialize=args.max_materialize, min_bulk_fields=args.min_bulk_fields,
                          disabled=frozenset(args.disable))
        report = optimize_folder(args.bot, args.output, options)
        if args.verify:
            try:
                checks = verify(args.output, cambc=args.cambc,
                                maps=[m.strip() for m in (args.maps or "").split(",") if m.strip()],
                                rounds=args.rounds)
            except (ValueError, OSError, subprocess.SubprocessError) as error:
                report["validation"]["runtime"] = {"status": "failed", "error": str(error)}
                (args.output / REPORT_NAME).write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
                raise
            report["validation"]["runtime"] = checks
            (args.output / REPORT_NAME).write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
        count = sum(report["pass_counts"].values())
        print(f"Wrote {args.output}: {count} rewrites in {len(report['files'])} Python files")
        for name, count in report["pass_counts"].items():
            print(f"  {name}: {count}")
        warnings = {warning for file in report["files"].values() for warning in file["warnings"]}
        for warning in sorted(warnings):
            print(f"Warning: {warning}")
        print(f"Report: {args.output / REPORT_NAME}")
        return 0
    except (ValueError, OSError, SyntaxError, subprocess.SubprocessError) as error:
        print(f"optimizer: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
