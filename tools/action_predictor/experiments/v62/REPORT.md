# V62: direct readout-weight edits improve the combined planner

The edited combined planner gets **310/513 movement queries correct (60.43%)**, up from V61's **219/513 (42.69%)**. It rescues 116 errors and introduces 25: **net +91 moves**. It still loses to V59 direct movement, **318/513 (61.99%)**, so it is an improvement to the failed combined planner, not a new best movement model or demonstrated strategy improvement.

## Weights read and changed

Inspection read the actual four saved parameter tensors. The final output layer had weight norm 0.879197 and bias **+0.104035**. On saved fitting predictions, 20,643/33,845 candidate scores were positive. The median best candidate score was 0.268746. Since the original policy intervenes when its best candidate is positive, these observations motivated testing a stricter readout; they do not establish that a positive bias is intrinsically incorrect or explain a neuron's semantics.

The selected edit changes only the existing final linear layer:

```python
new_output_weight = 0.5 * old_output_weight
new_output_bias = 0.5 * old_output_bias - 0.25
```

The resulting bias is **-0.197982639** and weight norm **0.439598411**. All 64 output weights and its one bias change. The hidden layer, V59 recurrent/code/movement tensors, candidate construction, supported routing and explicit 0.15 retention margin remain unchanged. No optimizer steps or new layers are involved.

For an original pre-tanh output z, the edited score is tanh(0.5*z - 0.25). Candidate ranking remains monotonic, but abstention and the effective retention margin change. This does **not** learn better goal identities; it makes the combined system more conservative about acting on its existing estimates. Edited scores should not be interpreted as calibrated expected utility or probabilities.

## Selection and measured effect

Eighteen scale/shift combinations were frozen before evaluation. Four matching fitting-fold V59/V61 checkpoints were tested on the original canonical held windows. Selection maximizes movement correctness while requiring nonnegative mean selected replay utility and goals active on at least 10% of candidate-available observed queries. Ties prefer a smaller coefficient change. Evaluation answers never choose the edit.

The selected scale 0.5 and shift -0.25 score 1,124/1,997 fitting-validation moves, versus 1,237 for direct movement. Goals remain active on 595/2,941 eligible validation queries (20.23%). The same edit is then applied to the full fitting checkpoint without a new fit.

On evaluation, goals remain active on **85/689 eligible queries (12.34%)**, down from 609/689 (88.39%). Actual movement overrides fall from **225 to 20 of 513 moves**. Compared with direct V59, the remaining overrides rescue five errors and introduce thirteen, net -8. Much of the gain over V61 therefore comes from suppressing harmful overrides, not additional strategic skill.

Mean selected recorded goal utility remains positive, **1.25/146 = 0.00856** per step, but drops from V61's 0.11016; abstention contributes zero. The positive-utility and minimum-activity guards pass. A separately reported disabled-planner control zeroes the output weights and sets bias to -1, reproducing V59 exactly with no active goals. It is not eligible for selection. This explicitly distinguishes partial suppression from simply turning planning off.

The combined-planner improvement condition passes; the condition requiring improvement over direct V59 fails. The overall gate remains false and no promotion occurred. Original weights and the playing bot are preserved.

## Verification and use

The direct parent verifier reconstructs the four matched fold caches and all 18 edit comparisons, reproduces selection and the disabled control, verifies exact output-weight arithmetic and unchanged hidden tensors, rebuilds both final forecast banks, and checks 64 streaming turns against cached predictions. Focused tests cover readout equivalence, unchanged tensors, identity edits and exact disabled-control behavior. No subagents were used.

`EditedPlannerPredictor` is an opt-in subclass of the previous objective predictor. `objective_movement` uses the edited planner; `conditional_movement` remains V59. It retains the required completed-turn `previous_moves`, descriptor/mask and per-actor history interface. Edited weights live at `.cambc/action-predictor/v62/selected.pt`; original V61 weights remain intact.

Repeatedly exposed research games, inherited fitting-fold exposure, observed past commands, conditional movement, partial visibility, proxy goal utility and a single selected setting limit interpretation. There is no autonomous rollout, verified Fish-intent, full-command reliability or playing-strength result. Reading and editing these weights improved this combined system, but did not solve useful long-term objective selection.
