# Additional Fish data: controlled first retrain

Architecture, feature definitions, sampling, training settings, seed and original validation benchmark are unchanged.
500 additional distinct games were collected in 100 complete groups; 350 train, 75 validation and 75 sealed test.
The initial experiment uses only the 350 new training games plus the original 120 training games. Both new reserved partitions remain unopened.

| Metric on original validation | Original E06 | More-data M01 |
|---|---:|---:|
| Macro F1 | 0.5599 | 0.6324 |
| Action accuracy | 0.8528 | 0.8873 |
| Joint observed NLL | 0.9694 | 0.8728 |
| Joint recorded-parameter accuracy | 0.7588 | 0.7903 |
| Movement exact_accuracy | 0.5851 | 0.5944 |
| Movement top3_accuracy | 0.8472 | 0.8607 |
| Movement top5_accuracy | 0.9475 | 0.9505 |
| Movement penalized_mean_chebyshev_error | 0.6410 | 0.6211 |

All per-action precision/recall/F1/support, confusion matrices, partial observable-invalid rates and paired whole-group uncertainty are in `validation-comparison.json`.
This is one matched seed, not a three-seed reliability claim. New games can change policy/engine/opponent composition. The unchanged epoch/patience budget also allows more optimizer updates; this is not an equal-compute comparison or a causal claim about volume alone.
Original API arguments and full engine legality retain the V4 limitations. No final test was evaluated; no matches, deployments or PRs were created.

Exact commands are recorded in `.cambc/action-predictor/v5/commands.jsonl`; downloaded metadata pages, source queries, receipts and hashes are retained locally.

## Completed matched-seed check

The primary comparison above uses seed 26. The two predeclared follow-up seeds
also finished, without opening the new validation or final-test games.

| Model | Seed | Macro F1 | Movement exact | Joint NLL |
|---|---:|---:|---:|---:|
| M01 | 26 | 0.6324 | 0.5944 | 0.8728 |
| M02 | 27 | 0.6177 | 0.5986 | 0.8591 |
| M03 | 28 | 0.5868 | 0.5885 | 0.8734 |

Movement mean is 0.5938 across seeds; macro F1 mean is 0.6123. All four original
targets were **not** met consistently. Movement remains below the fixed 0.6521
requirement. `three-seed-check.json` includes each matched comparison and paired
whole-group intervals. No seed was selected using final-test results.
