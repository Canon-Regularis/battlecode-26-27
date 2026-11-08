# AB00: marginal action-belief input experiment

Selected round **18 of 24**, using the original full-DEV observed-NLL rule. Selected/completed updates: 17,136/22,848. Trainable correction: 570 weights. Argument distributions and upstream filtering remain frozen.

DEV complete commands: **12,144/14,439**; macro F1 **0.618640**; observed joint NLL **0.625622**. Against JP02: **38 rescues / 31 regressions**. Paired accuracy interval: `{'low': -0.0005684644354437829, 'high': 0.0013289919595986799, 'valid_draws': 2000}`. Paired NLL interval: `{'low': -0.006749747397097328, 'high': 0.00026661581164466597, 'valid_draws': 2000}`.

These are exploratory results on five reused DEV groups, not untouched or three-seed certification. The control retains group/context and availability structure and sometimes identical features. Any benefit cannot be attributed to correctly associated scheduling information before the matched real-input contrast.

| Recorded family | Support | Complete correct | Type FP |
| --- | ---: | ---: | ---: |
| altar | 2 | 0 | 10 |
| attack | 985 | 891 | 110 |
| blocked | 110 | 4 | 9 |
| cancel | 2589 | 2542 | 175 |
| cast_0 | 213 | 157 | 21 |
| cast_1 | 243 | 69 | 38 |
| end | 4096 | 3965 | 82 |
| move | 2362 | 1365 | 196 |
| priority | 576 | 133 | 37 |
| recall | 3084 | 2999 | 443 |
| shop | 43 | 0 | 10 |
| submit | 22 | 19 | 38 |
| teleport | 2 | 0 | 4 |
| ward | 112 | 0 | 8 |

Actual selected-checkpoint fitting-input scores: 209,538/243,522 complete, NLL 0.501636. On the same correction-fit rows with real inputs, the primary scores are 209,514 complete and NLL 0.501971. These input conditions must not be confused when interpreting control trainability.

The JSON report preserves all original TRAIN rows, natural fit/excluded groups, category losses, type and joint errors, conditional and correctly typed parameters, movement continuation/change/blocked, engine context, partial legality and paired targeting evidence. Held TRAIN groups were excluded only from this correction optimization; warm components and earlier research already saw them. Natural membership retains the frozen augmented-cadence upstream state.

All 43 DEV shops remain strict failures with absent purchase-argument likelihood. Sparse categories, entity identity, full legality and global calibration remain uncertified. Frozen argument modes impose category ceilings; this action-only experiment cannot achieve the original movement or 90%-per-category targets. The original macro, likelihood, targeting and three-seed requirements remain binding.

No promotion or repeat seeds are justified from the control alone. The registered next arm requires a completed fresh Sol xhigh review and addressed correctness findings. Both reserved partitions remain sealed. No match, replay download, engine query, bot/runtime or deployment work was performed.

Fit source: `51b899f9d9e9f7c04d8ba5492d49a19edf263412`. Selected checkpoint SHA256: `3e37011a53a8524b4d620b62164fb2f6447d7a50f44e2e82a3b22bee6a49027b`. The measured 20.696s interval includes optimization, round DEV inference, serialization and final assessment after preflight; it is not pure optimization or end-to-end cost.

Reproduce diagnosis: `python -m tools.action_predictor.policy_action_readout.diagnose AB00`; consume existing immutable archives rather than overwriting them.
