# Fish predictor: fixed-benchmark development

**The proposed targets were not met consistently.**

No certified untouched Fish games remain. The original whole-group test partition was preserved, sealed during this development, and evaluated only after candidate locking. It was exposed in earlier work and is not a pristine final test.

Ten substantive fits: six development configurations and two additional seeds for each validation-selected GRU and stateless configuration. Seed results are sensitivity checks, not an ensemble. No test results select a configuration or seed.

## Experiment log

| Run | Configuration | Seed | Parameters | Best epoch | Validation macro F1 | Movement exact | Joint NLL |
|---|---|---:|---:|---:|---:|---:|---:|
| E01 | stateless-basic | 26 | 104384 | 8 | 0.423 | 18.54% | 1.483 |
| E02 | stateless-rich-spatial | 26 | 111648 | 10 | 0.426 | 32.22% | 1.161 |
| E03 | gru-rich-history4 | 26 | 104160 | 11 | 0.474 | 57.20% | 0.990 |
| E04 | gru-rich-history16 | 26 | 104160 | 10 | 0.521 | 56.86% | 1.013 |
| E05 | stateless-rich-rare-training | 26 | 111648 | 14 | 0.508 | 35.99% | 1.222 |
| E06 | gru-rich-rare-training | 26 | 104160 | 15 | 0.560 | 58.51% | 0.969 |
| E07 | gru-rich-rare-training | 27 | 104160 | 15 | 0.542 | 58.26% | 0.999 |
| E08 | gru-rich-rare-training | 28 | 104160 | 6 | 0.549 | 56.82% | 1.023 |
| E09 | stateless-rich-spatial | 27 | 111648 | 9 | 0.429 | 32.85% | 1.139 |
| E10 | stateless-rich-spatial | 28 | 111648 | 14 | 0.439 | 33.15% | 1.181 |

Checkpoint paths: `.cambc/action-predictor/v4/runs/<run>/model.pt`. Every run retains configuration, checkpoint hash, history and validation predictions. Earlier checkpoints are unchanged.

## Proposed targets: validation, all three GRU seeds

| Run | Macro F1 >= .65 | Movement gain >= 10 pp | Joint loss reduction >= 10% | No targeting drop > 2 pp |
|---|---:|---:|---:|---:|
| E06 | 0.560: FAIL | 3.30 pp: FAIL | 16.50%: PASS | FAIL |
| E07 | 0.542: FAIL | 3.05 pp: FAIL | 12.34%: PASS | FAIL |
| E08 | 0.549: FAIL | 1.61 pp: FAIL | 13.39%: PASS | FAIL |

Validation-selected references: `{"loss": "E02", "movement": "frequency-persistence", "targeting": {"attack": "frequency-lowest-health", "cast_0": "frequency-lowest-health", "cast_1": "E05"}}`.

Group-bootstrap confidence intervals and paired differences are in `validation-evaluation.json` and `test-evaluation.json`. Resampling unit is a whole match group, with 2,000 paired resamples. Only five validation and five test groups are available; seed variation is reported separately.

## Validation

| Run | Action accuracy | Macro F1 | Joint observable exact | Joint recorded-parameter exact, unknown shops fail | Joint NLL | Observable violations | Assessed commands |
|---|---:|---:|---:|---:|---:|---:|---:|
| E02 | 85.32% | 0.426 | 74.51% | 74.34% | 1.161 | 0.54% | 7582 |
| E05 | 79.43% | 0.508 | 67.40% | 67.17% | 1.222 | 4.58% | 6921 |
| E06 | 85.28% | 0.560 | 76.13% | 75.88% | 0.969 | 2.32% | 7060 |
| E07 | 84.59% | 0.542 | 75.78% | 75.51% | 0.999 | 1.97% | 7198 |
| E08 | 84.58% | 0.549 | 75.48% | 75.20% | 1.023 | 2.08% | 7114 |
| E09 | 85.34% | 0.429 | 74.17% | 74.01% | 1.139 | 0.69% | 7534 |
| E10 | 85.50% | 0.439 | 74.69% | 74.46% | 1.181 | 0.60% | 7539 |
| frequency-frequency | 28.37% | 0.032 | 28.37% | 28.37% | 2.839 | unassessed | 0 |
| frequency-legal-frequency | 28.37% | 0.032 | 28.37% | 28.37% | 2.923 | unassessed | 0 |
| frequency-lowest-health | 28.37% | 0.032 | 28.37% | 28.37% | 2.630 | unassessed | 0 |
| frequency-nearest | 28.37% | 0.032 | 28.37% | 28.37% | 2.711 | unassessed | 0 |
| frequency-persistence | 28.37% | 0.032 | 28.37% | 28.37% | 2.662 | unassessed | 0 |
| transition-frequency | 74.78% | 0.273 | 62.57% | 62.45% | 1.836 | 8.98% | 7241 |
| transition-legal-frequency | 74.78% | 0.273 | 63.52% | 63.40% | 1.920 | 3.70% | 7241 |
| transition-lowest-health | 74.78% | 0.273 | 63.16% | 63.04% | 1.627 | 8.98% | 7241 |
| transition-nearest | 74.78% | 0.273 | 67.37% | 67.26% | 1.708 | 3.70% | 7241 |
| transition-persistence | 74.78% | 0.273 | 68.45% | 68.34% | 1.659 | 3.70% | 7241 |

