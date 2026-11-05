# mf01: Marcella damage-stat choice

Base: `2f0f534e8311ee597e516b11c2afca1bbf608060`, copied from
`bots/leader_party_tuned/`. Candidate: `bots/pi_marcella-focus-01/`.

## Hypothesis

Buying Focus for Marcella's damage phases may improve ranged burst, score or
survival. The supplied PC evidence reports 288 Focus and 13 Health purchases
among 301 capped early shard units in 31 leader Marcella team views, versus
98 Health and 84 Strength purchases and no Focus in our latest 20 ranked games.
Those summaries are unavailable on this Pi and were not independently checked.
Different leader items and executors prevent a causal conclusion.

Strength may still suit this executor better: under the historical kit values,
one Focus shard adds 28 damage to the 2x Focus spell; nine landed basic/reset
attacks gain 40.5 damage from one Strength shard. A negative result remains
plausible. This experiment isolates shopping stat choice.

## Actual change

Added only `||type==champion_type::marcella` to the local `caster` predicate in
`src/economy.cpp::shop()`.

Marcella's phases now buy five Durability Health shards, five Monster Focus
shards, then alternate Power Focus and Power Health phases. Previously the
Monster and Power damage phases used Strength. Combined-emblem accounting,
five-unit phase targets, item families, purchase legality, gold thresholds,
40-purchase bound, fuel guard, altar-lock purchase and action ordering are
unchanged. Every other champion's classification is unchanged because the only
added disjunct matches Marcella. Vesper's Treasure Strength opening is preserved.

No planner, navigation, draft, targeting, configuration, SDK or dependency changes.

## Checks performed on Pi

- Confirmed checkout HEAD equals the requested base; before editing, recursive
  comparison found the candidate identical to `leader_party_tuned`.
- Read the current strategy overview, shopping, combat and route-planning notes,
  SDK 4 compatibility notes, relevant game rules, C++ SDK item declarations and
  purchase legality implementation, and shopping/combat/routing source.
- Inspected the unified economy diff. A temporary Python check compared every
  copied file byte for byte, confirmed only `src/economy.cpp` differed, and
  verified its full contents equal the base-commit economy file with exactly
  the requested disjunct appended. This establishes unchanged shopping phases,
  families and classification of every other champion without adding a test
  that restates the predicate.
- Compiled the existing native scenarios with
  `g++ -std=c++20 -O2 -Wall -Wextra -I bots/pi_marcella-focus-01/src bots/pi_marcella-focus-01/tests/decisions.cpp bots/pi_marcella-focus-01/src/state_machine.cpp -o /tmp/mf01-decisions`.
  Compilation succeeded without diagnostics; running `/tmp/mf01-decisions`
  printed `PASS protocol and state scenarios`. This is the existing PowerShell
  runner's compile/run check adapted to Linux with output in `/tmp`; it covers
  protocol/state behavior, not engine shopping or the modified translation unit.
- Tracked working-tree and staged diffs were empty; final scope comparison
  permits only the economy edit and this report relative to the copied baseline.

## Known interactions and unverified work

The executor still attacks before casting and supports attack resets. Travel and
banking can move before discretionary combat; `ready()` excludes a spell marked
movement-exclusive when normal movement is unavailable. Marcella's ranged damage
spell has that restriction, so extra Focus does not guarantee more effective
damage or survival.

`route_plan.cpp` deliberately retains its separate caster estimate (Heart and
Ren only). It therefore estimates Marcella with five Strength growth increments
and 20% of base Focus, while actual shopping now adds Focus. This mismatch can
affect estimated camp service times and loop selection. Pathfinding is preserved.

No CAMBC, uv, clang++ or PowerShell executable was exposed on PATH, and this
checkout has no provisioned WASI build assets. No WASM release build or engine
games were attempted, and no current-engine compatibility, purchase summaries,
VM-fault rate or performance benefit is claimed. No new tests, flags or logging
were added. Changes are left uncommitted for the bridge.

## PC evaluation handoff (pending)

PC must perform the actual WASM release build and artifact hash, use the verified
current CLI5/engine3 compatibility setup, and inspect purchases in engine
summaries. The screen is 80 games: eight fixed maps, five frozen controls and
both sides, including the frozen champion's matched common-opponent control.
Require zero candidate VM faults. Reject if direct champion wins are below 8/16
or common-opponent wins trail baseline by more than 2/64. Expand only with at
least 9/16 direct wins AND at least 2/64 more common-opponent wins than baseline;
otherwise label inconclusive and investigate the mechanism. These are screening
heuristics, not significance claims.

Record W/L/draw/faults, score differences, Marcella purchases, damage, collected,
submitted and lost gems, deaths, map/seed hashes, and exact engine/source/WASM
identities. No online upload or ranked change follows this screen. Broad and
fresh confirmation is required after any screen success. All PC results remain
unverified here.
