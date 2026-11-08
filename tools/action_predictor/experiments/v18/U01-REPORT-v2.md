# U01: dynamic versus mean geometry with a common frozen upstream

Both fits train identical copies of the existing execution readout. The L02 forecaster, representations, priors and baseline causal filtering are shared and frozen. Only the named projection geometry varies: dynamic causal predictions versus TRAIN means. This tests incremental geometry under fixed upstream state, not a fully retrained persistent policy.

| Original DEV measure | U00 mean | U01 dynamic |
| --- | ---: | ---: |
| Complete commands /14,439 | 12033 | 12029 |
| Exact joint accuracy | 0.833368 | 0.833091 |
| Action macro F1 | 0.609951 | 0.609930 |
| Observed joint NLL | 0.665298 | 0.665253 |

U01 rescues4 and regresses8 commands against U00.

| Movement context | Conditional U00 / U01 | Joint U00 / U01 | Support |
| --- | ---: | ---: | ---: |
| move | 1423 / 1420 | 1356 / 1353 | 2362 |
| blocked | 21 / 22 | 5 / 6 | 110 |
| continue | 1099 / 1099 | 1065 / 1065 | 1198 |
| change | 321 / 318 | 288 / 285 | 1158 |
| startup | 3 / 3 | 3 / 3 | 6 |

| Category | Joint U00 / U01 | Conditional parameter U00 / U01 | U01 type TP / FP |
| --- | ---: | ---: | ---: |
| <unknown> | 0 / 0 of0 | N/A / N/A | 0 / 0 |
| altar | 0 / 0 of2 | 1.0000 / 1.0000 | 0 / 21 |
| attack | 890 / 889 of985 | 0.9574 / 0.9563 | 927 / 99 |
| blocked | 5 / 6 of110 | 0.1909 / 0.2000 | 28 / 16 |
| cancel | 2545 / 2545 of2589 | N/A / N/A | 2545 / 219 |
| cast_0 | 158 / 158 of213 | 0.9014 / 0.9014 | 173 / 23 |
| cast_1 | 74 / 75 of243 | 0.5885 / 0.5885 | 109 / 52 |
| end | 3949 / 3947 of4096 | N/A / N/A | 3947 / 88 |
| move | 1356 / 1353 of2362 | 0.6025 / 0.6012 | 2199 / 193 |
| priority | 45 / 45 of576 | 0.1892 / 0.1892 | 164 / 22 |
| recall | 2991 / 2991 of3084 | N/A / N/A | 2991 / 498 |
| shop | 0 / 0 of43 | N/A / N/A | 41 / 10 |
| submit | 20 / 20 of22 | 1.0000 / 1.0000 | 20 / 37 |
| teleport | 0 / 0 of2 | 0.0000 / 0.0000 | 1 / 4 |
| ward | 0 / 0 of112 | 0.2232 / 0.2232 | 1 / 11 |

Conditional coordinates/ranks/parameter losses supply the recorded family after forecasting only for diagnosis. Complete commands use predicted families and the original probability-consistent joint decoder. B00 comparisons reconstruct archived family_commands; chosen-command coordinates are not misrepresented as true-family diagnostics.

Exploratory allocation checks: `{'command_NLL_lower': True, 'change_conditional_NLL_lower': False, 'change_conditional_gain_at_least_01': False, 'change_joint_not_lower': False, 'continuation_conditional_drop_within_005': True, 'overall_strict_not_lower': False, 'attack_cast_conditional_drop_within_02': True}`; all pass: `False`. These gates were frozen before fitting and do not replace any original success target.

TRAIN and natural-membership fitting, DEV direction conditional NLL/ranks/probabilities, paired targeting/category losses and initial-readout comparisons are in the versioned evaluation/diagnosis. Natural membership retains the common augmented filtering cadence; TRAIN remains in-sample. No isolated group-shift or observation-sufficiency inference.

Paired intervals use2,000 whole-group draws, seed20261106. Accuracy differences are fractions, macro-F1 differences are score units, NLL differences are nats per decision. Five repeatedly reused DEV groups and selected checkpoints are not untouched or selection-adjusted evidence. One seed does not establish robustness.

Selected round3 of9, updates 5227 selected /15678 completed. Original .0001 NLL improvement/patience6/max35 rule retained. Initialization, RNG/order, upstream and frozen-tensor contracts are in U01-pair-contract.json. No epoch0 replacement.

The supplemental fixed-weight mean-geometry sensitivity was registered during fitting after early NLLs, before selected-checkpoint analysis; it is not claimed as a before-fit preregistration. It changes no trained checkpoint or primary prediction and removes only the named projection variability, retaining other geometry/goal pathways.

No promotion, repeated seeds or Fish-intent claim. Original90%-per-supported-category, macro.65, movement.6520745131244708, likelihood, targeting and three-seed goals remain binding. Fixed P05 modes and missing shop arguments remain hard configuration limits. All43DEV shops are unassessed strict failures; purchase likelihood is absent. Sparse altar/teleport/submit, entity identity, full legality/calibration remain uncertified. Successful-move mask rejection is separate from blocked-attempt outcome diagnostics.

Model research only; both75-game reservations sealed. No matches, downloads, bot/runtime work or deployment. PR11DRAFT/open/unmerged/no-auto-merge/queue. Fresh Solxhigh review follows; continuing research is not stopped by completion of this comparison.
