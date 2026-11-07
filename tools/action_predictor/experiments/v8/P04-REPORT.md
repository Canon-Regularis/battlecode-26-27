# P04: matched priority-input control

Matched zeroed-recovered-input control for P03; same multimodal output and frozen M01 representation

**The category-wise 90% goal is not achieved.** One seed on the original reused development groups; no replacement or restored-input benefit is established.

| Model | Exact priority /576 | Joint priority /576 | Priority NLL | Mean integer error | Full observed joint NLL | Strict correct /14439 |
|---|---:|---:|---:|---:|---:|---:|
| M01 | 13 | 10 | 7.08824 | 355.200 | 0.872799 | 11411 |
| P01 | 22 | 15 | 6.75922 | 355.130 | 0.859674 | 11416 |
| P02 | 15 | 11 | 6.78100 | 354.905 | 0.860543 | 11412 |
| P03 | 96 | 57 | 3.99395 | 178.109 | 0.749362 | 11458 |
| frequency_hybrid | 16 | 8 | 5.05125 | 355.295 | 0.791540 | 11409 |
| P04 | 71 | 49 | 4.14836 | 435.851 | 0.755522 | 11450 |

Selected epoch 2 using the original joint-NLL rule; 8 completed epochs. Exploratory recovered-input follow-up gate met: False. This gate does not replace any original success target.

Matched P03/P04 head parameters 87528 each; P04 masks20319 extra-column weights; frozen M01 parameters 104160. Calls 13536, head updates 13534, supervised examples processed 118528; fitting 13.70s excluding verification. Computing only priority-row gradients preserves the full-minibatch denominator. Wider output, mixture initialization and decoding cost are part of this output-design package.

| Category | Support | Joint correct | Joint % | Type P/R/F1 % | True-family parameter % | Joint FP |
|---|---:|---:|---:|---:|---:|---:|
| altar | 2 | 0 | 0.00 | 0.00/0.00/0.00 | 100.00 | 93 |
| attack | 985 | 874 | 88.73 | 87.50/92.39/89.88 | 95.74 | 166 |
| blocked | 110 | 1 | 0.91 | 41.24/36.36/38.65 | 18.18 | 96 |
| cancel | 2589 | 2535 | 97.91 | 94.03/97.91/95.93 | N/A | 161 |
| cast_0 | 213 | 154 | 72.30 | 89.84/78.87/84.00 | 90.61 | 33 |
| cast_1 | 243 | 95 | 39.09 | 47.23/66.67/55.29 | 60.08 | 248 |
| end | 4096 | 3957 | 96.61 | 98.19/96.61/97.39 | N/A | 73 |
| move | 2362 | 1287 | 54.49 | 93.41/90.05/91.70 | 59.44 | 990 |
| priority | 576 | 49 | 8.51 | 64.96/59.55/62.14 | 12.33 | 479 |
| recall | 3084 | 2472 | 80.16 | 91.66/80.16/85.52 | N/A | 225 |
| shop | 43 | 0 | 0.00 | 82.35/97.67/89.36 | unassessed | 51 |
| submit | 22 | 19 | 86.36 | 25.33/86.36/39.18 | 100.00 | 56 |
| teleport | 2 | 0 | 0.00 | 25.00/100.00/40.00 | 0.00 | 8 |
| ward | 112 | 7 | 6.25 | 11.04/31.25/16.32 | 21.43 | 310 |

Type PRF measures action labels. True-family parameter accuracy uses ALL recorded rows in the category, including wrong predicted types. Joint correctness also requires the predicted type and every required exact parameter. The CSV separately reports joint precision/recall/F1 and parameter accuracy given a correct type. Null parameters mean not applicable for parameterless actions; shop arguments are unavailable and all43 remain strict failures.

All other action/spatial paths remain identical to M01. Movement top-k, destination errors, every targeting category, confusion matrix, priority history/unseen/frequency strata and paired group comparisons are in the JSON/immutable fit report. No original rows or support counts were dropped.

Historical partial flags remain zero successful-move mask rejections,92 blocked-forecast rejections and17 other readiness flags. A rejected blocked destination may match the intended outcome; full engine illegality is unassessed.

The fixed priority action decisions still cap joint priority correctness at343/576 (59.55%). All75 new validation and75 final-test games stay sealed; old exposed test unused. Five reused groups and two altar/teleport examples cannot certify broad reliability.

All epoch checkpoints, failed/negative studies and baselines remain preserved. Fresh Sol extra-high review is required before any further implementation or fitting.

P03 minus P04 exact-priority change: 4.340 percentage points; joint-priority change: 1.389 points. Priority-loss reduction: 3.722%.
The JSON P03_minus_P04 field has the treatment-minus-control direction. Other paired comparisons use candidate P04 minus the named comparator. Initial scores match exactly, shared completed-epoch shuffle RNGs match, and every saved control extra-column weight remains zero.
This comparison tests the39 direct recovered channels under a fixed M01 representation. Any later head-seed repeats would not establish independent full-GRU training or all-category reliability.
