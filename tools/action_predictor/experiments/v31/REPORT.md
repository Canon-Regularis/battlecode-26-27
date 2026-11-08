# Destination-conditioned entity attention: negative result

The matched E01 treatment does not improve movement over E00. Neither replaces
the stronger retained predictors. This is an offline imitation experiment, not
evidence that the model learned high-level strategy or improved playing strength.

Both arms train movement execution and the causal hierarchy jointly. E00 attends
to current personally known entities once per latent state; E01 attends separately
for each candidate destination. Both use identical input sets, parameter shapes,
initial tensors, sampling, reset boundaries, loss and checkpoint rules. No entity
identity numbers, future targets or hand-labelled strategies enter prediction.

| Selected predictor | Complete commands /14,439 | Complete moves /2,362 | Changes /1,158 | Continuations /1,198 | Joint NLL | Macro F1 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| E00 control | 12,117 | 1,343 | 292 | 1,048 | 0.636830 | 0.596967 |
| E01 treatment | 12,098 | 1,335 | 288 | 1,044 | 0.637624 | 0.615791 |

E01 loses 19 complete commands and eight moves, including four changes and four
continuations. It fails the required +24 moves, +12 changes and lower full-DEV
NLL conditions. The continuation loss stays within the half-point limit and
attack/cast targeting stays within the two-point limit against E00. Higher
macro F1 does not rescue the failed movement hypothesis.

The stronger references remain binding. E01 trails L02 by 30 complete moves
and JP02 by 29; both retain 1,089 continuations versus E01's 1,044. E01's
conditional cast-1 accuracy is 136/243, versus 144/243 for L02/JP02 and 146/243
for G00, exceeding the original two-point regression allowance. Ward remains
0/112 complete commands. All 43 shop rows remain strict failures because their
purchase arguments are unavailable. The full result files preserve every
category, conditional and joint score, false positives, original row denominator,
group comparisons and genuine consecutive-window diagnostics.

Both arms select round six (10,456 updates), after twelve completed rounds
(20,910 updates), using the original complete-DEV NLL rule. Each has 159,867
trainable parameters. All original 433,071 TRAIN and 14,439 DEV rows remain;
natural/augmentation-only TRAIN strata are in-sample, not held-out evidence.

The prefit implementation and E00 passed independent Sol xhigh reviews. E01's
fresh postfit review is pending. No identical seed repeats or promotion follow
this failed contrast. Both reserved 75-game partitions remain sealed. No matches,
replay downloads, bot/runtime changes or deployment occurred.

This experiment tests candidate-to-entity execution relationships, not persistent
entity-bound objectives. Unknown-prefix resets across missing roots and eight-node
gradient detachment still limit temporal learning. A negative result here cannot
establish observation insufficiency or rule out better long-horizon supervision.
Any next strategic-memory intervention needs its own matched control and evidence
of usable temporal history; this pair does not justify simply enlarging the model.

Reproduce contract tests from the repository root with the pinned interpreter:

```text
.venv-action-predictor/Scripts/python.exe -m unittest tools.action_predictor.entity_movement.test_model tools.action_predictor.entity_movement.test_entry -v
```

The immutable protocol is `protocol.json`; `E00.json` and `E01.json` bind all
saved checkpoints, forecasts and measurements. The additive summaries are
`E00-summary.json` and `E01-summary.json`. Their producer verifies bindings and
refuses overwrites. Reuse saved artifacts; do not rerun either fit to recreate
this report.
