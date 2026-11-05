# ase01: conversion observation epochs

Parent: `914cf67173be7c5231ccaa2878e4292d236b71e4`, base
`bots/pi_actor-scene-layout-01/`. Candidate:
`bots/pi_actor-scene-epoch-01/`. Changes remain uncommitted and confined to
this candidate. No games, uploads, ranked changes or infrastructure changes ran
on the Pi. No competitive improvement or measured strength loss is claimed;
asl01 was rejected from source review before release games.

## Hypothesis and exact production change

Production observation invalidation clears the cache and increments its unsigned
revision. Each controller action therefore makes its old Scene stale, but a new
capture in the same actor/life/round must be allowed to use the newer revision.
The parent's scalar conversion instead compared with the backend constructor's
revision, rejecting legitimate refreshed continuation.

Only `src/recovery_sdk.cpp` changes in production:

- Line 26 adds `check();const Epoch conversion=epoch();` before dimensions,
  coordinate export and conversion. This checks dispatch round/actor/life and
  reserve before taking the invocation's own complete entry epoch.
- Line 30 compares `current(conversion)` instead of `current(turn)` after the
  existing post-conversion reserve check. Actor, life, round and revision must
  all remain equal during this conversion.

The constructor's `turn` is never advanced. Checked `positions()`, dimension,
count and coordinate admission, owned scalar bytes, query quota and reserve
checks remain. Enclosing capture and defensive preflight retain their own scene
freshness checks. All other bytes of this production file and every other
production source/header, including `recovery_tiles.h`, are preserved against
the exact parent. Pathfinding, planner policy, thresholds, attempts, geometry,
static cache publication/reuse, guard outcomes, caller routing, defense,
economics and bookkeeping are unchanged.

Read the current leader-party overview, state machine, combat and pathfinding
documents, Pi bridge instructions, inherited implementation report, production
observations/controller/adapter and current SDK. In particular, inspected SDK
coordinate exports, cached self identity, live state flags, ability metadata,
move/cast/recall/cancellation wrappers and checked host error propagation.

## Test seam and actual executions

`tests/run_adapter.py` mechanically extracts the exact production observation
cache declaration, `invalidate_observations()` and `observation_version()` into
a temporary include. The fixture compiles these definitions, the real SDK
wrappers, production LiveBackend and production recovery controller. It asserts
two invalidations advance the revision by exactly two. No mock updates the
backend constructor epoch.

`tests/adapter_scene.cpp` adds explicit host mutations for successful ordinary
movement (position and movement allowance), dash (position and casting
allowance), recall (channel/started flags), cancellation (channel/cancelled
flags), and defensive attack. Test-only rollover hooks change round, Memory
life or the SDK's cached self view; replacing the cached view is the explicit
native actor-rollover simulation. Unexpected host error codes go through the
real SDK checker and become `cambc::error`. Unused host imports still fail fast.

`tests/adapter_epochs.h` actually executed these cases:

- LiveBackend ordinary step to (9,9), old-Scene rejection, fresh capture,
  supported dash to (7,7), fresh capture. Position, consumed allowances and
  increased revision are asserted; constructor epoch remains unchanged.
- Returned controller dash -> refreshed ordinary move -> health recall:
  one dash, one move, one recall, four captures, final `channeling`. The host
  action log asserts revision advancement and intervening coordinate exports
  before continuations; the predicted second motion is not issued directly.
- Controller ordinary movement out of the initial threatened observation;
  the move host explicitly hides the foe. Fresh safe low-health capture then
  permits recall. One move, one recall, three captures, final `channeling`.
- Active recall -> cancellation -> refreshed faster-home first step: one
  cancellation, one move, three captures, no recall restart. With movement
  permission absent, cancellation instead ends in `cancelled_wait`, no step.
- Controller defensive basic attack -> refreshed footer -> health recall:
  one defense, one recall, three captures, final `channeling`. The explicit
  attack host transition removes the visible foe, lowers observed health from
  30 to 25 and removes casting/attack permissions. A fresh capture verifies
  changed HP, empty foes, permissions and active recall. No self-heal effect is
  invented. Existing actual heal-mask tests still target ally handle 2 only.
  The unchanged scripted controller assertion where changed observed health
  releases the recovery latch remains separate.
