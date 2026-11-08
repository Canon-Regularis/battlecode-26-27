# L02: command-only retention gradients versus L01

One additional user-authorized fit isolates direct auxiliary derivatives on the retention mechanism. Model training and evaluation only; bot work remains paused. This is a controlled seed-specific training intervention, not proof of Fish intent.

Architecture, data, warm initialization/seed, decoder, evaluation functions, AdamW, global clipping and checkpoint rule are unchanged. Both retention weights and bias receive command-only gradients through the entire eight-node unroll. Every other parameter receives the original command plus .05 future-position auxiliary gradient. No gate activation is detached; auxiliary gradients still flow to other intended components. Shared clipping and learned representations leave indirect interactions possible.

| Original DEV measure | L01 | L02 |
| --- | ---: | ---: |
| Complete commands /14,439 | 12079 | 12064 |
| Complete-command accuracy | 0.836554 | 0.835515 |
| Action macro F1 | 0.612431 | 0.610444 |
| Observed joint NLL | 0.655216 | 0.656567 |
| Complete move | 1372/2362 | 1365/2362 |
| Complete blocked | 3/110 | 4/110 |
| Complete attack | 894/985 | 892/985 |
| Complete cast_0 | 159/213 | 158/213 |
| Complete cast_1 | 69/243 | 71/243 |
| Complete priority | 50/576 | 50/576 |
| Complete recall | 3002/3084 | 2996/3084 |
| Complete ward | 0/112 | 0/112 |

L02 rescues 40 and regresses 55 commands versus L01. Group net differences: `{'1': -2, '10': -3, '11': 2, '17': -7, '31': -5}`.
Accuracy difference paired 95% interval: -0.00184818 to -0.00013985 (accuracy in fractions).
Macro F1 difference paired 95% interval: -0.00394785 to 0.00137503 (accuracy in fractions).
Observed NLL difference paired 95% interval: -0.00003104 to 0.00282363 (accuracy in fractions).

Intervals use the same2,000 whole-group draws, seed20261106. They are conditional on selected checkpoints and five reused DEV groups, not untouched or three-seed evidence.

| Movement diagnostic | L01 | L02 |
| --- | ---: | ---: |
| continuation conditional_exact | 1123/1198 | 1121/1198 |
| continuation joint_exact | 1088/1198 | 1089/1198 |
| change conditional_exact | 311/1158 | 304/1158 |
| change joint_exact | 282/1158 | 273/1158 |
| startup conditional_exact | 3/6 | 3/6 |
| startup joint_exact | 2/6 | 3/6 |

True-family destination metrics are conditional diagnostics. Complete predictions use predicted actions and the unchanged probability-consistent joint decoder.

| Retention/execution diagnostic | L01 | L02 |
| --- | ---: | ---: |
| Direct per-root gate median | 0.525874 | 0.986763 |
| Effective gap-retention median | 0.259395 | 0.984659 |
| Forward decay-age feature median | 0.385509 | 24.166998 |
| Common component destination on moves | 2214/2,362 | 2267/2,362 |
| Component-mode oracle coverage | 1481/2,362 | 1462/2,362 |
| Conditional destination exactness | 1437/2,362 | 1428/2,362 |
| Current-reweighting conservative conditional ceiling | 1534/2,362 | 1495/2,362 |

Direct gates are measured before effective-retention underflow. Decay age is the exact forward decay feature, not the lifetime of all recurrent information: known world coordinates may be held unchanged without current position, and past information also reaches new forecasts through attention. Component-mode coverage is an oracle diagnostic; the dominance ceiling holds component distributions/past state fixed. Neither is achieved strategy accuracy or an architecture/data ceiling.

The full TRAIN/DEV tables, conditional versus correctly typed targeting, confusion/false positives, category NLL, root-gap/engine contexts and paired targeting comparisons are in L02-analysis.json and L02-L01-comparison.json. Original augmented traversal and identity-verified natural membership are distinct from the supplemental natural-cadence evaluation. All TRAIN figures remain in-sample.

Selected round 3 of 9, selected updates 5227, completed updates 15678; original NLL improvement .0001/patience6/max35. Source commit `530fa3af7341a2e3befbf326648d672af938197e`. All attempted rounds/checkpoints and final predictions preserved. No additional fit, repeat seed or alternative checkpoint selected. Fresh Sol6.1xhigh review required. No promotion or robustness claim. Original category/macro/movement/NLL/targeting/three-seed objectives remain binding. See the result interpretation addendum for the measured conclusion.

The subsequent continuing-research instruction is recorded in continuation-authority.json and the running RESEARCH-LOG.md. This single-arm experiment is a bounded comparison within that continuing work, not a global stop or experiment-count limit. Further controlled studies follow evidence and fresh review; the historical protocol remains unchanged.

Both75-game reservations remain sealed. Every43DEV shop remains an unassessed strict failure and purchase-argument likelihood is absent. Altar/teleport/submit support cannot certify reliability. Coordinate agreement retains entity-identity ambiguity. Successful-move mask rejection and blocked-attempt outcome diagnostics are separate; full legality/calibration remain unassessed. No matches, replay downloads, playing-bot changes, native/runtime work or deployment occurred.
