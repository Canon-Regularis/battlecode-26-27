# V60: eight-turn waypoint planning does not demonstrate strategy

This experiment trains a longer-horizon waypoint predictor, routes toward its prediction with A*, and tests retaining that waypoint for eight own-turn queries. **All three predeclared success conditions fail.** The V59 direct movement predictor remains unchanged and is not replaced.

| Research evaluation | Result |
| --- | ---: |
| Predicted eight-turn endpoint within two tiles | 23/77 (29.87%) |
| Existing V59 goal on the same endpoint labels | 25/77 (32.47%) |
| Staying at current position | 21/77 (27.27%) |
| Eight-tile continuation of prior direction | 14/77 (18.18%) |
| Original V59 direct moves correct | 318/513 (61.99%) |
| Replanned waypoint + A* moves correct | 202/513 (39.38%) |
| Committed waypoint + A* moves correct | 111/513 (21.64%) |

The learned endpoint's mean Chebyshev error is 4.416 tiles, versus 4.390 for V59, 4.481 for staying put and 7.052 for direction extrapolation. On the 56 endpoints at least three tiles away, it gets 11 within two tiles (19.64%), versus nine for heading extrapolation and four for V59. This misses the predeclared five-point improvement over the best baseline. Better performance on that subset cannot override failed overall endpoint and movement conditions.

## Implementation

The MLP consumes 704 causal features: frozen V59 recurrent state and soft behavior code, current candidate geometry, observed direction and completed previous-turn movement features. It predicts an offset eight **own turns** ahead. Future frames and executed movements construct labels only, never forward inputs. Original model weights remain frozen. The new head is trained with SmoothL1 offset loss, not next-step imitation alone.

Labels require observed, located endpoints within the same 32-turn window. Integrating intervening executed movement must agree with every available intermediate PRE position. Observed death and inconsistent relocation reject an interval. Missing intermediate observations remain missing. This yielded 2,341 fitting labels across all 32 fitting games. These are predicted replay positions, **not verified Fish goals**; unobserved events and intent remain unknown.

Four fitting-game folds train on expanded windows from the other 24 games and validate on original held windows. The 412 validation labels select epoch eight from zero, eight, sixteen, twenty-four and thirty-two by mean endpoint error, then within-two count and earlier duration. Epoch zero is the zero-offset/stay predictor. No evaluation result selects weights. The full refit uses fitting labels only. The 77 evaluation endpoint labels and all 513 original movement queries are distinct denominators.

Predictions project to the nearest statically reachable tile. A* respects actual first-step movement support. Missing paths fall back to V59. The commitment variant retains its goal for eight own-turn queries or until reached; window/actor resets and observed missing position clear it, while missing frames age it. This is specified persistence, not learned goal duration or demonstrated strategic reasoning.

`StrategicWaypointPredictor` exposes `strategic_waypoint`, `goal_guided_movement`, `committed_waypoint` and `committed_movement` as experimental alternatives. Its existing `conditional_movement` remains V59. It requires the same completed-turn `previous_moves` history. No playing-bot integration or promotion occurred.

## Interpretation and verification

This is a negative test of this regression-based waypoint representation and commitment rule. It does not show that hierarchical planning cannot work. A single regressed position may average incompatible destinations, and a position eight turns later need not be the objective being pursued now; neither explanation is established causally by these scores.

Evaluation replays actual subsequent states and commands; it is **not an autonomous game rollout**. Even a positive result would establish only a longer-horizon imitation proxy. Eight own turns contain a variable number of moves. Goal completion, safe replanning under model-generated actions and playing strength remain untested. Preexposed partitions, inherited fitting-fold exposure, missing frames, selected label availability and a single seed remain limitations.

Direct parent verification reproduces labels, five feature banks, twenty validation measurements, selection and saved forecasts; checks initialization, schedules, finite optimizer states and final checkpoint identity; and checks 32 streaming turns plus commitment expiry/reset. Focused tests cover censoring, inconsistent displacement, missing observations, initialization, gradients and reachable projection. No subagents or delegated reviews were used.

Artifacts are under `experiments/v60` and `.cambc/action-predictor/v60`. Original checkpoints are preserved. This experiment establishes **neither improved movement nor longer-term strategy**.
