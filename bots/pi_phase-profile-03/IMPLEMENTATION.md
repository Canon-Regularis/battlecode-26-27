# ppfx03 — defer profiler output until after round 100

Parent/base commit: `1f6e14016c82c71e363baf9f9e897a656a326d43`.
Candidate: `bots/pi_phase-profile-03/`, cloned from `pi_phase-profile-02`.
Instrumentation only; research only; source default `PPFX_ENABLED=0`.

## Hypothesis

PC verified ppfx02 OFF WASM exactly equals the original champion. Full ON and
observe+turn mask `0x5` produced complete trailers without parse errors, but
perturbed the measured first100 rounds: full ON fuel counts 19/12 versus original
12/12 with an extra early death on A; mask 0x5 gave 16/23 and changed a longer
match outcome. Observe is a large measured component, but that evidence does not
establish the release cause.

ppfx02 could print up to eight records per safe point inside the measured window
when fuel was at least 40,000. Deferring this avoidable actor lookup, formatting
and output may reduce observer perturbation. No trajectory identity or low
overhead is claimed for ppfx03 before PC engine comparisons.

## Actual changes

The only production source change is in `src/phase_profile.h::safe_point`.
After the existing no-data/final-sent returns, it takes one existing
`SDKClock::sample()` and returns if invalid or its final round is <=100.
This reuses exception-safe round/fuel/round sampling: two round SDK calls and one
fuel SDK call per guarded safe point with accepted scopes. That small sampling
cost remains during collection; its engine fuel cost is unmeasured. No actor
query, formatting or output occurs on this guarded path.

On the first valid safe point after 100, admission closes before actor tagging.
It then follows the inherited bounded drain: at most eight records per dispatch,
with a fresh clock sample requiring >=40,000 fuel before each record. The cached
public champion handle is read once per post-window drain attempt, including
attempts rejected by the per-record fuel guard. All records retain the exact
`PPFX <unsigned actor_id> [numeric array]` wire format. The original main-loop
safe-point location, action order and `end_turn` order are unchanged.

Every scope, phase, mask, aggregate, inclusive histogram, nested parent,
cross/invalid/unwinding/cutoff classification and overflow counter is unchanged.
Storage remains a 512-event FIFO, 128 retained crossed exits, and eleven phase
aggregates with eighteen histogram bins. No storage expansion or pathfinding,
policy, optimization, SDK, tool or settings changes.

The production output-contract test now calls safe_point with accepted data at
rounds 0, 1, 99 and 100. It asserts zero actor reads, unchanged queued data and
drain indices, and exactly one clock sample per call. The Python runner requires
a window-end marker before any production output, so early output fails the test.
Post-window tests check 39,999 blocks output, exactly 40,000 admits one record,
a drop to 39,999 stops the next record, and sufficient fuel admits exactly eight
records per call. Every actor-tagged entry, exit, retained cross copy, all eleven
summaries and the final trailer are checked against exact arrays for two
simulated actors (17 and 4294967295) reusing scope ID 1. Early returns before
accepted data and after the trailer do not sample or tag. Test SDK counters and
a controllable fuel decrement support these checks; production SDK is unchanged.

`SOURCE_SHA256SUMS` is regenerated for all candidate `src/` files. Only the
phase_profile.h hash changes from the parent manifest. Tests and this report are
not covered by that source manifest.

## Focused Pi validation

Command: `python3 bots/pi_phase-profile-03/tests/run_profile.py`.
Result: PASS on Pi (all checks below).

The inherited suite covers profiler ON/OFF, mask behavior, same-round costs and
histograms, nested scopes, unwinding, unstable/invalid samples, round crossings,
cutoff/open counts, bounded FIFO and cross-retention overflows. It also compares
all OFF preprocessed translation-unit tokens with `leader_party_tuned`, checks
all translation units OFF and ON against the real SDK, runs the production output
contract above, and executes inherited decision scenarios. Native SDK syntax
checks retain inherited `-fpermissive` and forced `-include cmath` workarounds;
neither SDK nor gameplay source is edited for them.

Source isolation and manifest verification: PASS. The six changed files versus
ppfx02 are phase_profile.h, profile_output.cpp, the test SDK stub, run_profile.py,
SOURCE_SHA256SUMS and this report. All other inherited files are byte-identical.
Git status contains only candidate-local files; no changes were committed.

## Missing evidence and residual perturbation

Collection still samples scopes, maintains aggregates/histograms and queues
records during rounds 0..100 inclusive. That work, nested instrumentation, and
the new safe-point sample can consume fuel or suspend. Post-window formatting
and output can also suspend and change later chronology; the 40,000 guard is an
admission threshold, not a measured bound. There is no Pi engine/WASM execution,
output-fuel calibration or binary identity proof in these native checks.

Deferring the drain can increase FIFO drops. Aggregates continue to include
accepted scopes even when exact entries/exits drop, and retained cross copies
remain independently bounded. Kind 4 reports accepted scopes, dropped events,
dropped cross copies, clock errors and parent. Kind 2 may duplicate kind 1;
deduplicate using actor plus scope ID. Missing per-call records remain missing,
not reconstructed costs. A trace without the final trailer is incomplete;
without it, losses are unknown. Games or actors ending before post-window drain
may emit nothing, including no aggregates or retained-cross evidence. Missing
exits mean unfinished at available trace termination, not zero cost or proof of
exhaustion. No early output is permitted to compensate for missing evidence.

PC gates remain: build OFF and require the frozen champion WASM/hash gate; build
ON with mask `0x5`; run 00swirl on both sides versus C02 with controlled
engine/map/seed inputs. Compare first100 events/pauses, deaths, complete trailers,
FIFO loss and retained-cross loss by actor. Record residual divergence before
interpreting phase costs or drawing release-cause conclusions. No strength
screen, tournament, upload or commit was performed; the bridge commits/pushes.