| GRU run | Macro F1, 95% group CI | Movement exact, 95% group CI | Movement gain, 95% paired CI | Joint-loss reduction, 95% paired CI |
|---|---:|---:|---:|---:|
| E06 | 0.531 to 0.570 | 55.9% to 61.2% | 1.7% to 5.2% | 12.4% to 20.2% |
| E07 | 0.527 to 0.558 | 56.2% to 60.4% | 1.8% to 4.3% | 9.5% to 15.5% |
| E08 | 0.512 to 0.562 | 55.0% to 58.2% | -0.3% to 3.1% | 7.5% to 17.3% |

| Run | Family | Conditional exact | Joint exact | Top 3 | Top 5 | Mean destination error | Support |
|---|---|---:|---:|---:|---:|---:|---:|
| E06 | move | 58.51% | 50.34% | 84.72% | 94.75% | 0.641 | 2362 |
| E06 | blocked | 14.55% | 0.00% | 27.27% | 41.82% | 2.245 | 110 |
| E06 | attack | 94.62% | 81.52% | 99.90% | 99.90% | 0.068 | 985 |
| E06 | cast_0 | 88.73% | 62.44% | 98.59% | 99.53% | 0.188 | 213 |
| E06 | cast_1 | 48.97% | 26.34% | 76.95% | 83.54% | 1.362 | 243 |
| E06 | ward | 20.54% | 4.46% | 33.04% | 51.79% | 2.143 | 112 |
| E06 | submit | 100.00% | 63.64% | 100.00% | 100.00% | 0.000 | 22 |
| E06 | altar | 100.00% | 0.00% | 100.00% | 100.00% | 0.000 | 2 |
| E06 | teleport | 0.00% | 0.00% | 0.00% | 0.00% | 3.000 | 2 |
| E06 | priority | unassessed | 1.91% | - | - | - | 576 |
| E06 | shop | unassessed | 0.00% | - | - | - | 43 |
| E07 | move | 58.26% | 49.87% | 84.93% | 94.12% | 0.646 | 2362 |
| E07 | blocked | 18.18% | 2.73% | 30.00% | 42.73% | 2.155 | 110 |
| E07 | attack | 95.33% | 84.16% | 99.90% | 99.90% | 0.072 | 985 |
| E07 | cast_0 | 86.85% | 56.34% | 98.59% | 100.00% | 0.272 | 213 |
| E07 | cast_1 | 51.85% | 30.86% | 74.07% | 81.89% | 1.379 | 243 |
| E07 | ward | 16.07% | 5.36% | 34.82% | 53.57% | 2.393 | 112 |
| E07 | submit | 100.00% | 81.82% | 100.00% | 100.00% | 0.000 | 22 |
| E07 | altar | 100.00% | 0.00% | 100.00% | 100.00% | 0.000 | 2 |
| E07 | teleport | 0.00% | 0.00% | 0.00% | 50.00% | 3.000 | 2 |
| E07 | priority | unassessed | 1.22% | - | - | - | 576 |
| E07 | shop | unassessed | 0.00% | - | - | - | 43 |
| E08 | move | 56.82% | 49.83% | 84.63% | 93.73% | 0.671 | 2362 |
| E08 | blocked | 11.82% | 1.82% | 21.82% | 36.36% | 2.227 | 110 |
| E08 | attack | 92.79% | 75.74% | 99.39% | 99.80% | 0.101 | 985 |
| E08 | cast_0 | 87.32% | 59.15% | 98.59% | 99.53% | 0.258 | 213 |
| E08 | cast_1 | 44.86% | 19.34% | 67.08% | 79.84% | 1.379 | 243 |
| E08 | ward | 19.64% | 1.79% | 34.82% | 48.21% | 2.098 | 112 |
| E08 | submit | 90.91% | 50.00% | 100.00% | 100.00% | 0.091 | 22 |
| E08 | altar | 50.00% | 0.00% | 100.00% | 100.00% | 0.500 | 2 |
| E08 | teleport | 0.00% | 0.00% | 50.00% | 50.00% | 4.000 | 2 |
| E08 | priority | unassessed | 0.87% | - | - | - | 576 |
| E08 | shop | unassessed | 0.00% | - | - | - | 43 |
| E02 | move | 32.22% | 29.76% | 72.86% | 91.62% | 1.179 | 2362 |
| E02 | blocked | 0.91% | 0.00% | 11.82% | 22.73% | 2.427 | 110 |
| E02 | attack | 90.46% | 77.56% | 99.39% | 99.90% | 0.173 | 985 |
| E02 | cast_0 | 84.51% | 58.69% | 95.77% | 98.59% | 0.380 | 213 |
| E02 | cast_1 | 38.27% | 5.35% | 58.85% | 71.60% | 1.733 | 243 |
| E02 | ward | 8.93% | 0.00% | 21.43% | 33.93% | 2.545 | 112 |
| E02 | submit | 90.91% | 0.00% | 95.45% | 100.00% | 0.136 | 22 |
| E02 | altar | 0.00% | 0.00% | 50.00% | 50.00% | 3.000 | 2 |
| E02 | teleport | 0.00% | 0.00% | 0.00% | 0.00% | 4.500 | 2 |
| E02 | priority | unassessed | 0.17% | - | - | - | 576 |
| E02 | shop | unassessed | 0.00% | - | - | - | 43 |
| E09 | move | 32.85% | 30.57% | 73.29% | 90.98% | 1.172 | 2362 |
| E09 | blocked | 5.45% | 0.00% | 11.82% | 22.73% | 2.091 | 110 |
| E09 | attack | 93.10% | 81.02% | 98.98% | 99.70% | 0.124 | 985 |
| E09 | cast_0 | 78.40% | 60.56% | 93.43% | 97.65% | 0.545 | 213 |
| E09 | cast_1 | 38.27% | 4.94% | 63.79% | 72.43% | 1.733 | 243 |
| E09 | ward | 8.93% | 0.00% | 15.18% | 23.21% | 2.741 | 112 |
| E09 | submit | 68.18% | 0.00% | 81.82% | 95.45% | 0.773 | 22 |
| E09 | altar | 0.00% | 0.00% | 50.00% | 50.00% | 5.000 | 2 |
| E09 | teleport | 0.00% | 0.00% | 0.00% | 0.00% | 4.500 | 2 |
| E09 | priority | unassessed | 0.00% | - | - | - | 576 |
| E09 | shop | unassessed | 0.00% | - | - | - | 43 |
| E10 | move | 33.15% | 31.03% | 72.73% | 91.36% | 1.163 | 2362 |
| E10 | blocked | 4.55% | 0.00% | 15.45% | 29.09% | 2.091 | 110 |
| E10 | attack | 91.98% | 76.24% | 98.88% | 99.59% | 0.143 | 985 |
| E10 | cast_0 | 83.57% | 61.03% | 94.84% | 99.06% | 0.371 | 213 |
| E10 | cast_1 | 42.39% | 5.76% | 67.08% | 74.49% | 1.691 | 243 |
| E10 | ward | 11.61% | 0.00% | 20.54% | 28.57% | 2.393 | 112 |
| E10 | submit | 90.91% | 0.00% | 100.00% | 100.00% | 0.091 | 22 |
| E10 | altar | 0.00% | 0.00% | 100.00% | 100.00% | 3.500 | 2 |
| E10 | teleport | 0.00% | 0.00% | 0.00% | 0.00% | 4.500 | 2 |
| E10 | priority | unassessed | 0.00% | - | - | - | 576 |
| E10 | shop | unassessed | 0.00% | - | - | - | 43 |
## Previously exposed final test

