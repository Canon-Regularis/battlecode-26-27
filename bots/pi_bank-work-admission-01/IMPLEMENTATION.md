# bwa01: bounded ordinary work after completed unavailable banking

Implemented on the Pi on 5 November 2026, from base
`2f0f534e8311ee597e516b11c2afca1bbf608060`, using the supplied
`leader_party_tuned` clone. Changes are uncommitted. No matches, uploads, baseline
reruns, tournament expansion, or ranked-v7 changes were performed.

## Hypothesis and scope

A completed search under the existing blocked|risk mask can establish that no
altar approach is spatially reachable. Revoking stale altar intent and permitting
the ordinary dispatcher for the next ten round numbers may recover camp income
while preserving the bag's original banking desire. This is an experiment, not a
claim of safe camp completion or improved scoring. A legal camp attack is not
proof that its capture or later banking is safe.

The selector now distinguishes selected, unavailable, cooldown, and deferred.
Spatial reachability precedes retry filtering; only eligible previous targets
participate in the original margin-three hysteresis. Distance, visibility, lock,
enemy penalties, and tie order are unchanged. The original single selector field,
blocked|risk mask, and clearing of its origin are retained. Completion checks the
current round and 5,000 reserve after field construction and after host-backed
scoring; it does not reuse the 30,000 field-admission threshold. Admitted searches
with no altars complete unavailable.

Both callers use the same application helper. Selected commits and clears work
admission. Completed failures revoke altar and queue; unavailable alone records
an eligible failure. Deferred leaves caller state intact, including the old bank
approach subject to existing execution guards. Application checks round/reserve
again after its urgency score query. Task expiry retains default previous=-1
ranking on a completed search. Its deferred case deliberately preserves a prior
positive commitment, unlike the original -2 assignment: a young non-due bag can
therefore remain preempted by banking.

`Memory::bank_unavailable_round` is the only new persistent stamp. Failure at F
never grants admission in F. Admission suppresses the entire altar-or-bank_due
preemption expression in F+1 through F+10; F+11 expires it without refreshing it.
Only a fresh completed eligible unavailable search can record a new failure.
The existing winning/endgame expression is factored into `hard_bank_due` and
shared by `bank_due` and admission. Bag size 35 alone can be deferred; positive
winning and endgame bags override immediately. Bag age, actual/prior bag, life,
channel accounting, and ordinary bank_due semantics are preserved.

Zero bag, observed death, selected altar, hard urgency, observed task completion,
and ordinary abandonment/stall/expiration clear admission. No task yet selected
does not clear it. Maintenance captures admission on entry and skips the legacy
preselector when admitted, even if maintenance then ends that admission. Later
normal dispatch owns reconsideration. Safety/channel interruptions and deferred
work consume absolute time. No task clocks or field counters are reset for this
experiment. The unchanged camp selector, initialization, camp_action, and
exploration remain responsible for work; no-camp exploration is not farming.

Navigation, combat, shop, draft, coordination, masks, configuration, and release
telemetry sources are unchanged. Gold recovery still requires bag==0. Host query
schedules are not identical on inactive paths: facts now obtains the score even
when an existing altar could previously short-circuit it; maintenance queries
urgency when a failure stamp exists, and unavailable application queries it too.

## Exact changed/added files relative to the supplied clone

- `src/model.h`: failure stamp, shared hard urgency, absolute work admission.
- `src/objectives.h`: typed selection result and shared application declaration.
- `src/objectives.cpp`: selector contract, eligibility hysteresis, completion
  guards, result application. Camp selector and exploration bodies unchanged.
- `src/economy.cpp`: apply typed results in bank, clear admission on empty bag.
  Route failure, queue, locks, submission and channel logic unchanged.
- `src/bot.cpp`: admission lifecycle, whole banking-preemption suppression,
  maintenance entry capture and typed expiry preselection.
- `tests/mock/cambc.h`: deterministic native scenario host.
- `tests/bank_admission.cpp`: production-boundary and public-dispatch scenarios.
- `tests/run_native.py`: runnable native fixture and existing decisions runner.
- `IMPLEMENTATION.md`: this report.

All other clone files are unchanged. All writes are confined to this candidate
and temporary compiler outputs in `/tmp`; repository SDK/tools/settings and other
bots are unchanged.

## Checks and results

From the repository root:

```sh
python3 bots/pi_bank-work-admission-01/tests/run_native.py
```

PASS: **170 production selection/application/dispatch assertions** and the
existing `decisions.cpp` protocol/state scenarios. Python 3.12 and native aarch64
GCC 13.3.0 were used. Test output includes existing LP telemetry; release logging
was not modified.

Coverage includes unreachable/cooling previous targets, mixed spatial/retry
eligibility, no altars, ties, margin three, visibility/lock/enemy penalties;
admission denial/field cap; round rollover and reserve exhaustion after fields
and during scoring; completed selection at post-field fuel 25,000 and completed
failure at reserve 5,000. Deferred application preserves old altar/queue/stamp.
Both callers revoke completed failure intent. Both reject failure stamping when
the application urgency query rolls over or exhausts reserve. Selected route
failure, legitimate queues, lock attacks, and tribute accounting remain distinct
from unavailable failure.

