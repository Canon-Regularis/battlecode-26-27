# Matched movement-gradient routing probe

This tests whether conflicting change and continuation coordinate gradients can
be routed to improve movement fitting without sacrificing continuation or other
commands. Earlier D02 gradients motivate the hypothesis but do not establish
interference in this fresh policy. The failed V35 cadence probe is preserved.

R00 and R01 use the unchanged 139,292-parameter policy, fresh seed 27 weights,
empty AdamW state, and every existing contiguous 32-root fitting window: 1,085
windows, 34,720 rows, all 40 fitting groups. All explicit histories and masks
remain intact; additional memory resets and detaches every eight roots. Window
starts already align with these reset boundaries. No held partition is loaded.

Both arms accumulate three full parameter gradients: change coordinate NLL,
continuation coordinate NLL, and all remaining original likelihood terms. Each
loss sum uses the actual whole-batch row denominator, 1,024 or 928 for the last
batch. R00 sums these gradients. R01 projects the two coordinate gradients away
from each other only when their dot product is negative, simultaneously using
their original vectors, then adds the remaining gradient. Dot products, norms
and projection use float64; gradients are cast back before global clipping at 5
and AdamW with learning rate 0.0003 and weight decay 0.01. Wholly unused parameters
retain `grad=None`, preserving ordinary AdamW behavior. Direction metadata only
partitions training losses and never enters forecasts.

Projection changes update direction and magnitude. It need not minimize the
original scalar objective or protect continuations. Control gradient parity is
checked against ordinary backpropagation with explicit floating-point tolerance;
losses and assimilation are checked exactly on synthetic mixed-family rows.

Both arms receive eight passes, 272 updates, and 277,760 row presentations. Frozen
permutations, identical batch denominators and RNG states are checked each pass.
Only final pass eight can be the result; initial evaluation is a reference and
intermediate loss cannot select a checkpoint. The combined fitting/evaluation
cap is two hours, without restart, extension or extra seeds. An incomplete pair
is inconclusive. Separate actual prefit and postfit reviews gate R00 then R01.

All acceptance conditions are required: complete changes +5 percentage points,
complete moves +1 point, continuation loss at most 0.5 points, change coordinate
NLL reduction at least 0.15 nats, within-alternative NLL reduction at least 0.05,
and lower balanced change/continuation joint NLL. Full-command NLL may increase
at most 0.005, complete accuracy may lose at most 0.2 points, and macro F1 at most
0.01. Attack and both casts must lose no more than two points in conditional
targeting and complete accuracy; an absent category cannot pass. Movement false
positives on nonmovement rows may increase at most 0.2 points. Change accuracy
and coordinate NLL gains must retain their favorable signs after deleting any
single group. These are allocation thresholds, not statistical power guarantees.

All categories, paired group/window diagnostics, repeat/complement losses,
conflict statistics and clipping remain reported. Passing supports only a new,
separately reviewed transfer study. Failure rejects this routing rule at this
budget. Neither outcome establishes intent, strategy, playing strength or
generalization. Stronger-reference, category-90%, reliability and three-seed
requirements remain, alongside preexposure, observed past commands, ambiguous
entity targets, missing shop arguments and incomplete legality/POST validation.
