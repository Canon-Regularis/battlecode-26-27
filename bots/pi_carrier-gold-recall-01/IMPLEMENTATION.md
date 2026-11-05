# cgr01: carried-bag gold recovery

## Hypothesis and scope

Base: `2f0f534e8311ee597e516b11c2afca1bbf608060`, original `leader_party_tuned`.
The bridge-provided candidate source was identical to that original before editing.
Allowing actors with carried gems to enter the existing threat-gated gold recovery
route may convert idle gold into equipment and useful work while retaining the bag
for later delivery. It can also delay or lose valuable deliveries, cause repeated
recall cancellations or extra trips, and increase fuel use. This is not a proposed
solution for Guardian's low-income farming/banking trap.

Read the current leader-party strategy overview, ordered state-machine document,
configuration, SDK 4.0.0 reference, relevant game rules/API recall descriptions, and
the actual C++ SDK wrappers/imports. The supplied census and replay observations
are motivation, not new measurements from this implementation job. In particular,
round 516 is a controlled fact-input regression case, not proof an earlier recall
would survive; probes 626/730 have enemies and the entire 223-round interval must
not be labeled eligible.

## Actual production change

Only `src/bot.cpp`, in `Bot::facts`, differs from the frozen original production
source. Removed exactly `s.bag==0&&` from the gold recovery branch:

```cpp
f.recovery=memory.recovering||(!s.spawn&&s.foes.empty()&&me.gold_count()>=Config::recall_gold);
```

Remaining terms retain their short-circuit order. The threshold remains 300.
Health hysteresis, state priorities, channel handling/cancellation, banking demand
and accounting, bag age, life and altar history, shopping, task handling, and all
navigation/pathfinding source are unchanged. No release instrumentation was added.

Recovery still precedes bank demand. Tests explicitly establish that both a
winning bag (2 gems with ally score 998) and a late bag (round 1999) choose recall
when gold recovery qualifies, even though `bank_needed` is true. Below 300 gold,
the late bag chooses banking. There is no bank-urgency veto, so this experiment
must not be described as safe for urgent deliveries.

## Focused Pi checks

Run from the repository root:

```sh
python3 bots/pi_carrier-gold-recall-01/tests/run_native.py
```

The runner writes binaries/generated headers to a temporary directory, removed
on exit. Results on this Pi with GCC 13.3:

- Exact source audit against the base commit: all production files identical
  except the single specified predicate deletion in `bot.cpp`.
- Existing `decisions.cpp` with the real `state_machine.cpp`: PASS.
- Existing `strategy_contracts.cpp`: PASS, 55,294,203 assertions, 5,041 map
  dimensions, 21,298,225 tiles, 1,176,588 requests. Its geometry header is generated
  from the actual candidate `World::chunk`/`center` bodies; protocol and state
  code are unchanged and used directly.
- New `recovery.cpp`: PASS, 197 checks against actual private `Bot::facts` and
  actual `decide`. Uses real checked-in SDK types/wrappers with controlled C host
  responses, GCC test-only `-fno-access-control`, and linker section collection
  to omit unused gameplay paths. No production access adapter or API changes.
- Negative control: compile the same recovery test against original `bot.cpp`
  from the frozen base; it fails positive-bag admission as expected.
- Every production C++ translation unit passes native syntax checks against the
  real SDK, without the test access flag; the native syntax command supplies
  `-include cmath` for the unchanged original's transitive math-header dependency.

Admission matrix covers bags 0/14/35, gold 299/300/372, spawn/nonspawn and
visible/no visible foes. Gold query counts verify remaining short-circuit gates,
including no gold query during health recovery. Checks include the supplied
round-516 position/HP/gold/bag input; low-health recovery with enemies, health
hysteresis; tribute/teleport priority over danger/recovery; spawn defense; danger;
quiet active recall and enemy/camp interruption; camp-hit escape; spawn healing;
pending-altar, size, age, late and winning bank demand; dead early return.
Fact calls assert unchanged carried bag and memory bag_since, prior_bag, life,
altar, bank_bag, bank_score, task, task_started, progressed, owned, queue_started,
pending_altar and carrier.

