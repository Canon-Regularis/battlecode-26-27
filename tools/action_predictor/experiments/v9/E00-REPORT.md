# E00: full predictor pilot

Selected epoch 8 by the frozen observed-joint-NLL rule; 14 completed epochs, 23,688 optimizer steps. 233,566 trainable and 312,234 frozen parameters. No reserved partitions opened.

| Model / split | Strict complete-command accuracy | Macro F1 | Observed joint NLL |
|---|---:|---:|---:|
| M01 dev | 79.0290% | 0.63239 | 0.872799 |
| P05 dev | 79.4515% | 0.63239 | 0.730903 |
| E00 train | 77.1432% | 0.81729 | 0.654296 |
| E00 dev | 79.3753% | 0.62910 | 0.726085 |

| Category | Joint correct / support | Joint accuracy | True-family parameter exact | Type P / R / F1 |
|---|---:|---:|---:|---|
| altar | 0/2 | 0.00% | 100.00% | 0.00% / 0.00% / 0.00% |
| attack | 894/985 | 90.76% | 95.74% | 87.15% / 94.31% / 90.59% |
| blocked | 7/110 | 6.36% | 24.55% | 33.33% / 37.27% / 35.19% |
| cancel | 2549/2589 | 98.46% | — | 93.34% / 98.46% / 95.83% |
| cast_0 | 163/213 | 76.53% | 90.61% | 80.80% / 84.98% / 82.84% |
| cast_1 | 94/243 | 38.68% | 60.08% | 49.38% / 65.84% / 56.44% |
| end | 3924/4096 | 95.80% | — | 98.54% / 95.80% / 97.15% |
| move | 1282/2362 | 54.28% | 59.86% | 94.30% / 89.03% / 91.59% |
| priority | 70/576 | 12.15% | 18.92% | 70.77% / 63.89% / 67.15% |
| recall | 2450/3084 | 79.44% | — | 91.97% / 79.44% / 85.25% |
| shop | 0/43 | 0.00% | unassessed | 78.18% / 100.00% / 87.76% |
| submit | 21/22 | 95.45% | 100.00% | 36.84% / 95.45% / 53.16% |
| teleport | 0/2 | 0.00% | 0.00% | 14.29% / 50.00% / 22.22% |
| ward | 7/112 | 6.25% | 21.43% | 9.95% / 35.71% / 15.56% |

True-family parameter accuracy uses every recorded row in the category, including misclassified rows. Joint correctness requires the predicted type and all exact required parameters. Type PRF describes action names; the CSV also reports complete-command PRF and false positives. Runtime coordinates route by the predicted family; correctly typed spatial rows are checked against that route.

Movement contexts (recorded direction labels are evaluation evidence, never inference inputs):
- TRAIN continuing: support 36368, destination exact 92.28%, joint 85.32%.
- TRAIN direction_change: support 35456, destination exact 38.59%, joint 33.90%.
- TRAIN no_previous: support 121, destination exact 76.03%, joint 49.59%.
- DEV continuing: support 1198, destination exact 90.90%, joint 84.06%.
- DEV direction_change: support 1158, destination exact 27.81%, joint 23.58%.
- DEV no_previous: support 6, destination exact 50.00%, joint 33.33%.

Priority value distributions are frozen P05; new action decisions can change priority joint correctness. Rare/unseen strata, train versus development, losses, top-k movement, destination errors and targeting deltas are retained in the immutable fit report. All 43 shop rows remain unassessed strict failures. Two altar/teleport examples cannot certify reliability.

Failure accounting: {'wrong_types': 1629, 'wrong_parameters_after_correct_type': 1306, 'correctly_typed_shops_unassessed': 43, 'strict_failures': 2978}.

Regression checks: {'no_overall_joint_regression': False, 'macro_drop_at_most_one_point': True, 'attack_ability_joint_drop_at_most_two_points': True, 'attack_ability_parameter_guard': True, 'ward_type_correct_at_least_35': True, 'ward_joint_at_least_seven': True}.

Paired whole-group intervals: {'joint_accuracy_gain': {'low': -0.00596449371973895, 'high': 0.005674825652946747, 'valid_draws': 2000}, 'macro_f1_gain': {'low': -0.01798401944563066, 'high': 0.02005691819501672, 'valid_draws': 2000}, 'loss_reduction': {'low': -0.0034800878790113288, 'high': 0.016899615183485706, 'valid_draws': 2000}, 'move_joint_gain': {'low': -0.011853022520742829, 'high': 0.011170688114387817, 'valid_draws': 2000}, 'scope': 'Five reused groups; pointwise conditional on checkpoint selection, not independent3seed/untouched confirmation'}. Five reused groups, conditional on checkpoint selection; no independent-seed or untouched-test confirmation.

E00 is redesigned zero-entity control; E01 is the matched input treatment. Improvements versus M01/P05 bundle classifier/GRU/movement retraining, separate fusions and common recovered priority channels. Entity attribution requires E01 minus E00. One head/representation warm-start seed is not three independent full-model seeds.

The 90% exact joint objective in every adequately supported category remains unmet. No below-target candidate is promoted as a certified replacement. Preserve P05/M01 and all failed studies.
