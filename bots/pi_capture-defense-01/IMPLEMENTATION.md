# cd01: combat during completed-camp occupation

Base: `2f0f534e8311ee597e516b11c2afca1bbf608060`; independent clone of
`leader_party_tuned`. Changes are uncommitted and confined to this candidate.

## Hypothesis and implementation

The supplied Sunburst/Fish diagnostic identifies unused legal combat windows
while occupying a cleared camp. It does not establish prevalence or show that
combat would save the capture or beat Fish. Existing stationary enemy combat
may recover useful attacks/casts without vacating the reward tile.

Only the fresh reward-available, self-on-reward-tile branch in
`src/bot.cpp::Bot::camp_action()` changes: when the existing snapshot's `foes`
vector is nonempty, call `fight(world, -1, true)`, then return as before. Empty
`foes` retains the immediate return. No new observation or threat query, combat
policy, pursuit, movement, telemetry, planner, item, draft, threshold, task,
leadership, navigation or dispatcher change was made. All other inherited
files match `leader_party_tuned`; additions are this report and focused tests.

Read current strategy overview, combat and state-machine documents,
`docs/cambc/api/SDK_4.0.0.md`, relevant game-rule kit descriptions, and the
checked-in C++ SDK. The SDK distinguishes `ability_dash` (a move to a different
tile) from damage, AoE damage, CC, attack reset, heal and shield. Actual `fight()`
selects only damage/AoE/CC or attack reset offensively; its existing
`defend_cast()` can heal/shield. None selects a dash. In particular, Ren's kit
has a stationary range-4 damage/stun spell, exclusive with walking, and a
separate range-2 dash. The former can be selected by `fight()` when ready and
movement is available; the latter cannot. Exclusive-with-movement consumes
movement opportunity, not occupancy. Existing shield/heal behavior is inherited,
not a new defensive-casting policy. `-1,true` excludes camp selection and camp
AoE scoring. Channel, action availability, readiness, current-round and fuel
reserve guards remain in the original combat function.

## Focused checks on the Pi

`bash bots/pi_capture-defense-01/tests/run_native.sh` passes with native
GCC 13.3.0. It runs the existing protocol/state scenarios, the new production
integration scenarios, and real-SDK syntax checks for every candidate `.cpp`.

`tests/capture_defense.cpp` links the actual `bot.cpp`, `combat.cpp`, and
`state_machine.cpp`, including the private production `camp_action()` and
public `play_turn()`. GNU link wrapping counts calls and forwards to real
`fight()`; there is no duplicated occupation policy. Test-only
`-fno-access-control` permits fixture setup and direct private entry access.
Cases cover:

- Fresh cleared group, self on tile, visible enemy: exactly one `fight` with
  `task=-1, travel=true`, one legal enemy basic attack, no movement or abandonment.
- Enemy-free occupation: no combat call, movement or abandonment.
- Unavailable actor (neither attack nor cast), and each recall/tribute/teleport
  channel with action allowances otherwise present: the real fight guards
  prevent attacks/casts.
- Damage, AoE and CC casts execute without movement; dash-only casting is
  excluded. Cooldown and movement-exclusive spell readiness are enforced;
  fuel at reserve and round rollover prevent offensive actions.
- No task remains inert. Living, unknown, stale/unseen, and outside-reward-tile
  paths retain their navigation and normal task-combat calls. Another ally's
  reward occupation retains the guard path.
- Real dispatcher enters camp combat in the ordinary occupation case. Danger
  instead abandons and retreats, with its existing combat occurring only after
  retreat. Tribute/teleport beat danger and make no combat call. Safe recall
  remains in recall with no camp combat.

Additional existing native checks passed:

- `tests/strategy_contracts.cpp`: 55,294,203 checks, 5,041 map dimensions,
  21,298,225 tiles, 116,964 centers, 1,176,588 requests. Its missing generated
  `geometry-under-test.h` was provided in a temporary directory using the exact
  `World::chunk`/`World::center` bodies from candidate `objectives.cpp`, adapting
  only `vec2` to a minimal native Point type.
- `tests/verify_translation.py`: all 240 differential planner cases matched the
  Git-stored Subhan reference rankings, routes, scores and timings. Executed
  its existing source with the Windows compiler path changed to `g++` and both
  output/reference directories redirected to `/tmp`; no repository tool or
  existing test file was edited.
- Candidate/base directory comparison: the only production difference is the
  requested occupation branch; all pathfinding and configuration files match.

Native portability caveats: unmodified SDK declarations such as
`team team()` fail strict GCC name lookup, so checks use `-fpermissive` (existing
SDK warnings). Full-source syntax checks also use `-include cmath` because
inherited `objectives.cpp` and `route_plan.cpp` use `std::ceil` without a direct
include on this host. Initial unadjusted checks exposed those issues; the SDK
and unrelated production sources were left unchanged. These host checks are
not the CLI5/engine3 release-build gate.

## Fixture limits and remaining PC gates

Host stubs use an 8x8 board, fixed legal enemy geometry and synthetic action
allowance bits. They do not calculate engine restrictions; unavailable actors
model the resulting lack of attack/cast allowances. World refresh, observation
invalidation, navigation, retreat and shopping are stubs; optional ward dispatch
is wrapped out. Living/unknown path fixtures have no physical camp entities,
so they verify dispatch/navigation calls rather than real camp target execution.
No damage/health resolution, capture countdown, engine fuel cost/suspension,
visibility changes, movement physics or replay counterfactual is simulated.
The tests establish execution coverage, not practical capture or strength value.
No engine matches, challenge, uploads or tournaments were run here.

Frozen PC work remains exactly as requested, before promotion:

- Review exact source; release build with CLI5/current engine3 and normal fuel;
  require zero candidate faults and unchanged higher-priority escape/channel
  behavior, with no movement caused by this branch.
- Standard 80-game screen: 8 maps, 5 controls, both sides. Preserve matched
  baseline 64 games. Reject if direct champion <8/16 OR common <31/64. Expand
  only if direct >=9/16 AND common >=35/64; otherwise inconclusive.
- Inspect captures, submitted gems, deaths/lost gems, and first-100/whole-game
  fuel suspensions. Inspect contested release capture windows for added
  stationary attacks and continuing occupancy. If no branch exposure can be
  identified, report mechanism unverified and use a separate controlled
  coverage fixture before broader strength conclusions.
- The original online replay is diagnostic only; no changed candidate replay
  against Fish is claimed without a real authorized challenge. No upload from
  screening alone. Freeze broader tests before outcomes and preserve the
  16 confirmation maps.
