# V67 - direct executor weight calibration

Reading the trained executor identified a training/runtime goal mismatch, then a bounded fitting-game search selected a **0.75 multiplier on the final output layer**. This reduces the learned movement correction by 25%, leaving V59, the goal selector, all first-layer weights and the routing/support interfaces unchanged. Exactly 65 scalar values in two tensors change. Original weights remain preserved.

The selected edit produces a small research-set gain: **317/513 (61.79%)**, versus V66's **316/513 (61.60%)**. It remains below V59 direct **318/513 (61.99%)**, and movement NLL still fails the direct-reference guard. The complete gate fails; the variant is opt-in, not promoted, and does not establish improved strategy or generalization.

## What reading the weights established

- In achieved-goal training data, relative goal offsets are at most eight tiles per axis. Predicted fitting objectives reach about 90 tiles away. Several absolute-distance inputs frequently exceed their training ranges.
- Goal-radius input column 134 is identically zero in training. Its connection vector remains nonzero, with norm 0.3962. Verification reproduces its final values from initialization plus AdamW weight decay: it received no data learning signal. Predicted fitting goals use radii 0, 1 and 3.
- These are concrete interface differences, not proof they uniquely caused the errors. The distance/radius edits were not selected. Simple output-strength calibration performed better under the frozen fitting guards.
- The final scalar bias is common to all nine move scores and cancels in softmax. Scaling that bias preserves the intended affine-layer edit, but the output-weight contribution drives changed movement decisions.

The audit inspects fitting examples and fitting predicted goals only. It includes all nine candidate slots, including unsupported slots; that qualification matters for distance-range statistics. See `inspection.json` and `weight-deltas.json`.

## Frozen comparison

Twenty-four prospective settings combine first-layer distance-column scales 0.1/0.25/0.5/1, optional radius-column zeroing, and output scales 0.5/0.75/1. Each uses the corresponding V66 fitting-fold checkpoint and unchanged V62 goals on the original held movement queries. Selection maximizes combined correctness while preserving supplied-goal diagnostic accuracy within two percentage points and not worsening predicted-goal NLL by more than 0.01 versus the original executor. Ties prefer the smallest squared weight edit. The unchanged model is eligible. No optimizer updates, evaluation-guided settings or new parameters are used.

The selected setting leaves distance scale at one and radius weights unchanged. Fitting-validation correctness improves **1,170 to 1,191 out of 1,997**. Supplied-goal diagnostic correctness falls **1,689 to 1,662 out of 2,106**, inside the frozen allowance. More aggressive shrinkage achieves larger fitting movement gains but fails the diagnostic-retention guard; it is not substituted after evaluation.

| Same 513 evaluation movements | Correct | Movement NLL |
| --- | ---: | ---: |
| V66 original executor | 316/513 | 1.271635 |
| Calibrated executor | 317/513 | 1.243919 |
| V59 direct reference | 318/513 | 1.200119 |

Relative to V66, the edit rescues three errors and introduces two, net +1. Relative to direct it rescues four and introduces five, net -1. Goal choices and activation stay fixed; inactive-goal rows retain exact direct fallbacks. The supplied-future-goal diagnostic changes from 365/470 to 362/470 and passes the two-point retention allowance. That diagnostic remains privileged future information, not usable-planner accuracy or evidence of reaching the original 80% target.

## Runtime and proof

```python
from tools.action_predictor.behavior_segments.goal_execution_edit_predictor import CalibratedGoalExecutor
predictor = CalibratedGoalExecutor()  # experimental, not promoted
```

The inherited `predict` interface is unchanged: current observation/map, prior completed-turn descriptors, actor state and `previous_moves`. `goal_conditioned_movement` / `objective_movement` expose this variant, with old routing and direct movement still available in separate fields. Replay future goals are never runtime inputs.

Parent verification reconstructs all four fold caches, all 24 setting comparisons, frozen selection, exact selected-weight arithmetic, original/direct controls and both full forecast sets. It checks the radius-column weight-decay explanation and 96 streaming turns, including 21 active-goal cases. Fourteen focused tests passed. No subagents or delegated reviews were used.

The broader V66 execution study is documented in [its report](../v66/REPORT.md). This edit does not resolve the short-point-goal versus distant-region-goal training mismatch. Reused research games, inherited fitting exposure, teacher-forced histories, inferred goals, one seed and the absence of autonomous outcomes remain limitations. No category/full-command reliability, playing-strength or strategic gain is claimed.
