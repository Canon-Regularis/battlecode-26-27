# V38: movement-only neighborhood correction

The center-only control N00 has completed its frozen eight-pass fit. It does not meet the allocation conditions against the frozen R00 reference. The actual-neighborhood treatment N01 has not run; no conclusion about neighborhood benefit follows yet.

The reviewed V37 audit motivates testing whether surrounding terrain helps distinguish destinations. Both arms add the same 5,697-parameter correction to movement tile logits while freezing the 139,292-parameter reviewed R00 backbone. N00 repeats each destination's center terrain across the available patch slots. N01 will receive the actual 3x3 terrain patch with the same crop-availability mask. Both retain the same candidate features, shared context, original support mixture, observed-command likelihood and joint decoder. This is distinct from the earlier shared map-fusion intervention; it does not establish that the earlier failure was caused by shared gradients.

The population is all 1,085 existing contiguous fitting windows: 34,720 rows across 40 previously exposed groups. Neither arm selects the V37 error cohort. Each arm has eight passes, 277,760 row presentations and 272 optimizer calls, with seed 27 for the fresh correction, identical schedules, reset/detach every eight roots, and final-pass-eight selection only. The paired fitting/evaluation cap is 7,200 seconds; there are no repeats or extensions. N00 consumed 81.279811 seconds. N01 requires a fresh, bound N00 postfit approval.

## Control result

| Fitting metric | Frozen R00 | N00 |
| --- | ---: | ---: |
| Complete commands / 34,720 | 26,717 | 26,726 |
| Complete moves / 5,472 | 2,924 | 2,922 |
| Complete changes / 2,669 | 258 | 261 |
| Complete continuations / 2,796 | 2,666 | 2,661 |
| Change coordinate NLL | 2.253202083 | 2.213696678 |
| Change within-alternative NLL | 1.617364970 | 1.609760849 |
| Balanced movement joint NLL | 1.725759753 | 1.716253537 |
| Full-command NLL | 1.246750918 | 1.245355751 |
| Macro-F1 | 0.351642256 | 0.351467071 |

Four of the 18 frozen conditions fail against R00: complete-change gain (+0.1124 percentage points versus at least 5), complete-movement gain (-0.0365 points versus at least 1), change-coordinate NLL reduction (0.03951 versus at least 0.15), and within-alternative NLL reduction (0.00760 versus at least 0.05). Continuation protection and the remaining guards pass. These small fitting changes are not a qualifying movement improvement. The grouped interval for complete-change gain includes zero; favorable leave-one-group-out signs are overlapping fitting diagnostics, not independent replication.

All category scores, movement false positives, paired group/window results, and probability decompositions are retained in `N00.json`. Nonmovement conditional scores and likelihoods remain unchanged, while some complete-command predictions change because movement competes in joint decoding. Complete casts, priority, ward and several other categories remain zero; all shops remain strict failures because purchase arguments are unavailable.

The prefit code review verified all 26 tests, 101 source and 113 input bindings, matched initialization, full initial forecast parity, and update/normalization/budget gates. Initial forecasts reproduce R00 on all 34,720 rows. The fit records exact frozen-backbone checks at every checkpoint and finite gradient norms at all 272 updates; no update clipped. Parent postfit verification and independent result review are required before N01.

## Interpretation and next gate

N00 is the center-only matched control, not the proposed neighborhood treatment. Its failed reference allocation does not cancel the already frozen N01 comparison, but neither does it justify additional fits. N01 must meet all 18 conditions against both N00 and frozen R00; beating a weakened control alone is insufficient. A passing pair would only support a separately reviewed transfer study.

This remains a one-seed, fitting-only correction on a warm, frozen fitting-trained model, using observed past actions and previously exposed, availability-enriched groups. Missing shop arguments, ambiguous entity targets, incomplete legality and new POST validation remain unresolved. No generalization, recovered intent, high-level strategy, playing-strength improvement or promotion is established. Strong G00/L02/JP02 references, category-90%, reliability and three-seed requirements remain binding.
