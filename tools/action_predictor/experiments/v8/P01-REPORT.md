# P01: Zeroed-input refit control

**Not an achieved ≥90%-in-every-category model.** This is one seed of an isolated priority-head study. Recovered priority channels are zeroed, so improvements cannot be attributed to recovered inputs.

Selected epoch 3; priority exact 22/576, joint 15/576. Conditional priority NLL 6.7592; observed full joint NLL 0.8597. All other action/spatial predictions remain frozen. Fixed action decisions cap priority joint correctness at343/576 (59.55%).

| Category | Support | Joint correct | Joint accuracy | Conditional parameter accuracy | Precision | Recall | F1 | False positives | Observed joint NLL |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| <unknown> | 0 | 0 | unavailable | unavailable | 0.00% | 0.00% | 0.00% | 0 | unavailable |
| altar | 2 | 0 | 0.00% | 100.00% | 0.00% | 0.00% | 0.00% | 93 | 2.4262 |
| attack | 985 | 874 | 88.73% | 95.74% | 87.50% | 92.39% | 89.88% | 130 | 0.3479 |
| blocked | 110 | 1 | 0.91% | 18.18% | 41.24% | 36.36% | 38.65% | 57 | 4.1667 |
| cancel | 2589 | 2535 | 97.91% | unassessed | 94.03% | 97.91% | 95.93% | 161 | 0.0742 |
| cast_0 | 213 | 154 | 72.30% | 90.61% | 89.84% | 78.87% | 84.00% | 19 | 0.8353 |
| cast_1 | 243 | 95 | 39.09% | 60.08% | 47.23% | 66.67% | 55.29% | 181 | 2.1388 |
| end | 4096 | 3957 | 96.61% | unassessed | 98.19% | 96.61% | 97.39% | 73 | 0.1074 |
| move | 2362 | 1287 | 54.49% | 59.44% | 93.41% | 90.05% | 91.70% | 150 | 1.4324 |
| priority | 576 | 15 | 2.60% | 3.82% | 64.96% | 59.55% | 62.14% | 185 | 7.9116 |
| recall | 3084 | 2472 | 80.16% | unassessed | 91.66% | 80.16% | 85.52% | 225 | 0.5973 |
| shop | 43 | 0 | 0.00% | unassessed | 82.35% | 97.67% | 89.36% | 9 | 0.0850 |
| submit | 22 | 19 | 86.36% | 100.00% | 25.33% | 86.36% | 39.18% | 56 | 0.2837 |
| teleport | 2 | 0 | 0.00% | 0.00% | 25.00% | 100.00% | 40.00% | 6 | 4.5774 |
| ward | 112 | 7 | 6.25% | 21.43% | 11.04% | 31.25% | 16.32% | 282 | 4.2483 |

Optimizer calls 15228; actual priority-head updates 15226; epochs 9; elapsed fitting seconds 10.3. Epoch-zero report was not selectable. Completed epochs only. Discarded partial-epoch work and time after interruption are not included; failure logs and every epoch checkpoint are retained. Optimizer calls include no-gradient batches; head updates exclude them.

All43 shop arguments remain unassessed strict failures. Their reported joint NLL includes observed action loss only, not unavailable purchase-argument likelihood. Categories with no required parameters have no conditional-parameter accuracy. Altar/teleport have only two examples and remain uncertified.

Legality is unassessed in the full engine. The unchanged historical partial metric combines zero successful-move mask rejections,92 rejected destinations in blocked forecasts, and17 other readiness/resource flags. Blocked mask rejection may be consistent with a blocked-outcome forecast; it is not automatically an illegal prediction.

Exact priority, joint priority and loss paired-group intervals are in the diagnostics JSON; all category joint intervals and history/unseen-value strata are in the immutable fit report. Intervals use2,000 paired resamples of five reused development groups and condition on checkpoint selection. They are not three-seed or untouched-test confirmation.

All75 new validation and75 final-test games remain sealed. No matches, bot changes, downloads, deployment or PR were performed by this experiment. A fresh Sol review is required before any next experiment.
