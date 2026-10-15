# CAMBC 2026 Strategic Review — 2026-10-14

## Trigger

The user emphasized that a strategy can become too elaborate for its fuel budget and that a small number of useful conditions may beat a large decision tree. E43 then produced a major regression while testing the occupied-camp split rule with the reported top roster. E44 also failed to demonstrate the expected fuel benefit from a core selector cleanup. This is a Loop B review under `docs/strategy/prompt.md`.

## Evidence base

- G2 remains the protected local champion. Its active loop preserves independent camp farming, immediate positive-bag banking, established combat ordering and proven multi-goal movement.
- E05A changes the draft toward Cassi & Issac / Stellar / Tavi without changing the champion gameplay. Its corrected full matrices reached 8/18 vs the carrier hunter and 8/18 vs altar denial, one more win than the matched G2 baselines in each pressure suite, while its all-suite secured-gem differential was +2,700.
- E41's one-condition occupied-camp yield improved the full altar suite to 9/18 and +417 net, compared with G2's 7/18 and -1,628. It was poor in its four-map hunter pilot (1/8, -2,170 net).
- E42 added a visible-enemy gate to E41. The full hunter suite fell to 5/18 and -4,443; the altar suite was 7/18 and -455. It did not preserve E41's altar win count or improve against the hunter.
- E43 paired E41's yield with E05A's roster. Its 32-match pilot scored 10/32 and -5,078 net, including 3/8 and -362 against E05A itself. It lost net gems against all four opponents and recorded 626 deaths, with zero faults.
- E39's loaded lethal-carrier interception produced 42/72 overall but its hunter suite submitted 718 fewer gems and conceded 808 more than the matched G2 baseline. It has a useful denial idea but no general pressure solution.
- E32 showed that replacing multi-goal movement with nearest-goal SDK pathfinding cut score throughput sharply. E34/E44 show that a selector cleanup without direct fuel evidence is not enough to justify a strategy or policy change.
- E45's one-map Packs gate improved its two hunter games, but its full hunter suite still trailed G2 by one win and 1,659 net gems; it also failed to retain E41's altar differential.

## Strategic alternatives

### 1. Independent economic throughput with fast banking

**Approach:** Keep the G2 farm, capture, combat and immediate-bank loop. Consider a proven draft independently, as in E05A, without adding team roles or route planning.

**Strengths:** This is the strongest validated foundation for turning camp access into submitted gems. It keeps decisions local, avoids brittle role assignments and is supported by broad map/opponent matrices.

**Weaknesses:** It can lose initiative on maps where a pressure opponent captures or banks first; its score and survivability against the hunter remain imperfect.

**Cost and likely consequence:** Lowest strategy and fuel cost. Improvements must preserve access to all available camps and must be judged by own submissions and enemy denial, not wins alone.

**Decision:** Keep as the default. G2 remains canonical; E05A remains an unpromoted roster challenger.

E37 adds a useful example of bounded complexity: one map gate selects the Jungle Strength purchase only on Elkring. Its direct two-side mirror against E05A went 2–0 with +414 aggregate submitted-gem differential. The evidence is too small to change the general policy, especially with E37's weaker full hunter suite, but it is a plausible specialist rule because the condition is simple and localized.

### 2. Conditional split-farm and regroup

**Approach:** Yield only a camp group visibly occupied by an ally, optionally changing behavior when danger appears.

**Strengths:** E41 suggests a real altar-denial matchup signal. The idea is easy to explain and its fallback avoids a permanent camp partition.

**Weaknesses:** E40's hard split caused a severe throughput loss. E41 was poor against the hunter; E42's added contact gate did not recover performance; E43 lost across every opponent suite. E46's refinement to yield only to empty-handed allies reproduced E41's matched G2/E05A/hunter totals and lowered its altar net by 92 gems. The loaded-ally distinction did not measurably change behavior.

**Cost and likely consequence:** Even a single condition can change camp choice, travel and encounter timing across all three units. Layered gates expand the number of states and make failures harder to diagnose.

**Decision:** Preserve E41 only as an unpromoted altar specialist. E45 did not justify a Packs gate as a broad upgrade, and E46 did not validate loaded-ally-aware yielding. Before another split/regroup change, inspect replay timelines for a concrete repeated waste (duplicate camp work, delayed capture, exposed loaded carrier or missed bank) and target that behavior with one condition.

