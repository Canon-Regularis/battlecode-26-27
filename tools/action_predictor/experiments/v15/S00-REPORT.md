# S00: single candidate-conditioned movement specialist

S00 is a measured negative result against retained G00. DEV complete moves fall
1318->1283/2362; blocked attempts8->2/110. It gains continuing commands but loses
more changes. No promotion, repeats or original-target success is justified.

| Recorded-family exact destination | G00 | S00 |
| --- | ---: | ---: |
| Natural TRAIN move /48286 | 31025 | 30209 |
| Natural TRAIN continuation /25918 | 24345 | 24905 |
| Natural TRAIN change /22279 | 6616 | 5247 |
| Natural TRAIN blocked /1906 | 445 | 271 |
| DEV move /2362 | 1434 | 1384 |
| DEV continuation /1198 | 1120 | 1131 |
| DEV change /1158 | 311 | 250 |
| DEV blocked /110 | 24 | 9 |

These conditional diagnostics use the recorded family only for evaluation. The
complete forecast always uses G00's genuinely predicted action type. Correctly
typed move placement is1283/2127; blocked2/40. DEV joint continuation1053->1061,
change263->219,startup2->3. Movement80rescues/115regressions plus blocked0rescues/
6regressions yield41 fewer complete commands overall. Other true-family arguments,
other predicted-family commands, all types, priority values and action confusion
remain exactly unchanged. Overall11469/14439 (79.4307%) versus11510, macro F1
.63239354 unchanged, observed jointNLL .73596057 versus.72655565.

Paired whole-original-group intervals: move joint difference[-2.702,-.293]
percentage points, conditional destination[-3.594,-.670], overallstrict[-.486,-.089].
Overall NLL difference[+.006681,+.012200]. These condition on selected checkpoints
and five repeatedly reused groups; no untouched, selection-adjusted or three-seed
claim. S00 fails the original movement.65207451 target and exploratory repeat
criteria. The retained simple persistence baseline is55.207% conditional and
50.339% joint (transition action control); S00 conditional58.594%, joint54.318%.
It does not clear the original+10point requirement. Complete simple controls are
preserved separately in simple-baseline-reference.json, never compared as though
their action choices matched G00.

The deficit is already present on matched natural TRAIN. Changing destinations
are23.55% versus29.70% G00; DEV21.59% versus26.86%. Thus the negative result is
not solely a held-out transfer problem. This configuration fits continuation
better at the expense of changes, despite no explicit direction partition.
It does not isolate whether representation compression, capacity, optimization,
initialization, natural sampling or goal/planner information dominates. In
particular, S00-G00 changes more than architecture; S00-X00 is the matched
latent-mixture comparison. More examples alone have not resolved selection.
The earlier R02 small-subset memorization remains distinct evidence, not a
contradiction or proof of observation sufficiency.

All2362DEV move labels fit the original coordinate window, in-map bounds and
historical personal successful-movement mask. All110blocked attempted destinations
fit the window/in-map bounds; only8pass the successful-movement mask. These are
support diagnostics, not achieved accuracy and not duplicate all-outcomes
candidates. S00 forecasts zero successful-move mask rejections and89blocked-attempt
rejections; the latter are NOT illegal successful moves. Full legality unassessed.
Fixed types separately cap joint movement at2127/2362 and blocked40/110, regardless
of parameter quality. Missing movement vocabulary is not an explanation for these
DEV destination errors under the tested mask/window; available information may
still be insufficiently represented or used.

S00 has57898parameters. It trains only on50192natural eligible TRAIN move/blocked
rows, with all augmented and natural rows retained in evaluation. It selected
round14/20 (2758selected/3940completedupdates) under the original fullDEV NLL rule.
All checkpoints are preserved. Model probabilities are normalized over the same
291outcomes used for loss and argmax. Primary hierarchical type/conditional
selection is explicit, not global jointMAP. No opaque fallback mass comparison,
oracle intent label, direction partition or goal label is used. Candidate/entity
attention is a hypothesis; current goal features and local distances are not
verified Fish objective/pathfinding rules. Long persistent memory is not tested.

Read-only serving parity passes179rawPREcases/25games/bothengines, including52move
and22blocked forecasts. Raw features/entities/grid/masks match; frozen128context
max difference4.768e-6, new conditional log-probability max1.431e-5 within the
prospective2e-5 numerical tolerance. Changed command forecasts match saved arrays.
179case prepared-history actual inference timing is in the serving receipt; it
includes feature construction, frozen G00/P05 and BOTH new-family probability
calls, excludes initialization/history replay, and is not production latency.

Measured fit interval506.083seconds includes optimization, per-roundDEV inference,
checkpoint saves and final TRAIN/DEV inference/reporting. Whole command518.378
also includes hashing/loading/normalization. No extraction or match occurred.

See S00.json, S00-completion.json and S00-causal-roundtrip.json for all contexts,
per-category PRF/typeFP/jointFP/conditional parameters, uncertainty, artifact hashes,
commands and costs. Both75+75partitions remain sealed. Shop43arguments unavailable
strict failures with absent argument likelihood; sparse categories and ambiguous
entity IDs uncertified. Ward work stopped by user at3/4fits; T01 unrun. X00 is the
remaining prospective movement fit, pending a fresh requested Solxhigh review.
