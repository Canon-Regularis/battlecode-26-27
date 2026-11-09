# V51: adapting movement to the improved code predictor

**Negative result.** A movement correction conditioned on V49's predicted codes gets 108/513 evaluation moves right (21.05%), versus 134/513 (26.12%) for unchanged V49. The matched constant-code correction gets 103/513 (20.08%). Neither result supports replacement or a useful additional code effect.

The existing movement head already receives the predicted code embedding, but was frozen during the recent code-weight updates. This experiment freezes all V49 weights and adds eight linear movement-residual experts over its 48-dimensional recurrent state. The treatment mixes those experts with predicted soft code probabilities. The control uses the fitting-training mean probabilities. Both start with zero residuals, have 3,528 trainable parameters, retain the original supported movement decoder, and share identical training rows, initial tensors, permutations and update counts. The unchanged baseline itself still depends on code; this tests additional code conditioning, not removal of all code information.

All 1,607 fitting windows are used, containing 12,318 recorded movement queries across 32 games. Four fitting-game folds use their matching V49 code checkpoints; each validates only its original 64 windows. Movement loss is divided by actual movement rows in each batch. Hindsight codes and future endpoints never enter movement inputs. A shared epoch is selected for both arms from 0, 8, ..., 64 using pooled fitting-fold correct moves, then NLL. Epoch 32 wins: control 421/1,997; treatment 401/1,997. Both are refitted for 1,632 updates and 394,176 movement presentations on all fitting games, then assessed on the unchanged evaluation queries.

| Evaluation model | Correct moves / 513 | Accuracy | Movement NLL |
| --- | ---: | ---: | ---: |
| Original S01 | 112 | 21.83% | 1.782698 |
| Improved-code V49 baseline | 134 | 26.12% | 1.801918 |
| Constant-code correction | 103 | 20.08% | 1.835390 |
| Predicted-code correction | 108 | 21.05% | 1.863128 |

The treatment rescues 70 V49 mistakes but introduces 96, for a net loss of 26. Against the constant control it rescues 27 and loses 22, insufficient for the frozen one-point code-effect threshold; likelihood also worsens. All six allocation conditions fail. Code and goal forecasts are unchanged, including 573/699 inferred-code predictions correct. The result does not show that the code lacks useful information, or that the observations are insufficient; it rejects this residual at the tested training configuration.

Parent verification reconstructs all five frozen feature banks (8,035 window instances), all movement supports and targets, 72 validation measurements, the shared selection, schedules, denominators, optimizer states, and finite gradients. All 7,288 selected-checkpoint original fitting/evaluation forecasts reproduce exactly across the two arms; 64 streaming turns match. Nine focused causal, support and gradient-isolation tests passed. No subagents or delegated reviews were used.

Artifacts are `plan.json`, `cache.json`, `selection.json`, `refit.json`, `result.json`, `comparison.json` and `verification.json`. Checkpoints remain local under `.cambc/action-predictor/v51/`. The explicit `CodeMovementPredictor` loader is experimental and does not replace the playing bot or select a command family.

These are repeatedly exposed research games with observed past commands, availability-selected windows, and inferred labels. Original backbone/discovery fitting-group exposure limits the folding interpretation. Conditional movement accuracy is not full-command accuracy, goal recovery or playing strength. Historical category, reliability and multi-seed requirements remain unmet. The failed weights and original checkpoints are preserved.
