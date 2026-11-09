# V45: balanced replacement weights for rare behavior codes

The user requested further weight edits so rare codes would no longer be missed. Replacing the complete code readout substantially reduces dominant-code collapse and recovers codes 2, 6 and 7 on evaluation queries. It does **not** meet the request for reliable recognition of every rare code. Code 3's single evaluation example remains missed, code 5 has no fitting examples, and code 7 has many false positives. The checkpoint remains experimental and fails its declared acceptance requirements.

## What changed

The original S01 model and V44 checkpoints are preserved. V45 tests the original hidden representation and the previously motivated fivefold history-input weight scaling. For each representation, it solves five class-balanced ridge regressions for the code head, with strengths 0.01, 0.1, 1, 10 and 100. Labels are the existing inferred behavior codes, not verified Fish objectives.

Each supported class contributes equal total weight to the squared-error objective. Hidden-state normalization is estimated on the fitting portion of each fold and folded algebraically into the final `code.weight` and `code.bias`; inference does not require an extra feature transform. A fixed logit multiplier of four controls the soft embedding scale. Classes absent from fitting have zero readout weights and bias -30, explicitly making this a classifier for the supported classes rather than inventing evidence for unseen classes.

Selection uses four deterministic whole-game folds within the 32 fitting groups. It maximizes the worst supported-class recall, then macro-F1, then overall accuracy. The existing backbone was already trained on those groups: this is cross-validation of the replacement readout conditional on that backbone, not independent end-to-end validation. The selected `history5_ridge10` head is then solved on all 2,945 fitting queries. Its receipt and checkpoint are saved before scoring the eight preexposed evaluation groups. No choice changes after evaluation.

The saved copy changes 3,312 GRU history-input weights, 384 code-head weights and eight code-head biases. All other tensors remain identical to S01. There are 40 fold solves and one final analytic solve; no optimizer or gradient-descent updates. This is supervised fitting of replacement weights, not an unfitted manual adjustment.

## What it achieves

| Evaluation code | Available fitting examples | Evaluation examples | Correct in V44 | Correct in V45 | V45 recall | V45 precision |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 0 | 1,743 | 453 | 445 | 302 | 66.67% | 90.42% |
| 2 | 370 | 54 | 0 | 37 | 68.52% | 33.04% |
| 3 | 58 | 1 | 0 | 0 | 0% | 0% |
| 4 | 676 | 158 | 72 | 99 | 62.66% | 85.34% |
| 5 | 0 | 2 | 0 | 0 | 0% | 0% |
| 6 | 52 | 20 | 0 | 11 | 55.00% | 22.45% |
| 7 | 46 | 11 | 0 | 6 | 54.55% | 9.84% |

Balanced recall rises from V44's 20.54% to 43.91%, while overall code accuracy falls from 73.96% to 65.09%. Original S01 accuracy was 64.81%. Thus the new readout makes a substantial tradeoff between majority agreement and recognition of less common classes. It is not uniformly better.

The model predicts code 3 on 27 queries and code 7 on 61 queries. None of the code-3 predictions is correct; six code-7 predictions are correct. Simply making rare classes win more often is therefore insufficient. Out-of-fold fitting diagnostics already expose code 7's weakness: recall 23.91%, precision 4.25%. In contrast, in-sample final fitting recall is at least 60.87% for every supported class, illustrating why fitting coverage alone would be misleading.

Evaluation movement is 119/513 correct (23.20%), compared with original S01's 112 and V44's 120. Movement NLL is 1.779278. All destination choices remain unchanged: 51/98 within two tiles, 17 exact, mean error 3.3061 tiles, and goal-plus-A* remains 10/513 correct. Better code coverage has not repaired destination prediction or established strategy.

## Remaining misses and acceptance

The code-3 miss is at turn index 30 in its window with a real previous observation and 22 available prior-descriptor fields. It cannot be dismissed as a reset or wholly missing history. Its previous commands include movement, end, recall and cancel. The model has 58 fitting examples across nine groups, but one evaluation example is too little to quantify reliable generalization for this class.

Code 5 has two evaluation examples and zero fitting query labels. The replacement explicitly leaves it unsupported. That is a coverage gap which this supervised readout edit cannot resolve from labeled examples; it is not proof that the underlying behavior is unknowable. Relabeling those examples or tuning their weights after looking at their answers would invalidate the evaluation. A separate study would need fitting support or a validated open-set/descriptor-based assignment rule.

The fitting result passes all eight declared requirements. Evaluation fails three: supported-class recall, supported-class precision, and complete code coverage. Overall code accuracy, movement accuracy/NLL, and destination error/accuracy guards pass against original S01. The complete conjunction fails. No zero-miss, generalization, goal, strategy, playing-strength or promotion claim follows.

## Verification and use

Ten focused tests pass, including analytic normal-equation residuals, rare-class recovery on a synthetic imbalanced example, missing-class rejection, deterministic group folds, precision accounting, original tensor preservation, causal model behavior and the prior scaling-equivalence tests.

The verifier independently reconstructs both 2,945-row hidden-state banks, all fold selections, the exact replacement checkpoint, all 3,644 full query forecasts and acceptance checks. It also exercises the explicit loader and matches 32 streaming code predictions to batch inference. Input/checkpoint bindings verify unchanged; no optimizer state is stored in the edited checkpoint.

Checkpoint: `.cambc/action-predictor/v45/selected.pt`. Explicit loader: `behavior_segments.rare_code_predictor.RareCodePredictor`. It reports its supported codes and `all_guards_passed=False`; the original predictor and playing bot remain unchanged.

The remaining work requires better evidence and a separately scoped learning change, particularly for code 7's poor discrimination and the unsupported code 5. Repeated edits against these same evaluation answers would conceal those problems. Prior limitations remain: inferred hindsight labels, previously exposed groups, observed history, selected available observations, sparse endpoints and no verified objective logs.
