"""Read probe records directly from replay ZIPs; never extract archive paths."""

import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import zipfile


def summarize(path):
    pairs = defaultdict(list)
    phases = {}
    metadata = []
    completed = Counter()
    failures = []
    with zipfile.ZipFile(path) as replay:
        for name in ("team-a.stdout", "team-b.stdout"):
            phase = None
            text = replay.read(name).decode("utf-8", errors="replace").replace("\0", "")
            for line in text.splitlines():
                if line.startswith("PAIR "):
                    record = json.loads(line[5:])
                    pairs[record["name"]].append(record)
                    phases[record["name"]] = phase
                elif line.startswith("META "):
                    record = json.loads(line[5:])
                    metadata.append(record)
                    phase = record.get("phase", phase)
                elif line.startswith("DONE "):
                    completed[line[5:]] += 1
                if "FATAL " in line or "Traceback (most recent call last)" in line:
                    failures.append(line)
    if failures or completed["draft"] != 2 or completed["game"] == 0:
        raise ValueError(f"Incomplete or failed probe in {path}: {dict(completed)}, {failures}")
    if completed["game"] != sum(record.get("phase") == "game" for record in metadata):
        raise ValueError(f"Not every gameplay instance completed in {path}")
    for name, records in pairs.items():
        expected = 2 if phases[name] == "draft" else completed["game"]
        if len(records) != expected:
            raise ValueError(f"Incomplete pair {name!r} in {path}: expected {expected}, got {len(records)}")
    first = metadata[0]
    return {
        "replay": Path(path).name,
        "dimensions": [first["width"], first["height"]],
        "python_version": first["version"],
        "completed": dict(completed),
        "pair_count": len(pairs),
        "pairs": {
            name: {
                "baseline_fuel": [min(r["baseline"] for r in records), max(r["baseline"] for r in records)],
                "alternative_fuel": [min(r["alternative"] for r in records), max(r["alternative"] for r in records)],
                "ratio": [min(r["ratio"] for r in records), max(r["ratio"] for r in records)],
                "observations": len(records),
            }
            for name, records in pairs.items()
        },
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("replays", nargs="+", type=Path)
    parser.add_argument("--json", action="store_true", help="Emit machine-readable summary")
    args = parser.parse_args()
    datasets = [summarize(path) for path in args.replays]
    if args.json:
        print(json.dumps({"cambc_version": "3.0.4", "datasets": datasets}, indent=2))
        return
    for dataset in datasets:
        width, height = dataset["dimensions"]
        print(f"\n## {width}x{height}: {dataset['pair_count']} pairs\n")
        print("| Case | Baseline / alternative fuel |")
        print("| --- | ---: |")
        for name, record in dataset["pairs"].items():
            lo, hi = record["ratio"]
            ratio = f"{lo:.2f}x" if round(lo, 2) == round(hi, 2) else f"{lo:.2f}–{hi:.2f}x"
            print(f"| {name} | {ratio} |")


if __name__ == "__main__":
    main()
