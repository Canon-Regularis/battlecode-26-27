# V63 - movement-supervised planner readout

The bounded readout update failed. Fitting-game selection retained epoch zero, so the combined planner remains **310/513 (60.43%)**, below the requested **411/513** threshold and the preserved direct predictor's **318/513**. No model was promoted.

Only the existing final 64 weights and one bias were trained, starting from the V62 edit of each matched V61 goal head. The hidden layer, movement network, candidates, routes and goal-retention rule stayed fixed. Movement supervision rewarded candidate routes or abstention that emitted the recorded move, with a four-turn progress-utility regularizer. All four fold readouts changed. Selection used actual hard retained-goal inference, not the soft training surrogate.

| Epoch | Combined fitting-validation moves | Goal activity | Recorded progress utility sum |
| --- | ---: | ---: | ---: |
| 0 | 1124/1997 | 595/2941 | 42.3333 |
| 4 | 982/1997 | 2307/2941 | 111.9167 |
| 8 | 989/1997 | 2262/2941 | 116.2500 |
| 12 | 965/1997 | 2420/2941 | 127.6667 |
| 16 | 1022/1997 | 2153/2941 | 99.0833 |

The selected original readout has 595/2,941 active goal queries. Trained readouts activate goals substantially more often and improve the progress proxy, but lose movement correctness. This is a failed surrogate/readout configuration, not proof that movement supervision cannot help goal selection.

Before fitting, a fitting-validation output audit found the gold move among the direct prediction and candidate-route outputs on only **1,598/1,997 = 80.02%** of movement queries. This is a conditional hindsight bound for this fixed output set, not achievable accuracy, evidence about Fish intent, or a global model ceiling. It motivates changing execution outputs rather than repeatedly adjusting only their selector.

Verification reproduced all 20 fold measurements, all frozen sampler schedules and optimizer-step accounting, the epoch-zero selection, both complete saved forecast sets and 64 streaming turns. The synthetic readout test passed. No evaluation answers were used for gradients or selection. The canonical fitting windows, inherited fitting exposure, repeatedly exposed research evaluation, observed past commands, replay-inferred codes/goals and lack of autonomous play evidence remain limitations. The 80% goal is unmet.