| Run | Action accuracy | Macro F1 | Joint observable exact | Joint recorded-parameter exact, unknown shops fail | Joint NLL | Observable violations | Assessed commands |
|---|---:|---:|---:|---:|---:|---:|---:|
| E02 | 86.54% | 0.425 | 74.95% | 74.70% | 1.152 | 0.54% | 8136 |
| E05 | 81.18% | 0.491 | 68.51% | 68.12% | 1.173 | 4.19% | 7375 |
| E06 | 85.59% | 0.549 | 76.65% | 76.26% | 0.945 | 2.14% | 7490 |
| E07 | 85.67% | 0.544 | 77.11% | 76.73% | 0.965 | 1.81% | 7627 |
| E08 | 85.97% | 0.534 | 77.03% | 76.65% | 0.965 | 1.51% | 7500 |
| E09 | 86.52% | 0.443 | 74.16% | 73.89% | 1.110 | 0.76% | 8015 |
| E10 | 87.09% | 0.440 | 75.39% | 75.11% | 1.090 | 0.39% | 8115 |
| frequency-frequency | 28.30% | 0.032 | 28.30% | 28.30% | 2.777 | unassessed | 0 |
| frequency-legal-frequency | 28.30% | 0.032 | 28.30% | 28.30% | 2.935 | unassessed | 0 |
| frequency-lowest-health | 28.30% | 0.032 | 28.30% | 28.30% | 2.610 | unassessed | 0 |
| frequency-nearest | 28.30% | 0.032 | 28.30% | 28.30% | 2.685 | unassessed | 0 |
| frequency-persistence | 28.30% | 0.032 | 28.30% | 28.30% | 2.594 | unassessed | 0 |
| transition-frequency | 76.67% | 0.286 | 62.67% | 62.46% | 1.729 | 8.70% | 7839 |
| transition-legal-frequency | 76.67% | 0.286 | 63.73% | 63.52% | 1.887 | 2.35% | 7839 |
| transition-lowest-health | 76.67% | 0.286 | 63.17% | 62.96% | 1.562 | 8.70% | 7839 |
| transition-nearest | 76.67% | 0.286 | 68.81% | 68.60% | 1.637 | 2.35% | 7839 |
| transition-persistence | 76.67% | 0.286 | 70.91% | 70.70% | 1.546 | 2.35% | 7839 |

