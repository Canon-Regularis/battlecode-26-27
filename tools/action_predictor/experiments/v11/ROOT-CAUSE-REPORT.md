# Why the Fish predictor is failing

The evidence does not support one definitive hidden cause. It does establish three separate problems: **the current selector cannot emit many required commands; it often chooses incorrectly when the right command is available; and the existing neural architecture can memorize a small movement sample but transfers poorly under the diagnostic protocol.** Missing information, persistent objectives and Fish policy changes remain unresolved explanations, not established facts.

New production training is paused. This investigation reused saved predictions, checkpoints, candidate caches and prior audits. One bounded fit answered the explicitly requested small-subset capacity question; no new architecture or large-model phase was started. Both reserved 75-game partitions remain sealed. No matches, simulations, downloads, bot changes or deployment occurred.

## 1. Missing commands and selection failures are both large

For A00 on every original DEV row:

| Fixed-library diagnosis | Commands | Share of its errors |
|---|---:|---:|
| Correct command unavailable from C00 simple library plus G00 hard forecast | 1,301 | 46.18% |
| Correct command available, but not selected | 1,516 | 53.82% |
| Total failures | 2,817 | 100% |

This is a disjoint partition **for this particular support/decoder combination**. Representation, optimization and policy variation could contribute to either side; they cannot be added as further disjoint causal buckets.

The oracle ceiling is 13,138/14,439 (90.99%) overall, versus A00's achieved 11,622/14,439 (80.49%). The category ceilings explain why overall oracle coverage was an inadequate allocation signal:

| DEV category | Support | A00 achieved | Oracle ceiling | Unavailable failures | Available but missed |
|---|---:|---:|---:|---:|---:|
| Move | 2,362 | 1,330 | 1,953 | 409 | 623 |
| Blocked attempt | 110 | 8 | 8 | 102 | 0 |
| Priority | 576 | 69 | 71 | 505 | 2 |
| Ward | 112 | 5 | 12 | 100 | 7 |
| Cast 1 | 243 | 92 | 125 | 118 | 33 |
| Attack | 985 | 881 | 972 | 13 | 91 |
| Cast 0 | 213 | 152 | 206 | 7 | 54 |
| Recall | 3,084 | 2,570 | 3,084 | 0 | 514 |

No amount of improved routing within this fixed support can reach the original category requirements. These are not ceilings on the underlying observations or on algorithmic methods generally. The neural conditional heads have broader support than this hard selector.

Specific omissions are demonstrated: C00 lacked ground-target cast handling; its ward placements were inappropriate; zero/copy priority proposals were ineffective; and movement-readiness gating suppressed recorded blocked attempts. C01/C02 partially repair support on TRAIN, but still fail their frozen gates. C02's oracle TRAIN coverage is 41.49% for blocked attempts, 24.71% for ward, 8.53% for priority and 43.00% for cast 1. These are neither learned accuracies nor DEV improvements.

Selection is independently weak. A00 rescues only 135 of 1,628 library-covered G00 errors (8.29%). Its 112 net gains are 135 rescues minus 23 regressions; recall contributes 98 of the net gain. Excluding recall, observed NLL worsens. A01 captures only 69 of those opportunities and loses against A00. It also changed shared scoring, context size and parameter count, so that negative result does not isolate candidate geometry.

Decoding matters separately from learning. The posthoc matched G00 probability decoder already gets 11,950 commands right, versus the original action-first G00's 11,510. D00 gets 12,039, adding 89 net successes over that control, while worsening the macro-F1 point estimate and predicting no complete wards correctly. A lower mixture NLL or better aggregate accuracy therefore does not establish broad policy recovery.

Orthogonally, A00's errors comprise 1,532 wrong action types, 1,243 wrong arguments after correct typing, and 42 correctly typed shops with unavailable arguments. Repairing only action selection or only movement parameters is insufficient. See [saved-output summary](R00-summary.json) and the [V10 correction](../v10/A01-review-corrections.json).

