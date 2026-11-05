# bge01: destination-directed bank egress

## Hypothesis and scope

Starting point: `2f0f534e8311ee597e516b11c2afca1bbf608060`, original
`leader_party_tuned`. The supplied candidate initially matched that directory
exactly. This implementation does not incorporate bce01.

When an actual safe bank approach fails while the carrier currently takes camp
basic damage, one walking step toward the same bank may preserve delivery tempo
without increasing estimated incoming. Unlike survival retreat, this step has no
spawn destination. Equal incoming is permitted; a strictly smaller field distance
is required. This is a falsifiable delivery hypothesis, not a safe-path guarantee.
Visible basic champion/camp damage omits future spells, hidden threats and damage
mitigation. Marcella's ordinary camp-hit-false banking oscillation, Braided's
altar rejection, Guardian's occupied banks, and other objective policies remain
outside this experiment.

Read the current strategy README, state machine, tuning report, navigation and
altar-selection documents, the older meta-strategy context, and the checkout C++
SDK implementations of movement, live entity queries, bitboards and fields.
The tuned source constants (30,000 admission, 5,000 reserve, three fields) take
precedence over historical navigation-document numbers.

## Actual change

Only `src/economy.cpp` differs in production source. An anonymous-namespace
`bank_egress(bitboard, TurnBudget&, Memory&)` implements the private fallback:

- Uses current-round/fuel, alive, channel, movement availability and movement
  restriction checks. Requires a current observation. Keeps the existing field
  counter, admission threshold and maximum.
- Masks the supplied altar goals with physical occupancy plus the existing enemy
  risk mask, clearing self only. This private field omits camp attack regions.
  Empty goals and an origin already in the goals cause no action or field.
- Captures visible enemy positions/ranges/strengths, then living awake
  positive-strength camps, once locally. Current and candidate incoming use that
  same ordered captured set and ordinary C++ Chebyshev tests. No observation
  scans or global caches changed.
- Computes at most one extra reverse SDK field toward those goals. Enumerates
  the SDK walking mask at distance one, excluding self. Only finite, strictly
  lower goal distances with incoming no higher than the origin qualify. Orders
  candidates by distance, incoming, y, x.
- Rechecks movement and epoch/fuel before a single `move_checked` attempt. Only
  an actual move clears `blocked` and writes the selected `last_distance`.
  Rejection retains normal observation invalidation, without another attempt or
  another failure increment.

`bank` invokes this only after an actual `no_route_now` or `invalid_goals`, after
its original third-failure cooldown/reset. Its refreshed snapshot must have
`camp_hit` and positive incoming, and its budget/fuel must still be current and
above reserve. Goals come from the local altar coordinate captured before that
reset; there is no lookup through a cleared altar index. The branch always
returns false, including after movement. Moved/at-goal/wait/deferred approaches,
channels, empty bags and absent altars do not enter this branch's fallback.
Ordinary navigation and retreat, draft, configuration, state, shopping, queue,
channels, observation, telemetry and coordination source remain unchanged.

## Pi checks

Run from the repository root:

```sh
python3 bots/pi_bank-goal-egress-01/tests/run_native.py
```

Final result: all three stages pass:

1. Production bank-egress and integration scenarios.
2. Existing unmodified protocol/state scenarios (`decisions.cpp` with
   `state_machine.cpp`).
3. All candidate production translation units pass native syntax checking
   against the real checkout SDK.

The fixture includes the actual `economy.cpp`, `navigation.cpp`, and
`observations.cpp`, using real SDK wrappers. It calls the private helper in that
same translation unit and also calls actual `bank`/`move_to`/`move_checked`.
There are no copied decision predicates. Only engine imports, combat and altar
selection are substituted. Unimplemented imports abort rather than silently
succeed. The Python runner creates generated stubs and binaries under a temporary
`/tmp` directory and removes them afterward.

Covered scenarios include:

- Isolated exposed origin, north-side spawn and south bank; equal-incoming
  southbound egress; bank returns false, no submission, one additional field.
- Higher incoming rejects every improving neighbor, without a second blocked
  increment; physical occupancy and enemy-risk exclusions; unreachable origin,
  fully masked goals and already-at-goal; deterministic incoming/y/x ties.
- Both no-route and invalid-goals third-failure resets retain the original bank
  goals after altar becomes -1, including the original cooldown value.
- Actual safe approach success, no altar, empty bag, deferred, wait and channel
  paths do not take the fallback. Failed approaches independently require camp
  hit and positive incoming. After an egress leaves camp range, next turn uses
  the ordinary safe bank approach.
