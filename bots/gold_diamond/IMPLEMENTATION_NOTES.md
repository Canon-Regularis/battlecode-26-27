# Gold Diamond candidate: implementation notes

## What runs

`src/main.py` selects `fast_policy.Bot` by default. The active loop drafts, farms visible camps, moves toward reachable camp spawn tiles, holds a reward tile for capture, vacates known respawn tiles while carrying gems, and heads to an unlocked altar whenever it carries gems. It buys permanent Power Strength shards at spawn; Tavi buys them in the field. Local attacks include a lethal gem carrier check. It uses the documented SDK action checks and refreshes vision after movement before attempting a melee attack.

The draft chooses Tavi, Cassi & Issac, then Varg by default. Map density, bushes, compact terrain, and revealed enemy picks can change later priorities. `draft_memory` stores the complete body roster with a magic value and checksum, including separate Cassi and Issac entries. The active policy does not yet consume that roster.

The active economic loop is adapted from this repository's `bots/D1/src/simple_policy.py` and `bots/D1/src/combat.py`. This was a deliberate measured fallback: it starts acting around round 29 on Expanse, while the richer policy first acted around round 71 and lost most baseline matches. All code for the richer candidate remains in `src/policy.py`, `src/world.py`, `src/navigation.py`, `src/combat.py`, and `src/comm.py`. Set `ENABLE_EXPERIMENTAL_POLICY = True` in `src/strategy_config.py` to run it, then rebuild and benchmark before submitting. Its source implements a deterministic post-draft camp matching estimate, eight-byte shared objective/alert protocol, camp status memory, retreat/banking logic, and legal attack/spell attempts. Several advanced feature flags remain off.

## SDK and rule observations

- The local SDK is 2.1.5 and exposes `CampGroup.state()` only under vision. The active policy catches visibility errors and remembers observed respawn timers.
- The attached master spec says camp groups are unavailable in draft, while this SDK's `game_map.camp_groups()` documentation says they are available. Opening assignments were intentionally computed after draft regardless.
- `cambc run` has map, side, rounds, fuel, and statistics options, but no seed option in this installed CLI. The benchmark matrix covers maps and sides; it is not a seeded tournament.
- Neither a local match nor these proxy opponents establish ladder rank. No Gold or Diamond ranking is claimed.

## Verification and remaining gaps

The final bot built, bundled, passed 14 deterministic draft/protocol tests, and completed 36 full local matches against D1 and three opponent styles without an engine bot fault. Match statistics are in `benchmarks/`; see `BENCHMARKS.md` for interpretation.

The active policy does **not** provide deterministic six-body camp assignments or use the eight-byte objective protocol. A tested single-target shared-claim candidate fell from 9/18 to 1/18 wins against D1, so it was not promoted. The richer candidate has these features but incurs an expensive startup and lost its initial D1 matrix. Active play also lacks full Cassi/Issac paired survival handling, conditional Ren denial, Stellar harassment, planned wards/chokepoints, monolith scheduling, and the master's full 42-case mechanics matrix. The 14 tests exercise protocol and draft decisions; they do not substitute for engine mechanics tests. These are open performance and completeness gaps.

## Next three measured improvements

1. Keep the compact first-turn path and use a reachable-distance-field assignment for post-draft claims. Compare each map and side against the current loop before enabling it; geometric nearest-camp claims performed badly.
2. Add carrier/altar defense only at validated payoff thresholds, including Cassi/Issac's linked-death cost. Measure gem tribute and deaths against the carrier-hunter and altar-denial proxies.
3. Build the 42 engine mechanics fixtures from the supplied case matrix, then run fuel and outcome A/B checks on every enabled tactical feature. The largest current uncertainty is legal and profitable multi-action turn ordering under live vision changes.

## Commands

Run from the repository root:

```powershell
cambc build bots/gold_diamond
python -B -m unittest discover bots/gold_diamond/tests -v
cambc run bots/gold_diamond bots/D1 --map expanse --statistics bots/gold_diamond/benchmarks/recheck_expanse_a.json
cambc run bots/D1 bots/gold_diamond --map expanse --statistics bots/gold_diamond/benchmarks/recheck_expanse_b.json
python bots/gold_diamond/summarize_benchmarks.py
cambc bundle bots/gold_diamond --output bots/gold_diamond/submission.zip
```

The bundle is local and ready for review. Uploading it is a separate external action: `cambc submit bots/gold_diamond`.
