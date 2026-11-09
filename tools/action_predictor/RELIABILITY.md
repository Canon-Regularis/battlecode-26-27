# Fixed-benchmark Fish prediction experiment

This page describes the completed V4 study. The subsequent
[500-game collection and V5 retrain](experiments/v5/RESULTS.md) now reserves
75 new final-test games, which remain sealed. See [SPATIAL.md](SPATIAL.md) for
the additional public-map encoding experiment.

The experiment budget is exhausted at **ten substantive fits**. The proposed
targets were **not met consistently**; this remains an experimental replay
predictor, not a certified reliable opponent model.

See [complete results](experiments/v4/RESULTS.md), including every run, per-action
precision/recall/F1/support, confusion matrices, per-family parameter accuracy,
top-k movement scores, destination errors, observable violation rates and
whole-group confidence intervals. CSV tables are under `experiments/v4/tables`.
Machine-readable validation and test evaluations contain all paired group intervals.

## What was frozen

`experiments/v4/benchmark.json` predates all V4 training. It fixes the old whole-group
partition: 120 training games / 24 groups, 25 validation games / five groups, and
25 previously exposed test games / five groups. Actual replay payload identities
remain disjoint. The source ledger confirms the old Fish reservation was already
inspected; the unopened reservation belongs to the candidate team. **There was no
certified untouched Fish final test at the V4 freeze.** The old exposed test was sealed for this
development and opened only after all configuration and checkpoint choices were locked.

The proposed .65 macro F1, +10-point movement gain, 10% loss reduction and no material
targeting regression were retained. Before training, "material" was specified as
more than two percentage points in conditional attack or either cast-slot accuracy.
Known action macro F1 always averages all fourteen named actions, including zero
for an absent rare class; the unused unknown label is excluded. This is stricter
than silently removing rare classes in resampled groups.

## What was investigated

- **Data quality:** original unzipped payload hashes, PRE-before-action cursors,
  actor ownership, shared-field snapshot equality, duplicate action IDs and gaps.
  No fabricated strategy/intent labels are used.
- **Observation encoding:** original 200 features versus additional PRE gold,
  stats, ward resources, public map geometry, reachable movement tiles and a
  17x17 spatial candidate representation. Unset utility-event `(0,0)` transport
  fields are removed from historical location inputs.
- **History:** comparable stateless models versus GRUs over the previous four
  or sixteen actually recorded own actions, including actions between sampled
  turns. This is event history, not sixteen complete observation frames. The
  longer-history experiment also adds class balancing, so those effects are not
  separately identified.
- **Training:** joint categorical action/coordinate likelihood, discrete-logistic
  priority likelihood, unweighted versus class-balanced objectives, deterministic
  training-only rare-turn augmentation and early stopping by validation joint NLL.
- **Architecture:** matched-size stateless and GRU encoders with conditional spatial
  rankers; paired augmented fits add identical personal movement and compatible-target
  constraints. A fixed full-support probability mixture retains contradictory labels.
- **Baselines:** action frequencies and previous-action transitions; frequency,
  persistence, nearest camp/altar, nearest compatible and lowest-health targeting;
  learned stateless variants. Reference choices use validation only.

The source-quality audit motivated a documented design amendment before training:
six development configurations plus two extra seeds for each selected GRU and
stateless configuration fit within the ten-run budget. After E01-E04 validation
exposed avoidable target-geometry errors, E05/E06 received the same constraint
change; `parameter-mask-amendment.json` records the evidence before either fit.
Neither amendment changed test membership, labels, metrics or numerical targets.

Augmentation adds **37,140 actions** in **7,669 complete rare-action turns** from
the original training replays only. It grows training from 73,568 to 110,708 actions.
All original training samples are retained. Validation/test samples are unchanged.

## Result and bottleneck

The validation-selected GRU configuration is **E06**, with E07/E08 checking seeds
27/28. Selection is frozen in `selection-lock.json`; the additional seeds do not
change the chosen configuration. The selected stateless configuration is E02,
repeated as E09/E10. The separate E05 stateless fit uses the same augmented data
and geometry constraints as E06, providing that controlled comparison too.

Across three GRU seeds on validation:

- Macro F1: **.542-.560**, below **.65**.
- Exact movement: **56.8%-58.5%**, versus the strongest simple baseline's **55.2%**;
  gains are **1.6-3.3 points**, below **10 points**.
