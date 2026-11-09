# V68 - bounded goal representation

This larger representation/weight change failed. It removes absolute goal distance and the untrained radius scalar from the goal-specific inputs, replacing them with unit direction, local geometric/path progress, current/next goal-region membership, move alignment and availability. All eight channels are bounded in [-1,1]. The existing map/state features remain unchanged. The 8,833-parameter executor is retrained from the same initial tensors as V66; this is not merely a rescaling of trained weights.

The completed V66 goal-conditioned arm is the matched original-feature control. Initialization, examples, repeated-horizon weighting, permutation seed, optimizer settings, sixteen passes and checkpoint opportunities are identical. Four fitting-game folds select epoch 16 by the unchanged supplied-goal diagnostic rule. No control fit is repeated and no evaluation-dependent choice is made.

Fitting-validation diagnostic correctness reaches 1708/2106, versus the original selected 1,689/2,106. On the supplied-future-goal evaluation it gets **363/470**, compared with original 365/470. These privileged diagnostic results are not usable-planner accuracy.

With predicted goals on the unchanged evaluation, it gets **308/513 (60.04%)**, versus original executor 316, calibrated executor 317 and direct predictor 318. NLL is **1.343626**. Four transfer gates fail; diagnostic retention passes. No promotion or strategic improvement is supported.

The test confirms that the training-to-runtime goal-range mismatch can be removed from these inputs, but doing so did not improve the planner. It does not prove goal selection is the sole bottleneck: the representation also removes potentially useful distance information, and learned achieved-position goals differ semantically from selected objectives. No stronger claim is made.

Preflight checks reproduced five matched initializations, exact baseline predictions, finite backward gradients and bounded training/predicted-fitting-goal features. Parent verification reproduced all 20 fold measurements, matched original sampler schedules, optimizer accounting, selected weights, all saved summaries and 96 streaming turns including active goals. Existing source/feature receipts supply underlying replay provenance. The runtime is opt-in `BoundedGoalPlanner`; original and calibrated variants are preserved. The negative variant is not adopted.

Preexposed games, inherited fitting exposure, teacher-forced histories, one paired seed, point-to-region transfer and absence of autonomous outcomes remain limitations. No new high-level value learner or termination policy is introduced. No subagents were used.
