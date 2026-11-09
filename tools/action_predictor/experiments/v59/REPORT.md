# V59: joint movement weights reach 61.99%; 80% remains open

The selected checkpoint predicts **318/513 evaluation moves correctly (61.99%)**, up from V58's 309/513 (60.23%) and the original V52 correction's 226/513 (44.05%). Movement NLL improves to **1.2001**, from 1.2924 for V58. Inferred-code accuracy is **574/699 (82.12%)**, one more than V58. The code-retention and movement-NLL guards pass. The user's 80% target requires at least 411 correct moves and remains **93 short**.

This experiment updates **25,569 existing parameters** in the context projection, recurrent memory, base movement readout, geometry correction, observed-direction correction and previous-command correction. No inputs or layers are added relative to V58. The map encoder, code readout/embedding and goal query/readout remain frozen. The objective is movement cross entropy plus code KL with coefficient one to the matching warm-start code distribution.

Four fitting-game folds train on all expanded windows of the other 24 games and validate on the original 64 windows of their eight held games. Epochs zero, four, eight, twelve and sixteen are eligible. Selection maximizes pooled movement correctness while allowing at most one percentage point of code regression, then prefers lower movement NLL and earlier duration. Selection chose **epoch eight**, with 1,237/1,997 correct moves (61.94%) and 2,416/2,945 codes. Warm-start values were 1,213 moves and 2,422 codes.

The single full refit completed **808 updates / 98,544 movement presentations**. Expanded in-sample movement is 8,087/12,318 (65.65%). The unchanged 513 evaluation moves were assessed only after this selection. Relative to V58 the model rescues 21 errors and introduces 12. Endpoint within-two and exact accuracy stay at 51/98 and 15/98; the goal likelihood changes slightly through the recurrent inputs. Frozen goal weights do not guarantee identical goal outputs.

## Progress and remaining limitation

| Experiment | Evaluation moves correct | Accuracy | Movement NLL |
| --- | ---: | ---: | ---: |
| V52 original geometry correction | 226/513 | 44.05% | 1.5504 |
| V54 recurrent/movement weight updates | 227/513 | 44.25% | 1.5080 |
| V55 existing direction-bias edits | 229/513 | 44.64% | 1.5211 |
| V56 full-map update, retained epoch zero | 229/513 | 44.64% | 1.5211 |
| V57 explicit observed direction | 298/513 | 58.09% | 1.3246 |
| V58 explicit previous-command direction | 309/513 | 60.23% | 1.2924 |
| V59 joint adaptation with direction features | 318/513 | 61.99% | 1.2001 |
| Requested threshold | at least 411/513 | at least 80% | — |

The largest gain came from preserving signed history that the original descriptor omitted. V57 and V58 add causal features and small learned corrections; they should not be described as pure edits to existing weights. V54, V55, V56 and V59 do edit existing weights. All earlier results, including negative and mixed trials, remain preserved.

The saved fitting-error audit localizes remaining errors. Among fitting moves with a previous executed direction, the final model gets **6,459/6,761 repetitions correct (95.53%)**, but only **1,415/5,073 direction changes (27.89%)**. It gets 213/484 moves without prior direction correct. Changes account for 3,658 of the 4,231 fitting errors. These are **in-sample diagnostics**, not evaluation percentages. They support investigating how the model selects a new destination; they do not prove missing observations, recovered Fish objectives, an accuracy ceiling, or that another weight adjustment will reach 80%.

## Verification and use

Parent verification reproduced all 20 fitting-validation measurements, selection, initial states, schedules, actual loss denominators, finite gradients/optimizer states and frozen tensors. All 3,644 original fitting/evaluation forecasts reproduce exactly, and 32 streaming turns match. Twelve focused tests across V54–V59 cover causality, feature masks/resets, weight-only changes, supported decoding, gradients, accumulation and runtime parity. No subagents or delegated reviews were used, as requested.

The opt-in loader is:

```python
from tools.action_predictor.behavior_segments.trajectory_movement_predictor import TrajectoryMovementPredictor

predictor = TrajectoryMovementPredictor()
result = predictor.predict(
    current, route, round_number,
    previous=previous_turn_descriptor,
    previous_mask=previous_descriptor_mask,
    state=actor_state,
    previous_moves=completed_previous_turn_move_vectors,
)
actor_state = result['state']
destination = result['conditional_movement']
```

`previous_moves` contains executed `(dx, dy)` vectors from the completed previous own turn. An empty list means no moves; omitted history after the first query raises an error. No current-turn or future command may enter this list. Keep state separate per actor and reset it at genuine gaps; the predictor also resets at actor changes and the trained 32-turn boundary. The output is a destination **conditional on choosing movement**, not a complete command or independently chosen strategic objective.

The new joint checkpoint is `.cambc/action-predictor/v59/selected.pt`. Its loader verifies the bound architecture, prior research artifacts and weights. V58 remains available when exactly unchanged code and goal outputs are preferred. Original checkpoints and the playing bot remain untouched; this is not a promotion.

The same research evaluation has been repeatedly exposed, so these improvements are exploratory rather than clean generalization certification. Inherited fitting-fold exposure, actual previous commands, sparse/inferred goal labels, conditional movement and selected observation availability remain limitations. Category/full-command accuracy, calibration, multiple seeds and autonomous playing strength remain unestablished. `target_met` and `promoted` are both false.
