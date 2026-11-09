# V52: movement using the frozen code predictor and current-map geometry

**Movement improves; an additional benefit from code conditioning is not demonstrated.** The predicted-code geometry correction gets **226/513 moves right (44.05%)**, compared with **134/513 (26.12%)** for the unchanged V49 code predictor. That is 92 additional correct moves, or **17.93 percentage points**. The matched constant-code geometry control also gets 226 right and has slightly better likelihood. Both remain experimental; no playing-bot replacement or strategy claim follows.

## What changed

The V49 code predictor, recurrent state, original movement logits and goal head are frozen. A small correction scores each of the nine local movement candidates using 60 features from the current personal PRE and public terrain. These describe progress toward currently known nearest/weakest camps and enemies, nearest allies, public altars, and fixed home/enemy-home spawn locations. They are candidate input features, not human objective labels or claims about Fish's intent.

For altar/home candidates, progress uses eight-neighbor static-terrain shortest-path distances. Entity progress uses current geometric distances, proximity and health; it does not claim dynamic pathfinding or future legality. Unknown entity dynamics are excluded. The original personal movement support remains the final admission mask, including the original stay bucket.

A zero-initialized linear layer maps the frozen 48-dimensional recurrent state plus eight predicted code probabilities to coefficients for these candidate features. The matched control substitutes the fitting-training mean code distribution in that layer. Both contain 3,420 trainable parameters, retain the original code-dependent baseline logits, and have identical rows, optimizer settings, initial tensors, schedules, denominators and checkpoint opportunities. This tests additional code-conditioned execution; the control is not a policy with all code information removed.

The previous [V51 correction](../v51/REPORT.md) used only the frozen recurrent state and code probabilities and failed. V52 uses the original V49 weights, not those failed correction weights. Comparing V52 with V49 supports the geometry-aware correction as a package; it does not isolate every feature or optimization contribution.

## Selection and results

All 1,607 existing fitting windows from 32 games are retained, containing 12,318 recorded movement queries. Four whole-game fitting folds use their corresponding V49 code checkpoints and validate only the original 64 windows per fold. Additional movement training never sees the held fold's movement labels. The old backbone and discovery already had fitting-group exposure, so this is validation of the added correction rather than untouched end-to-end validation.

The frozen schedule uses AdamW at 0.003, 32 windows per batch, and movement-row loss denominators. A single shared epoch for both arms is selected from 0, 8, ..., 64 by pooled correct moves, then NLL. **Epoch 40** is selected before evaluation: predicted code gets 908/1,997 fitting-validation moves right, constant code 903/1,997, and the zero correction 386/1,997. Both selected heads are refitted on all fitting games for **2,040 updates and 492,720 movement presentations per arm**. No evaluation-based checkpoint switch or additional fit is performed.

| Same evaluation movement queries | Correct / 513 | Accuracy | Movement NLL |
| --- | ---: | ---: | ---: |
| Original S01 | 112 | 21.83% | 1.782698 |
| Unchanged V49 code predictor | 134 | 26.12% | 1.801918 |
| V51 code-only correction, rejected | 108 | 21.05% | 1.863128 |
| V52 geometry, constant-code control | 226 | 44.05% | 1.546572 |
| V52 geometry, predicted-code treatment | 226 | 44.05% | 1.550405 |

The treatment rescues 153 V49 errors and introduces 61, net +92. Seven evaluation games improve; one loses four correct moves out of 80. Against the constant-code control there are three rescues and three regressions. All four movement-improvement allocation guards pass, while both additional-code-benefit guards fail. The similar control result means the gain cannot be credited to the extra use of predicted code probabilities.

All code and goal predictions, likelihoods and recurrent states remain unchanged. Inferred-code accuracy remains **573/699 (81.97%)**, with the earlier rare-code failures. Endpoint accuracy remains 51/98 within two tiles; this intervention does not solve goal prediction. Movement accuracy is conditional on an already-recorded movement query, not complete-command accuracy or an autonomous decision to move.

## Verification and use

Parent verification reconstructs all 1,607 candidate-geometry windows, checks movement supports/labels, reproduces all five frozen feature banks and 72 fitting-validation measurements, checks selection and every saved schedule/denominator/optimizer state, and confirms identical update schedules across arms. It reproduces all **7,288 original fitting/evaluation forecasts** exactly across the two arms and checks **64 streaming turns**. Code and goal forecasts remain exact matches to V49. Thirteen focused tests pass, including unknown-entity masking, obstacle-sensitive path progress, zero-correction parity, causal streaming, supported likelihoods, fitting-group separation and frozen-backbone gradient isolation. No subagents or delegated reviews were used.

Explicit experimental loader:

```python
from tools.action_predictor.behavior_segments.code_path_predictor import CodePathPredictor

predictor = CodePathPredictor(arm="predicted")  # "constant" exposes the matched control
prediction = predictor.predict(current, route, round_number,
                               previous, previous_mask, state)
destination = prediction["conditional_movement"]
state = prediction["state"]
```

`current` is the original personal-PRE input; history must describe only the completed prior turn. Maintain separate state per actor and reset at real gaps; the existing loader also resets at actor changes and 32 turns. `conditional_movement` is an absolute destination conditional on the caller choosing movement; `movement_probabilities` follows the existing nine `OFFSETS`. Missing/dead observations return no movement distribution. Existing code, goal and A* fields are retained, and `promoted=False` remains explicit.

Checkpoints are `.cambc/action-predictor/v52/predicted.pt` and `constant.pt`; each requires the unchanged, hash-bound V49 backbone. Reports and source code are tracked, while large local checkpoints and forecast archives are bound by hashes in `result.json`. `comparison.json` provides per-game, direction and inferred-code diagnostics. Original checkpoints and the playing bot remain intact.

These results come from one matched training configuration on repeatedly exposed research games, after the negative V51 result. They use observed past actions, availability-selected windows, inferred codes and sparse goal labels. Static-terrain distances are a movement hypothesis, not full engine legality. Historical full-command references, category-90%, reliability and three-seed requirements remain unfulfilled; there is no fresh-data certification, verified Fish-intent, strategy or playing-strength claim.
