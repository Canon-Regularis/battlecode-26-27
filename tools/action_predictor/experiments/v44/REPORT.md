# V44: reading and directly editing the collapsed code predictor's weights

The user requested direct weight inspection and then direct edits. The original trained checkpoint remains unchanged. Three edited copies were tested without gradient descent. The combined edit breaks the all-code-0 behavior and improves overall inferred-code agreement, but it still misses rare codes and fails the declared balanced-recall requirement. Destination predictions do not improve. This is a partial diagnostic repair, not a promoted strategy model.

## What the weights reveal

The S01 classifier is not dead or disconnected. Its code-weight matrix changes by Frobenius norm 1.445 from initialization and the GRU input matrix by 3.160. On 2,945 fitting queries, code probabilities vary with the input, and code NLL is 1.0476 versus 1.1224 for a constant empirical-prior predictor. The collapse is principally in the winning class, not a completely constant probability vector.

Code 0 accounts for 1,743 fitting labels (59.19%), code 4 for 676 (22.95%), and code 2 for 370 (12.56%). Each remaining used class has only 46–58 observed labels. Mean predicted probability for code 0 is 65.14%; code 4 receives 18.03%. The classifier learns some distinctions, but they are usually too weak to overcome its majority preference.

The output bias is not the principal source. On true code-4 rows, the average code-0 advantage is 1.006 logits: only 0.189 comes from the output-bias difference, while 0.817 comes from the hidden-state/readout product. On true code-2 rows, the bias contributes only 0.002 of a 1.516-logit disadvantage. Removing the final biases leaves all 177 queries in the bounded intervention cohort assigned to code 0.

The prior-turn values are explicitly divided by five before the GRU. Their observed input RMS is 0.0968, versus 0.7183 for map context and 0.9428 for availability masks. The learned GRU weights do not compensate much: weight RMS is 0.0953 on history-value columns versus 0.0856 on context columns. After multiplication by the actual weights, history contributes RMS 0.0515 to the gate inputs versus 0.6221 from context and 0.5029 from masks. Much of that context contribution is constant; after centering, the corresponding context/history RMS values are 0.1051/0.0441. These measurements support a history-scaling hypothesis without proving it is the sole training failure.

Saturation and missing gradients are not supported as simple explanations. Only 0.033% of context tanh activations exceed magnitude 0.99, no measured update gate exceeds 0.99, and 3.06% of candidate-state activations exceed that magnitude. Across 16 fixed-hash fitting windows, mean weighted code-loss gradient norm on the context/GRU/code parameters is 0.1956, versus 0.1762 for movement. Mean code/movement gradient cosine is approximately -0.009. These are final-checkpoint probes, not a reconstruction of the whole training path.

The decoder can also use the recurrent state directly, so useful movement features do not have to become a discriminative code. The previous permutation diagnostic left goal choices unchanged. That establishes weak measured dependence on the code embedding in this checkpoint, not a unique causal account of training failure.

## The direct edits

All parameters start from the same verified S01 final checkpoint. No optimizer is constructed and no original file is overwritten.

1. `history_x5`: multiply only `memory.weight_ih[:, 32:55]` by five, exactly compensating the history-value division in the forward pass. This changes 3,312 scalar weights.
2. `prior_half`: add `-0.5 * log(fitting_class_frequency)` to each of the six observed class biases. Absent classes receive no change. This is an explicit class-prior correction, not merely zeroing the learned biases.
3. `combined`: apply both edits. All other tensors remain exactly unchanged.

The three variants and six guards were frozen before scoring them. Selection uses fitting data only. None passes the required ten-point balanced-recall gain, so the combined candidate is selected as the predeclared best diagnostic by balanced recall, not as an eligible replacement. Its selection receipt is written before evaluating that one candidate on the eight evaluation groups. No switching or extra candidates follows evaluation.

## Results

| Evaluation on the same queries | Original S01 | Combined weight edit |
| --- | ---: | ---: |
| Correct inferred codes / 699 | 453 (64.81%) | 517 (73.96%) |
| Balanced code recall | 14.29% | 20.54% |
| Predicted codes | code 0: 699 | code 0: 612; code 4: 86; code 3: 1 |
| Recall of code 4 | 0% | 45.57% |
| Conditional movement correctness / 513 | 112 (21.83%) | 120 (23.39%) |
| Movement NLL | 1.782698 | 1.779227 |
| Endpoint within two tiles / 98 | 51 (52.04%) | 51 (52.04%) |
| Mean endpoint Chebyshev error | 3.3061 | 3.3061 |
| Predicted endpoint + A* correct steps / 513 | 10 | 10 |

The edit recovers a useful distinction between codes 0 and 4, but no correct predictions of the other evaluation codes. Its overall code gain therefore does not establish broad objective classification. The prior-turn persistence diagnostic still has substantially better balanced recall (43.55%), although its overall agreement (72.96%) is slightly lower. Those postfit comparisons are descriptive only.

All guards except the ten-point balanced-recall gain pass on both fitting and evaluation. The conjunction fails. The model's endpoint choices and A* outcomes remain unchanged, so this edit does not fix goal-guided movement or demonstrate learned strategy.

## Verification and usage

Two focused tests establish exact intended tensor scope, original-state preservation, inactive-class handling, and numerical equivalence between scaling the history columns and scaling history inputs. Parent verification checks all three saved edits against their formulas, all unchanged tensors and original input hashes, and reproduces all 3,644 selected-checkpoint query forecasts and guards. Edited checkpoints omit optimizer state because they are inference-only artifacts.

The selected copy is `.cambc/action-predictor/v44/combined.pt`. The explicit experimental loader is `behavior_segments.edited_predictor.EditedBehaviorPredictor`; the existing `BehaviorPredictor` and playing bot remain unchanged. The edited loader reports `all_guards_passed=False`.

The evidence points toward normalizing history features during a separately controlled fit and validating the code predictor on its own before allowing destination learning to rely on it. It does not establish that more training, class reweighting, or these manual edits will solve the remaining classes. Single-checkpoint edits, preexposed groups, inferred labels, selected available observations, sparse endpoint targets and incomplete strategic-ground-truth evidence remain material limitations.
