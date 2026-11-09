# Public map encoder experiment

The completed more-data GRU study is in [V5 results](experiments/v5/RESULTS.md).
The map experiment's fixed protocol is [V6 plan](experiments/v6/plan.json);
its output is [V6 results](experiments/v6/RESULTS.md) and
[the comparison](experiments/v6/comparison.html). Each fit retains its checkpoint,
configuration, epoch log, validation predictions and full metrics.

The dataset is unchanged: 433,071 training actions from 470 games/94 groups and
14,439 original validation actions from 25 games/five groups. The additional
75 validation and 75 final-test games remain unopened. Models are selected with
validation results only; the old exposed test is not scored.

## Added information

The SDK exposes static walls, holes, bushes, altars, both spawn regions and camp
spawn tiles. The new eight-channel raster contains these and an in-bounds mask.
The global view also receives the actor's personal PRE position. Dynamic hidden
camp state, unseen units, outcomes and future observations are excluded. Existing
personal observation/history inputs and recorded action/coordinate labels are
unchanged. Map IDs only select rasters and never enter the neural network.

A local 23×23 depthwise CNN produces a 17×17 destination-aligned feature field.
A global 32×32 CNN encodes terrain/objective layout. Their features join the
existing 16-action GRU context and destination ranker. Added residual projections
start at zero, preserving original GRU/head initialization and the baseline's
training-shuffle RNG stream. Every map row was checked against its cached personal
PRE position, recorded action, round and group.

The same architecture with every added map channel zeroed is the capacity control.
Original features, including the existing movement mask, remain present in that
control. Both first fits use seed 26. The predeclared promising-model rule permits
two further map fits with seeds 27 and 28; the capacity control has one seed and
does not establish control consistency across seeds. Training settings, losses,
class weights, normalization, epoch cap and joint-NLL checkpoint rule are unchanged.

Original benchmark targets and reference models are preserved for historical
comparability. Direct same-data GRU/control comparisons are also reported; passing
an original target does not imply beating a newly stronger control by that margin.

## Reproduce

From the repository root using the original training environment:

```powershell
./.venv-action-predictor/Scripts/python.exe -m tools.action_predictor.spatial_experiment --freeze-only
./.venv-action-predictor/Scripts/python.exe -m tools.action_predictor.spatial_data
./.venv-action-predictor/Scripts/python.exe -m tools.action_predictor.spatial_experiment
./.venv-action-predictor/Scripts/python.exe -m tools.action_predictor.spatial_report
./.venv-action-predictor/Scripts/python.exe -m unittest tools.action_predictor.test_map_model
```

Existing experiments/checkpoints are verified and reused, never overwritten.
`execution-lock.json` archives source snapshots and package versions;
`data-ready.json` records input hashes. Exact commands, including static map
queries, are appended to `.cambc/action-predictor/v5/commands.jsonl`.

## Replay inference

```python
from tools.action_predictor.map_predictor import MapPredictor

predictor = MapPredictor('.cambc/action-predictor/v6/runs/S01/model.pt', actor=actor_id)
# Append actual past actions only, using their recorded cursor and round:
predictor.observe(observed_cursor, recorded_step, observed_round)
prediction = predictor.predict(personal_pre_observation, personal_pre_supplement,
                               public_static_map, round_number, pre_cursor)
```

Create a new instance per actor/game. `public_static_map` follows `public_map.cjs`:
`route` contains dimensions, blocked tiles, altars and both spawn rectangles;
`walls`, `holes`, `bushes` are flattened tile indices; `camps` contains static
spawn coordinates. Team ordering must match the observation. This helper accepts
recorded observation dictionaries and executes no SDK actions.

Movement/target exact and top-k scores condition on the recorded action type.
Joint scores also require the predicted type to match. Original target entity IDs
and shop arguments are unavailable; unassessed shops count as failures in joint
recorded accuracy. Movement error uses the unchanged 16-cell penalty for
unrepresentable predictions. Full engine illegal-action rate is unassessed;
observable violations use the existing partial movement/readiness/resource checks.
Held-out match groups may share maps with training games.
