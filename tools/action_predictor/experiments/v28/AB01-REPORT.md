# AB01: marginal action-belief input experiment

Selected round **8 of 14**, using the original full-DEV observed-NLL rule. Selected/completed updates: 7,616/13,328. Trainable correction: 570 weights. Argument distributions and upstream filtering remain frozen.

DEV complete commands: **12,137/14,439**; macro F1 **0.620101**; observed joint NLL **0.626130**. Against JP02: **34 rescues / 34 regressions**. Paired accuracy interval: `{'low': -0.0009237547075960917, 'high': 0.0006340260655159913, 'valid_draws': 2000}`. Paired NLL interval: `{'low': -0.0067988415527703875, 'high': 0.001859151852530494, 'valid_draws': 2000}`.

These are exploratory results on five reused DEV groups, not untouched or three-seed certification. The control retains group/context and availability structure and sometimes identical features. Any benefit cannot be attributed to correctly associated scheduling information before the matched real-input contrast.

| Recorded family | Support | Complete correct | Type FP |
| --- | ---: | ---: | ---: |
| altar | 2 | 0 | 15 |
| attack | 985 | 891 | 108 |
| blocked | 110 | 4 | 9 |
| cancel | 2589 | 2543 | 177 |
| cast_0 | 213 | 156 | 22 |
| cast_1 | 243 | 70 | 37 |
| end | 4096 | 3967 | 80 |
| move | 2362 | 1365 | 196 |
| priority | 576 | 126 | 31 |
| recall | 3084 | 2996 | 453 |
| shop | 43 | 0 | 10 |
| submit | 22 | 19 | 35 |
| teleport | 2 | 0 | 4 |
| ward | 112 | 0 | 9 |

Actual selected-checkpoint fitting-input scores: 209,504/243,522 complete, NLL 0.501881. On the same correction-fit rows with real inputs, the primary scores are 209,504 complete and NLL 0.501881. These input conditions must not be confused when interpreting control trainability.

The JSON report preserves all original TRAIN rows, natural fit/excluded groups, category losses, type and joint errors, conditional and correctly typed parameters, movement continuation/change/blocked, engine context, partial legality and paired targeting evidence. Held TRAIN groups were excluded only from this correction optimization; warm components and earlier research already saw them. Natural membership retains the frozen augmented-cadence upstream state.

All 43 DEV shops remain strict failures with absent purchase-argument likelihood. Sparse categories, entity identity, full legality and global calibration remain uncertified. Frozen argument modes impose category ceilings; this action-only experiment cannot achieve the original movement or 90%-per-category targets. The original macro, likelihood, targeting and three-seed requirements remain binding.

No promotion or repeat seeds are justified from the control alone. The registered next arm requires a completed fresh Sol xhigh review and addressed correctness findings. Both reserved partitions remain sealed. No match, replay download, engine query, bot/runtime or deployment work was performed.

Fit source: `eb68cdd275dd73d498e13cfc0ed29f7656209ba9`. Selected checkpoint SHA256: `fcc2a471d6cb7fc3847df802e978430301d5494c5f335529876959a5ded88fe3`. The measured 14.413s interval includes optimization, round DEV inference, serialization and final assessment after preflight; it is not pure optimization or end-to-end cost.

Reproduce diagnosis: `python -m tools.action_predictor.policy_action_readout.diagnose AB01`; consume existing immutable archives rather than overwriting them.
