# PC01: broader P05 population, unchanged head and controls

One diagnostic changes PC00’s fitting population from 128 examples to all 5,876 natural priority rows in its actual 55 fit groups, excluding both unchanged control cohorts. The original 128 fit rows are included. No row is selected by current model error.

| Update | Broad fit /5,876 | Original fit /128 | Same-fit-group control /128 | Disjoint-group control /128 |
| --- | ---: | ---: | ---: | ---: |
| 0 | 1463 | 34 | 25 | 28 |
| 100 | 3762 | 76 | 18 | 22 |
| 500 | 4631 | 97 | 13 | 23 |
| 1000 | 4844 | 100 | 13 | 18 |
| 2000 | 4898 | 102 | 13 | 16 |

| Cohort | Initial NLL | PC01 final NLL | PC00 final NLL |
| --- | ---: | ---: | ---: |
| broad_fit | 3.002684 | 0.606291 | unassessed |
| original_fit | 2.894059 | 0.701733 | 0.000878 |
| same_fit_groups | 3.147922 | 8.920198 | 7.119178 |
| held_groups | 3.051521 | 8.772601 | 7.241176 |

All 430 absolute and 560 available-residual training labels are empirical labels from the broader population. The existing P05 vocabulary remains unchanged; every control target has an absolute or available-residual explanation represented in this population. This is oracle support, not achieved accuracy or a true-intent assignment.

The same step-zero warm P05 head, frozen M01 contexts, 39 normalized causal priority channels, exact int64 anchors, normalized probability arithmetic and integer MAP are retained. Optimization remains AdamW, .003 for 1,000 updates then .001 for 1,000, zero decay, clip 5, seed 20261120. Each update accumulates the full-population mean gradient through chunks before one optimizer step. The population treatment therefore increases total row presentations; it is not an equal-compute comparison. No new architecture, sampler, decoder or loss is introduced.

The accumulated-versus-full128gradient check differs by at most 5.22e-08. Initial modes reproduce G00/P05 exactly; maximum NLL discrepancy 4.55e-07. Input affine ranks are 128/128 for PC00’s sample and 156/5,876 for the broader population. This removes unrestricted 128-row interpolation; rank alone is not a policy recoverability or classification-capacity bound.

Both controls were previously seen by the frozen encoder AND warm P05 head, vocabulary and normalization. They are excluded only from new optimization. Their results cannot be called untouched full-policy/group generalization. Coverage, diversity, forgetting and representation are not separately isolated. Broad fitting gains alone do not prove reusable rules or sufficient observations. All rows and negative results are retained.

Paired whole-group intervals, rescues/regressions and NLL changes are in PC01-analysis.json. They are conditional diagnostic comparisons on pre-exposed TRAIN cohorts; no overall policy accuracy or original success certification follows. Fixed final update 2,000 is retained regardless of intermediate scores; no replacement checkpoint, threshold or seed is selected.

Execution source commit: `76fc4d0c36dc56b278b5cb1f8d9ad56708a77e78`. Every declared source byte was checked against HEAD before prerequisites and again before optimizer creation. One checked command sequence runs the five focused tests, preparation and preflight before reaching optimization. The negative-path receipt confirms the normal entrypoint refuses uncommitted source. PC00’s historical uncommitted execution remains disclosed and unchanged.

This is conditional integer training/evaluation only. The complete policy remains unchanged. Any future integrated comparison must recompute normalized joint command probabilities and winning action families. Shops remain unassessed strict failures; sparse categories cannot certify reliability. Original category, macro, movement, NLL, targeting and three-seed targets remain binding. No DEV payloads or reserved partitions are opened, and no matches, downloads, bot/runtime work or deployment occur. Fresh Sol xhigh review follows this fit.

Reproduce once into absent immutable destinations: `python -m tools.action_predictor.priority_broad.experiment`; then `python -m tools.action_predictor.priority_broad.analyze` and `python -m tools.action_predictor.priority_broad.report`. Do not rerun completed fitting.