- Revision changes inside either dynamic positions()/scalar conversion reject,
  even following an already committed move. Controller stale/incomplete refresh
  after a move preserves that move exactly once, with no defense or recall.
- Round/life/actor rollover before conversion rejects without exporting or
  acting; rollover during conversion rejects old-Scene action; rollover inside
  the first motion or its subsequent refreshed conversion preserves exactly one
  move/history entry and stops before defense/footer. All three identities are
  exercised at each boundary.
- False-return ordinary move and dash invalidate once, return blocked without
  continuation and reject reuse of the old Scene. False-return ally heal
  invalidates once and leads to stale without footer recall. Unexpected errors
  from both move and dash propagate without observation invalidation, committed
  action or continuation, preserving the existing exception behavior.

All parent coordinate controls remain: 45x30 and odd 5x3 empty/full/sparse masks,
row/final-cell indices, malformed coordinates/counts/dimensions, cap and
overflow-shaped dimensions, owned earlier scenes, distinct masks, both defensive
range masks, post-conversion reserve failure, static/dynamic conversion failures,
field admission, completed static compute/export rollover and next-round reuse.
The inherited 292 controller assertions, protocol/state tests and strategy
contract sources remain byte-identical. `source_contracts.py` verifies their
preservation and the exact parent production bytes with only the two scalar
edits permitted. README points to the candidate's focused command.

## Checks performed on Pi

aarch64, GCC 13.3.0. Generated binaries/includes live in temporary directories.

```sh
python3 bots/pi_actor-scene-epoch-01/tests/run_focused.py
python3 bots/pi_actor-scene-epoch-01/tests/source_contracts.py
python3 bots/pi_actor-scene-epoch-01/tests/run_adapter.py
python3 bots/pi_actor-scene-epoch-01/tests/run_adapter.py --parent-control
ADAPTER_CXXFLAGS='-O1 -g -fsanitize=address,undefined -fno-omit-frame-pointer' \
ASAN_OPTIONS=detect_leaks=0 \
python3 bots/pi_actor-scene-epoch-01/tests/run_adapter.py
```

Results: focused suite passed unchanged 292 recovery assertions, inherited
protocol/state scenarios, every production .cpp's current-SDK syntax,
integration/source-preservation checks and the actual adapter fixture. Source
checks and normal adapter also passed independently. ASan/UBSan passed with no
finding; leak detection was disabled. Syntax retains the inherited GCC
`-fpermissive` workaround for SDK declarations; shared SDK files were not edited.

The optional negative control compiles the exact parent's recovery_sdk.cpp from
Git with the corrected revision seam and new epoch cases. It reproduced stale
on the first fresh capture after exactly one successfully committed step, with
the constructor revision unchanged. The runner expects that failure and reports:
`EXPECTED: exact parent rejects fresh capture after one committed step`.
This is a source/fixture regression demonstration, not a game result.

## Gaps and PC follow-through

Native mocks do not establish engine fuel, scheduling, suspension, WASM resource
use, actual engine legality or competitive improvement. Board storage, full
field values, visibility changes, action effects and rollover are mocked.
The static-home detour limitation and bookkeeping remain separate work.

PC must review exact source and independently rerun this actual-adapter regression
before release. Retain the same eight construction games: Swirl/Lanes/Elkring/
Guardians, both sides against exact C02 WASM
`605207958ed3f3dc778f03b0b122dfa9c7469f09e19dd7b48c979a47532e73d7`,
current CLI 5 / engine 3 build
`96ce858f548c14560eff737967a691a30eaf0a469afd1f4f400f125e094bd1fd`.
Retain original construction gates: zero VM faults, SDK error classification,
real recovery activation and same-turn movement followed by health recall.
Missing required coverage is incomplete. Compare the original and defective
atc01 controls; report asl01 as unplayed. These are reused development
conditions, not fresh confirmation. No standalone win threshold, automatic
80-game expansion, upload or ranked change.
