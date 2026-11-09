# V57: explicit observed direction improves movement

The selected correction reaches **298/513 evaluation moves (58.09%)**, up from V55's 229/513 (44.64%). It rescues 93 errors and introduces 24, net **+69 moves / +13.45 percentage points**. Movement NLL improves from 1.5211 to **1.3246**. The user's 80% target requires 411 correct moves and remains **113 short**.

The original history descriptor records unsigned net walking distance but omits signed direction. A fitting-only diagnostic found that displacement between previous and current observed PRE positions contains useful information. V57 makes that direction explicit using four candidate features: cosine alignment and exact sign match, each also divided by elapsed rounds. Only already-observed positions enter this feature. Missing PRE retains the last observed position; observed missing position clears it; actor changes and 32-turn resets clear history. Current and future movement labels never construct the input.

A zero-initialized residual predicts four coefficients from the frozen recurrent state and soft behavior code. Two heads, linear and one hidden layer, were compared using four whole-game fitting folds, with all expanded windows from the other 24 games for training and the original 64 held windows for validation. The original V55 policy stays frozen. This is a new causal feature and small learned correction, **not merely editing existing weights**.

Selection chose the **228-parameter linear head at epoch 24**, scoring 1,156/1,997 fitting-validation moves versus the warm-start 938/1,997. The one full refit completed **624 updates / 295,632 movement presentations**. Expanded in-sample movement is 7,686/12,318 (62.40%); this is distinct from evaluation accuracy. The same 513 evaluation moves were then assessed once. No evaluation-dependent checkpoint choice was made.

All code and goal forecasts remain exactly unchanged from V55: 573/699 inferred codes, 51/98 endpoints within two tiles and 15/98 exact endpoints. This supports improved conditional movement, not better goals or verified strategy. The playing bot is unchanged.

Verification reconstructed all five feature banks, checked 160 raw-map/cache probes, reproduced all 40 validation measurements and selection, audited schedules/denominators/optimizer states, reproduced all 3,644 saved forecasts exactly and matched 32 streaming turns. Tests cover causal prefixes, missing/dead/actor/round handling, zero-start parity and gradients. No subagents or delegated reviews were used.

Use the opt-in `HeadingMovementPredictor`, with correction weights at `.cambc/action-predictor/v57/selected.pt` and its bound V55 parent. It maintains position history in the opaque per-actor state. Runtime callers must retain the existing window/gap reset contract.

These repeatedly used research games are not untouched certification data. Inherited fitting-fold exposure, actual past commands, selected observation availability, unnamed inferred codes and conditional movement remain limitations. Full-command/category quality, reliability, multiple seeds and playing strength are unestablished. The 80% target is explicitly false in the result artifact.
