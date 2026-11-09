# Replay-inferred goals and goal-guided movement

This is an experimental, separate **current map → goal distribution → A* next step** pipeline. The playing bot does not use it. V42's first fitted pilot fails its allocation test; it is not an improved replacement policy.

`evaluator.py` labels an achieved approach position before a future interaction. It uses the complete indexed actor chronology, validates continuous walking positions, and keeps labels separate from current inputs. These positions are **replay-inferred proxies**, never verified Fish internal goals. The preserved `evaluator_v1.py` attempt rejected every recall; V1 produced no labels. R2 permits explicitly cancelled recalls while checking position continuity.

`model.py` implements the independently trained goal network, full-map encoder, and A* movement adapter. The map retains its original resolution, including the largest 100×100 maps. Current entity fields use a dictionary learned from the fitting groups, presence indicators, and fixed signed-log numeric scaling. Every entity contributes to the set representation; known positions also contribute to a spatial raster. Hidden entity dynamics and identity indices are excluded. Unknown evaluation fields are counted, not added to the fitted dictionary.

The goal network predicts a categorical distribution over reachable tiles. Its weights are learned by gradient descent on goal labels; no prior action-predictor checkpoint is modified. The movement stage consumes the predicted goal and current movement mask. It uses unit-cost eight-neighbor A*, which is a pathfinding hypothesis, not a reconstruction of Fish's danger costs, dynamic future occupancy, or tie rules.

For experimental current-only inference:

```python
from tools.action_predictor.goal_position.predictor import GoalPredictor

predictor = GoalPredictor()  # verifies the local protocol and checkpoint bindings
prediction = predictor.predict(observation, supplement, public_route)
goal = prediction['goal']
next_step = prediction['movement']  # None if no path/step is available
```

`model.adapt_movement` leaves nonmovement destinations unchanged and retains an existing movement destination when pathfinding cannot supply a step. This adapter is available for experiments; it is not enabled in production.

Verification:

```text
.venv-action-predictor/Scripts/python.exe -m unittest tools.action_predictor.goal_position.test_evaluator tools.action_predictor.goal_position.test_model
.venv-action-predictor/Scripts/python.exe -m tools.action_predictor.goal_position.verify
```

The frozen pilot is one seed, twelve passes, 804 updates, final checkpoint only. Its immutable run directory prevents accidentally rerunning it. See `experiments/v42/REPORT.md`, the frozen protocol, and the saved verification receipt for results and limitations.
