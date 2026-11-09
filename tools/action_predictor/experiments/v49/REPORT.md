# V49: more fitting examples for the same neural weights

The selected checkpoint reaches **573/699 correct inferred codes, 81.97%**, on the unchanged eight evaluation groups. This improves V48's 552/699 and the previous V44 best of 517/699, but still falls short of the user's 85% target. At least **595 correct** are required; the remaining gap is **22 predictions**. No evaluation target attainment or model promotion is claimed.

## Why expand the fitting data

The original behavior-code experiment used eight windows per fitting game: 256 windows and 2,945 observed queries. Its own data audit counted 1,607 eligible windows in the same 32 fitting games. V49 reconstructs all of those already available windows using the original validated assembler. This yields 51,424 distinct own turns and **18,177 observed fitting queries**, without new replay downloads, engines, evaluation-game reconstruction or label-driven selection.

The 32-turn boundaries, minimum eight observed queries, chronological histories, missing masks, current personal PREs, original feature schema and frozen discovery prototypes are unchanged. All 256 original fitting windows reproduce as complete objects; their inferred code sequences and encoded tensors are exact matches. No turns overlap across windows. All 1,607 cached-map code forward paths match the original network, and no fields fall outside the original schema.

The expanded fitting-query code counts are: code 0: 10,858; code 2: 2,048; code 3: 211; code 4: 4,442; code 6: 391; code 7: 223; codes 1 and 5: two each. These remain frozen hindsight-inferred labels, not verified Fish objectives. The tiny new counts for codes 1 and 5 do not establish reliable learning of those classes.

## Weight training and selection

The 45,762-parameter neural architecture and inference interface remain unchanged. Only the existing context, GRU and code-head weights are updated; the map encoder and destination/movement heads remain frozen. Each fold starts from its matching V46 checkpoint with a fresh AdamW optimizer. Its training set includes all expanded windows from the other 24 fitting games. Every window from the eight held fitting games is excluded from gradient updates; validation uses exactly their original 64 windows.

Two learning rates, 0.0001 and 0.0003, run for 32 epochs, measured every four epochs. Epoch zero is eligible. Selection uses pooled original-query correct counts, NLL and deterministic tie-breaks, before the final evaluation. The selected learning rate is **0.0003 at epoch 24**:

| Original fitting-fold validation queries | Correct / 2,945 | Accuracy |
| --- | ---: | ---: |
| V46 warm-start baseline | 2,363 | 80.24% |
| V49 selected duration | 2,431 | 82.55% |

The selected configuration is then fitted on all expanded fitting windows from the V46 full-fit checkpoint, completing 2,424 optimizer updates. The eight fold runs plus this refit total 21,752 additional AdamW updates. The expanded in-sample score is 15,297/18,177; the original fitting-query subset scores 2,502/2,945 (84.96%). Neither should be rounded into a claim of reaching the 85% evaluation target.

## Same evaluation rows, improved code agreement

| Evaluation metric | V44 | V45 balanced readout | V48 | V49 |
| --- | ---: | ---: | ---: | ---: |
| Correct inferred codes / 699 | 517 | 455 | 552 | 573 |
| Code accuracy | 73.96% | 65.09% | 78.97% | 81.97% |
| Balanced code recall | 20.54% | 43.91% | 32.71% | 40.34% |
| Correct conditional moves / 513 | 120 | 119 | 141 | 134 |
| Endpoint within two tiles / 98 | 51 | 51 | 51 | 51 |
| Exact endpoints / 98 | 17 | 17 | 15 | 15 |
| Goal plus A* correct moves / 513 | 10 | 10 | 10 | 10 |

Against V48, V49 rescues 30 code errors and introduces nine, for a net gain of 21. Six evaluation games improve in net correct codes and two tie. These are descriptive comparisons on reused research groups, not independent replications.

Code recall is 409/453 for code 0, 33/54 for code 2, 0/1 for code 3, 120/158 for code 4, 0/2 for code 5, 11/20 for code 6, and 0/11 for code 7. Code 6 recovers from V48's 2/20 to 11/20. Codes 3, 5 and 7 remain completely missed. The earlier rare-code objective is therefore still unmet.

Conditional movement top-1 accuracy falls from V48's 141 correct to 134. Movement NLL is 1.801918, worse than V48's 1.788463 and original S01's 1.782698. All goal choices are identical to V48; mean endpoint error remains 3.3265 tiles. Higher inferred-code accuracy has not solved destination prediction or demonstrated strategy.

## Verification and artifacts

The new data and fitting-split tests pass alongside the earlier model/weight tests. Read-only parent verification rehashes all bound source/input artifacts, reconstructs all 1,607 feature windows and frozen code sequences, checks exact original-256-window parity, and verifies disjoint fitting/validation groups. It checks every saved optimizer schedule, denominator, step count, finite norm and frozen tensor; reproduces all 72 initial/checkpoint validation measurements and selection; reproduces all 3,644 original fitting/evaluation query forecasts exactly; and checks 32 streaming predictions.

- Checkpoint: `.cambc/action-predictor/v49/selected.pt`.
- Explicit experimental loader: `behavior_segments.expanded_code_predictor.ExpandedCodePredictor`.
- Evidence: `parity.json`, `cache.json`, `selection.json`, `result.json`, `comparison.json`, `verification.json`.

The loader reports `research_code_accuracy_target_met=False` and `promoted=False`. Original checkpoints and the playing bot are preserved. No subagents or delegated reviews were used.

This expansion follows the exposed V48 result. The outer games and the fitting-fold selection process are repeatedly used research data, and the old backbone/discovery were already trained on fitting groups before these folds. The new data uses the same availability threshold and inferred labels; it does not fix label uncertainty, teacher-forced history, sparse endpoint supervision or lack of internal Fish goals. Historical reference, category-90%, reliability and three-seed requirements remain unmet. The 85% evaluation target remains open.
