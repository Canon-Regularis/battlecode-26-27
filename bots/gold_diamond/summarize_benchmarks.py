"""Summarize checked-in CAMBC statistics JSON files by experiment prefix."""

import json
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).parent / "benchmarks"
PREFIXES = ("final_", "fast_", "coord_", "monster_", "draftv_",
            "economic_farmer_proxy_", "carrier_hunter_proxy_",
            "altar_denial_proxy_")


def main():
    rows = defaultdict(lambda: [0, 0, 0, 0, 0])
    for path in ROOT.glob("*.json"):
        prefix = next((value for value in PREFIXES if path.name.startswith(value)), None)
        if prefix is None or not (path.stem.endswith("_a") or path.stem.endswith("_b")):
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        side = 0 if path.stem.endswith("_a") else 1
        row = rows[prefix]
        row[0] += 1
        row[1] += data["outcome"] == ("teamA" if side == 0 else "teamB")
        row[2] += data["teams"][side]["submittedGems"]
        row[3] += data["teams"][1 - side]["submittedGems"]
        row[4] += data["botFaults"][side]
    print("experiment,matches,wins,our_gems,opponent_gems,bot_faults")
    for prefix in PREFIXES:
        if prefix in rows:
            print(prefix.rstrip("_"), *rows[prefix], sep=",")


if __name__ == "__main__":
    main()
