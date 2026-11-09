# V53: direct destination-weight updates

**Mixed result; replacement criteria fail.** Updating 1,840 existing destination parameters increases exact endpoint matches from **15/98 to 19/98**, improves goal likelihood, and raises correct goal-guided A* moves from **10/513 to 42/513**. However, endpoints within two tiles fall from **51/98 to 50/98**, and mean error worsens slightly. The original destination checkpoint remains the default; the edited weights are a separate experimental artifact.

## Weight inspection and intervention

The original query and goal-head tensors are finite and nonzero. Their norms do not establish useful strategy or identify a unique bottleneck. The final goal bias adds the same scalar to every valid tile, so editing it alone cannot change normalized probabilities or the chosen destination. That scalar remains frozen.

The intervention updates only `query.weight`, `query.bias`, `goal.0.weight`, `goal.0.bias`, and `goal.2.weight`: **1,840 parameters across five tensors**. All five change. The map encoder, recurrent code predictor, code embedding, original movement head and V52 movement correction are unchanged. There are no new layers, input features, inferred code meanings or decoder changes. The selected weights load into the original `SegmentPolicy` architecture.

To make fitting practical, fixed map features and recurrent inputs are cached. The original pointwise convolution is factored into equivalent spatial and context linear terms; its maximum initial logit difference on the 2,099 fitting examples is **9.54e-7**. Synthetic forward/loss/gradient parity tests pass. A separate postfit check runs the original full network for all selected fitting-fold goal queries: every destination matches the cached selection prediction exactly, and mean NLL differences stay below 2e-6. Deployment continues to use the original full-network forward path.

## Data and selection

The unchanged next-segment endpoint rule is applied to all 1,607 existing fitting windows. This provides **2,099 goal examples from 32 games**, with exact preservation of all **369 original fitting labels**. These are replay-inferred endpoints, not Fish's internal goals. Future frames and discovered codes are used only to construct supervision; they never enter the destination inputs.

Four fitting-game folds use their matching V49 code checkpoints. Each trains on expanded windows from the other 24 games and validates only its original held-game goal queries. Two learning rates, 0.0003 and 0.001, run for 16 epochs. Epochs 0, 4, 8, 12 and 16 are eligible. Selection maximizes within-two correctness, then exact correctness, then minimizes mean error and NLL, with deterministic duration/rate tie-breaks.

The selected rate is **0.001 at epoch 16**, selected before evaluation. Pooled fitting validation changes from 199/369 to 204/369 within two tiles, and from 53/369 to 64/369 exact. Mean error changes from 1,398/369 to 1,367/369 tiles, and NLL from 4.9441 to 4.5535. The selected setting is refitted once on all 2,099 examples for **2,112 updates / 33,584 endpoint presentations**. No evaluation-based switch or extra fit is performed.

The backbone and discovery had earlier fitting-group exposure; these folds evaluate further head updates, not untouched end-to-end generalization. All evaluation games were already exposed research data.

## Same evaluation queries

| Metric | Original V49/V52 destinations | Edited V53 destinations |
| --- | ---: | ---: |
| Exact endpoint / 98 | 15 (15.31%) | 19 (19.39%) |
| Endpoint within two tiles / 98 | 51 (52.04%) | 50 (51.02%) |
| Mean Chebyshev endpoint error | 3.3265 tiles | 3.3367 tiles |
| Goal NLL | 5.3895 | 4.9899 |
| Correct goal-guided A* moves / 513 | 10 (1.95%) | 42 (8.19%) |
| Correct direct V52 moves / 513 | 226 (44.05%) | 226 (44.05%) |
| Correct inferred codes / 699 | 573 (81.97%) | 573 (81.97%) |

The within-two comparison rescues two endpoints and regresses three. The required five-point within-two gain and lower mean error both fail. Exact accuracy, NLL and A* guards pass, so `all_checks_pass=False` is the correct outcome. The A* improvement is still far below the direct movement head and does not justify replacing it.

Postfit descriptive diagnostics show less collapse to the current tile: among the 98 endpoint-labeled queries, current-position predictions fall from **82 to 36**. Across all 699 observed queries, 374 goal choices change. This is not proof of recovered long-term objectives. Among the 46 labeled goals farther than two tiles from the current position, exact accuracy remains **0/46**. Within-two accuracy on that subset rises only from 1/46 to 3/46, and mean error stays 5.9348 tiles. The four additional exact matches are all in the near-goal subset. These diagnostics did not select checkpoints or trigger additional training.

## Verification and artifacts

**Sixteen focused tests pass.** Parent verification reconstructs all 2,099 labels and spatial feature caches, all five recurrent-input banks, all 40 validation measurements and the frozen selection. It checks every saved optimizer schedule, denominator, finite gradient/state, selected tensor and unchanged non-goal tensor. All **3,644 original fitting/evaluation forecasts** reproduce exactly. Code and direct movement predictions and likelihoods are identical to V52; 32 streaming turns match. The supplemental full-network check reproduces all 369 selected fitting-fold destinations. No subagents or delegated reviews were used.

- Edited checkpoint: `.cambc/action-predictor/v53/selected.pt`.
- Experimental loader: `behavior_segments.destination_predictor.DestinationWeightPredictor`.
- Existing default remains `CodePathPredictor`, with the original goal weights.
- Evidence: `plan.json`, `cache.json`, `selection.json`, `refit.json`, `result.json`, `comparison.json`, `verification.json`, and `parity-supplement.json`.

The edited loader preserves the V52 direct movement correction and exposes changed `goal` and `astar_movement` fields. Maintain the existing per-actor causal state/reset contract. `promoted=False` remains explicit. Original checkpoints and the playing bot are unchanged.

This is one weight-only research intervention with inferred and sparse endpoint supervision, observed command histories, availability-selected windows and repeatedly used groups. It does not establish verified intent, reliable long-range destination prediction, autonomous strategy, full-command accuracy or playing strength. Historical reference, category-90%, reliability and multi-seed requirements remain unmet. The negative replacement verdict does not prove an architectural ceiling or observation insufficiency.
