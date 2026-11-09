# Automatic behavior segments

This package discovers **unnamed persistent behavior codes** from Fish replays and learns to predict those codes causally. It requires no manually named objective classes or manually marked boundaries. Its first matched experiment fails the movement/goal improvement gates; it is research code, not an enabled playing policy.

The fitted neural classifier selects code 0 on every evaluation query. Its 64.8% accuracy is therefore majority-class accuracy, not successful objective classification. A separately frozen postfit diagnostic in `persistence.py` classifies the completed prior turn against the same prototypes and assumes persistence: 72.96% code agreement and 43.55% balanced recall on evaluation. This performs no additional optimization and establishes neither goal-location accuracy nor movement improvement.

The discovery algorithm is a minimum-duration switching centroid model, a small semi-Markov clustering method. It is **not a reproduction of CompILE**. Hard EM alternates an exact dynamic-program assignment with masked centroid updates. Each code change costs a fixed penalty and segments last at least two own turns. There is no forced boundary at an attack, ward, cast or recall. No absolute position or direction enters the discovery descriptor. The number of available codes (eight), duration constraint, feature design and penalty are human-chosen hyperparameters; the code assignments and internal boundaries are learned.

The retrospective descriptor contains observed own-turn command counts, walking amount, and available changes in health, gems, gold and distances to known objectives/threats. Changes in nearest-entity distance can reflect entity changes as well as movement. They are descriptive evidence, not verified causes or rewards. Missing changes remain masked.

The data has 320 nonoverlapping windows of 32 actual own turns across the same previously exposed 32 fitting and eight evaluation groups as V42. Each window has at least eight cached current personal PREs. Missing observations remain rows with masks; no turns are stitched away. The query is the first nonadministrative action in an own turn. The offline segment endpoint is the PRE position at the start of the following segment, when observed and reachable. The last segment is right-censored. Window edges are administrative and must not be interpreted as discovered objective boundaries.

The causal network receives the current full-resolution public map, all known entity/own fields with masks, current round, and the preceding completed-turn descriptor. A GRU maintains history. It predicts a distribution over behavior codes and uses the expected code embedding in separate goal and movement heads. Current/future descriptors, inferred codes and endpoint labels never enter its forward inputs.

S00 and S01 have identical initialization, architecture, schedules, data and goal/movement losses. S01 additionally learns the discovered code using an auxiliary classification loss. This tests code supervision against the same architecture without that supervision. Both arms use the learned segment endpoint labels, so it does not isolate automatic segmentation against a fixed-horizon alternative.

Experimental streaming inference:

```python
from tools.action_predictor.behavior_segments.predictor import BehaviorPredictor

predictor = BehaviorPredictor('S01')
result = predictor.predict(
    current={'observation': observation, 'supplement': supplement},
    route=public_route,
    round_number=current_round,
    previous=completed_previous_turn_descriptor,
    previous_mask=previous_descriptor_availability,
    state=previous_result_state,
)
# result: code probabilities, inferred endpoint, A* step, next recurrent state
```

Use a separate state per champion and call at the same own-turn cadence as training. The helper resets at 32 turns or an observed actor change. Reset it explicitly at unknown history gaps. A missing observation can be passed as `current=None`; a dead/shop observation without position remains available for code prediction but has no invented goal position. `data.descriptor` can construct completed-turn descriptors using only earlier commands and observations through the current PRE. Never pass a descriptor of the current, not-yet-completed turn.

Checks:

```text
.venv-action-predictor/Scripts/python.exe -m unittest tools.action_predictor.behavior_segments.test_segments tools.action_predictor.behavior_segments.test_model
.venv-action-predictor/Scripts/python.exe -m tools.action_predictor.behavior_segments.verify
```

Also run `tools.action_predictor.behavior_segments.test_inference` for actor reset and past-only prototype forecasting contracts. `persistence.forecast(previous, mask, fitted, default_code)` exposes that simple diagnostic forecast separately from the neural policy. Its targets remain automatically inferred hindsight codes.

The frozen protocol permits one six-pass fit per arm. Existing attempt directories prevent accidental repeats. The original failed data-density attempt and origin-unavailable preflight are preserved; neither performed optimizer updates. Read `experiments/v43/REPORT.md` for results, coverage, limitations and interpretation.
