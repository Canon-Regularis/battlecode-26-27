# E01: full predictor pilot

Selected epoch 5 by the frozen observed-joint-NLL rule; 11 completed epochs, 18,612 optimizer steps. 233,566 trainable and 312,234 frozen parameters. No reserved partitions opened.

| Model / split | Strict complete-command accuracy | Macro F1 | Observed joint NLL |
|---|---:|---:|---:|
| M01 dev | 79.0290% | 0.63239 | 0.872799 |
| P05 dev | 79.4515% | 0.63239 | 0.730903 |
| E01 train | 76.7188% | 0.79152 | 0.677367 |
| E01 dev | 79.2091% | 0.63357 | 0.728824 |

| Category | Joint correct / support | Joint accuracy | True-family parameter exact | Type P / R / F1 |
|---|---:|---:|---:|---|
| altar | 0/2 | 0.00% | 100.00% | 0.00% / 0.00% / 0.00% |
| attack | 884/985 | 89.75% | 95.74% | 88.47% / 93.50% / 90.92% |
| blocked | 6/110 | 5.45% | 17.27% | 32.33% / 39.09% / 35.39% |
| cancel | 2542/2589 | 98.18% | — | 93.22% / 98.18% / 95.64% |
| cast_0 | 152/213 | 71.36% | 90.61% | 87.96% / 78.87% / 83.17% |
| cast_1 | 106/243 | 43.62% | 60.08% | 46.94% / 69.55% / 56.05% |
| end | 3930/4096 | 95.95% | — | 98.50% / 95.95% / 97.21% |
| move | 1275/2362 | 53.98% | 59.70% | 94.17% / 88.82% / 91.42% |
| priority | 69/576 | 11.98% | 18.92% | 70.02% / 64.06% / 66.91% |
| recall | 2445/3084 | 79.28% | — | 91.47% / 79.28% / 84.94% |
| shop | 0/43 | 0.00% | unassessed | 84.31% / 100.00% / 91.49% |
| submit | 19/22 | 86.36% | 100.00% | 28.36% / 86.36% / 42.70% |
| teleport | 0/2 | 0.00% | 0.00% | 22.22% / 100.00% / 36.36% |
| ward | 9/112 | 8.04% | 21.43% | 9.63% / 32.14% / 14.81% |

True-family parameter accuracy uses every recorded row in the category, including misclassified rows. Joint correctness requires the predicted type and all exact required parameters. Type PRF describes action names; the CSV also reports complete-command PRF and false positives. Runtime coordinates route by the predicted family; correctly typed spatial rows are checked against that route.

Movement contexts (recorded direction labels are evaluation evidence, never inference inputs):
- TRAIN continuing: support 36368, destination exact 90.37%, joint 82.56%.
- TRAIN direction_change: support 35456, destination exact 38.58%, joint 33.36%.
- TRAIN no_previous: support 121, destination exact 71.90%, joint 35.54%.
- DEV continuing: support 1198, destination exact 88.65%, joint 82.22%.
- DEV direction_change: support 1158, destination exact 29.71%, joint 24.87%.
- DEV no_previous: support 6, destination exact 66.67%, joint 33.33%.

Priority value distributions are frozen P05; new action decisions can change priority joint correctness. Rare/unseen strata, train versus development, losses, top-k movement, destination errors and targeting deltas are retained in the immutable fit report. All 43 shop rows remain unassessed strict failures. Two altar/teleport examples cannot certify reliability.

Failure accounting: {'wrong_types': 1654, 'wrong_parameters_after_correct_type': 1305, 'correctly_typed_shops_unassessed': 43, 'strict_failures': 3002}.

Regression checks: {'no_overall_joint_regression': False, 'macro_drop_at_most_one_point': True, 'attack_ability_joint_drop_at_most_two_points': True, 'attack_ability_parameter_guard': True, 'ward_type_correct_at_least_35': True, 'ward_joint_at_least_seven': True}.

Paired whole-group intervals: {'joint_accuracy_gain': {'low': -0.006926952141057985, 'high': 0.0028032271297688816, 'valid_draws': 2000}, 'macro_f1_gain': {'low': -0.014854575219507282, 'high': 0.018507162217615725, 'valid_draws': 2000}, 'loss_reduction': {'low': -0.009444711901825942, 'high': 0.017590696755414137, 'valid_draws': 2000}, 'move_joint_gain': {'low': -0.008311295806573415, 'high': -0.0013966480446927498, 'valid_draws': 2000}, 'scope': 'Five reused groups; pointwise conditional on checkpoint selection, not independent3seed/untouched confirmation'}. Five reused groups, conditional on checkpoint selection; no independent-seed or untouched-test confirmation.

E00 is redesigned zero-entity control; E01 is the matched input treatment. Improvements versus M01/P05 bundle classifier/GRU/movement retraining, separate fusions and common recovered priority channels. Entity attribution requires E01 minus E00. One head/representation warm-start seed is not three independent full-model seeds.

The 90% exact joint objective in every adequately supported category remains unmet. No below-target candidate is promoted as a certified replacement. Preserve P05/M01 and all failed studies.
