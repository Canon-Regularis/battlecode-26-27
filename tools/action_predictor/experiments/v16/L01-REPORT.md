# L01 persistent-goal model: no established benefit

The second registered fit is complete. Learned persistence adds three complete
DEV commands over L00, with slightly worse NLL and no movement joint gain.
Paired intervals span zero. No promotion or repeat seeds are justified. This is
a result about this learned position/belief-retention mechanism, not proof that
Fish lacks persistent objectives or that all persistent policies fail.

Bot/runtime work is paused by the latest explicit user instruction. This report
covers model training and evaluation only. Existing prototype work is preserved.

| Original DEV measure | G00 | B00 | Reset L00 | Persistent L01 |
| --- | ---: | ---: | ---: | ---: |
| Complete commands /14,439 | 11,510 | 12,061 | 12,076 | 12,079 |
| Complete-command accuracy | 79.71% | 83.53% | 83.63% | 83.66% |
| Action macro F1 | .632394 | .624643 | .610579 | .612431 |
| Observed joint NLL | .726556 | .676064 | .654770 | .655216 |
| Complete moves /2,362 | 1,318 | 1,387 | 1,372 | 1,372 |
| True-family destinations /2,362 | 1,434 | 1,465 | 1,438 | 1,437 |
| Complete blocked attempts /110 | 8 | 6 | 6 | 3 |

L01 versus L00 has30 rescues and27 regressions. The2,000 paired whole-group
resamples (seed20261106) give accuracy difference -.075 to +.150 percentage
points, NLL difference -.000312 to +.001527 and macro-F1 difference -.001201 to
+.003817. These are five reused DEV groups after checkpoint selection, not
untouched, selection-adjusted or three-seed evidence. Against B00, +18 commands
also has an accuracy interval spanning zero. Its NLL improvement over B00 remains
measurable, without establishing broad category recovery.

Movement changes are small and mixed: L01 continuing joint correctness is1,088
versus L00's1,090; changing joint correctness282 versus279; startup2 versus3.
Conditional continuation remains1,123, while changing destinations fall312 to311.
There are148 wrong movement types and842 wrong destinations after correct typing.
All2,362 recorded move destinations remain inside the vocabulary/map/historical
success mask. Vocabulary coverage therefore does not explain this failure.

The stronger execution diagnosis reproduces LP-01. Four goal components choose
the same top destination on2,214/2,362 moves (L00:2,223), including1,052/1,158
changes (L00:1,059). Their current-mode union covers1,481 destinations in both
models; this is an oracle diagnostic, not achieved accuracy or a support ceiling.
Of L01's842 correctly typed destination failures,802 have no correct component
mode available. On natural TRAIN, the corresponding count is15,309/16,042.

A conservative fixed-distribution bound is sharper:828 DEV moves have the SAME
wrong top destination in every component. That destination dominates the recorded
one under any nonnegative CURRENT mixture reweighting, including first-argmax
ties. Thus current conditional reweighting alone cannot exceed1,534/2,362, and
760 of842 typed destination errors are already blocked by this dominance. The
bound holds current component distributions/past state fixed. Retraining the
executor or changing earlier recurrent state can change it; it is not an
architecture, data or all-algorithm ceiling. Other rows may also be unreachable.

The learned retention is short in a descriptive reconstruction: median expected
soft age is .386 own roots,95th percentile1.291, maximum6.710; the median
per-root continuation weight is .516 despite initialization at .99. Soft age is
not a hard memory cutoff or true objective lifetime, and small older contributions
may remain. Root-count quantization is disclosed in the memory addendum. These
results do not demonstrate useful long-lived strategic state.

Two predeclared inference-time sensitivity controls support that narrow result:

| Selected L01 weights | Complete commands | NLL | Complete moves |
| --- | ---: | ---: | ---: |
| Original forward filter | 12,079 | .655216 | 1,372 |
| Reset persistent goal state each decision | 12,081 | .655145 | 1,372 |
| Remove waypoint/uncertainty/availability projection | 12,049 | .669408 | 1,355 |

