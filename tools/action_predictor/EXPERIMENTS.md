# Continued replay prediction experiments

## Audit and frozen baseline

The audit verified the actual unzipped replay payload for every original game:
170 unique payloads, zero duplicates within or across partitions. It checked all
103,611 saved action inputs against their personal PRE feature encodings and
recorded labels, strict PRE-before-event cursors, actor ownership and sequence
boundaries. Snapshot provenance relies on the prior hash-verified extraction and
its read-before-`replayNext` implementation; no games were executed or resimulated.

The baseline checkpoint is preserved at `.cambc/action-predictor/run-1/model.pt`,
SHA256 `fcb5e834aa5817dacd50f260f89044fe9f55eba20393533fc0723a6e708850ac`.
Its test confusion matrix reproduces exactly. The baseline's 25 test games in five
groups, plus all other original group assignments and original array checksums,
are frozen in [split-lock.json](experiments/v3/split-lock.json). The original
reservation from the source study is still excluded.

Further fitting uses the existing separate validation partition: 25 games in five
groups. Training uses 120 games in 24 groups. No test results select checkpoints
or hyperparameters. The final test is a fixed comparison of locked candidates,
not a fresh unseen corpus; it has already been reported and should not be tuned on.

## Experiment ledger

- **V1 baseline:** frozen 81,487-parameter GRU, no retraining. Action type includes
  ability slot. Its original checkpoint and metrics remain unchanged.
- **E1 stateless action model:** 78,543 parameters, two 192-wide ReLU layers,
  identical current-state inputs and normalization. It cannot see previous actions,
  sequence position or recurrent state. Validation loss selected epoch 8.
- **Initial structured attempt (`v2`):** aborted before target test scoring.
  Training-only inspection found that several ability events leave `from=(0,0)`
  while recording a valid aim in `to`. An overly strict origin check dropped
  reliable cast labels. Partial validation records are preserved under `v2`.
- **E2 corrected structured GRU (`v3`):** frozen V1 states plus a trainable spatial
  ranker for recorded destinations/aim coordinates. The action classifier is
  unchanged. A separate experiment config and target-data hash were locked before fitting.
- **E3 corrected stateless targets (`v3`):** the same ranker architecture takes
  current-state features instead of recurrent states. It is paired with E1 for
  joint action-type/coordinate scoring.
- **Simple baselines:** train-most-common action, prior-action transition table,
  and train-most-common valid coordinate offset per action family. No test labels
  fit any baseline. Offset baseline masks candidates using the same PRE rules.

All new fits use seed 26, deterministic CPU execution, AdamW at .001, weight decay
.0001, gradient clipping at 1, batch size 128, at most 40 epochs and six-epoch
validation-loss patience. Full histories and selected epochs are in the per-experiment
JSON reports. The experiment plan, data and candidate checkpoint hashes are locked
separately. Existing prepared data, checkpoints and locks refuse replacement.

## Target evidence and inference

Labels are direct recorded move destinations or attack/cast aim coordinates.
Moves require recorded POST movement confirmation and matching PRE origin. Ability
origin is the personal PRE actor position; an unset event `from` is not a movement
origin. No retreat/farming/intent annotations are invented.

Candidates are offsets within +/-8 cells, constrained to the map. Movement and
ground-capable casts consider every such in-map cell. Unit-targeted actions use
visible living compatible occupants from personal PRE state; self-only casts admit
only self. Candidate features never receive the recorded destination. Terrain,
paths and full legality are unavailable. Original entity IDs are not recorded:
a unique compatible occupant at a coordinate can be shown as a diagnostic, but is
not presented as an original entity-ID label.

On the frozen test, coordinate labels are supported for 2,691 moves, 958 attacks,
184 slot-zero casts and 253 slot-one casts. Three attacks lack a compatible visible
target and are excluded explicitly. No supported target falls outside the fixed
coordinate window. Reports separate cases with more than one candidate, exposing
trivial self-only/single-target successes.

Per-family scores condition on the recorded family, as in a teacher-forced
autoregressive head. **Joint action-type and coordinate scores** also require the
model's predicted family to be correct. Normal inference selects the family from
the action classifier before predicting its coordinate; it does not consume the
current recorded action or any POST state.

```python
from tools.action_predictor.model import StructuredPredictor

model = StructuredPredictor('.cambc/action-predictor/run-1/model.pt',
                            '.cambc/action-predictor/v3/E2-gru-targets.pt')
model.reset()  # Every champion turn.
forecast = model.predict(personal_pre_observation, width=40, height=30)
# After observing the action that actually happened:
forecast = model.predict(next_pre_observation, width=40, height=30,
                         previous_action='move')
```

The checkpoint verifies which baseline GRU its head was fitted against. Use a
separate predictor per concurrent actor. Supplying `family=` explicitly requests
a conditional coordinate forecast; otherwise the model predicts the family.

## Held-out finding

The GRU's original action result is reproduced, not improved: **88.27% accuracy,
46.93% macro F1**. The stateless ablation reaches **86.14%, 43.07% macro F1**;
the majority baseline reaches **28.30%**. History helps action-type prediction
modestly in this comparison. Rare classes such as blocked movement, wards and
submission remain poorly predicted; the class-level tables make this visible.

The new GRU coordinate head reaches **41.34%** exact conditional coordinate
accuracy, versus **34.85%** for the valid-offset baseline. However, the stateless
head reaches **43.25%** overall and predicts movement destinations better. The
GRU head is stronger on attack and slot-one aim in this run. Joint action-type
plus coordinate accuracy is **33.16%** for GRU and **33.55%** for the stateless pair,
on the same 4,086 supported target actions. This does not establish an overall
history benefit for target prediction.

Only five test groups and one training seed are represented. No statistical
significance, playing-strength gain or strategy-similarity percentage is claimed.
The deployed bot is unchanged and no matches were launched.

See [RESULTS.md](experiments/v3/RESULTS.md), `*-per-action.csv`, `*-confusion.csv`,
`comparison.html` and `final-test.json` for detailed counts, precision/recall/F1,
confusion matrices, coordinate metrics and coverage. All confusion matrices have
actual actions on rows and predictions on columns. Macro F1 excludes zero-support
classes and uses zero for undefined precision/recall.

## Reproduce the audit or a new experiment

From the repository root, with the environment from README:

```powershell
./.venv-action-predictor/Scripts/python.exe -m tools.action_predictor.audit --data .cambc/action-predictor/data --baseline .cambc/action-predictor/run-1 --out tools/action_predictor/experiments/v3
./.venv-action-predictor/Scripts/python.exe -m unittest tools.action_predictor.test_predictor tools.action_predictor.test_audit_targets -v
./.venv-action-predictor/Scripts/python.exe -m tools.action_predictor.experiment finalize
./.venv-action-predictor/Scripts/python.exe -m tools.action_predictor.report
```

To reproduce fitting, use fresh `--reports` and `--out` directories. First run the
audit to copy the identical frozen lock into the fresh reports directory; then run
`experiment prepare`, `experiment fit`, and `experiment finalize` with those paths.
This reuses the frozen partition, not new random splits. Finalization verifies
candidate hashes before scoring. Generated datasets and model weights remain
ignored under `.cambc`; audit locks and experiment reports are committed for review.
