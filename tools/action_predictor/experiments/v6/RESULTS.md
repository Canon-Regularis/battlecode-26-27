# Public map encoding experiment

Keep current M01 baseline: the map candidate improves conditional movement but fails the targeting-regression guard.

All current V5 seeds finished before spatial training. Training data, validation groups, target labels, losses, optimizer and epoch/patience settings are unchanged.
The added CNN reads static bot-visible terrain and objective layout: local 23×23 and global 32×32 rasters. An identical zero-map architecture is the one-seed capacity control. Original initialization and shuffle stream are preserved.

| Model | Seed | Macro F1 | Movement exact | Joint movement | Joint NLL | Original target gates |
|---|---:|---:|---:|---:|---:|---:|
| M01 | 26 | 0.6324 | 0.5944 | 0.5449 | 0.8728 | baseline |
| S01 | 26 | 0.6586 | 0.6143 | 0.5495 | 0.8003 | 3/4 |
| S02 | 26 | 0.6335 | 0.6016 | 0.5406 | 0.8619 | 2/4 |
| M02 | 27 | 0.6177 | 0.5986 | 0.5423 | 0.8591 | baseline |
| M03 | 28 | 0.5868 | 0.5885 | 0.5305 | 0.8734 | baseline |

Only one map seed was fitted: the predeclared repeat checks failed (targeting_guard). The identical zero-map control was completed. No three-seed confirmation is claimed.

All original targets met consistently across three map seeds: **False**.
Map versus current-GRU movement gain: +1.99 pp; paired 95% whole-group interval +0.98 to +3.21 pp (seed 26 only).
Map versus zero-map movement gain: +1.27 pp; paired 95% whole-group interval +0.14 to +2.16 pp (one matched seed).
Against the strongest same-data seed-26 control (S02), joint loss reduction is 7.15%. Target-coordinate changes versus M01: attack +0.00 pp, cast_0 -0.47 pp, cast_1 -5.35 pp.
Original target gates use the unchanged V4 reference set for historical comparability. Direct comparisons against the stronger same-data GRU and capacity control are reported separately; gains against those controls must not be inferred from the original gate count.

All per-action precision/recall/F1/support, confusion matrices and parameter metrics are exported as CSV. `validation-comparison.json` includes each run and paired whole-group intervals; `comparison.html` displays the comparisons.
Full engine illegal-action rate and original target IDs/shop arguments retain the documented limitations. No final test or new validation game was scored. Maps may recur across held-out game groups.

Data alignment passed for every row against its personal PRE observation. `sealed-test-audit.json`, `plan.json`, `execution-lock.json` and `data-ready.json` record provenance and constraints. Exact commands remain in `.cambc/action-predictor/v5/commands.jsonl`.
Checkpoints: `.cambc/action-predictor/v6/runs/S*/model.pt`. The original V5 checkpoints are unchanged. No bot deployment, matches or PRs were created.