## 2. Movement: what the tests distinguish

G00 gets 1,053/1,198 continuing moves right jointly, but only 263/1,158 direction changes. Its true-family destination counts are 1,120 and 311, respectively; these conditional counts must not be compared with joint action-plus-destination counts.

R01 tests five declared current goals: nearest visible camp, lowest-health visible camp, nearest visible enemy, nearest altar and own spawn. It uses current personal movement masks and compares greedy distance with uniform terrain fields. All original 2,362 DEV moves are retained. The geometric relationship partition is:

| Relationship to these hypotheses | DEV moves |
|---|---:|
| Emitted by the frozen C00 simple library | 1,593 |
| Additional compatibility with a greedy-optimal alternative tie | 295 |
| Additional compatibility with a terrain-field optimum | 180 |
| Unexplained by these progress/optimality sets | 294 |

These are progressively broader oracle diagnostics, **not additional executable candidate coverage** and not definitive cause labels. In particular:

- **Goal selection:** among G00's 1,044 movement failures, 635 commands already exist in the frozen library. Wrong selection among proposed goals/behaviors is a demonstrated opportunity. It is not proof that the true goal is one of those five.
- **Tie-breaking:** 295 moves are compatible with a different optimum after unioning several possible goals. This does not mean 295 tie-breaking bugs. Fixed global `yx` versus `xy` changes barely affect the tested forecasts; there is no evidence that swapping one global ordering solves the gap.
- **Pathfinding:** 180 additional moves are compatible with the tested field. This does not identify 180 routing failures: the field's route costs, occupancy and stopping assumptions are not verified Fish rules. Prior obstacle diagnostics also cut against an obstacle-only explanation. G00 direction-change joint success is 65/394 away from nearby obstacles versus 198/764 near them.
- **Persistent objectives/history:** the causal past-five-move proxy gives 783 field/yx matches versus 503 for nearest camp, but changes objective family and availability together. On shared availability it gives 504 versus 435 across 1,177 moves. For direction changes, the headline +72 decomposes into **+9 on shared rows, +102 newly available successes and −39 lost successes**. Even the shared-row comparison mixes goal choice with history. It scores past movement against current goal locations; it does not track a historical goal identity.
- **Missing objectives/information:** 294 moves remain outside these declared geometric explanations. Possible causes include another objective, combat spacing, a different cost, earlier observations or state. None can be assigned from the destination alone.

History is usually present in the cache: 1,151/1,158 direction-change rows have 16 available earlier observation frames. G00 gets only 259 of those right jointly. Thus “the cache has no previous frames” cannot explain most changes. This does **not** establish sufficient memory: G00 primarily consumes compressed current features and prior action encodings, not the full sequence of those observation frames.

The strongest conclusion is **objective/command selection and insufficiently identified cost/tie/state rules**, rather than a demonstrated universal pathfinding defect. Neither persistence nor hidden intent is proven. The geometry audit includes 2,606 naturally sampled moves from 24 TRAIN games as a diagnostic comparison; its TRAIN geometry sample is not the whole corpus. See [R01](R01-movement.json) and [availability correction](R02-review-addendum.json).

## 3. Training and generalization

The previous augmented-TRAIN versus DEV comparison mixed different action frequencies. Applying the identity-verified natural mask gives:

| Existing model | Natural TRAIN | TRAIN standardized to DEV cells | Original DEV |
|---|---:|---:|---:|
| G00 | 81.79% | 81.02% | 79.71% |
| A00 | 83.03% | 82.30% | 80.49% |

Standardization matches action, engine and movement-continuation cells, with zero unmatched DEV rows. It controls those frequencies only, not maps, opponents, observation difficulty or policy versions. Existing TRAIN scores remain in-sample. The residual gap is real in these measurements but is not attributable to a particular omitted factor.

