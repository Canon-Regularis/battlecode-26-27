# V70 - one shared executor with optional predicted goals

The requested shared executor is implemented and verified. It runs on every located movement query, using the same weights with or without a goal. Training uses current predicted goals from the frozen V62 selector rather than achieved future replay endpoints. An availability mask zeros missing goal fields; the executor still runs. A ninth goal field supplies the selector's bounded utility estimate, not calibrated confidence. V59 and the selector remain frozen.

This removes the conditional execution-coverage limit, but does not improve top-one movement accuracy. On the same 513 evaluation movements, both the goal-aware and matched goal-blind executors get **311/513 (60.62%)**, versus direct V59 **318/513 (61.99%)**. The goal arm rescues 16 errors and introduces 23. Movement NLL improves from 1.200119 to 1.182086, but the accuracy gates fail. Goal-present results are 46/69 versus direct47; no-goal results are265/444 versus direct271. Neither group violates the predeclared two-point guard. No promotion, 80% attainment or strategic benefit is established.

## Matched training

Both arms have 8,897 parameters in a shared137-64-1 tanh residual and identical initial tensors, zero initial corrections, samples, permutations, optimizer settings and checkpoint opportunities. The blind arm masks all nine goal fields. Each uses all12,318 expanded fitting movement examples once per epoch. In the full-data bank,3,200 have predicted goals and9,118 have none. No future-goal eligibility or horizon duplication remains.

Four fitting-game folds select from epochs0/4/8/12/16 using all1,997 canonical held movements, maximizing correct count subject to NLL<=initial+0.01. Seed70001,AdamW lr0.001,weight decay0.01,batch128,clip5. Both select epoch16: goal1,246/1,997; blind1,241; initialdirect1,237. Each then refits once on all32 fitting groups. Combined training/refitting takes19.743seconds within the600second cap. Evaluation does not select weights or checkpoints.

Each outer fold uses its own frozen training-group V59/V62 models. Training goals are in-sample predictions from those models; held-fold goals exclude those held groups. There is no new inner cross-fitting. Previously inherited fold exposure remains a limitation. Inputs are causal even though labels used to train the frozen selector originally included replay progress supervision.

## Reading the weights

The goal inputs are connected and trained. Goal-geometry, availability and utility weights change substantially beyond weight decay. Masking goals in the full fitting bank changes162 predictions and reduces correct movements from8,300 to8,254. This is a fitting diagnostic, not an evaluation improvement or strategic claim. The blind arm's unused goal columns change only through weight decay.

Supported hidden saturation is about8.3% in the goal arm. Its centered supported residual RMS is0.691; the raw3.532RMS includes common score shifts that do not change softmax choices. The output scalar bias is common to every candidate and cancels in softmax. These facts do not support a disconnected-input or wholesale saturation explanation. See `weight-inspection.json` and `weight-debug.json`.

## Runtime and proof

Opt-in API: `tools.action_predictor.behavior_segments.shared_goal_execution_predictor.SharedExecutionPlanner(arm='goal')`. `shared_movement`/`objective_movement` return its movement; `conditional_movement` retains V59 and `routed_objective_movement` retains routing. It accepts current observations, route/map, previous completed-turn information and per-actor state. No future goal can be passed through this runtime API.

Fifteen focused tests pass. Direct parent verification reproduces40 fold measurements,12,416 optimizer-update records, selected weights, saved forecast summaries, current-goal construction and192 streaming turns including42 goal-present and30 located no-goal queries. Eight raw fitting-window probes preserve predictions. Batched versus single-window inference differs by at most4.92e-7 in context,3.82e-6 in baseline logits and7.46e-8 in goal utility; geometry and goal identity match exactly. The verifier was corrected to use these explicit bounded floating-point checks instead of bit equality across batching modes. No training or selection changed.

The implementation fixes execution coverage, not goal quality or autonomous strategy. These remain preexposed research games, one seed, teacher-forced history, inferred goals and conditional movement metrics. Stronger direct weights are preserved. No subagents were used.