- Field quota, admission fuel, exact reserve, stale budget, and injected epoch
  changes during camp/champion collection, field computation, neighbor-mask
  acquisition and final movement checks refuse movement/movement-memory writes.
  Reserve exhaustion during collection, field computation and neighbor-mask
  acquisition is also covered. A started field remains counted on deferral.
- Hidden bad-destination error is caught by actual `move_checked`, attempts once,
  invalidates observations and does not claim success. Successful movement
  changes only the two movement-memory members (checked against prior Memory).
- Champion live range/strength and camp aggregation, asleep/dead/zero-strength
  filtering, captured current incoming rather than stale snapshot incoming, and
  one position/strength copy per active camp. A floating-point cancellation
  case exercises enemy-then-camp accumulation order, including the existing
  champion semantics without a new positive-strength filter.

The fixture uses a controlled 8x8 grid and a host substitute BFS with eight
walking directions. Its full BFS is a substitute for the SDK host's early-stop
field implementation; production calls the unchanged real SDK `compute_to`.
Dynamic physical blockers are supplied through teleport occupancy. A few
aggregation-only cases clear synthetic snapshot risk to isolate champion damage;
separate integration cases preserve actual observed enemy risk. Altar selection
is fixed to the supplied selection, and combat is inert. These limits prevent
this fixture from establishing official replay legality, actual engine exposure,
release fuel cost, release VM fault counts or match performance.

During harness bring-up, unsupported imports (map symmetry, teleport occupancy,
and error text) intentionally aborted until implemented. Initial stock GCC
syntax checking also found the SDK's existing `team team()` naming diagnostic
and inherited `std::ceil` uses without a direct `<cmath>` include in untouched
files. The runner suppresses only `-Wchanges-meaning` and injects `<cmath>` for
its all-source native syntax pass. Production and SDK source were not changed
for these existing toolchain differences. No WASM release build was attempted.

## Cost and suspension limits

The ordinary safe approach gets first refusal. The fixture's actual failed-safe
approach plus successful egress consumes two fields total, versus one for the
failed safe approach alone. Invalid-goals approach plus egress consumes one.
At a three-field quota the helper refuses without resetting it. Added work also
includes one local threat collection and at most eight neighbor evaluations
plus the origin, with no repeated host damage scans per neighbor. Per active
camp the local copy queries state twice, strength once, position once and design
range once; champion position/range/strength are each queried once. Reserve and
round queries and SDK board operations also consume fuel. This is bounded work,
not free work; numeric WASM fuel and rollover frequency remain PC measurements.

Epoch/reserve guards surround the new path's observation, collection, field,
neighbor evaluation and final movement boundary. They do not make a whole host
query sequence atomic across arbitrary fuel suspension. SDK list construction,
individual queries, existing observation refreshes and the final action can
still suspend or fail. Existing engine exceptions propagate normally except the
existing hidden-destination handling. No claim of universal suspension safety
or safe future escape is made. No permanent egress state is stored.

## Frozen PC evaluation pending

No release games, large tournaments, uploads or ranked changes were run here.
No performance or promotion conclusion follows from these fixtures.

Use normal fuel, CLI 5/current engine 3
`96ce858f548c14560eff737967a691a30eaf0a469afd1f4f400f125e094bd1fd`.
Review exact source and require zero candidate VM faults. Retain every outcome
and caught error. Standard 80-game screen: reject direct <8/16 or common <31/64;
expand only with direct >=9/16 AND common >=35/64 (baseline 33/64), plus useful
mechanism and the Elkring requirements. Other results are inconclusive. No upload
from this screen.

For preselected Swirl/C02/A, inspect first divergence and actual fallback
exposure. Require legal useful egress before the original round-151 low-health
escape, preserve seven gems, deposit before 164 and resume useful work. Earlier
trajectory changes require identifying their actual trigger rather than assuming
original timestamps. Record selected legality and added field/fuel cost.

After the screen, run the two predeclared Elkring/gold_diamond games, both sides,
using frozen opponent WASM
`6478b9afa543394325b82e03d763aa31d033002d27df3f42f3733bc0b83572d6`.
Matched original baselines are `cd01-broad-baseline/00010.zip` (A, 1012 delivered)
and `00011.zip` (B, 979). Require zero faults and A >=911 / B >=882 delivered.
Inspect full-health bank-directed egress, subsequent delivery, and any new
oscillation or spawn-defense trap. Merely beating bce01's 110/484 is insufficient.
These are consumed development-case diagnostics, not independent confirmation;
if the numeric screen fails they remain bounded diagnostics, not expansion or
promotion. All 16 original confirmation maps are consumed. Freeze any broader
gates/new confirmation separately before seeing outcomes. Retain negative findings.

Changes are intentionally uncommitted for the bridge.
