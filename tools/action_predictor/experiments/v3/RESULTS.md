# Frozen-test prediction results

All action metrics use the same 15,604 actions from 25 games in five frozen match groups.
Validation selected checkpoints. Counts and metrics weight sampled actions equally.

| Model | Accuracy | Macro F1 |
|---|---:|---:|
| frozen_gru | 88.27% | 46.93% |
| stateless_mlp | 86.14% | 43.07% |
| most_common | 28.30% | 3.15% |
| previous_action_only | 76.65% | 28.60% |

## frozen_gru: per-action metrics

| Action | Precision | Recall | F1 | Support |
|---|---:|---:|---:|---:|
| <unknown> | 0.000 | 0.000 | 0.000 | 0 |
| altar | 0.000 | 0.000 | 0.000 | 3 |
| attack | 0.773 | 0.809 | 0.790 | 961 |
| blocked | 0.000 | 0.000 | 0.000 | 81 |
| cancel | 0.935 | 0.980 | 0.957 | 2860 |
| cast_0 | 0.676 | 0.668 | 0.672 | 184 |
| cast_1 | 0.464 | 0.257 | 0.331 | 253 |
| end | 0.969 | 0.940 | 0.954 | 4416 |
| move | 0.869 | 0.909 | 0.888 | 2691 |
| priority | 0.623 | 0.421 | 0.502 | 615 |
| recall | 0.840 | 0.934 | 0.884 | 3338 |
| shop | 0.642 | 0.548 | 0.591 | 62 |
| submit | 0.000 | 0.000 | 0.000 | 16 |
| teleport | 0.000 | 0.000 | 0.000 | 2 |
| ward | 0.000 | 0.000 | 0.000 | 122 |

## stateless_mlp: per-action metrics

| Action | Precision | Recall | F1 | Support |
|---|---:|---:|---:|---:|
| <unknown> | 0.000 | 0.000 | 0.000 | 0 |
| altar | 0.000 | 0.000 | 0.000 | 3 |
| attack | 0.759 | 0.759 | 0.759 | 961 |
| blocked | 0.000 | 0.000 | 0.000 | 81 |
| cancel | 0.920 | 0.988 | 0.953 | 2860 |
| cast_0 | 0.645 | 0.543 | 0.590 | 184 |
| cast_1 | 0.477 | 0.209 | 0.291 | 253 |
| end | 0.969 | 0.930 | 0.949 | 4416 |
| move | 0.849 | 0.899 | 0.873 | 2691 |
| priority | 0.365 | 0.094 | 0.150 | 615 |
| recall | 0.779 | 0.933 | 0.849 | 3338 |
| shop | 0.638 | 0.597 | 0.617 | 62 |
| submit | 0.000 | 0.000 | 0.000 | 16 |
| teleport | 0.000 | 0.000 | 0.000 | 2 |
| ward | 0.000 | 0.000 | 0.000 | 122 |

## most_common: per-action metrics

| Action | Precision | Recall | F1 | Support |
|---|---:|---:|---:|---:|
| <unknown> | 0.000 | 0.000 | 0.000 | 0 |
| altar | 0.000 | 0.000 | 0.000 | 3 |
| attack | 0.000 | 0.000 | 0.000 | 961 |
| blocked | 0.000 | 0.000 | 0.000 | 81 |
| cancel | 0.000 | 0.000 | 0.000 | 2860 |
| cast_0 | 0.000 | 0.000 | 0.000 | 184 |
| cast_1 | 0.000 | 0.000 | 0.000 | 253 |
| end | 0.283 | 1.000 | 0.441 | 4416 |
| move | 0.000 | 0.000 | 0.000 | 2691 |
| priority | 0.000 | 0.000 | 0.000 | 615 |
| recall | 0.000 | 0.000 | 0.000 | 3338 |
| shop | 0.000 | 0.000 | 0.000 | 62 |
| submit | 0.000 | 0.000 | 0.000 | 16 |
| teleport | 0.000 | 0.000 | 0.000 | 2 |
| ward | 0.000 | 0.000 | 0.000 | 122 |

## Recorded destination and target coordinates

These scores condition on the recorded action family. They are not joint full-action accuracy.
Attack and unit-cast coordinates require visible compatible occupants; ground casts use recorded aim cells.
Original target entity IDs are unavailable; unique-occupant mapping is a diagnostic, not ID ground truth.

| Model | Family | Exact coordinate | Top 3 | Mean Chebyshev error | Support | Multi-candidate exact | Multi-candidate support |
|---|---|---:|---:|---:|---:|---:|---:|
| E2-gru-targets | move | 19.40% | 42.92% | 1.454 | 2691 | 19.40% | 2691 |
| E2-gru-targets | attack | 95.51% | 99.48% | 0.066 | 958 | 94.45% | 775 |
| E2-gru-targets | cast_0 | 90.76% | 98.37% | 0.326 | 184 | 60.47% | 43 |
| E2-gru-targets | cast_1 | 33.60% | 42.69% | 2.095 | 253 | 25.66% | 226 |
| E3-stateless-targets | move | 23.86% | 50.58% | 1.329 | 2691 | 23.86% | 2691 |
| E3-stateless-targets | attack | 94.05% | 99.48% | 0.113 | 958 | 92.65% | 775 |
| E3-stateless-targets | cast_0 | 91.85% | 97.28% | 0.288 | 184 | 65.12% | 43 |
| E3-stateless-targets | cast_1 | 21.74% | 29.25% | 1.672 | 253 | 12.39% | 226 |
| train_most_common_valid_offset | move | 13.45% | 49.57% | 1.579 | 2691 | 13.45% | 2691 |
| train_most_common_valid_offset | attack | 88.00% | 97.91% | 0.266 | 958 | 85.16% | 775 |
| train_most_common_valid_offset | cast_0 | 90.76% | 97.83% | 0.326 | 184 | 60.47% | 43 |
| train_most_common_valid_offset | cast_1 | 20.55% | 41.50% | 1.561 | 253 | 11.06% | 226 |

Joint action-type and coordinate accuracy on the same 4,086 supported target actions:

- E2-gru-targets: 33.16%.
- E3-stateless-targets: 33.55%.

## Coverage and limits

Frozen-test target evidence counts: `{"attack/no_visible_compatible_target": 3, "attack/supported": 958, "attack/unique_visible_entity_at_aim": 958, "cast_0/supported": 184, "cast_0/unique_visible_entity_at_aim": 184, "cast_1/coordinate_only": 188, "cast_1/supported": 253, "cast_1/unique_visible_entity_at_aim": 65, "move/coordinate_only": 2691, "move/supported": 2691}`.

The fixed +/-8 coordinate window covers every supported test move/cast. Three attacks lack a visible compatible target and are excluded with an explicit reason.
Self-only casts and actions with one candidate can be trivial; the multi-candidate columns expose that effect.
No terrain/path legality is reconstructed. Hidden state resets at each sampled turn. This is historical engine 2/3 replay prediction, not a strategy-similarity percentage or a playing-strength result.

Confusion matrices are in `*-confusion.csv` (actual rows, predicted columns); exact counts and every model's per-action metrics are also in `final-test.json`.