Resetting goal state has almost no effect; the tiny NLL improvement is not a
new promoted model. Removing the five-channel goal_condition projection hurts
aggregate likelihood and joint movement, although conditional movement improves
six destinations and macro F1 rises. This removes one projection, not all goal
pathways: latent embeddings, attention, proposals and mixture remain. Neither
intervention is matched retraining or causal identification of Fish intent.
Thus some projection information is useful, while useful persistence remains
unestablished. No result was selected as a replacement checkpoint.

The achieved-position goal forecast is also weak: over5,593 available DEV rows,
prior-mean Chebyshev error is5.703 tiles versus L00's5.662 and holding position's
5.788. Rounded mean endpoints match87 versus97 and560. Continuous goal-density
NLL (-.91149) is separate from command NLL. Future achieved position is a
receding-horizon supervised outcome, not a verified persistent objective.

A bounded TRAIN-only local-gradient probe identifies a concrete loss-coupling
hypothesis. It uses192 cases from12 distinct training groups, identical across
initial/round1/selected weights, with no optimizer or parameter change. At
initialization, the already-weighted .05position auxiliary gives mean absolute
retention-bias gradient .008571 versus .000002710 from command NLL (about3,160x).
Its average direction decreases retention; the combined local bias gradient
decreases it on128/192 cases. Initial command gradients are very weak while the
components begin with near-identical execution and zero goal-conditioning
projection. Mean effective retention on these cases falls .883 to .316 after
round1. The initial loss pressure is consistent with learning to track a moving
forecast rather than hold an objective.

This is not definitive training-trajectory attribution. Earlier state is detached
in the probe; it is not the full8-node BPTT gradient. At the selected checkpoint,
the mean combined local bias gradient instead favors increasing retention, and
the samples are bounded early trajectories. The evidence motivates an isolated
training-objective intervention, not a claim that the auxiliary caused every
failure or that larger models cannot help. No third fit has run.

After independent review, the single most informative training test is a matched
retention-gradient-routing intervention: let command/sequence NLL train the
retention parameters while the position auxiliary continues to train the goal
forecaster, holding architecture, inputs, sampling and decoder fixed. This would
test the demonstrated direct loss competition, without imposing a Fish strategy
or guessing a persistence deadline. It requires a separately frozen study budget;
it is proposed and unrun, not an extension hidden in this two-fit result.

The natural-cadence supplemental evaluation retains all288,801 identity-verified
natural TRAIN decisions and correctly counts omitted augmented roots as earlier
intervening actions. Normalization/current PRE/full actual history windows are
unchanged. L00 keeps247,697 correct commands; L01 obtains247,702. L01 natural
cadence NLL is .518388, macro F1 .686077. Its changing-destination correctness is
6,359/22,279 versus L00's6,365; continuation24,436/25,918 versus24,431. This is
in-sample evidence under matched natural traversal definitions, not isolated
group-shift evidence. The original433,071-row TRAIN and every original DEV row
remain in the primary reports. No nonconsecutive sampled actions are stitched.

L01 selected round3/9 under the original whole-DEV NLL .0001/patience6/max35 rule,
with5,227 selected and15,678 completed updates, seed20261114. The same150,599
nominal parameters/inputs/loss/initialization as L00 were used; L00's151 retention
parameters are inactive. All checkpoints, predictions, goal diagnostics and
negative results remain. Inference is forward and consumes actual earlier own
actions only after prediction; future endpoints enter training losses or
postprediction diagnostics, never current goal selection.

Important failures persist: complete cast_1 is69/243, priority50/576, ward0/112,
blocked3/110. Fixed P05 conditional modes still cap priority at109/576 even under
perfect family choice. Perfect family decisions with current conditional modes
would give only12,668/14,439 overall; this is a current-mode diagnostic, not an
architecture/data ceiling. All43shops remain unassessed strict failures with no
purchase-argument likelihood. Sparse altar/teleport/submit, target-identity
ambiguity, incomplete observations, five reused groups and one seed remain
limitations. Successful-move mask rejection is zero;36 blocked-forecast rejections
are attempted-outcome diagnostics, not illegal successful moves. Full legality
and calibration remain unassessed.

The original category, macro, movement, NLL, targeting and three-seed objectives
remain unmet. No matches, replay downloads, reserved-partition access or deployment
occurred. Both75-game reservations remain sealed. Fresh requested Solxhigh review
is required before further fitting. Model-only scope remains in force.