Caught check issue: an initial plain GCC real-SDK syntax command failed on three
existing `team()` declarations (`-Wchanges-meaning`) in `sdk/cpp/cambc.h`. The final
runner disables only that diagnostic with `-Wno-changes-meaning`; no SDK edit or
broad permissive compilation is required. The first negative-control run correctly
rejected the original at the added gold query count for a 299-gold positive bag, earlier than the runner expected. Ordered
the matrix to check 300 gold first so its asserted failure identifies recovery
admission directly. The negative control's failure is intentional and asserted
by the runner. The first all-unit syntax sweep also caught the unchanged
`objectives.cpp` use of `std::ceil` without its own `<cmath>` include under GCC.
The native syntax command now supplies `-include cmath`; production files remain
exactly within scope. PC toolchain validation remains required. All final
focused checks pass.

## Gaps and frozen PC handoff

No matches, tournaments, upload, ranked change, or broad evaluation were run.
Native mocks do not establish engine survival, spending, delivery, fuel budgets,
or win rates. Recall cancellation's existing decision is tested; its actual
engine action, retained bag on arrival, shopping and subsequent work require the
PC replay inspection below. The inherited Windows-specific planner differential
script was left intact and not run; planner/navigation source is byte-identical.
PC CLI/engine builds are pending, and no evaluation gate is claimed passed.
Changes remain uncommitted for the bridge.

Before evaluation, review the returned exact source. Use ordinary fuel,
CLI5/currentengine3 build
`96ce858f548c14560eff737967a691a30eaf0a469afd1f4f400f125e094bd1fd`.
Preserve all caught errors and outcomes. Frozen standard screen is 80 games:

- Zero candidate VM faults, direct >=9/16 and common >=35/64 required for broader
  expansion (original common 33/64). Direct <8 or common <31 rejects; otherwise
  unmet gates mean inconclusive/no expansion.
- Common team banking >=44,512; gem losses <=2,352; deaths <=548. Report differing
  round exposure and retain these fixed-panel totals; do not replace with rates.

The eight preselected conditions are already in that screen. Match by
map/opponent/side; do not run duplicate deterministic games or assume receipt
indices match the baseline.

| Map / opponent | Original A / B banks | Required candidate A / B banks |
| --- | --- | --- |
| Breadcrumbs / without_search | 560 / 1015 | 504 / 914 |
| Swirl / record_guard | 1015 / 1005 | 914 / 905 |
| Guardian / record_guard | 0 / 0 | Inactive gold-threshold control; inspect differences |
| Swirl / phase4 | 1034 / 798 | 931 / 719 |

All six positive-bank delivery floors must pass, with >=5 wins among those six.
Preserve original Guardian/A's win with zero faults. Scoreless Guardian tiebreaks
are controls, not evidence of banking. Extra purchases cannot substitute for
delivery floors.

For original Breadcrumbs/without_search/A Vesper entity 2, inspect first divergence
and actual gold-only positive-bag recall exposure; earlier trajectory changes may
prevent the round-516 state from recurring. Require same-life survival of that
carried bag through completed recall, actual spending, and actual subsequent camp
damage/collection or completed bank within 30 rounds of shopping. If this actor
never meets the trigger, record censored/inconclusive rather than assign another
episode. Inspect post-return delivery/loss and teammate outcomes. Interruptions
must retain original cancellation behavior; repeated trips without spending or
useful work fail the mechanism. Record all first-100-round and selected-episode
fuel effects and any urgent bank delayed/lost by the new recall. Native query
counts are not engine fuel measurements.

These eight conditions, the census-informed case and original 16 confirmation
maps are consumed development data. No broader expansion until every required
gate passes; freeze separate broader gates and new validation conditions only
then. Never relabel consumed conditions as fresh.
