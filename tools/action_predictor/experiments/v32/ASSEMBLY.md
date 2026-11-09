# Restored-history feature assembly completed

The frozen 60-game assembly contains 97,152 rows: 65,465 fitting, 15,298 tuning,
and 16,389 assessment. All 55,142 original selected rows reproduce canonical
current features, previous-command vectors, float16 candidate grids, in-map and
movement masks, action/coordinate/integer labels, and range/target rules exactly.
The remaining 42,010 rows use the reviewed recorded-command/PRE bindings.

All actual omitted-root gaps remain explicit. Earlier command history uses the
full actor index, including unselected actions. Missing earlier observations are
stored as zeros with separate presence/availability masks. Current and scheduled
priority fields remain uniformly unavailable; strictly earlier integer arguments
remain available. Target direction is a diagnostic label, never a model input.

Mean and sample standard deviation (floor 0.01) use only the 65,465 current
observation vectors from fitting groups. Independent parent recomputation
reproduced both arrays exactly. The parent verified all 60 assembled array and
row-identity hashes, row/offset coverage, missing-observation zeros, and uniformly
unavailable current/scheduled priority inputs. Thirteen focused tests passed.

The immutable manifest is `assembly.json`; data are in the ignored directory
`.cambc/action-predictor/v32/features-v1`. All source and input bindings are in
`assembly-plan.json`. No optimizer or new model fit has run. Independent review
of the completed assembly approved the inputs without findings; the actual
review is bound in `assembly-review.json`. This approval does not cover fitting.

The next planned contrast separates recurrent access from gradient horizon:
reset every eight available roots, carry state with eight-step detachment, and
carry state with 32-step detachment. All arms must have the same actual-root gap
resets, tensors, rows, losses, optimizer update cadence, seed and checkpoint
opportunities. Initial weights and all trained components must use fitting groups
only; prior M01/P05/RC01 components cannot be reused. Missing observations must be
masked again after normalization. Utility-command coordinate fields must receive
the existing input sanitation. Model/loader/likelihood implementation and a frozen
matched protocol still require review before fitting.

Availability enrichment and prior research exposure remain limitations. These
are research partitions, not untouched certification data. Shops lack purchase
arguments; full legality, ambiguous entity identity and new POST/outcome checks
are not established. Passing assembly checks is not evidence of improved strategy.
