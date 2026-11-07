# Intercontinental Fish GRU action predictor

## Current learned algorithmic phase

V10 measures executable candidate coverage before learning causal command selection.
A00 improves complete-command agreement mainly through recall; A01's shared
candidate scorer loses against A00. A separate decoder diagnostic increases
accuracy while worsening macro F1 and ward performance. None is promoted or meets
the original category targets. See [V10 results, evidence and ranked next work](experiments/v10/INDEX.md).
Both reserved partitions stay sealed; all prior V4–V9 artifacts are retained.

## Current completed movement pair

G01 does not improve the unrestricted G00 control: 11,505 versus 11,510
complete commands, and it fails the fixed continuation guard. No identical
repeats or promotion. Actual serving-cost accounting is corrected separately.
See the [current results and next classifier priority](experiments/v9/INDEX-G01.md).

## Prior movement control

G00, the unrestricted two-expert movement control, gets 11,510/14,439 complete
commands right (79.71%), 38 more than P05. This small single-seed development
gain does not meet the reliability targets or justify certification. The
continuation/change treatment G01 has not run. See the
[current V9 index](experiments/v9/INDEX-G00.md).

## Prior V9 entity studies

The matched trainable-GRU entity-input pair did not improve complete-command
prediction: E00 has 11,461/14,439 strict successes and E01 has 11,437, versus
P05's 11,472. Neither is promoted or triggers identical repeats. See the
[V9 study index](experiments/v9/INDEX.md) for the measured bottlenecks, full
category results, uncertainty, serving costs and next substantial hypotheses.
E01 has passed its completed-fit execution/negative-result review. Reserved games remain sealed.

## Preserved V8 priority study: 7 November 2026

The predictor has **not met the reliability targets**. The latest reviewed
experiment, P05, gets 11,472/14,439 complete recorded commands right (79.45%),
including 1,287/2,362 moves (54.49%) and 71/576 priority commands (12.33%).
Action-type accuracy is 88.73%; macro F1 is 0.63239. These results use five
repeatedly reused development groups, not untouched-test performance.

M01 remains the preserved whole-model baseline. P03 and P05 change only
priority parameters; action, movement and ability paths remain unchanged.
P05 recovers 109/576 exact priority values, six rare cases and one unseen case,
but misses its fixed 125-value gate. Wrong-sign predictions increase81?92.
Neither P05 nor the earlier P04 input study triggers identical seed repeats.
No certified replacement exists; all prior checkpoints and negative results remain.

See the [V8 study index](experiments/v8/INDEX.md),
[P05 results](experiments/v8/P05-REPORT.md),
[P05 failed gate and adverse outcomes](experiments/v8/P05-TAIL-NOTE.md),
[P04 missed-gate report](experiments/v8/P04-INPUT-NOTE.md), and
[all A01 baselines](experiments/v8/A01-REPORT.md). Both the 75 new validation
games and the 75 final-test games remain unopened. All 43 shop arguments remain
unassessed strict failures. This is offline research; it has not changed or
deployed a playing bot, and it establishes no strategy-similarity percentage.

## Preserved earlier studies

**Additional-data study:** [V5 controlled retrain](experiments/v5/RESULTS.md)
uses 350 newly collected training games from a frozen 500-game collection.
Three matched seeds are complete. The new public-map encoder is documented in
[SPATIAL.md](SPATIAL.md); its [frozen V6 protocol](experiments/v6/plan.json)
uses the same validation groups. The 75 new final-test games remain sealed.
The completed [V6 comparison](experiments/v6/RESULTS.md) retains M01: map inputs
improved movement in the matched seed but regressed `cast_1` targeting.

**Preserved V4 baseline:** [fixed-benchmark V4 report](experiments/v4/RESULTS.md) and
[usage/reproduction](RELIABILITY.md). Ten experiments and three-seed checks did
not meet the proposed reliability targets. The historical V1/V3 results below
remain preserved as baselines; they are not the current reliability claim.

The continued experiment is documented in [EXPERIMENTS.md](EXPERIMENTS.md).
It audits the original result, freezes its test groups, compares a stateless model,
and adds recorded destination/aim prediction. Full per-action metrics and confusion
matrices are in [the frozen-test report](experiments/v3/RESULTS.md).

Trained on 6 November 2026. The replay manifest identifies the team as
**Intercontinental Fish**, ID `1890540d-1ffc-4847-adbf-d0d08772f268`.

The original downloads are in
`C:/Users/Subhan/.t3/worktrees/starter-python/t3-e88e3f9a/.cambc/replay-evaluation/2026-11-05-500/replays`.
The collection contains 250 games per cohort, including other teams. Training uses
the existing, hash-verified personal PRE extractions in
`C:/Users/Subhan/.t3/worktrees/starter-python/t3-e88e3f9a/.cambc/replay-evaluation/micro-expanded-v1.5`.
Original artifacts in that worktree are read only.

