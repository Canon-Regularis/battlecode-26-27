# V46-V48: weight-only search toward 85% inferred-code accuracy

The selected neural checkpoint reaches **552/699 correct inferred codes, 78.97%**, on the eight evaluation groups. This improves the prior best overall accuracy of 517/699 (73.96%), but the requested 85% target is **not met**: at least 595 correct predictions are required, leaving a gap of 43. Its 85.40% fitting accuracy must not be reported as evaluation success.

The original 45,762-parameter architecture, causal inputs, eight labels and prediction interface remain unchanged. Original S01, V44 and V45 checkpoints are preserved. The final model changes eight existing context/GRU/code tensors, totaling 20,680 scalar weights, relative to V44. It introduces no new model parameters, inference heuristics, relabeling, evaluation-row exclusions or playing-bot modifications.

## Search and selection

Three separately frozen stages test existing neural weights:

1. **V46, code-focused updates:** cache the frozen map encoder and train the existing context, GRU and code weights. Four fitting-game folds compare two learning rates over 96 epochs. The selected learning rate 0.0003 and epoch 96 reach 80.24% pooled fold-validation accuracy. A full-fitting refit reaches 85.40% in sample.
2. **V47, encoder updates:** continue the corresponding V46 fold checkpoints, unfreezing the existing map/entity encoder for up to 16 epochs. Epoch zero wins. These encoder changes are rejected.
3. **V48, regularization:** from the original V44 initialization, compare training-only context/recurrent dropout, label smoothing with stronger decay, and their combination. Each uses four folds and 96 epochs. The best is smoothing/decay at epoch 92, with 80.00% validation accuracy; it does not beat V46.

Selection uses pooled fitting-fold correct counts, then NLL and the recorded deterministic tie-breaks. There are 129 checkpoint/configuration choices across the stages, each assessed on the same 2,945 fitting-fold queries. The final choice is written before outer evaluation. Only one final checkpoint is evaluated on the eight outer groups in this search; no switching or extra candidate evaluation follows.

The selector names V47's encoder epoch zero because its NLL accumulation is about 6.6e-9 lower than V46's otherwise identical score. The saved final weights are tensor-for-tensor equal to the V46 refit. This is numerical tie-breaking, not an encoder improvement.

All three stages complete 24 fold training runs, plus one nonzero-update full-fitting refit: 26,112 optimizer updates altogether. The encoder's selected transfer and final checkpoint copy use zero further updates. These are supervised weight-training experiments, not unfitted manual adjustments. Budgets, random seeds, updates, schedules and selection opportunities are saved.

## Evaluation results and tradeoffs

| Same 699 evaluation queries | Original S01 | V44 bias/history edit | V45 balanced readout | Selected V48 checkpoint |
| --- | ---: | ---: | ---: | ---: |
| Correct inferred codes | 453 | 517 | 455 | 552 |
| Code accuracy | 64.81% | 73.96% | 65.09% | 78.97% |
| Balanced code recall | 14.29% | 20.54% | 43.91% | 32.71% |
| Correct conditional movement / 513 | 112 | 120 | 119 | 141 |
| Endpoints within two tiles / 98 | 51 | 51 | 51 | 51 |
| Exact endpoints / 98 | 17 | 17 | 17 | 15 |
| Mean endpoint error, tiles | 3.3061 | 3.3061 | 3.3061 | 3.3265 |
| Goal plus A* correct movement / 513 | 10 | 10 | 10 | 10 |

The selected model improves overall inferred-code agreement and conditional movement top-1 accuracy. Movement NLL is 1.788463, slightly worse than S01's 1.782698. Goal NLL is 5.385922 and goal precision does not improve. These changes establish neither full-command accuracy nor goal-based strategy or playing strength.

Rare-code coverage regresses relative to the V45 model that explicitly prioritized balanced recall:

| Code | Correct / evaluation examples | Recall |
| --- | ---: | ---: |
| 0 | 405 / 453 | 89.40% |
| 2 | 31 / 54 | 57.41% |
| 3 | 0 / 1 | 0% |
| 4 | 114 / 158 | 72.15% |
| 5 | 0 / 2 | 0% |
| 6 | 2 / 20 | 10% |
| 7 | 0 / 11 | 0% |

There are still no fitting-query labels for code 5. The current objective again suppresses code 7. Thus the latest overall-accuracy objective improves without satisfying the preceding request to stop missing rare codes. Accuracy varies substantially by evaluation game, from 48/83 to 75/81. No universal 85% reliability claim is supported.

## What the errors tell us

The selected V46 fitting-fold predictions score 36/124 (29.03%) on code-change queries and 40/75 (53.33%) at window index zero. Stable-code queries score 2,287/2,746 (83.28%); queries with a missing previous observation score 438/588 (74.49%). These overlapping diagnostic strata are defined after prediction using archived labels. They are never model inputs or checkpoint selectors.

Changes and window starts have higher error rates, but stable-code queries still account for 459 of the 582 validation errors. The results do not establish that missing history, unpredictable behavior or representation capacity is the unique bottleneck, and do not establish an accuracy ceiling. The measured training-validation gap, failed encoder updates and failed regularization search do show that additional weight updates alone have not delivered the requested result in these experiments.

## Proof and artifacts

Sixteen focused tests pass. They cover cached/full forward and gradient parity, independent window resets, future/label perturbation causality, exact observed-query denominators, frozen tensor scope, seeded training-only dropout, original inference behavior and the preceding direct-weight edits.

Read-only parent verification checks all source/input/archive bindings, initial states, frozen tensor preservation, sampler schedules, row coverage, optimizer steps/settings and finite gradients. It reconstructs all 256 cached map-feature windows, reproduces all 516 saved validation-checkpoint measurements, verifies all three selectors, and reproduces the final 2,945 fitting plus 699 evaluation forecasts exactly. Thirty-two streaming code predictions match batch inference. No subagents or delegated reviews were used.

- Final checkpoint: `.cambc/action-predictor/v48/selected.pt`.
- Explicit opt-in loader: `behavior_segments.code_weight_predictor.CodeWeightPredictor`.
- Selection and scores: `winner.json`, `result.json`, `analysis.json`.
- Proof: `verification.json`.

The loader reports `research_code_accuracy_target_met=False` and `promoted=False`. The original predictor and playing bot remain unchanged.

These are repeatedly exposed research groups, not untouched certification data. The original backbone and discovery already saw all fitting groups before fold selection; the folds assess additional weight updates rather than fresh end-to-end training. Repeated validation selection adds further exposure. Labels are hindsight-inferred behaviors, observed past commands are supplied, endpoint supervision is sparse, and verified Fish intent is unavailable. Historical reference, category-90%, reliability and three-seed requirements remain unmet. The 85% evaluation target remains open; these artifacts must not be presented as its completion.
