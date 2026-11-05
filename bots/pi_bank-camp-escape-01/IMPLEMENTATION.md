# bce01: escape camp coverage after a failed bank approach

## Hypothesis and scope

Base: `2f0f534e8311ee597e516b11c2afca1bbf608060`; candidate cloned from
`leader_party_tuned`. An actual failed safe altar approach while already taking
live camp damage can isolate the carrier inside the safe navigation mask. Calling
the existing retreat at that point may restore movement and delivery before the
ordinary low-health survival branch activates. A physically legal adjacent move
does not establish safety; this experiment relies on the existing retreat policy.

The supplied Swirl/C02/A Ren episode (failed banking 113–150, low-health escape
151, deposit 164) motivates the change. It has not been reproduced on this Pi.
This does not address no-selected-altar banking demand, altar hysteresis, or the
distinct Braided River no-candidate case. No map-specific behavior was added.

Read the current banking and navigation strategy documents, tuned configuration
README, SDK API notes, and relevant C++ SDK/host-import declarations, alongside
banking, observation, navigation/retreat, and dispatcher source. The navigation
strategy document's historical admission/reserve figures differ from the tuned
source; this change uses the existing `Config::reserve` (5000) without changing
field admission (30000) or field quota (3).

## Actual changes

Only two production lines were added in `src/economy.cpp`, inside `bank()`'s
`no_route_now` / `invalid_goals` branch, after the unchanged three-failure altar
cooldown/clear operation:

- Check the current TurnBudget, then `camp_hit` and positive `incoming` from the
  stable snapshot already refreshed by the existing post-movement `observe()`.
- Recheck the budget and require fuel strictly above `Config::reserve`, then call
  `retreat(budget, memory)` once. Ignore its result and return false as before.

No added observation calls, threat scans, fields, persistent memory, recall,
release diagnostics, or new movement code. Existing retreat supplies any extra
work. Navigation, masks, retreat ranking/guards, demand thresholds, selector,
queue/courtesy, active channels, remembered tasks, accounting, shopping, roster,
planner, coordination, combat, telemetry, and dispatcher priorities are unchanged.
No roster-pair, cd01, dominant-objective, threat-skip, profiler, or reliable-r08
changes were inherited. No production guard adaptation was needed.

Added `tests/bank_escape.cpp` and `tests/run_native.py`. The harness links the
actual production `economy.cpp` against the checked-in real C++ SDK header,
controlled host imports, and link substitutes for `move_to`, `retreat`,
`choose_altar`, `observe`, and `fight`. It does not copy the bank predicate/body.
Unused shop code is discarded through section garbage collection. The runner
keeps all generated artifacts in a temporary directory and preserves the existing
tests. The existing exhaustive geometry test receives its expected generated
header containing the production chunk/center function bodies.

## Pi checks

Run from the checkout root:

```sh
python3 bots/pi_bank-camp-escape-01/tests/run_native.py
```

Results:

- Production bank contract harness: PASS. Both failure statuses invoke retreat
  exactly once for a refreshed camp hazard; moving and immobile retreat results
  both leave bank false with no submit call or bank accounting change. First
  failure retains the altar; third failure cooldown/clear occurs before retreat.
- Refreshed hazard replaces the pre-approach value. Missing camp coverage,
  zero/negative incoming, fuel at/below reserve, round crossing in movement,
  observation refresh, or the second current-round guard exclude the fallback.
  Nonhazard and crossed-round third failures retain the old cooldown behavior.
- Deferred, wait, at_goal, and moved statuses do not invoke retreat. Empty bag
  clears altar/queue; no selected candidate returns false. Ordinary movement into
  altar range starts submission with normal accounting; existing submission
  channels return normally. No false submission from a retreat result.
- Existing protocol/state scenarios: PASS.
- Existing exhaustive strategy contracts: PASS, 55,294,203 checks, 5,041 map
  dimensions, 21,298,225 tiles, 116,964 centers, 1,176,588 requests.
- Real-SDK production syntax check over every `src/*.cpp`: PASS with native GCC
  accommodations below.
- Compared candidate with `leader_party_tuned`: only `economy.cpp` differs among
  production files. HEAD matches the requested base. No files outside the
  candidate were edited; changes remain uncommitted.

Native GCC 13 rejects existing SDK `team()` declarations without `-fpermissive`;
existing objective/route code also needs `-include cmath` with this standard
library. The runner supplies these flags, preserving the SDK and production
sources. Initial unadapted syntax checks exposed these existing portability
issues. Existing SDK/formatting warnings remain visible in the runner output.

## Limits and pending frozen PC evaluation

These are caller contracts with controlled SDK/link substitutes. Retreat movement
and immobility are modeled return/position outcomes, not execution of real
retreat navigation or host legality, camp coverage, fields, fuel suspension,
engine channel timing, scoring completion, or gameplay. Native checks establish
neither release strength nor actual fallback exposure. CLI/uv, Clang/WASI and the
PC replay artifacts are unavailable here; no release WASM build or matches ran.
The historical Windows planner differential runner was preserved, not run.

The caller checks round/fuel before entry. Existing retreat local rank queries
can consume fuel and suspend within that function; its guards are unchanged.
This does not make retreat atomic across suspension. Measure release fuel,
round transitions, oscillation, and ordinary banking regressions on the PC.

PC handoff remains the supplied frozen protocol: review exact source and release
build with CLI5/current engine3, normal fuel (evidence engine build
`96ce858f548c14560eff737967a691a30eaf0a469afd1f4f400f125e094bd1fd`). Run all
80 screen games: 8 maps, 5 frozen controls, both sides, zero candidate VM faults.
Reject direct <8/16 or common <31/64. Expand only with direct >=9/16 and common
>=35/64 (baseline 33/64), plus a verified useful mechanism; otherwise inconclusive.
Never upload on screening alone.

Inspect Swirl/C02/A Ren against the same artifact/map/seed/opponent controls,
starting with release first divergence, actual local camp coverage, legal actions,
movement, bag retention and deposit. If comparable, the prediction is first
egress before low-health round 151 and deposit before 164 without losing the bag.
If earlier trajectories diverge, identify the first relevant failed-route/escape
episode instead. Without verified fallback exposure make no mechanism claim;
use bounded diagnostics before expansion. Inspect both sides of Swirl and retain
all games, including failed escapes. Report the entire matched 64 common games,
banking/collection/loss/deaths/captures, first-100 and whole-game fuel suspensions,
and caught errors. If qualified, run the same two preexisting Braided/C02 ordinary
bank controls before broader expansion.

All 16 original confirmation maps were consumed by cd01. Broad/fresh confirmation
requires separately frozen new map/opponent conditions and recorded historical
exposure. No ranked selection change, upload, commit, or push was performed.
