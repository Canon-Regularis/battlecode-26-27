# V8: category audit and isolated priority studies

The complete goal remains unmet: at least 90% joint correctness in **every**
recorded action category, including exact required arguments, on each of three
training seeds. Original macro-F1, movement, loss and targeting requirements
remain binding. No candidate is a certified replacement or playing bot.

## Frozen evidence boundary

Training contains 433,071 rows from 470 games in 94 groups. Development contains
the original 14,439 rows from 25 games in five groups. Group and replay-payload
identities are disjoint. The 75 new validation and 75 final-test games stay
sealed; the old exposed test is unused in V8. No new matches, replay downloads
or deployment were performed by these studies.

The original M01 audit reproduces 3,028 failures: 1,627 wrong types, 1,359 wrong
parameters after correct types, and 42 correctly typed shops with unavailable
arguments. All 43 shops are strict failures. The [amendment](audit-amendment-01.json)
binds the expanded provenance and separates successful-move violations from
blocked forecasts. Full engine legality remains unknown.

## Completed experiments

| Study | Change | Measured result and interpretation |
|---|---|---|
| P01 | Matched logistic-head refit; recovered channels zeroed | 22/576 exact priority values, 15/576 joint. A control, not recovered-input benefit. |
| P02 | Same head plus causal priority inputs | 15/576 exact, 11/576 joint. Negative result versus P01. No repeats. |
| P03 | Training-only absolute integer modes plus learned full-support logistic fallback | 96/576 exact, 57/576 joint. Larger output package: 87,528 head parameters versus 336. Rare/unseen failures and twelve errors above 1,000 remain. |
| P04 | Same P03 head with the 39 recovered channels zeroed | 71/576 exact, 49/576 joint. P03's 4.34-point exact gain misses the fixed five-point gate. No identical matched repeats triggered. |
| A01 | Thirteen fixed signed-copy and residual-frequency baselines | Best exact baseline: 40/576 values, 30/576 joint commands. Different families win likelihood and integer error. All families reported; none adopted. |

Reports: [P01](P01-REPORT.md), [P02 pair](PRIORITY-LOGISTIC-PAIR.md),
[P03](P03-REPORT.md), [P03 adverse strata](P03-TAIL-NOTE.md),
[P04](P04-REPORT.md), [P04 gate](P04-INPUT-NOTE.md), [A01](A01-REPORT.md).
The machine-readable reports and CSVs preserve type and joint metrics,
both parameter-accuracy denominators, false positives, losses, support and
whole-group uncertainty. The chronological command snapshot is
[commands-through-A01.jsonl](commands-through-A01.jsonl).

P03's full observed joint NLL is 0.749362. The strongest A01 likelihood hybrid
has NLL 0.779098, giving an additional 10% reference of 0.701188; P03 misses it.
Likelihood excludes unavailable purchase arguments, while strict correctness
counts those arguments as failures. Action/spatial predictions are unchanged
from M01. Negative copying predicts one of four values absent from training and
five rare-value commands correctly, but has much worse overall likelihood and
exactness than P03. No single metric supports adopting that rule.

## Correctness, uncertainty and remaining work

The priority data chain verifies every original row, game offset and upstream
receipt, including 306,834 setter checks and 403,135 rollover checks. The new
inference paths preserve personal PRE perspective, exact earlier own-action
order, availability and gaps. Target headers and POST diagnostics never enter
their feature arrays. Current/scheduled values and actual earlier priority
arguments are recovered without clipping; latest arguments outside the history
window remain available.

P03/P04's 75-target, 25-game inference roundtrips and every saved raw priority
output reproduce. The corrected A01 preparation passes 35 correctness tests
and six training-only stream probes. Its interrupted pre-freeze preparation and
half-integer tie correction remain explicitly preserved. Tests establish
extraction/inference correctness; measured predictions establish quality.

Bootstrap intervals condition on selected checkpoints and five reused groups.
A01's thirteen comparisons are pointwise, not multiplicity-adjusted. No V8
three-seed confirmation or untouched evaluation is established. Two altar and
two teleport examples cannot certify reliability. Frozen priority type decisions
cap joint priority correctness at 343/576 (59.55%), even with perfect arguments.

Priority residual learning and action discrimination remain separate future
hypotheses. Frequency imbalance, movement inputs, ward coverage, ability
targeting, end/cancel semantics, blocked outcomes, objective conditions and
original purchase-command recovery are still open. The prior map/history
candidates' failed targeting guards remain valid negative evidence.

## Artifacts and reproduction boundary

Checkpoints, every epoch, raw replay evidence and prediction archives remain in
the ignored `.cambc/action-predictor` workspace. They are **not** bundled in Git;
their hashes, configurations and provenance receipts are in the reports.
The executable sources are versioned, as are the derived analysis-script text
snapshots. Additional preserved runtime-source snapshots and pinned reader
assets remain in the ignored workspace. Historical manifests bind that workspace and
pinned runtime assets. Auditing them requires those exact local artifacts;
these are not portable, data-free training examples.

The broader packaging check passes 93 source/downloader unit tests, using the
original workspace data and `tools` on `PYTHONPATH`; see the
[test receipt](pr-source-tests.json). The first invocation's import-layout
failure and the corrected runner/output remain preserved. No matches or real
downloads are performed by that test suite.

In the prepared original workspace, run the correctness/audit commands with
`.venv-action-predictor/Scripts/python.exe`, for example:

```powershell
./.venv-action-predictor/Scripts/python.exe -m tools.action_predictor.priority_verify
./.venv-action-predictor/Scripts/python.exe -m tools.action_predictor.priority_modes_roundtrip P03
./.venv-action-predictor/Scripts/python.exe -m tools.action_predictor.priority_modes_control_roundtrip P04
```

Completed experiment IDs refuse refitting or reevaluation. A new experiment
needs a new frozen protocol and the required fresh review; do not rewrite old
receipts to accept changed sources. Text snapshots of ignored report scripts
must be restored to their recorded original paths before running them. No
replay download or playing-bot execution is needed to audit existing artifacts.