R02 tests whether the existing M01 architecture can fit a small diverse subset. It initializes the same 104,160-parameter architecture from scratch with fit-only normalization, uses 1,981 natural TRAIN rows, and withholds 20 of the 94 eligible TRAIN groups. A disjoint same-group control has 1,920 rows; the withheld-group control has 1,882. Action/context quotas deliberately make this a diverse capacity test, not a natural-frequency production benchmark. The fixed budget is 2,000 updates/256,000 row presentations, about 23 measured seconds. No DEV selection, pretrained weights or G00 fallback is used.

| Fixed final R02 checkpoint | Fitted rows | Other rows, same groups | Withheld groups |
|---|---:|---:|---:|
| Action type | 100.00% | 58.85% | 60.84% |
| Move destination, true family (512 rows each) | 99.61% | 34.96% | 37.30% |
| Joint move | 99.61% | 29.30% | 32.03% |
| Complete command, all probe categories | 85.16% | 31.09% | 32.78% |

The full-set scores retain every selected row. Rare support differs: all 37 fitted altar and 24 teleport examples exhaust those fit-group pools, so the same-group control has neither category. A supplementary equal-action comparison on common categories is 81.02%, 31.54%, 33.52%; it excludes those unsupported categories only for that explicitly separate diagnostic. It replaces no benchmark or full-set result.

The fitted model's 294 complete-command failures are 128 shops, 125 priorities, 18 blocked destinations, 18 ward destinations, 2 moves, 2 cast-1 targets and 1 teleport target. Therefore:

- A hard inability of this architecture to fit these movement examples is ruled out under this budget. Complete-command fitting, especially priority, is **not** solved: only 3/128 fitted priority arguments are exact.
- Transfer is poor even within seen groups. Withheld groups do not have a worse accuracy point estimate than the same-group control, so this experiment does not isolate a map/group-shift cause.
- Continued fitting becomes overconfident: control NLL rises from about 3.18/3.16 at update 100 to 14.30/17.20 at update 2,000. The final checkpoint remains fixed; update 100 is not retrospectively selected.
- This small-data, unregularized, one-fold/one-seed test demonstrates memorization and poor transfer under its protocol. It does not measure full-data retraining on fresh folds, prove information insufficiency, or establish a universal architecture limit.

The fresh review reproduced every final prediction and checked normalization, natural membership and row/group separation. Its likelihood calculation agreed within 0.00022 per row. Legacy legality summaries are corrected additively: all 117 fitted “invalid” flags are blocked-forecast movement-mask rejections, while fitted successful-move rejections are zero. Controls have 134/105 blocked rejections and 6/10 successful-move rejections, respectively. These must not be combined as an illegal-command rate. See [R02](R02-capacity.json), [review](R02-review.md) and [addendum](R02-review-addendum.json).

## 4. Representation/history loss is real, but its error contribution is unknown

The retained D02 audit documents concrete omissions: nearest-three summaries omit 50,902/90,182 visible living camp instances (56.44%) in 24 TRAIN games; other entity attributes and their associations are also compressed. The grid retains aggregates from all visible positions, so it is incorrect to say every distant entity disappears. Local geometry is not a full objective-conditioned route representation. Earlier observations exist but are not equivalent to the short action-history encodings used by G00.

These are potentially observable inputs that a configuration omits or compresses. Their causal share of errors is unmeasured. Earlier negative entity/history experiments do not establish that richer information cannot help; they changed learning arrangements and did not isolate every information channel.

Private bot memory, team task state and hidden dynamic entities must be distinguished from omitted observable evidence. Causal memory may retain earlier personally seen state with availability and age; it cannot turn unknown current state into known state. Exact own-priority history already exists in P05, so missing that specific field is not an adequate explanation of its priority failures.

**Observation sufficiency is unresolved.** The movement memorization result shows that these encoded samples can be separated, not that Fish's policy is a deterministic function of the retained inputs. Conversely, a bad model does not prove missing information. No present test establishes a Bayes error or an observation-imposed accuracy ceiling.

## 5. Labels, event semantics and policy variation

Known issues are specific rather than evidence of widespread contradictory labels:

- All 43 DEV shop purchase arguments remain unavailable and unassessed strict failures. Inventory/gold effects do not uniquely recover the original command. This currently prevents certification of the shop category; it is not proof of fundamental unrecoverability.
- Blocked attempts are recorded outcomes with attempted destinations, not successful moves to be removed by a movement mask. C01's readiness assumption was demonstrably wrong for support generation; C02 partially repairs it on TRAIN.
- Historical end reason 0 is decoded as `Yielded`. It does not distinguish an explicit bot end call from normal return. Root/effect order is audited, but caller-origin interpretation remains limited. Those labels are kept unchanged.
- Altar/teleport have two DEV rows each, submit 22, and entity-coordinate agreement can leave original target identity ambiguous. These cannot certify reliable complete API-command recovery.

The existing D02 encoded-input audit found only 5 conflicting classifier encodings/10 rows and 9 conflicting full-current encodings/18 rows among 415,798 assessed TRAIN rows. Almost every encoding was unique. This has little power to reject policy variation and is not a full personal-evidence contradiction test. Repeating the unchanged expensive audit would not resolve that limitation.

Eligible metadata contains engine versions but no Fish policy/binary fingerprint. TRAIN has 51 engine-2 and 43 engine-3 groups; DEV has four engine-2 groups and **one** engine-3 group. An apparent engine effect is confounded with group, and engine version is not Fish policy version. Contradictory labels under equivalent complete personal evidence, historical Fish updates and stochastic decisions remain **unresolved**, not demonstrated causes of the error mass.

## Ranked diagnosis and the next experiment

1. **Demonstrated hard limit:** incomplete command support in the current selector/decoder. Priority, ward, blocked attempts and cast 1 are structurally far below their targets. More selector capacity alone cannot fix that configuration.
2. **Demonstrated selection/decoding problem:** over half of A00's failures have an available correct command. The learner captures few rescue opportunities, and its hard decoder does not optimize the same command probabilities as its mixture loss. Aggregate recall/decoder gains obscured category failures.
3. **Demonstrated fitting/transfer problem:** the existing architecture memorizes the small movement set but transfers poorly, including within seen groups; priority still fits badly. This rules out one blanket capacity explanation while leaving optimization, information and inductive-bias explanations open.
4. **Demonstrated representation loss, unquantified causal impact:** visible entities and earlier observations are compressed or omitted. No experiment yet isolates how much this costs, and no evidence establishes observation sufficiency or irreducible hidden intent.
5. **Unresolved dataset/policy inconsistency:** known argument and semantics limits matter, but widespread contradictory examples or a policy-version mixture have not been shown.

**The single most informative next experiment is a matched, TRAIN-only causal goal-history control, with no fit.** Generate exactly the same five-goal command candidates for all arms; hold planner, tie rule, stopping radius, candidate availability and fallback fixed. Compare a prospectively frozen current-observation goal selector, a forward history-based selector and a last-heading control. Use only actual earlier personal evidence and explicit gaps; do not reconstruct intent backwards from the current destination. Report paired group results on identical direction-change rows, and separate any availability changes.

This addresses the specific confounding in R01 and tests whether causal history adds predictive information once goal-family and availability changes are removed. A gain would support useful history, not prove Fish's internal objectives. A failure would reject this proxy, not all persistence methods. No new architecture or large training allocation is justified before that question is answered.

## Artifacts and preservation

[R00-summary.json](R00-summary.json) contains natural-sampling comparisons and support/selection partitions. The exhaustive 6.5 MB group/confusion export stays local, hash-bound and reproducible; it is not a bulk git export. [completion.json](completion.json) binds new sources, reports, checkpoints, predictions and commands. Original V4–V10 results, splits, every DEV row, unfinished frequency preparation and all negative results remain preserved. The original 90%-per-category, macro-F1, movement, likelihood, targeting and three-seed requirements are unchanged and unmet. Production training remains paused; no model is promoted.
