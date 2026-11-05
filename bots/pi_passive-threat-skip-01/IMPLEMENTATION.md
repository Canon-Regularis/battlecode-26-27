# pts01: passive-camp threat skips

## Hypothesis and scope

Base: `2f0f534e8311ee597e516b11c2afca1bbf608060`, cloned from
`leader_party_tuned`. Gem and gold clusters cannot attack. Skipping them by cached
immutable type before querying live state should preserve pointwise threat results
while avoiding unnecessary host imports. Repeated `incoming_at` calls can amplify
the savings. This is an independent release optimization, with no objective,
profiler, telemetry, or dt01 experiment changes.

Read the leader-party strategy overview, combat and pathfinding notes, candidate
README/test instructions, SDK reference notes, game rules, and relevant C++ SDK
definitions. In `sdk/cpp/cambc.h`, `camp_type` documents both clusters as
nonattacking; `kind()` returns `type_`, and the two cluster predicates compare that
cached value. The game rules note the internal range can be 3 despite zero
Strength. Range alone is therefore not a reason to treat clusters as dangerous.
The task supplies current-engine zero-strength/growth probe evidence; that probe
was not rerun here. No measured release speedup is claimed from diagnostic traces
or these native checks.

## Actual changes

Added `if(c.is_gem_cluster()||c.is_gold_cluster()) continue;` at the start of
exactly three existing visible-camp loops:

1. `src/observations.cpp::incoming_at`.
2. `src/observations.cpp::observe`, in the loop setting `camp_hit`.
3. `src/navigation.cpp::move_to`, inside safe blocking.

The original expressions remain intact after each guard, including short-circuit
order, comparisons, repeated strength query for summed damage, and danger masks.
`vision::camps()` enumeration remains in place. Physical occupancy still comes
from `vision::camp_tiles()`. All other production files are byte-identical to
base `leader_party_tuned`; pathfinding, same-round guards, collision handling,
capture/target selection, shopping, planner, flags, and cache invalidation are
unchanged. Existing baseline telemetry was neither added to nor changed.

## Focused checks on the Pi

Run from the repository root:

```sh
bash bots/pi_passive-threat-skip-01/tests/run_native.sh
```

Passed on aarch64 with GCC 13:

- **12 production observation/navigation scenarios.** `tests/passive_threats.cpp`
  compiles the actual `observations.cpp` and `navigation.cpp`, including their
  real headers, against `tests/fake_sdk/cambc.h`. Both cluster types are exercised
  dead, sleeping and awake. All three scans produce zero passive live queries
  (`is_alive`, `is_awake`, strength, position, range), no passive incoming damage,
  no `camp_hit`, and no additional safe danger mask. Camp enumeration counts are
  checked. Living passive tiles remain occupied, and both safe/unsafe attempts to
  target them return `invalid_goals` before field computation or movement.
- **Mixed visible groups with each attacking kind** (wolf, elk, monolith, golem):
  awake/in-range, awake/out-of-range, sleeping, dead and zero-strength members,
  both passive types, plus an enemy champion. Checked exact damage sum (31),
  `camp_hit`, enemy risk and the complete safe-blocking mask passed to the field.
  Live-call traces retain the attacking-camp sequence/count, including the
  repeated strength read when damage is added. Position/range pairs permit either
  C++ argument evaluation order. Sleeping/dead attackers also have isolated
  no-threat cases.
- **Existing native protocol/state scenarios** passed (`decisions.cpp` with
  `state_machine.cpp`), using the same build as `tests/run.ps1` with a temporary
  Linux output location.
- **Real-SDK syntax check of every production translation unit** passed with
  `g++ -std=c++20 -fpermissive -include cmath -fsyntax-only -I sdk/cpp ...`.
  Initial strict GCC checks failed on existing SDK `team()` declarations;
  `-fpermissive` downgrades those errors. A subsequent all-source check exposed
  baseline `std::ceil` include dependencies in objectives/route_plan; compiler
  preinclude `cmath` resolves them without editing production or SDK files.
- **Existing 240-case planner differential check** passed against the local Git
  Python reference. Used a temporary `/tmp/pts01-verify-translation.py` copy of
  `tests/verify_translation.py`, changing only its Windows compiler/output paths
  and reference-directory paths for Linux. Rankings, routes, scores and timing
  matched. GCC reported the existing planner indentation warning.
- Compared every candidate `src` file against the base Git object's
  `bots/leader_party_tuned/src`: only the two intended files differ.

All generated executables/adapted wrappers were placed under `/tmp`. The fake SDK
records masks and query calls; it does not implement engine pathfinding, visibility
faults, suspension, or fuel accounting. These checks establish the local contract,
not engine performance or scoring strength. `strategy_contracts.cpp` requires the
absent generated `geometry-under-test.h` and was not run. No WASM release build,
engine games, engine-contract/Wasmtime suite, or new runtime probe was run: this Pi
has no `uv`, CAMBC CLI, Clang/WASI SDK or Wasmtime on PATH. The native compatibility
check is not an exact-source CLI5/current-engine release-build substitute.

## Frozen PC gate (pending; no outcomes viewed)

Use exact-source CLI5/current-engine release artifacts, normal fuel, no profiler
in either artifact, and require zero candidate VM faults. Run the standard
80-game screen: 8 maps, 5 frozen controls, both sides, with matched current-engine
baseline64 common fixtures. Retain the existing frozen maps/controls/fixtures;
their exact roster and release artifact hashes must be recorded by the PC runner.

- Reject if direct champion is below **8/16**, or common is below **31/64**.
- Expand for strength only if direct is at least **9/16** AND common at least
  **35/64**. Otherwise label inconclusive and inspect the mechanism.
- Inspect per-map/per-actor `fuelExhausted` counts separately for initialization
  rounds 1–2, the first 100 rounds and the whole game, alongside completed camp
  captures, banked gems, deaths and score. Compare early timing as well as totals;
  whole-game pauses depend on game duration. Explicitly inspect Swirl on both
  sides against C02 using original baseline fixtures.
- Lower fuel-event counts alone cannot justify promotion if scoring regresses.
  If observation costs remain dominant or pauses fail to improve, do not broaden
  the claim to all runtime work. Any diagnostic-ON rerun stays separate from
  strength evidence.
- If the screen qualifies, predeclare diverse-opponent/new-development-map tests
  before viewing their outcomes. Preserve the 16 confirmation maps and require
  fresh confirmation before a ranked recommendation. No upload from the screen
  alone. Interaction with dt01's dense passive group remains a separate experiment.

Implementation is ready for that PC gate; strength and release-fuel value remain
unmeasured. Changes are left uncommitted for the bridge to commit and push.
