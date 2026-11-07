# Observation-history findings

Observation history produced a modest destination improvement, but failed the frozen macro-F1 and ability-targeting guards against retained M01. The study stopped after two fits; no seed search or additional experiment was substituted. M01 remains the baseline.

| Metric | Fresh action+gap control H01 | Observation history H02 | Retained M01 |
|---|---:|---:|---:|
| Action accuracy | 88.09% | 88.39% | 88.73% |
| Action macro F1 | 61.94% | 61.42% | 63.24% |
| Joint action + encoded parameter | 78.68% | 79.04% | 79.03% |
| Exact movement destination | 60.25% | 61.43% | 59.44% |
| Joint movement | 54.28% | 54.53% | 54.49% |
| Observed joint NLL | 0.8670 | 0.8447 | 0.8728 |

Against the matched control, exact movement gained +1.19 pp (95% paired-group interval [+0.08, +2.46] pp). Joint movement gained only +0.25 pp, with interval [-1.36, +2.01] pp spanning zero. Joint loss decreased by 2.57%; its relative-reduction interval is [+1.65, +3.72]%. These are conditional development-group intervals from five groups, not untouched-test or three-seed confirmation.

## Where the movement gain occurs

| Objective context | Move support | Control exact | History exact | Gain | Paired-group interval (pp) |
|---|---:|---:|---:|---:|---|
| direction_change | 1158 | 26.08% | 28.15% | +2.07 pp | [+0.66, +3.92] |
| same_direction | 1198 | 93.32% | 93.74% | +0.42 pp | [-0.70, +1.54] |
| near_static_obstacle | 1378 | 56.97% | 58.78% | +1.81 pp | [+1.00, +2.79] |
| away_from_static_obstacle | 984 | 64.84% | 65.14% | +0.30 pp | [-1.18, +2.57] |
| new_own_turn | 218 | 57.34% | 63.76% | +6.42 pp | [+3.30, +9.23] |
| same_own_turn | 2140 | 60.51% | 61.21% | +0.70 pp | [-0.29, +1.77] |
| visible_set_changed | 157 | 48.41% | 53.50% | +5.10 pp | [+1.81, +9.09] |

Direction changes remain the main destination bottleneck: 832 of 911 H02 destination errors (91.33%) occur on the 1158 recorded direction-changing moves. Exact accuracy there is only 28.15%, versus 93.74% when repeating the earlier direction. History corrected 24 additional direction-changing destinations, but did not resolve that gap.

The larger gains occur at new own-turn boundaries and after personally visible entity-set changes; the latter has only157 move examples. Near-obstacle and direction-changing gains exceed their comparison contexts. These contexts overlap, so their gains cannot be added or treated as causal explanations. They are objective evaluation strata, not invented intent labels or additional success criteria.

## Why the study stopped

H02 macro F1 is 61.42%, versus 63.24% for M01 (-1.81 pp, exceeding the frozen1pp regression guard). Ability-slot1 coordinate targeting is 57.61%, versus 60.08% (-2.47 pp on243 examples, exceeding the2pp guard). The improvement trigger passed; both required guards failed. The point regression and its uncertainty are both retained in the full report.

The original65% macro-F1 and65.21% exact-movement targets remain unmet. Passing the historical loss threshold against E02 does not establish a10% improvement over stronger current action-history baselines. No threshold or benchmark was changed to claim success.

## Evidence and limits

- All433,071 training rows and14,439 original development-validation rows were retained, with whole groups and payload hashes disjoint.
- Recovered1,889,036 earlier personal PRE observations. Full raw whitelisted evidence is retained; neural history uses M01's existing253-field observation encoder and a32-field projection.
- Seven causal/matching/accounting tests passed. Saved-model inference matched all four input tensors exactly and reproduced action/parameter outputs on75 real replay targets for each of H01/H02, including natural empty-history cases.
- Only112 development rows have fewer than16 earlier observations (28 movement rows). No missing-history rows were dropped; startup and unavailable-observation conclusions remain limited.
- Both fresh arms have119,392 nominal parameters; M01 has104,160. Measured total training time was522.7s/19 epochs for H01 and684.2s/26 epochs for H02, using the unchanged stopping rule.
- All75 new validation and75 final-test games remain sealed. No further replays, matches, bot changes, deployment or PR.

Full per-action precision/recall/F1/support, confusion matrices, targeting regressions, top-k movement, destination error, partial legality, history bins, hashes and exact commands: [RESULTS.md](RESULTS.md). Full engine illegal-action rate is unassessed; the partial observable metric is not a legality certificate.