## Historical V1 result and artifacts

The selected checkpoint predicts the next recorded action **type**, including
ability slot, with **88.27% test accuracy** and **46.93% macro F1** on 15,604 sampled
actions from 25 games in five match groups. The macro score shows that performance
is uneven across classes; overall accuracy should not be read as reliable rare-action
prediction. See `metrics.json` for each class's support, precision, recall and F1.

Validation loss selected epoch 12; training stopped at epoch 18. The test set was
not used to select model settings. A reporting iteration bug required an identical
deterministic rerun; no model, split or hyperparameter choices changed after testing.

Artifacts, relative to the repository root:

- `.cambc/action-predictor/run-1/model.pt`: trained model, normalizer, feature schema and labels.
- `.cambc/action-predictor/run-1/metrics.json`: metrics, baselines, confusion matrix and training history.
- `.cambc/action-predictor/data/dataset.json`: source hashes, game identities and group splits.
- `.cambc/action-predictor/data/data.npz`: prepared numeric sequences.

These generated artifacts and the isolated Python environment are ignored by Git.
The source and this guide are ordinary repository files. Keep the checkpoint and
dataset manifest together if archiving the experiment.

## Model and evaluation boundary

A 200-feature personal visible-state vector passes through a linear/ReLU encoder.
The GRU receives that encoding plus a 16-dimensional embedding of the previous
actually observed action. Its 96-dimensional recurrent state feeds a classifier.
Classes include move, blocked move, attack, two casts, end, shop, recall, submit,
altar, priority, teleport, cancel and ward, plus a training-vocabulary unknown class.

Training has 120 games / 24 groups / 73,568 actions; validation has 25 games / five
groups / 14,439 actions. All 170 raw replay identities are unique. Whole match groups
stay together across partitions. Normalization and the action vocabulary use only
training data. Extraction file hashes and Fish team/actor ownership are verified.

Sequences contain all decisions within a sampled complete turn. Hidden state resets
at the turn boundary: the sampled turns are separated by gaps and cannot safely be
treated as consecutive rounds. Prior-action inputs are shifted labels; the current
action and POST observation never enter their own prediction. Only visible entities
affect features. Neither match outcomes nor event headers/cursors enter the model.

These are new disjoint partitions of previously exploratory games, not a pristine
external benchmark. Previously reserved games remain excluded. The existing sample
selects up to 32 complete turns per champion per game; reported metrics weight sampled
actions equally rather than estimating all turns with inverse sampling weights.
The historical games use engine 2/3; compatibility with engine 4 has not been tested.

This is one-step prediction given observed history. It does not predict movement
destinations or attack targets, enforce action legality, establish playing strength,
or plug a neural network into the WASM bot runtime.

## Reproduce

Run from `F:/Code/battlecode-26-27` in PowerShell. CPU training takes roughly a minute
on this machine; no GPU installation is needed.

```powershell
python -m venv .venv-action-predictor
./.venv-action-predictor/Scripts/python.exe -m pip install -r tools/action_predictor/requirements.txt
./.venv-action-predictor/Scripts/python.exe -m tools.action_predictor.train prepare --source C:/Users/Subhan/.t3/worktrees/starter-python/t3-e88e3f9a/.cambc/replay-evaluation/micro-expanded-v1.5 --out .cambc/action-predictor/reproduction-data
./.venv-action-predictor/Scripts/python.exe -m tools.action_predictor.train train --data .cambc/action-predictor/reproduction-data --out .cambc/action-predictor/reproduction-run
./.venv-action-predictor/Scripts/python.exe -m unittest tools.action_predictor.test_predictor -v
```

Defaults: seed 26, batch 128, AdamW learning rate .001, weight decay .0001, gradient
clip 1, maximum 40 epochs, validation-loss patience six, deterministic CPU execution
with four Torch threads. Cross entropy ignores padded labels.

## Use from Python

```python
from tools.action_predictor.model import Predictor

predictor = Predictor('.cambc/action-predictor/run-1/model.pt')
predictor.reset()  # At the start of every champion turn.
probabilities = predictor.predict(personal_pre_observation)
# After observing the action actually taken, obtain the next PRE observation:
probabilities = predictor.predict(next_personal_pre_observation, previous_action='move')
```

Observations follow the existing extractor's `observation` schema: `own` and
`entities` with personal visibility `known` flags, positions, health, items,
cooldowns and ability properties. `predict()` returns action names and probabilities
in descending order. Maintain a separate Predictor for each concurrently tracked
actor, and reset at a new turn. The API requires observed action history rather
than silently feeding its own predictions back.

Seven tests cover visibility filtering, translation invariance, shifted history,
turn boundaries, causal outputs, online/batch equivalence, padding and checkpoint
inference. Group separation, original reservation exclusion and replay identity
uniqueness were also checked on the prepared corpus.
