# pp01: reward yield versus camp damage

## Hypothesis

Replace phase-1 Monster with Prospector to test whether amplified captured
rewards increase collected and banked gems enough to offset slower camp clearing.
The supplied engine3 probe reports both emblems cost 150 gold (five 30-gold
shards) and give five chosen-stat points; their passives are respectively 0.15
camp damage and 0.25 reward amplification. Historical rules describe the latter
as a bonus on the holder's own share, floored separately for gold and gems;
exact current sharing/rounding semantics remain for PC verification.

The simplified damage-limited ratio 1.25/1.15 suggests about 8.7% more yield per
time, not a guaranteed improvement. Travel/capture time, cooldowns, overkill,
contested captures, death and bag loss can change the result. Shares below four
receive no bonus under historical floor rules; longer fights can be worse.
The supplied current-engine corpus shows widespread Prospector use, but neither
presence nor completion timing establishes causality. The supplied restricted-area
loss (392 versus 1092 collected, 31 versus 30 clears by round 500, zero deaths
and lost gems) motivates economic investigation without identifying its cause.
These PC evidence artifacts were unavailable here and were not independently
revalidated on the Pi.

## Actual change and isolation

Base: `2f0f534e8311ee597e516b11c2afca1bbf608060`.
Parent: `bots/leader_party_tuned/`, not the rejected Focus candidate/mf01.
Before editing, recursive comparison found the candidate identical to the parent.

Only `src/economy.cpp::shop`'s `second` initializer changes:
`monster_shard_of_focus` / `monster_shard_of_strength` become
`prospector_shard_of_focus` / `prospector_shard_of_strength`.
The existing caster list remains Heart of Ruin, Ren, Prism, Stellar, Willow,
Tavi and Cassi. Marcella remains Strength.

Phase 0 remains Durability Health, except Vesper's Treasure Strength. Phase 1
uses Prospector with the same stat selection; later phases still alternate
Power damage stat and Power Health. Five-shard targets, inventory/emblem
accounting, legality checks, runtime cost lookup, channel/spawn/death/Tavi guards,
40-purchase bound, fuel guard and altar-lock purchases are unchanged.
No configuration, roster, pathfinding, movement, camp selection, route estimates,
combat, logging or flags changed. This report is the only added file.

Clear-time and routing heuristics deliberately remain unchanged. They may value
routes inaccurately after losing Monster damage or gaining reward amplification;
this experiment measures the family substitution within those existing policies.

## Checks performed on Pi

- Confirmed checkout HEAD equals the requested base.
- Verified all 33 copied files against the parent's Git objects at that base.
  After the edit, the candidate equals those bytes except the exact single-line
  substitution in `src/economy.cpp`. Reviewed the unified diff: classifications,
  phase selection and purchase continuation are unchanged.
- Read the current leader-party strategy, shopping strategy and tuning report,
  SDK reference, relevant game rules and C++ item/purchase declarations. Both
  Prospector enumerators exist; combination metadata and costs come from runtime.
  Checked-in workspace documentation/configuration targets SDK/CLI 4.0.0, which
  does not establish CLI5/engine3 behavior.
- Built the existing native decision scenarios on aarch64 with GCC 13.3.0:

  ```sh
  g++ -std=c++20 -O2 -Wall -Wextra \
    -I bots/pi_prospector-phase1-01/src \
    bots/pi_prospector-phase1-01/tests/decisions.cpp \
    bots/pi_prospector-phase1-01/src/state_machine.cpp \
    -o /tmp/pp01-decisions
  /tmp/pp01-decisions
  ```

  Compilation succeeded without diagnostics; execution printed
  `PASS protocol and state scenarios`. This is the existing `tests/run.ps1`
  check translated to a native shell command with output outside the repository.
  It covers protocol/state behavior, not engine shopping or Prospector rewards.
  No test that merely restates the changed ternary was added.
- No tracked repository files changed. All task edits are inside the candidate;
  changes remain uncommitted for the bridge.

## Gaps and PC acceptance handoff

No WASM build or matches ran here: `uv`, `cambc` and `clang++` were absent from
PATH. No current-engine purchase/combination events, stat points, completion
rounds, phase continuation or candidate VM fault counts were measured. The PC
must compile the exact pushed source on CLI5/engine3 and verify those properties.
No performance conclusion or recommendation follows from the native check.

Use the same fixed 80-game screen as mf01: eight maps, five frozen controls,
both sides. The cached champion control has 33 wins in the 64 common games;
artifact/map/seed/engine identities must match before comparison. Require zero
candidate VM faults. Reject if direct champion wins are below 8/16 OR common
wins below 31/64. Expand only if direct wins are at least 9/16 AND common wins
at least 35/64; otherwise remain inconclusive pending mechanism inspection.
These are exploratory screen heuristics. Reusing the screen is development,
not confirmation.

Record total and per-actor collections, banked/lost gems, deaths, camp clear
counts, purchase/completion rounds, opportunity to collect after completion,
W/L/draw/faults and score deltas. Final inventory alone cannot establish a
mechanism. No online upload based on this screen; broad diverse-opponent
evaluation and frozen fresh confirmation are required before recommendation.