| GRU run | Macro F1, 95% group CI | Movement exact, 95% group CI | Movement gain, 95% paired CI | Joint-loss reduction, 95% paired CI |
|---|---:|---:|---:|---:|
| E06 | 0.522 to 0.571 | 58.0% to 65.9% | -0.5% to 3.4% | 13.0% to 25.0% |
| E07 | 0.529 to 0.560 | 57.9% to 65.1% | -1.3% to 3.3% | 11.5% to 15.2% |
| E08 | 0.518 to 0.549 | 57.5% to 64.8% | -1.2% to 2.6% | 9.8% to 13.2% |

| Run | Family | Conditional exact | Joint exact | Top 3 | Top 5 | Mean destination error | Support |
|---|---|---:|---:|---:|---:|---:|---:|
| E06 | move | 61.95% | 50.61% | 87.33% | 96.17% | 0.586 | 2691 |
| E06 | blocked | 17.28% | 4.94% | 38.27% | 50.62% | 2.049 | 81 |
| E06 | attack | 95.32% | 76.69% | 99.48% | 99.79% | 0.073 | 961 |
| E06 | cast_0 | 92.93% | 54.35% | 98.37% | 98.37% | 0.168 | 184 |
| E06 | cast_1 | 50.59% | 27.27% | 71.15% | 81.42% | 1.273 | 253 |
| E06 | ward | 22.13% | 7.38% | 43.44% | 63.93% | 2.213 | 122 |
| E06 | submit | 100.00% | 68.75% | 100.00% | 100.00% | 0.000 | 16 |
| E06 | altar | 100.00% | 0.00% | 100.00% | 100.00% | 0.000 | 3 |
| E06 | teleport | 0.00% | 0.00% | 0.00% | 0.00% | 5.000 | 2 |
| E06 | priority | unassessed | 1.14% | - | - | - | 615 |
| E06 | shop | unassessed | 0.00% | - | - | - | 62 |
| E07 | move | 61.43% | 51.58% | 87.03% | 95.76% | 0.596 | 2691 |
| E07 | blocked | 14.81% | 3.70% | 38.27% | 54.32% | 2.185 | 81 |
| E07 | attack | 95.63% | 82.62% | 99.38% | 99.79% | 0.077 | 961 |
| E07 | cast_0 | 92.39% | 56.52% | 98.37% | 99.46% | 0.245 | 184 |
| E07 | cast_1 | 47.43% | 20.55% | 73.52% | 81.42% | 1.423 | 253 |
| E07 | ward | 23.77% | 4.92% | 45.08% | 61.48% | 2.066 | 122 |
| E07 | submit | 100.00% | 75.00% | 100.00% | 100.00% | 0.000 | 16 |
| E07 | altar | 100.00% | 33.33% | 100.00% | 100.00% | 0.000 | 3 |
| E07 | teleport | 50.00% | 50.00% | 50.00% | 50.00% | 2.000 | 2 |
| E07 | priority | unassessed | 1.46% | - | - | - | 615 |
| E07 | shop | unassessed | 0.00% | - | - | - | 62 |
| E08 | move | 61.06% | 50.91% | 86.73% | 95.95% | 0.603 | 2691 |
| E08 | blocked | 14.81% | 6.17% | 29.63% | 45.68% | 1.975 | 81 |
| E08 | attack | 96.05% | 74.40% | 99.69% | 100.00% | 0.059 | 961 |
| E08 | cast_0 | 91.30% | 57.61% | 98.37% | 100.00% | 0.283 | 184 |
| E08 | cast_1 | 36.76% | 12.65% | 62.85% | 74.70% | 1.625 | 253 |
| E08 | ward | 21.31% | 3.28% | 40.98% | 50.00% | 2.098 | 122 |
| E08 | submit | 100.00% | 31.25% | 100.00% | 100.00% | 0.000 | 16 |
| E08 | altar | 100.00% | 0.00% | 100.00% | 100.00% | 0.000 | 3 |
| E08 | teleport | 0.00% | 0.00% | 50.00% | 50.00% | 3.000 | 2 |
| E08 | priority | unassessed | 0.98% | - | - | - | 615 |
| E08 | shop | unassessed | 0.00% | - | - | - | 62 |
| E02 | move | 30.62% | 28.13% | 71.46% | 93.61% | 1.198 | 2691 |
| E02 | blocked | 6.17% | 0.00% | 18.52% | 24.69% | 2.321 | 81 |
| E02 | attack | 92.92% | 72.94% | 99.27% | 99.79% | 0.146 | 961 |
| E02 | cast_0 | 85.33% | 54.35% | 94.02% | 98.37% | 0.408 | 184 |
| E02 | cast_1 | 39.53% | 3.16% | 58.10% | 69.57% | 1.589 | 253 |
| E02 | ward | 0.00% | 0.00% | 19.67% | 32.79% | 2.811 | 122 |
| E02 | submit | 81.25% | 0.00% | 93.75% | 100.00% | 0.438 | 16 |
| E02 | altar | 0.00% | 0.00% | 0.00% | 0.00% | 2.000 | 3 |
| E02 | teleport | 0.00% | 0.00% | 0.00% | 0.00% | 4.500 | 2 |
| E02 | priority | unassessed | 0.00% | - | - | - | 615 |
| E02 | shop | unassessed | 0.00% | - | - | - | 62 |
| E09 | move | 30.55% | 28.24% | 70.75% | 92.98% | 1.213 | 2691 |
| E09 | blocked | 7.41% | 0.00% | 17.28% | 29.63% | 2.012 | 81 |
| E09 | attack | 92.51% | 75.96% | 98.96% | 99.90% | 0.143 | 961 |
| E09 | cast_0 | 78.80% | 52.17% | 93.48% | 98.91% | 0.663 | 184 |
| E09 | cast_1 | 35.57% | 8.30% | 58.10% | 67.19% | 1.640 | 253 |
| E09 | ward | 9.02% | 0.00% | 18.03% | 24.59% | 2.934 | 122 |
| E09 | submit | 56.25% | 0.00% | 93.75% | 93.75% | 0.562 | 16 |
| E09 | altar | 0.00% | 0.00% | 0.00% | 0.00% | 2.333 | 3 |
| E09 | teleport | 0.00% | 0.00% | 0.00% | 0.00% | 5.000 | 2 |
| E09 | priority | unassessed | 0.00% | - | - | - | 615 |
| E09 | shop | unassessed | 0.00% | - | - | - | 62 |
| E10 | move | 31.18% | 29.32% | 71.20% | 93.05% | 1.194 | 2691 |
| E10 | blocked | 8.64% | 0.00% | 16.05% | 25.93% | 2.062 | 81 |
| E10 | attack | 93.76% | 74.71% | 99.48% | 99.90% | 0.116 | 961 |
| E10 | cast_0 | 87.50% | 53.26% | 96.20% | 98.37% | 0.342 | 184 |
| E10 | cast_1 | 37.55% | 5.93% | 60.08% | 71.94% | 1.719 | 253 |
| E10 | ward | 5.74% | 0.00% | 13.11% | 26.23% | 2.803 | 122 |
| E10 | submit | 93.75% | 0.00% | 93.75% | 100.00% | 0.062 | 16 |
| E10 | altar | 66.67% | 0.00% | 66.67% | 100.00% | 1.333 | 3 |
| E10 | teleport | 0.00% | 0.00% | 0.00% | 0.00% | 4.500 | 2 |
| E10 | priority | unassessed | 0.00% | - | - | - | 615 |
| E10 | shop | unassessed | 0.00% | - | - | - | 62 |

