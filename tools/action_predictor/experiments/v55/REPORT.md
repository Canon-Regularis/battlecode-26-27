# V55: bounded direction-bias edits

The selected bias edit reaches **229/513 correct evaluation moves (44.64%)**, two more than V54 and three more than V52. The user's 80% target needs 411 correct moves, leaving **182 missing**. Movement NLL worsens from V54's 1.5080 to **1.5211**; this trades a small accuracy gain for worse likelihood. V54 remains available as the lower-NLL alternative. Neither is promoted.

A fitting-data audit of V52 found 3,923 northwest predictions against 2,280 northwest labels among 12,318 moves. This motivated a bounded output-bias test, not a conclusion that class imbalance explains all remaining errors. V55 starts from the selected V54 model and changes only entries in its existing nine-way `backbone.movement.bias`. It introduces no layers, features, support changes or decoder rules.

Each fitting fold uses its matching V54 checkpoint. Four passes of coordinate search evaluate a fixed 0.02-spaced bias grid, optimizing training correct count, then NLL, then smaller absolute bias. Bounds 0.1, 0.3 and 0.6 are compared using only original held fitting-game windows; identity is eligible. The best bound is selected by pooled validation accuracy and NLL before full refit and outer evaluation. No neural optimizer updates occur.

The selected bound is **0.6**, scoring **938/1,997** validation moves versus V54's 912/1,997. Full fitting produces bias increments, in the original `OFFSETS` order:

```text
NW     N      NE      W     stay     E      SW     S     SE
-0.18 +0.18  -0.24  +0.10  -0.60   +0.24  +0.10 +0.30  0.00
```

Eight entries change; southeast is unchanged. The stay offset remains subject to the same support mask and is not a new command rule. All other model tensors are identical to V54.

On evaluation the edit rescues 24 errors and introduces 22, net +2. Code and goal outputs are exactly unchanged from V54: 573/699 codes, 51/98 endpoints within two tiles, and 10/513 A* moves. The direct movement result remains conditional on choosing movement, not complete-command accuracy.

Verification repeats all 16 fold calibrations including identities and the full-data calibration, reconstructs all five logit banks, checks selection and exact bias arithmetic, and reproduces all 3,644 final fitting/evaluation forecasts. Thirty-two streaming turns match. Focused tests cover bounded search, support exclusion and identity eligibility. No subagents or delegated reviews were used.

The opt-in loader is `MovementBiasPredictor`; weights are `.cambc/action-predictor/v55/selected.pt`. Original checkpoints and the playing bot remain untouched. Plans and hashes bind the cached forecasts and calibration traces; no evaluation labels guide the edit.

The earlier data and interpretation limitations still apply: repeatedly exposed groups, inherited fitting exposure, observed histories, inferred codes and sparse goal labels. This modest direction correction does not establish recovered objectives, reliable long-range goals, full-command quality or playing strength. The 80% target and historical category/reliability/multi-seed requirements remain open.
