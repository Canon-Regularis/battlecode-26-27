# V42: replay-inferred goals, a separate full-map predictor, and A* execution

The requested separation is implemented and tested. Its first learned goal predictor **does not improve movement** against the declared baselines. It fails two of three prospective allocation conditions and is not enabled in the playing bot. No subagents or delegated code reviews were used.

This differs from L00/L01's fixed-horizon achieved-position auxiliary: the goal model is independently trained on interaction-anchored approach positions using the entire available current map. A separate A* executor consumes its predicted goal. Related goal-conditioned approaches existed, but this precise evaluator/model/executor pipeline had not been tested.

## Goal evaluator

Fish source or internal intent is not assumed. A label is the actor's achieved PRE position before the first attack, cast, submit, altar, shop, or ward interaction after at least four successful walking steps and within 32 actual own roots. Position discontinuities, unavailable anchor observations, unpaired cancellation, uncancelled recall and teleport censor the query. The first interaction is not skipped to obtain a longer favorable trajectory.

The original definition produced zero labels because Fish routinely starts recall after moving and cancels it before moving again. V1 artifacts are preserved. R2 permits this observed cancellation sequence while preserving position checks, the horizon, the thresholds and the group split. It yields **1,345 labels from 10,400 movement queries (12.93%)**: 1,067 from 32 fitting groups and 278 from eight evaluation groups. These correspond to 536 and 122 distinct actor/anchor episodes. Queries sharing an anchor overlap and are not independent.

All labels are statically reachable and all recorded first steps occur in their current personal movement masks. Median endpoint distance and walking horizon are five steps. Oracle shortest-path-set compatibility is 89.60% on fitting and 89.93% on evaluation. Deterministic oracle-goal A* matches only 67.39%/67.63% of exact recorded steps. This distinction exposes path ambiguity; it is neither deployable accuracy nor a claim that Fish uses A*. Some trajectories loop back to their origin.

Coverage losses remain explicit: 5,197 first interactions are too near, 1,576 exceed the horizon, 1,312 lack the anchor frame, 819 have uncancelled recall, 71 encounter teleport, 51 have position discontinuities, and 29 reach the actor suffix end. This is a selected, retrospectively labelable movement population, not all Fish decisions.

## Goal learning and movement

The 23,073-parameter model sees full-resolution public terrain, altar/spawn geometry, relative/absolute coordinates, current movement availability and public-terrain distance fields; current own inventory/stats and all known entity numeric fields have presence masks. Entity embeddings are scattered at known positions and pooled globally. Four dilated convolution layers and whole-map context produce a categorical tile distribution. Unknown entities contribute static metadata only. Actor IDs, replay cursors, future events, anchor types and target coordinates never enter learned inputs. Fifteen evaluation field occurrences are absent from the fit-only dictionary; none are absent on fitting rows. Numeric category codes are not dedicated semantic embeddings.

One fresh seed (43001), twelve fixed passes and 804 AdamW updates present each fitting row twelve times (12,804 presentations). Only final pass twelve is evaluated. The run takes 61.986 seconds; 704 updates hit the frozen gradient clip of five. All 18 parameter tensors change. High clipping is a measured optimization characteristic, not proof of the failure's cause. The existing action-predictor weights remain separate.

| Eight-group evaluation; 278 queries | Learned goal | Hold current position | Nearest known camp approach | Nearest altar approach | Future inferred goal (oracle) |
| --- | ---: | ---: | ---: | ---: | ---: |
| Exact inferred goal | 5.04% | 2.52% | 2.16% | 8.63% | 100% |
| Goal within two tiles | 21.22% | 10.79% | 9.71% | 19.78% | 100% |
| Mean goal Chebyshev error | 5.928 | 4.741 | 5.802 | 10.299 | 0 |
| Exact next step using A* | 30.94% | 0% | 11.15% | 41.01% | 67.63% |

The learned goal improves within-two-tile accuracy over all baselines, but fails lower mean error and the required five-point movement gain. Its 86 correct next steps are 28 fewer than the nearest-altar baseline's 114. Oracle-goal A* gets 188, using unavailable future information. Fitting next-step accuracy is 40.11%, below nearest altar's 43.02%; this is not solely an evaluation regression.

## What the evidence narrows down

The evaluator supplies a usable but limited future-position proxy. Predicting that proxy remains a bottleneck in this configuration; A* does not repair a poor goal. Even the future proxy does not uniquely determine Fish's exact step because costs, dynamic considerations and tie choices are unspecified.

Label semantics are also unresolved. On fitting rows, 352/1,067 anchors are ward placements and 430 are casts; 37 cast anchors target the actor's own position. These interactions can occur while travelling toward a different objective. Shortest-path compatibility does not prove that the endpoint was the strategic destination. A defensible next label study would distinguish destination-defining engagements/deposits from incidental wards and self-buffs, using fitting evidence and retaining rejected/censored paths. This result does not justify simply extending training or declaring the model has learned Fish's strategy.

## Verification and scope

All twelve focused tests pass, covering label censoring and cancelled recalls, path obstacles/first-step masks, hidden-state and identity exclusion, full-map/entity encoding, finite gradients, output normalization, variable-map padding, entity-order invariance, and nonmovement/fallback adapter behavior. Parent verification reconstructs initialization, every shuffle, exact coverage and update counts, all optimizer step counts, and all 1,345 saved forecasts, losses, baseline scores and summaries. Current-only inference reproduces a saved goal. No optimizer steps are performed by verification.

The eight evaluation groups are excluded from this model's optimization but were exposed in earlier research. One seed, sparse selected labels, overlapping episodes, incomplete command arguments, ambiguous targets and unvalidated full legality/outcomes prevent generalization, intent, playing-strength or promotion claims. Historical G00/L02/JP02, full-category/reliability, 90% and three-seed requirements remain unmet. No original tuning/assessment or reserved payloads, engine runs or runtime changes were needed.