## Per-action detail: validation-selected GRU, final exposed test

| Action | Precision | Recall | F1 | Support |
|---|---:|---:|---:|---:|
| <unknown> | 0.000 | 0.000 | 0.000 | 0 |
| altar | 0.000 | 0.000 | 0.000 | 3 |
| attack | 0.794 | 0.798 | 0.796 | 961 |
| blocked | 0.311 | 0.395 | 0.348 | 81 |
| cancel | 0.953 | 0.988 | 0.970 | 2860 |
| cast_0 | 0.572 | 0.603 | 0.587 | 184 |
| cast_1 | 0.291 | 0.569 | 0.385 | 253 |
| end | 0.983 | 0.962 | 0.972 | 4416 |
| move | 0.909 | 0.803 | 0.853 | 2691 |
| priority | 0.600 | 0.698 | 0.645 | 615 |
| recall | 0.912 | 0.758 | 0.828 | 3338 |
| shop | 0.803 | 0.984 | 0.884 | 62 |
| submit | 0.136 | 0.688 | 0.227 | 16 |
| teleport | 0.027 | 1.000 | 0.052 | 2 |
| ward | 0.087 | 0.303 | 0.136 | 122 |

## Data quality, information boundary and remaining limits

- Original 170 replay payloads are unique and group assignments are unchanged. Supplemental snapshots are queried at the exact personal PRE cursor; original shared fields are checked against prior evidence. History consists of strictly earlier actions by the same actor, including roots between sampled turns. Utility `(0,0)` coordinates are not treated as genuine prior locations.
- Training-only augmentation adds 37,140 recorded actions in 7,669 complete rare-action turns. It retains all original sampled training actions, deduplicates action IDs and changes neither validation nor test. Shop/ward/blocked/submit/altar/teleport support improves, but selection bias in augmented training and unknown private policy state remain limitations.
- The parameter head uses recorded destination/aim cells, plus a discrete logistic model of exact priority integers. Original attack/cast entity IDs are not stored. Original shop item/count can be unidentifiable; immediate inventory deltas are retained as diagnostic labels only. Joint recorded-parameter scoring counts unsupported shop arguments as failures. Full original API-command accuracy is unassessed; the legacy JSON key `strict_full_command_accuracy` names a recorded-parameter score, not proof of original ID/argument recovery.
- Joint NLL is the mean partially observed action + required coordinate + required priority negative log likelihood. It is not a likelihood for missing original shop arguments. Conditional parameter accuracy uses the true family; joint accuracy additionally requires the predicted family. Outside-window/missing-position labels remain in loss and count as exact-command failures.
- PRE movement and target-geometry masks are inputs/constraints, not future labels. A fixed 1e-4 full-support mixture keeps contradictory recorded labels in the likelihood instead of filtering them. Masks do not establish full engine legality.
- Reported illegal-action information is an observable violation rate with an assessed denominator: exact personal movement-mask violations plus partial resource/readiness checks. **Full engine illegal-action rate is unassessed**, not zero. Predicted blocked attempts are forecasts of recorded failed actions and naturally contribute violations.
- Destination error is Chebyshev error in cells, with a fixed 16-cell penalty for undecodable forecasts. Raw decoded-label error and coverage are also retained in JSON. Top-k movements include all movement rows, and joint top-3 also requires the correct action type.
- These are personal-Fish-view, teacher-forced replay forecasts. Complete own history, gold and private resources are not generally available to an opposing bot. Historical engine 2/3 evidence does not establish deployment compatibility or playing strength.
- No matches, alternate-action simulations, deployments or PRs were created. No strategy labels or strategy-similarity percentage are used.

Machine-readable benchmark, design amendments, data receipts, source pins, selection locks and all metrics remain next to this report. The fixed proposed targets were not weakened.
