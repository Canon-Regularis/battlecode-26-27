# V69 - learned execution when no goal is selected

The broader fallback did not improve evaluation movement. It gets **313/513 (61.01%)**, versus calibrated V67 **317/513** and direct V59 **318/513**. Movement NLL is **1.234916**, above the direct reference 1.200119 and its +0.01 allowance. Three performance guards fail; active-goal preservation passes. No promotion, 80% attainment or strategy gain is supported.

## Bottleneck examined

The previous executor only changes movement when the frozen goal selector activates. Across all 1,997 fitting-fold validation moves, it activates on 496. The frozen inactive predictions get 864 correct. Even perfect active execution would therefore yield only **1,360/1,997 (68.10%)** under that fixed selector/fallback. This is a conditional coverage ceiling, not a ceiling on the full model or evidence of missing information. See `coverage.json`.

The V66 executor was trained on 12,123 horizon examples but only 8,009 distinct movement queries. This intervention trains a fresh goal-blind residual on **12,318** fitting movement queries, including **4,309** not represented by that achieved-goal dataset. Each query contributes once per epoch. There is no future-position eligibility requirement or repeated horizon weighting. At inference the new residual runs only when no goal is selected. V67's calibrated goal-conditioned executor remains exact on active queries; V59 and the goal selector are frozen.

This changes training population/weighting and inference coverage together. It is not an isolated architecture comparison. Fallback execution is not a new strategy objective.

## Training and selection

Same shared 136-64-1 candidate scorer, 8,833 parameters, goal inputs masked to zero, zero initial residual. Seed 66001; AdamW lr 0.001, weight decay 0.01, batch 128, clip 5, sixteen epochs in four whole-game fitting folds. Train on expanded other-24-game rows and select using all 1,997 canonical held fitting movement queries with predicted goals. Epochs 0/4/8/12/16 are eligible, subject to NLL <= initial +0.01; maximize correct count, then minimize NLL, then choose earlier epoch.

Epoch **8** wins with **1197/1,997**, versus initial 1,191. Full refit uses all 32 fitting groups. Fitting and refit took 9.421 seconds within the frozen 600-second cap. Evaluation never selected weights or epochs. The original and all candidate checkpoints remain preserved.

| Fixed evaluation cohort | Calibrated V67 | New fallback |
| --- | ---: | ---: |
| Active goal: 69 movements | 46 | 46 |
| No goal: 444 movements | 271 | 267 |
| All 513 movements | 317 | 313 |

Relative to V67, the intervention rescues 10 errors and introduces 14. Relative to direct V59, it rescues 14 and introduces 19. No-goal coverage is no longer frozen, but this learned correction does not transfer its small fitting-validation gain. This does not prove a capacity ceiling or that additional training would help.

## Runtime and verification

Opt-in loader: `tools.action_predictor.behavior_segments.universal_execution_predictor.UniversalExecutionPlanner`. It uses the inherited causal `predict` interface and per-actor state. `objective_movement` and `goal_conditioned_movement` expose the hybrid; `conditional_movement` remains direct V59; `fallback_execution_used` identifies the new branch. Runtime receives no future replay goals. The playing bot is unchanged.

The parent verifier rebuilds five feature banks and all 12,318 labels, reconstructs sample schedules/RNG and optimizer counts, checks every checkpoint selection measurement, reproduces saved forecasts and guards, preserves active-goal outputs, and checks actual streaming calls through both branches. See `verification.json`. Focused tests cover initial parity, goal blindness, selection guards, population coverage and existing executor/geometry/report contracts. No subagents or delegated reviews are used.

The verifier's first membership check incorrectly required every observed held window to contain a movement training row. It was corrected to validate against the canonical window index, including windows with only nonmovement queries. No model, data, fit or selection changed.

These remain preexposed research games with inherited fitting-fold exposure, teacher-forced histories and inferred goals. One seed and conditional replay accuracy do not establish autonomous strategy, reliable full-command prediction or playing strength. The stronger direct checkpoint remains the reference. See [weight calibration](../v67/REPORT.md) and [bounded-goal negative result](../v68/REPORT.md).
