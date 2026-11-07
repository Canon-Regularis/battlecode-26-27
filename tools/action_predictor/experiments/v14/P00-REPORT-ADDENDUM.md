# P00 reporting corrections after its fresh review

The original report, baseline receipt, predictions and checkpoint remain frozen.
Its baseline called uniform was actually **uniform plus the G00 probability
tail**: that tail breaks equal-probability ties, yielding24/112DEV. A new pure
uniform control with coordinate-order ties gives **10/112DEV,1083/10842TRAIN**.
The correctly named maskedG00 gets24/112DEV and2325/10842TRAIN. P00's2247TRAIN
placements therefore lose78againstmaskedG00. Its negative conclusion is unchanged.

`placement-baselines-correction.json` retains every original value under its
correct label. `P00-head-reporting-addendum.json` supplies all-family conditional
metrics, correctly typed supports, paired all-family/matched-typed/joint targeting
comparisons, and corresponding augmented/natural TRAIN and DEV contexts.

The new reporting plan predates P01/T00/T01 fitting. It includes current ward-state
availability, charges, priorward history and geometric coverage, champion, engine,
channel and movement contexts; empty support and group concentration are explicit.
Future P01-P00 andT01-T00 contrasts directly estimate the prespecified richer-input
effects, alongside each complete prediction versus the retained control.

`completion_v2` reads the actual placement/typing identifiers from each evaluation
and binds both relevant experts for a combined result. It records correct command
positions for typing and combined reproduction. P00's original correct placement
receipt is not rewritten. No model was refitted or promoted by these corrections.
