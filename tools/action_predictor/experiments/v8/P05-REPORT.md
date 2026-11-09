# P05: learned causal anchored-residual priority output

**The category-wise 90% goal remains unmet.** One head seed, five reused development groups. No replacement or three-seed success claim.

| Model | Exact priority /576 | Joint priority /576 | Priority NLL | MAE | Full observed joint NLL | Strict correct /14439 |
|---|---:|---:|---:|---:|---:|---:|
| M01 | 13 | 10 | 7.08824 | 355.200 | 0.872799 | 11411 |
| P01 | 22 | 15 | 6.75922 | 355.130 | 0.859674 | 11416 |
| P02 | 15 | 11 | 6.78100 | 354.905 | 0.860543 | 11412 |
| P03 | 96 | 57 | 3.99395 | 178.109 | 0.749362 | 11458 |
| P04 | 71 | 49 | 4.14836 | 435.851 | 0.755522 | 11450 |
| A01/global_frequency | 16 | 8 | 5.05125 | 355.295 | 0.791540 | 11409 |
| A01/current_plus_copy | 0 | 0 | 11.30494 | 698.844 | 1.041012 | 11401 |
| A01/current_plus_residual | 29 | 8 | 4.75333 | 699.028 | 0.779655 | 11409 |
| A01/current_minus_copy | 40 | 30 | 9.41826 | 153.260 | 0.965748 | 11431 |
| A01/current_minus_residual | 28 | 11 | 5.00670 | 154.781 | 0.789763 | 11412 |
| A01/scheduled_plus_copy | 0 | 0 | 11.30494 | 698.844 | 1.041012 | 11401 |
| A01/scheduled_plus_residual | 29 | 8 | 4.75333 | 699.028 | 0.779655 | 11409 |
| A01/scheduled_minus_copy | 40 | 30 | 9.41826 | 153.260 | 0.965748 | 11431 |
| A01/scheduled_minus_residual | 28 | 11 | 5.00670 | 154.781 | 0.789763 | 11412 |
| A01/latest_plus_copy | 0 | 0 | 11.23324 | 698.830 | 1.038152 | 11401 |
| A01/latest_plus_residual | 27 | 7 | 4.73935 | 699.049 | 0.779098 | 11408 |
| A01/latest_minus_copy | 40 | 30 | 9.35776 | 153.247 | 0.963335 | 11431 |
| A01/latest_minus_residual | 28 | 11 | 4.99253 | 154.705 | 0.789198 | 11412 |
| P05 | 109 | 71 | 3.53123 | 144.566 | 0.730903 | 11472 |

Selected epoch 2 by unchanged joint-NLL rule, 8 epochs; 13536 optimizer calls, 13534 updates, 118528 supervised examples processed. 22.77s fitting excludes evidence verification. All epoch checkpoints and failures retained.

Fixed exploratory gate: False. Individual checks: {'exact': False, 'joint': True, 'nll': True, 'rare_nll': True, 'unseen_nll': True, 'tail': True, 'nonpriority_paths_identical': True}. This criterion does not replace any original target or authorize repeats.

Output capacity207816 versus87528 P03;104160 M01 parameters frozen. This changes output modes, priors and analytic access to exact PRE integers, and does not isolate one factor. No new information or target-derived sign enters inference. Missing history remains explicit.

| Category | Support | Joint correct | Joint % | Type P/R/F1 % | True-family parameter % | Joint FP |
|---|---:|---:|---:|---|---:|---:|
| altar | 2 | 0 | 0.00 | 0.00/0.00/0.00 | 100.00 | 93 |
| attack | 985 | 874 | 88.73 | 87.50/92.39/89.88 | 95.74 | 166 |
| blocked | 110 | 1 | 0.91 | 41.24/36.36/38.65 | 18.18 | 96 |
| cancel | 2589 | 2535 | 97.91 | 94.03/97.91/95.93 | — | 161 |
| cast_0 | 213 | 154 | 72.30 | 89.84/78.87/84.00 | 90.61 | 33 |
| cast_1 | 243 | 95 | 39.09 | 47.23/66.67/55.29 | 60.08 | 248 |
| end | 4096 | 3957 | 96.61 | 98.19/96.61/97.39 | — | 73 |
| move | 2362 | 1287 | 54.49 | 93.41/90.05/91.70 | 59.44 | 990 |
| priority | 576 | 71 | 12.33 | 64.96/59.55/62.14 | 18.92 | 457 |
| recall | 3084 | 2472 | 80.16 | 91.66/80.16/85.52 | — | 225 |
| shop | 43 | 0 | 0.00 | 82.35/97.67/89.36 | Unassessed | 51 |
| submit | 22 | 19 | 86.36 | 25.33/86.36/39.18 | 100.00 | 56 |
| teleport | 2 | 0 | 0.00 | 25.00/100.00/40.00 | 0.00 | 8 |
| ward | 112 | 7 | 6.25 | 11.04/31.25/16.32 | 21.43 | 310 |

Type PRF measures labels. True-family parameter accuracy uses every recorded category row, including wrong type forecasts; joint requires correct type and all exact required parameters. CSV additionally reports joint PRF, both FP definitions and parameter accuracy given correct type. All43 shops are unassessed strict failures; observed likelihood excludes unknown arguments.

Rare exact 6/65; unseen exact 1/4. Errors above1000: 4; max 1489; wrong signs 92. All adverse strata, four unseen cases and twenty largest errors are preserved in JSON.

Every action, movement and ability path is unchanged. Movement top-k, destination errors, confusion matrix, partial legality coverage and group/category intervals are in the immutable report and analysis. Historical flags remain0 successful-move rejections,92 blocked forecasts and17 readiness/resource checks; full engine legality is unknown.

Frozen priority action correctness caps this branch at343/576=59.55%. Both75-game reserved partitions remain unopened and old exposed test unused. Five reused groups and two altar/teleport examples cannot certify reliability. All original targets and failed guards remain binding. Fresh Sol xhigh completed-fit review required before further experiments.
