# V65 - hard-choice margin edits

The alternative readout loss failed to produce a qualifying planner. It selected a goal on only **0-1 of 2,941** candidate-available fitting-validation queries at the trained checkpoints. That recovers the direct predictor's **1,237/1,997** fitting-validation moves, but fails the predeclared minimum 10% goal-activity requirement. Disabling planning is not counted as achieving the user's movement goal.

Selection retained epoch zero and the combined result remains **310/513 (60.43%)**, below the **411/513** target. The preserved direct predictor remains **318/513 (61.99%)**. No model was promoted.

Only the existing 64 final output weights and one bias were trained. Unlike V63's soft aggregate-choice likelihood, this loss asks the highest-scoring correct-output candidate (or abstention) to beat incorrect-output choices by 0.2, exceeding the fixed 0.15 goal-retention margin. Correct-output membership uses movement labels only inside training; inference receives no labels. Uncovered moves and rows with no competing incorrect output contribute zero movement gradient. The same four-turn utility regularizer remains. No new architecture, inputs, movement predictions or candidate routes were added.

| Epoch | Combined fitting-validation moves | Active goals | Utility sum |
| --- | ---: | ---: | ---: |
| 0 | 1124/1997 | 595/2941 | 42.3333 |
| 4 | 1237/1997 | 1/2941 | 1.0000 |
| 8 | 1237/1997 | 0/2941 | 0.0000 |
| 12 | 1237/1997 | 0/2941 | 0.0000 |
| 16 | 1237/1997 | 0/2941 | 0.0000 |

This independently frozen contrast used the verified V63 canonical fitting caches and four whole-game folds. It did not use V64 results or any evaluation-dependent choice. Epoch-zero eligibility prevented a near-disabled planner from being presented as an improvement.

Two synthetic tests passed: a correct candidate receives the intended gradient, and uncovered/all-correct output sets have no movement gradient. Parent verification reproduced all 20 fold measurements, sampling and optimizer accounting, hidden-layer preservation, selected weights, both full saved forecast sets and 64 streaming turns. The available-output bound remains 1,598/1,997 on fitting-validation queries. Exposed research games, inherited fold exposure, observed past commands, inferred goal utilities, conditional movement and lack of autonomous playing-strength evidence remain limitations.

Direct inspection of rejected epoch-16 readouts found output-weight norms of 0.178-0.252, down from 0.367-0.432. Their highest held-query goal scores were all negative (fold maxima -0.0559 to -0.1040). The unchanged inference threshold therefore abstains; this is not evidence of an internal strategy representation. See `weight-inspection.json`.
