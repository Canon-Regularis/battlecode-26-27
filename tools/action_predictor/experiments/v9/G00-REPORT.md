# G00: movement mixture study

Selected epoch1 from7;11,844 optimizer calls,11,844 actual updates. Nominal trainable212,447; frozen mixture-model parameters108,546. Separate unchanged P05 priority head also remains part of the complete predictor.

| Model/split | Strict joint | Macro F1 | Observed joint NLL |
|---|---:|---:|---:|
| M01 dev | 79.0290% | 0.63239 | 0.872799 |
| P05 dev | 79.4515% | 0.63239 | 0.730903 |
| G00 train | 76.2136% | 0.77245 | 0.699603 |
| G00 dev | 79.7147% | 0.63239 | 0.726556 |

| Category | Joint correct/support | Joint accuracy | True-family parameter exact |
|---|---:|---:|---:|
| altar | 0/2 | 0.00% | 100.00% |
| attack | 874/985 | 88.73% | 95.74% |
| blocked | 8/110 | 7.27% | 21.82% |
| cancel | 2535/2589 | 97.91% | — |
| cast_0 | 154/213 | 72.30% | 90.61% |
| cast_1 | 95/243 | 39.09% | 60.08% |
| end | 3957/4096 | 96.61% | — |
| move | 1318/2362 | 55.80% | 60.71% |
| priority | 71/576 | 12.33% | 18.92% |
| recall | 2472/3084 | 80.16% | — |
| shop | 0/43 | 0.00% | unassessed |
| submit | 19/22 | 86.36% | 100.00% |
| teleport | 0/2 | 0.00% | 0.00% |
| ward | 7/112 | 6.25% | 21.43% |

Parameter accuracy supplies the true family over all recorded rows of that category. Joint requires the predicted type and every exact required argument. Missing purchases remain unassessed strict failures; no-required-parameter rows have no parameter metric. Per-action type PRF and false positives remain in the CSV; type confusion is frozen with the classifier.

Failure accounting: {'wrong_types': 1627, 'wrong_parameters_after_correct_type': 1260, 'correct_type_missing_shop_arguments': 42, 'strict_failures': 2929}.

Prospective guards: {'P05': {'no_strict_regression': True, 'continuation_exact_drop_at_most_half_point': True, 'direction_change_joint_not_worse': True, 'attack_cast_parameters_and_joint_unchanged': True, 'lower_joint_nll': True}}. Ward protection: {'ward_type_correct': 35, 'ward_joint_correct': 7, 'ward_type_FP': 282, 'recall_to_ward': 257, 'ward_type_precision': 0.11041009463722397, 'passed': True}.

Gate diagnostics: {'train': {'supervised_support': 71824, 'confusion_change_continue': [[25947, 9509], [6699, 29669]], 'accuracy': 0.7743372688794832, 'missing_move_history': 121, 'scope': 'True move family conditional gate evaluation on every eligible recorded move; predicted gate from causal inputs, no oracle routing.'}, 'validation': {'supervised_support': 2356, 'confusion_change_continue': [[816, 342], [242, 956]], 'accuracy': 0.7521222410865874, 'missing_move_history': 6, 'scope': 'True move family conditional gate evaluation on every eligible recorded move; predicted gate from causal inputs, no oracle routing.'}}.

Original targets: {'macro_f1_at_least_065': False, 'movement_gain_vs_simple': 0.0550381033022862, 'movement_gain_at_least_ten_points': False, 'loss_reduction_vs_P05': 0.005948286983705309, 'all_category_90_certified': False, 'three_seed_confirmed': False}. No certified replacement; both reserved75-game partitions remain sealed.

Direction contexts and train/development results are complete in the immutable report. Any improvements remain conditional on one warm-start seed and five reused development groups. G00 is an unrestricted control, not evidence that direction specialization helps. G01 must compare directly with G00 after the fresh completed-G00 review.
