# A01: signed-anchor and residual-frequency baselines

All13 families were fixed from training before this development evaluation. These are arithmetic/frequency parameter baselines with M01 action/spatial predictions preserved, not newly trained GRUs. No neural optimizer ran.

| Family | Exact priority /576 | Joint priority /576 | Priority NLL | Full observed joint NLL | Mean integer error | Unseen exact /4 | Rare exact /65 |
|---|---:|---:|---:|---:|---:|---:|---:|
| global_frequency | 16 | 8 | 5.05125 | 0.791540 | 355.295 | 0 | 0 |
| current_plus_copy | 0 | 0 | 11.30494 | 1.041012 | 698.844 | 0 | 0 |
| current_plus_residual | 29 | 8 | 4.75333 | 0.779655 | 699.028 | 0 | 1 |
| current_minus_copy | 40 | 30 | 9.41826 | 0.965748 | 153.260 | 1 | 5 |
| current_minus_residual | 28 | 11 | 5.00670 | 0.789763 | 154.781 | 0 | 1 |
| scheduled_plus_copy | 0 | 0 | 11.30494 | 1.041012 | 698.844 | 0 | 0 |
| scheduled_plus_residual | 29 | 8 | 4.75333 | 0.779655 | 699.028 | 0 | 1 |
| scheduled_minus_copy | 40 | 30 | 9.41826 | 0.965748 | 153.260 | 1 | 5 |
| scheduled_minus_residual | 28 | 11 | 5.00670 | 0.789763 | 154.781 | 0 | 1 |
| latest_plus_copy | 0 | 0 | 11.23324 | 1.038152 | 698.830 | 0 | 0 |
| latest_plus_residual | 27 | 7 | 4.73935 | 0.779098 | 699.049 | 0 | 1 |
| latest_minus_copy | 40 | 30 | 9.35776 | 0.963335 | 153.247 | 1 | 5 |
| latest_minus_residual | 28 | 11 | 4.99253 | 0.789198 | 154.705 | 0 | 1 |

Descriptive minimum full observed joint NLL: 0.779098; additional10% improvement reference: 0.701188. All original benchmarks remain binding. Exactness, joint correctness, likelihood and error winners may differ; no family is adopted.

A01-summary.csv retains all families, available/missing counts, tail errors and out-of-vocabulary forecasts. A01-per-category.csv includes type and joint PRF/FP, parameter exactness over all true-family rows and among correctly typed rows, support, observed loss and unassessed arguments. A01.json preserves confusion matrices, every spatial metric, per-group counts, rare/unseen/missing/outside-window strata and pointwise paired uncertainty versus P03.

All14439 rows remain. Latest-argument absence uses the frozen unconditional prior, rather than dropping rows or treating missing as zero. All43 shop arguments remain unavailable and strict failures; their observed likelihood includes action loss only. Full engine legality is unknown. Historical partial flags remain0 successful-move mask rejections,92 blocked-forecast rejections and17 other flags.

No original goal is achieved by this study. The M01 action classifier remains frozen, so priority joint correctness is capped at343/576 (59.55%). The90%-in-every-category/three-seed and original macroF1/movement/loss/targeting requirements are unchanged. Five reused groups and two altar/teleport examples cannot certify broad reliability.

All baseline priors, source snapshots, interrupted-preparation evidence and prediction archives are preserved. Both75-game reserved partitions remain sealed; old exposed test unused. Fresh Sol extra-high review is required before any learned residual design or other work.
