# Distribution of the existing V27 gain

This is a lookup of the already saved V27 paired group counts against canonical eligible-job engine metadata and the original DEV numeric group array. It performs no new inference or model selection and does not replace the full five-group result.

| Historical engine | Original DEV rows | Numeric groups | RC01 policy net commands vs P05 policy | RC01 policy net commands vs RC00 policy |
| --- | ---: | --- | ---: | ---: |
| 2.0.0 | 11,727 | 1, 10, 11, 17 | +26 | -3 |
| 3.0.0 | 2,712 | 31 | +47 | +14 |

All engine-3 DEV games belong to one group. Its +47 supplies 64.4% of the total +73 over P05, but positive engine-2 net gains remain. The additional real-versus-shuffled gain is +3, 0, -6, 0, +14 across the original five groups; its full-group accuracy interval spans zero. These counts do not identify an engine effect: opponent, map, Fish policy version and other group attributes remain confounded. Engine version alone is not evidence of Fish policy version.

The first metadata lookup incorrectly assumed `job['group']`; the actual schema stores the UUID in `job['record']['group']`, while report groups are numeric dataset encodings. That lookup failed before producing a result. The corrected lookup maps each canonical job's row interval to the original `validation.npz` group array, rather than converting a UUID into an invented numeric code. The authoritative overall counts and V27 reports were not changed.

Inputs are the existing `.cambc/action-predictor/v7/jobs.json`, `.cambc/action-predictor/v4/validation.npz` group array and `experiments/v27/JP-results.json` saved `overall.group_net` tables. Their hashes/identities are already bound in the V27 evidence. No replay, reserved data, optimization, bot/runtime or PR action was used. This supplemental interpretation is later than the currently running V27 review and is outside that review's requested independent scope.