- Observed joint NLL reduction: **12.3%-16.5%** against matching-seed learned
  baselines. This numerical point target passes, but some group-confidence lower
  bounds fall below a 10% reduction.
- Targeting regression: the fixed tolerance fails across the seed checks,
  especially slot-zero targeting. The selected seed's validation drop is **2.8 points**.

For the selected seed on the **previously exposed final test**: action accuracy is
85.6%, macro F1 .549, joint recorded-parameter exact accuracy 76.3% across all
15,604 roots, and 46.1% on the parameterized subset. Non-parameterized end/cancel/
recall actions make the all-root score easier; the subset score is reported to
avoid hiding that difference. Exact movement is 61.9% versus persistence at 60.8%,
top-3 is 87.3%, top-5 is 96.2%, and mean Chebyshev destination error is .59 cells.

The E06 test macro-F1 group interval is **.522-.571**, and movement is **58.0%-65.9%**.
These bootstrap intervals use only five groups and do not establish broad
generalization. Precision remains poor for utility actions: teleport .027 (two
examples), ward .087, and submit .136. Altar F1 is zero on three examples. Rare-turn
augmentation increased support and recall but did not solve calibration or the
uncertainty in those decisions. Movement gains over persistence are small despite
high top-k coverage; exact next-destination selection remains a bottleneck.

## Limits of the task and metrics

Labels are recorded action types, aim/destination coordinates and exact priority
integers. Original attack/cast entity IDs and some API arguments are absent from
the event format. Shop roots do not identify original item/count; immediate
inventory/gold deltas are retained as diagnostic labels. The model does not claim
to reconstruct the original transaction.

Joint NLL is a **partially observed** action+coordinate+priority likelihood. Joint
recorded-parameter accuracy counts unsupported shop arguments as errors. The
legacy JSON field `strict_full_command_accuracy` contains that recorded-parameter
score; **full original API-command accuracy is unassessed**, since omitted IDs and
arguments cannot be verified. Outside-window/missing-position predictions are
retained in loss and count as exact failures; none of the current recorded spatial
labels fall outside the chosen window.

The selected seed has 160 observable violations among 7,490 assessed test
forecasts (**2.14%**), or 1.03% of all roots. This combines exact personal movement
mask contradictions and partial resource/readiness checks. It is **not full engine
illegal-action rate**, which is unassessed. Recorded blocked attempts contribute
violations because they are genuine failed-move labels. The reader has movement
and restriction/shop queries but no general personal per-command legality query;
visualiser target masks do not certify full legality. No alternate actions or
matches were run to manufacture legality evidence.

Inputs use the Fish champion's personal view and earlier own action history.
Private gold/history are not generally available to an opposing bot. This
retrospective personal-view task should not be presented as live opponent
prediction from another team's fogged observations. Engine 2/3 data also does not
certify deployment compatibility with engine 4. No bot was deployed or changed,
and no PR was created.

## Use and reproduce

From the repository root, use `.venv-action-predictor/Scripts/python.exe` and the
pinned requirements in this directory. Existing experiment outputs refuse
replacement. The original V1 checkpoint and old report artifacts remain unchanged.

```python
from tools.action_predictor.reliable_predictor import ReliablePredictor

predictor = ReliablePredictor('.cambc/action-predictor/v4/runs/E06/model.pt', actor=actor_id)
# personal_pre, supplemental_pre and public_route come from read-only replay queries.
forecast = predictor.predict(personal_pre, supplemental_pre, public_route,
                             round_number=round_number, pre_cursor=pre_cursor)
# After an action was actually observed, preserve it across turns:
predictor.observe(event_cursor, recorded_step, action_round)
```

Maintain one predictor per actor and match. Do not feed forecasts back as observed
actions. History persists across turns, unlike the older V1/V3 API. The API rejects
future history or mismatched PRE cursors. Saved-checkpoint inference was checked
against a cached validation prediction, including rejection of a future event.

The reproducible workflow is `benchmark`, `rich_data`, `reliable_baselines`,
`augment`, `development`, then—only after the final candidate lock—`rich_data --test`,
`reliable_evaluate` and `reliable_report`, all as modules under
`tools.action_predictor`. The staged design and mask amendments are part of the
recorded development sequence, so rerunning from scratch should use a new artifact
root rather than overwriting this experiment. The external replay reader and
official assets are hash-bound in `reader-provenance.json`; original replay paths
remain in the preserved V3 dataset manifest.
