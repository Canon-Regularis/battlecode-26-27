# H01 corrected neural semi-Markov hierarchy

Selected round6of12; 10,456selected/20,910completed updates. Original fullDEVNLLcheckpoint rule, every original TRAIN/DEV row retained. Fresh post-fit review pending; no promotion.

| Predictor | Complete /14,439 | Joint move /2,362 | Conditional move | Joint change /1,158 | Joint continuation /1,198 | Macro F1 | Joint NLL |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| G00 | 11510 | 1318 | 1434 | 263 | 1053 | 0.632394 | 0.726556 |
| L02 | 12064 | 1365 | 1428 | 273 | 1089 | 0.610444 | 0.656567 |
| JP02 | 12137 | 1364 | 1428 | 272 | 1089 | 0.620048 | 0.629052 |
| AB00 | 12144 | 1365 | 1428 | 273 | 1090 | 0.618640 | 0.625622 |
| AB01 | 12137 | 1365 | 1428 | 273 | 1090 | 0.620101 | 0.626130 |
| H00 | 12091 | 1322 | 1406 | 280 | 1039 | 0.615318 | 0.638183 |
| H01 | 12115 | 1335 | 1411 | 287 | 1045 | 0.597725 | 0.636526 |

All comparisons retain the original action/parameter definitions. Conditional destinations are recorded-family diagnostics; actual complete commands use predicted families and normalized joint MAP. The JSON includes paired groups, categories, targeting guards, false positives and context losses. Improving only relative to the weaker direct control would not establish improved imitation against stronger retained predictors.

Numerical exploratory conditions versus H00: `{'joint_move_gain_at_least24': False, 'joint_change_gain_at_least12': False, 'conditional_change_gain_at_least12': False, 'observed_NLL_below_direct': True, 'continuation_loss_at_most_half_pp': True}`. Both conditional and joint change gains are shown; there is no favorable posthoc choice between them. Original category/macro/movement/loss/targeting/three-seed targets remain binding; no robustness or untouched-test claim.

The repaired previous-command buffer is written after prediction and cleared at identical gaps. Only transitions/hazards gain21inputs; initial128inputlayer and original weights/RNG are preserved. This compares a combined discrete state/age inference and conditioned-execution policy with continuous recurrence, not isolated duration benefit. DEVselectedruns reach at most15roots, unknown prefixes are explicit, and BPTT detaches every8nodes. State lifetimes do not establish Fish objectives.

Component diagnostics distinguish available-mode misses, mixture-shape effects and common-wrong execution limits. A component-mode union is not achieved accuracy or a full mixture ceiling. Frozen common-wrong bounds do not prove observation insufficiency and can change when execution or encoded observations change. State indices have no assigned semantic labels.

Natural/augmentation-only TRAIN metrics in H01.json are in-sample row-membership strata under augmented traversal, not held-out policy or natural-cadence evidence. Sequential windows overlap and use earlier recorded Fish actions after occurrence; they are not autonomous execution. Five repeatedly reused DEV groups, one seed, selected checkpoints and engine/group confounding limit inference.

All43shop rows remain strict failures; purchase-argument likelihood is absent. Sparse altar/teleport/submit cannot certify reliability. Ambiguous entity identity, full legality and global calibration remain unresolved. Successful-move mask rejection is separate from blocked-attempt rejection. Both reserved75gamepartitions stay sealed, with no matches, downloads, proposed-action simulations or bot/runtime/deployment work.

Reproduce saved-output analysis: `python -m tools.action_predictor.segment_policy.component_analysis` then `python -m tools.action_predictor.segment_policy.matched_report`. Producers refuse overwrites; reuse hash-bound artifacts. Fit command is preserved as `python -m tools.action_predictor.segment_policy.hierarchy_fit H01`, executable only under the immutable reviewed amendment and in an unused namespace.
