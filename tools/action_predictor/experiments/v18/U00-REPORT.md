# U00: frozen-upstream execution readout

TRAIN-mean geometry control.
One shared frozen L02 checkpoint supplies forecasts, latent representations, priors and baseline causal filtering. Only existing execution heads and the conditioning projection are trained. This changes several training freedoms versus L02; only the matched U01-U00 comparison isolates the named geometry-input treatment.

| Original DEV measure | L02 | U00 |
| --- | ---: | ---: |
| Complete commands /14,439 | 12064 | 12033 |
| Complete-command accuracy | 0.835515 | 0.833368 |
| Action macro F1 | 0.610444 | 0.609951 |
| Observed joint NLL | 0.656567 | 0.665298 |

| Category | Joint L02 | Joint U00 | Conditional parameter | Type TP / FP |
| --- | ---: | ---: | ---: | ---: |
| <unknown> | 0/0 | 0/0 | unavailable/not applicable | 0 / 0 |
| altar | 0/2 | 0/2 | 1.0000 | 0 / 21 |
| attack | 892/985 | 890/985 | 0.9574 | 927 / 101 |
| blocked | 4/110 | 5/110 | 0.1909 | 28 / 16 |
| cancel | 2542/2589 | 2545/2589 | unavailable/not applicable | 2545 / 217 |
| cast_0 | 158/213 | 158/213 | 0.9014 | 173 / 23 |
| cast_1 | 71/243 | 74/243 | 0.5885 | 108 / 52 |
| end | 3966/4096 | 3949/4096 | unavailable/not applicable | 3949 / 88 |
| move | 1365/2362 | 1356/2362 | 0.6025 | 2199 / 194 |
| priority | 50/576 | 45/576 | 0.1892 | 163 / 22 |
| recall | 2996/3084 | 2991/3084 | unavailable/not applicable | 2991 / 498 |
| shop | 0/43 | 0/43 | unavailable/not applicable | 41 / 10 |
| submit | 20/22 | 20/22 | 1.0000 | 20 / 36 |
| teleport | 0/2 | 0/2 | 0.0000 | 1 / 4 |
| ward | 0/112 | 0/112 | 0.2232 | 1 / 11 |

| Sampling | Complete / rows | NLL | Change conditional / joint | Continue conditional / joint |
| --- | ---: | ---: | ---: | ---: |
| train/all | 343455/433071 | 0.637355 | 12864 / 11797 of 35456 | 33868 / 33089 of 36368 |
| train/natural | 247810/288801 | 0.519406 | 6604 / 6049 of 22279 | 24193 / 23679 of 25918 |
| validation/all | 12033/14439 | 0.665298 | 321 / 288 of 1158 | 1099 / 1065 of 1198 |

Conditional metrics supply the recorded family only after forecasting for diagnosis. Complete predictions use predicted action types and the original probability-consistent joint MAP. Component-mode union/common-wrong bounds are frozen-distribution diagnostics, not achieved selector accuracy or architecture/data ceilings.

Natural TRAIN figures use identity-verified membership with the common augmented-traversal filtering cadence. They remain in-sample and do not isolate group shift. No sampled rows are stitched as adjacent observations. Current recorded actions enter the frozen filter only after their PRE features have been cached; the trained readout never changes that filter.

Selected round 3 of 9; updates 5227 selected / 15678 completed. Original .0001 NLL improvement, patience6, max35. Every attempted round and final archive retained. Trainable/readout parameters 13662, resident model parameters 104928; serving additionally requires the frozen upstream policy. No total production latency or architecture-efficiency claim.

The evaluation includes paired overall/category/targeting/context differences against L02, L01, B00 and G00; U01 additionally compares directly with U00. Accuracy intervals use fraction differences, macro F1 score differences, and NLL nats per recorded decision. All are conditional on selected checkpoints and five repeatedly reused DEV groups, not untouched, selection-adjusted or three-seed evidence.

This diagnostic tests incremental utility of the named predicted-geometry channel under a fixed upstream model. Other paths still carry geometry and history. Positive results cannot identify Fish intent; negative results cannot reject strategic objectives or prove observation insufficiency. Fixed P05 priority modes and missing purchase arguments remain configuration limits that readout training cannot remove.

Original category90%, macro.65, movement.6520745131244708, likelihood/targeting and three-seed targets remain binding. No promotion or robust improvement is claimed. All43DEV shops are unassessed strict failures; purchase-argument likelihood is absent. Sparse categories, entity identity and full legality/calibration remain uncertified. Successful-move mask rejections remain separate from blocked-attempt mask diagnostics.

Model research only. Both75-game reservations remain sealed. No matches, replay downloads, bot/runtime changes or deployment. PR11DRAFT/open/unmerged/no-auto-merge/queue. Fresh Sol xhigh review follows this fit; matched continuation is separately recorded.