Public Bot dispatch exercises an aged still-due eight-gem bag, F with no work,
F+1..F+10 with production camp_action reaching simulated attacks, F+11 restored
preemption, deferred attempts without timer extension, and unchanged bag/age/life.
It also covers task-expiry failure followed by selection of a different eligible
camp (the abandoned camp retains its cooldown), an admitted-entry task expiry
whose later normal bank dispatch owns the fresh retry, and no eligible camp
falling through to exploration. Young non-due expiry failures/cooldown keep
ordinary same-round dispatch while its camp selector correctly defers on the
already consumed field. Separate cases cover the intentional young-bag deferred
commitment change, no previous-target preference on completed expiry selection,
zero bag/death/completion/stall/abandonment, hard urgency, bag35, whole-expression
suppression, danger before search, recall/healing/spawn-defense, and a dormant
failure window during an existing channel without cancellation or work.

SDK-facing syntax check:

```sh
g++ -std=c++20 -fpermissive -include cmath -fsyntax-only -I sdk/cpp \
  bots/pi_bank-work-admission-01/src/*.cpp
```

PASS for all candidate translation units against the actual checkout SDK. Plain
native GCC first rejected existing SDK `team team()` declarations and existing
missing transitive `<cmath>` declarations in objectives/route_plan. The command
above permits the former and injects the latter for this host check; it produces
only those SDK naming warnings. Neither SDK nor unrelated source was changed to
accommodate native GCC. This is not a WASM compilation. The Pi has no callable
`uv`, `clang++`, or CAMBC/WASI build toolchain on PATH, so the exact release build
must be performed on the PC.

## Simulation substitutions and remaining uncertainty

The fixture reads production sources at runtime. It compiles the unchanged
selector, shared application helper, camp selector/goals/exploration, bank body,
all Bot methods (including public play_turn and camp_action), model and state
machine. Only World initialization/refresh and shop bodies are omitted; a
private-state access modifier is inserted in a temporary copy of bot.h. No
selector, application or dispatch decisions are copied into the fixture.

The mock header substitutes a 20x20 eight-neighbor BFS and bitboard geometry for
the SDK host, scripted snapshot/lifecycle/score/fuel/round values, and simple
champion/channel/shared-memory queries. Navigation is a programmable route-status
stub, combat records simulated attacks and damage, planner preference falls back
to the original selector, and optional wards are inert. These substitutions test
production branch transitions and selector/application behavior, not the host ABI,
real path execution, champion spell adapters, engine visibility exceptions,
observation-refresh timing, fuel costs, WASM suspension, captures/rewards, or
simultaneous channels. No assertion establishes useful release farming, safe
completion, match exposure prevalence, or identical original trajectories.

There are no release measurements here for collection, deposits, gem losses,
survival/deaths, spending, actual in-game work, reopening/retry cadence, fuel,
or unequal game duration. No caught runtime SDK errors were measured: no engine
was run. Native compiler compatibility findings above are separate from runtime
SDK errors. Risk of waking camps, unsafe carried-gem movement, interrupted work,
deferred deposits and extra host-query fuel remains open. Danger-before-search
is explicitly tested to create no failure stamp; the Breadcrumbs case is not
claimed fixed. No implementation-policy deviation from the requested contract
was made; engine/release validation remains outstanding.

## Frozen PC evaluation handoff (not executed)

Review the returned exact source and fixture before games. Build/test that exact
source for WASM. Before broad testing, freeze receipt hashes in the PC protocol
and run the two specified ordinary-bank negative controls: Braided
`ec74a61178cf4ad301db9c2ca467e7a3978f8e9d97a2a4b9faecbf7afb0b5f0b`
versus frozen C02, both sides with the existing original-control seeds. Require
bank A>=800 and bank B>=882 and zero faults. Do not rerun the original baseline or
call these controls reproduction of the original online trap.

The ordinary 80-game screen's expansion gates remain zero VM faults,
direct>=9/16, common>=35/64, common banking>=44512, gem loss<=2352 and deaths<=548;
direct<8 or common<31 is clear rejection, and any missed gate forbids expansion.
Keep Guardian/C02 A+B, retain the original A win, audit A Marcella through400,
and establish the earliest qualifying actor exposure by round then entity ID
using exact release preturn masks/vision and action records, joined with fixture
branch proof. A reconstructed unavailable witness is inference, not an observed
private status. A later camp action must retain the still-due original bag and
occur within ten rounds; channel time or exploration is not useful exposure.
Inspect actual candidate divergence rather than assuming baseline trajectories.
Without release mechanism evidence, do not expand even if wins improve. Report
all requested economy/work/survival/fuel/duration metrics and investigate new
repeatable caught SDK errors separately. Guardian banking is not required;
zero-zero tiebreaks do not prove bank access. No broadening/upload without every
gate and a separately frozen next panel using genuinely new conditions.
