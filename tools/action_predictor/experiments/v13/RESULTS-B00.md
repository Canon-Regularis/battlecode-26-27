# Consistent command probabilities: B00 checkpoint, review pending

The loss and final decoder now use the same quantity:

`P(command) = fallback_weight * Q(command) + sum(matching_point_weights)`.

They sum equivalent explanations and use family-aware command equality. The
decoder considers the finite point pool plus the fallback's conditional modes;
every off-point command is dominated by a fallback mode. This gives exact MAP
in the modeled **observed representation**, including unassessed shop and
outside/missing-coordinate buckets. It does not establish probabilities over
unrecovered original purchase arguments or resolve ambiguous entity identity.

On all original DEV rows, the selected B00 winner's probability equals the loss
calculation to **4.5e-16 in log space**. There are **zero** cases where an
available correct point has higher modeled probability than the emitted command.
Thus the earlier opaque-fallback veto defect is removed from this path.

## Measured controls and baseline

| Predictor | Strict DEV correct / 14,439 | Action macro F1 | Observed joint NLL |
|---|---:|---:|---:|
| G00, original action-first | 11,510 | .6324 | .72656 |
| A00, original hard routing | 11,622 | .6407 | .68131 |
| D01, A00 weights with consistent decoding | 12,044 | .6130 | .68131 |
| Q00, fallback probability alone | 11,953 | .6204 | .72656 |
| U00, fixed .9 fallback/.1 point mixture | 11,953 | .6210 | .79292 |
| B00, new matched-study baseline | **12,061** | **.6246** | **.67606** |

D01 isolates decoding with unchanged A00 weights/library: **549 rescues and
127 regressions**, net422; paired whole-group accuracy interval **+2.606 to
+3.238pp**. Its macro F1 worsens. Likelihood is unchanged apart from numerical
precision. It is not promoted.

B00 adds repaired support and a newly fitted shared scorer, so its difference
against A00 must not be attributed to decoding alone. Against D01, B00 adds only
**17 commands**, with139 rescues/122 regressions. The paired strict interval
**-0.128 to +0.322pp** includes zero. Its loss improves by .00525; the paired
loss-difference interval is **-.00711 to -.00383**. These intervals use2,000
paired whole-group draws, seed20261106, five reused DEV groups, conditional on
checkpoint selection. They are not untouched or three-seed evidence.

B00 selected **round22 of28**, retaining all checkpoints; selected18,612 and
completed23,688 optimizer updates. It has36,482 trainable selector parameters.
The frozen fallback and argument models remain part of the complete predictor.
No repeat seeds or promotion are justified by these results.

## Selection and remaining failure modes

On the **same28,903 original natural-TRAIN rescue opportunities**, B00 rescues
**13,292 (45.99%)**, versus historical A00's3,814 (13.20%). This is a complete
configuration comparison involving new support/scorer/decoding, not an isolated
causal estimate for any one change.

On the new repaired-library opportunity set, B00 captures **13,999/33,846
(41.36%) natural TRAIN** and **677/1,861 (36.38%) DEV**. Comparable natural TRAIN
strict accuracy is85.66% versus83.53% DEV; these TRAIN predictions are in-sample.
Augmented TRAIN accuracy is79.04% and must not substitute for the natural
comparison. The repaired-library and decoder configuration still cannot emit
1,068 original DEV answers; another1,310 available commands are not selected.

Most net gain against G00 is recall: **+499 of551** net commands. Supported
category failures remain substantial:

| Category | B00 joint correct / support | G00 joint correct |
|---|---:|---:|
| Move | 1,387 / 2,362 | 1,318 |
| Blocked | 6 / 110 | 8 |
| Priority | 44 / 576 | 71 |
| Ward | 0 / 112 | 7 |
| `cast_1` | 71 / 243 | 95 |
| `cast_0` | 150 / 213 | 154 |
| Attack | 901 / 985 | 874 |

Movement is58.72%, below the65.21% original target. Macro F1 remains below.65;
loss reduction against G00 is below10%. Cast1 joint agreement loses24 commands;
its all-true-family parameter accuracy is still146/243, so this must not be
described as24 additional parameter errors. Every shop is still a strict failure with unavailable arguments;
sparse altar/teleport/submit remain uncertified. This baseline is not a
certified replacement.

## Causal serving and next work

All335 selected raw-PRE cases across25games/both engines reproduce B00 features,
descriptors, commands and fallback modes exactly. Maximum log-weight discrepancy
is7.7e-6; command-log-probability discrepancy4.7e-6. They include21 missing-position
cases and258 with some unavailable earlier PREs. Earlier actual own actions
update the filter only after they occur; no sampled-row stitching or smoothing.
The harmless diagnostic warning from subtracting matching unavailable `-inf`
weights is masked before error aggregation; those slots are not model NaNs.

The requested **fresh Sol xhigh review of B00** is next. After resolving its
findings, B01 adds current-goal geometry and B02 adds forward causal goal memory,
with the same architecture, repaired library, seed, sampler, loss, decoder and
selection rule. Neither has run. Memory snapshots are incomplete: TRAIN has
personal PREs for1.90million of8.02million traversed prior own roots. Unknown
history is explicit, and memory evidence is a declared proxy rather than Fish's
hidden intent. The paired study can test this proxy's usefulness; it cannot
establish that all persistent policies or observations have been exhausted.

See protocol-r3, B00-analysis, B00-selection, B00-probability-contract,
B00-causal-roundtrip and B00-completion JSONs. Both reserved partitions stay sealed;
no games, simulations, downloads or bot changes. PR11 remains DRAFT only.
