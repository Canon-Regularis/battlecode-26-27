# PD02: fixed-weight changes are co-adapted; control failure is not confined to bias

All eight combinations of warm P05 and final PC01 parameter blocks are evaluated on the original 128 fitted rows and both unchanged 128-row controls. This is a saved-checkpoint readout intervention, with no optimizer, upstream neural recomputation, branch selection or policy replacement. The original fitted subset is in-sample for both PC00 and PC01; it is not the full 5,876-row PC01 fit population.

The three bits identify updated **context weights**, **explicit priority-input weights**, and **bias**, respectively. All categorical logits, fallback gate, and logistic location/scale participate. Exact int64 analytic anchors and input availability masks are retained in every branch. Explicit-input weight replacement therefore does not remove all priority information.

| Updated blocks | Original fit exact | Same-group control exact | Disjoint-group control exact | Fit NLL | Same-group NLL | Disjoint-group NLL |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 000: warm endpoint | 34 | 25 | 28 | 2.894 | 3.148 | 3.052 |
| 001: bias | 22 | 17 | 18 | 3.483 | 3.798 | 3.721 |
| 010: explicit inputs | 17 | 10 | 8 | 4.490 | 6.731 | 7.726 |
| 011: explicit inputs + bias | 18 | 5 | 5 | 5.008 | 7.385 | 8.362 |
| 100: context | 49 | 20 | 19 | 2.811 | 8.452 | 8.031 |
| 101: context + bias | 62 | 21 | 26 | 2.213 | 7.979 | 7.534 |
| 110: context + explicit inputs | 90 | 17 | 17 | 1.042 | 9.280 | 9.076 |
| 111: PC01 endpoint | 102 | 13 | 16 | .702 | 8.920 | 8.773 |

Each exact-count denominator is 128. Both endpoint branches reproduce every saved prediction array exactly, including probability-based diagnostics. All intermediate branches and prediction archives are retained.

The fit improvement depends on combined parameter changes: updated explicit-input weights alone worsen the fitted subset, while adding them to the updated context and bias improves exactness from 62 to 102. This establishes dependence through the defined fixed-weight combinations; it is not evidence that a retrained model needs this exact package.

Control NLL worsens when any one updated block is substituted alone. Reverting final PC01's explicit-input weights raises control exact counts from 13/16 to 21/26, while reducing fitted-subset exactness from 102 to 62. The control loss therefore is not confined to a changed global bias. However none of these hybrids surpasses warm P05 on either control's exact count.

These are deliberately mixed parameter settings that were not trained together. Effects interact through normalization, duplicate-point aggregation and fallback parameters. They do not isolate causes along the training trajectory or prove that the observation context, explicit inputs, bias, or the underlying information is defective. No preferred hybrid is selected or promoted, and no architecture change follows automatically.

Controls were previously seen by the frozen encoder and warm head and are held out only from new optimization. This remains conditional integer evaluation with the priority action supplied. It is not complete-command improvement or untouched group generalization. Both reserved partitions remain sealed; no DEV payloads, matches, downloads or bot/runtime work are used.

Reproduce once into absent immutable destinations: `.venv-action-predictor/Scripts/python.exe -m tools.action_predictor.priority_diagnosis.blocks`. PC01's independent review was already running when this separate later diagnostic was performed; do not claim its coverage unless explicitly stated by that reviewer.
