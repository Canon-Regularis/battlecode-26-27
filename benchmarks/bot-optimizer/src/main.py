"""Paired runner; original.py and optimized.py are supplied by the host driver."""

import json
import sys

import cambc
import original
import optimized


def measure(function, repeats=20):
    start = cambc.fuel_remaining()
    for _ in range(repeats):
        function()
    spent = start - cambc.fuel_remaining()
    assert spent > 0, "fuel measurement crossed a suspension boundary"
    return spent / repeats


def run():
    print("BCOPT_META " + json.dumps({"python": sys.version,
          "width": cambc.game_map.width(), "height": cambc.game_map.height()}), flush=True)
    for name in original.CASES:
        before, after = getattr(original, name), getattr(optimized, name)
        # Also compare position ordering, not merely set equality.
        assert before() == after(), name
        for _ in range(20):
            before()
            after()
        baseline, candidate = [], []
        for batch in range(5):
            if batch % 2:
                candidate.append(measure(after))
                baseline.append(measure(before))
            else:
                baseline.append(measure(before))
                candidate.append(measure(after))
        old, new = sorted(baseline)[2], sorted(candidate)[2]
        print("BCOPT_PAIR " + json.dumps({"name": name, "baseline": old, "optimized": new,
              "ratio": old / new, "baseline_samples": baseline, "optimized_samples": candidate}), flush=True)
    print("BCOPT_DONE", flush=True)


ran = False
while True:
    try:
        if cambc.is_draft():
            if not ran:
                run()
                ran = True
            chosen = cambc.draft.current_draft(cambc.Team.ALLY)
            cambc.draft.pick(next(p for p in range(11) if p not in chosen))
    except Exception:
        import traceback
        traceback.print_exc()
        print("FATAL optimiser benchmark", flush=True)
        raise
    cambc.end_turn()