### 3. Direct enemy-gem denial

**Approach:** Attack a gem carrier when an in-range attack can kill it, then return to banking or farming.

**Strengths:** The condition is local, bounded and directly trades a low-cost action for removal of enemy secured-gem potential. It is simpler than pursuit or escort plans.

**Weaknesses:** E39's full results did not improve hunter secured gems over baseline. A target can be lethal yet still not be worth delaying an own bank or camp action if the opponent's team immediately replaces the score.

**Cost and likely consequence:** Low-to-moderate query cost when checking visible enemies; risk is mainly lost farm/bank tempo rather than code size.

**Decision:** Retain only as a narrow idea already present in the validated policy where applicable; do not add pursuit or broader attack exceptions without evidence from a specific replay.

## Foundation and next direction

The evidence favors starting from the simple economic loop and changing one observable decision at a time. Keep multi-goal navigation, camp access, immediate banking and established attack ordering. E37's map-gated purchase is worth retaining as a specialist hypothesis; do not generalize it without all-map evidence. Avoid fixed assignments, contact-triggered regroup states, and extra conditions intended to compensate for another weak condition. E46 shows that a plausible condition can be inert; inspect match traces before expanding the policy.

When the next candidate changes core algorithms, hold strategic decisions constant and demand two pieces of evidence before adoption: preserved secured-gem throughput across maps/opponents, and a repeatable fuel reduction measured on more than one map and side. Current profile samples include instrumentation overhead and the runner does not export fuel directly, so small differences are inconclusive. No promotion is justified by E43 or E44. No official submission or account action has occurred.

E47 provides a larger efficiency screen: caching the static obstacle mask lowered the sampled mean peak-turn fuel by 16.8% across nine maps and both sides, with no faults. Its separate unseeded hunter matches nevertheless fell from 7/18 to 6/18 and from -1,724 to -3,152 net gems. Treat the fuel result as a useful implementation lead, not a reason to promote a candidate with no demonstrated score preservation. Keep the strategic loop small and continue to require both throughput and fuel evidence.

E48 and E49 tested the E41 replay's low-health Varg signal. A global 45% retreat cut deaths modestly but reduced submissions across G2, hunter and altar pilots. A Varg-only 40% threshold showed an initial four-map gain, then fell to 4/18 and -5,627 net against the hunter over all nine maps; its altar net (-463) was 880 below E41. The precise-health trigger was observable and cheap, but still did not balance survival with secured gems. Do not raise recall thresholds again without a new replay showing the threshold itself causes a repeatable loss. Keep the compact core and investigate the full-matrix hunter failures by map and death cause.

E50 tested the same Varg-only threshold at 45%. Its unseeded 36-match matrix scored 1/18 and -6,367 net vs hunter, then 3/18 and -4,865 vs altar denial (zero faults). This is a clear rejection signal, though not a paired causal estimate. Stop threshold tuning. The next useful step is replay diagnosis of repeated losses or core-only fuel profiling; keep the economic loop compact until one simple rule demonstrates better secured gems and denial.

E51 validates the user's simplicity hypothesis. Removing one empty-handed health-recall branch from the economic core produced 16/18 wins and +4,198 gems in the direct G2 mirror, then positive gem differentials against both pressure proxies (+1,578 hunter, +1,557 altar denial) with zero faults. This also explains why E48/E49/E50's higher recall thresholds were a poor direction: low-health time away from camps appears more valuable than proactively recalling when empty, while loaded champions still bank. Promote E51 locally as G3. Keep the small farm/capture/bank/fight loop and next isolate a draft-only test of the reported leader rosters; do not layer tactical conditions onto the successful change.

E52 tested the leader-reported Cassi/Issac/Stellar/Tavi roster on top of G3's simple gameplay. Across the 54-match matrix, it lost seven G2-mirror wins, two hunter wins and four altar-denial wins relative to G3; deaths rose substantially in every suite. Competitive intelligence is a hypothesis, not a universal draft rule. Keep G3's roster and economic loop; inspect the losses before considering any narrower roster/map test.
