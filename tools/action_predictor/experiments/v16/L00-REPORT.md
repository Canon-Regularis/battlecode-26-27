# L00 reset-goal learned-policy control

The first registered fit completed. It improves aggregate command likelihood
and accuracy against G00, but does not establish learned strategic objectives or
broad category recovery. No promotion or repeat seeds are justified. The matched
persistent L01 arm is unrun and must wait for the requested fresh review.

L00 learns action types and spatial execution conditioned on four learned goal
hypotheses. Achieved future PRE positions supervise a goal forecast; no named
Fish intent is supplied. L00 resets its goal state at each selected decision,
while retaining the common causal action/observation inputs. It is the control
for L01, not evidence that persistence works. No manual farming, banking,
retreat, target-ranking or pathfinding strategy replaces learned decisions.

| Original DEV measure | G00 | Retained B00 | L00 |
| --- | ---: | ---: | ---: |
| Complete commands /14,439 | 11,510 | 12,061 | 12,076 |
| Complete-command accuracy | 79.71% | 83.53% | 83.63% |
| Action macro F1 | .632394 | .624643 | .610579 |
| Observed joint NLL | .726556 | .676064 | .654770 |
| Complete moves /2,362 | 1,318 | 1,387 | 1,372 |
| True-family destination exact /2,362 | 1,434 | 1,465 | 1,438 |
| Complete blocked attempts /110 | 8 | 6 | 6 |

L00 rescues744 G00 errors and introduces178: +566 commands. Recall supplies525
of the566 net gains (92.76%). Excluding recall, the gain is41 commands and NLL
changes only .7616545 to .7605578. Against B00, the net gain is15 commands through
226 rescues/211 regressions. Its paired whole-group accuracy difference interval
is -0.034 to +0.235 percentage points; a command-accuracy advantage is unresolved.
The paired NLL difference against B00 is -.02721 to -.01585. These are2,000
resamples of five reused DEV groups (seed20261106), conditional on checkpoint
selection, not untouched, selection-adjusted or three-seed evidence.

The category tradeoff prevents acceptance: against G00, complete cast_1 commands
fall95 to70, priority71 to50, ward7 to0 and blocked8 to6. Attack improves874 to894
and cast_0 improves154 to158. Separate all-true-family targeting counts are
attack943 to944, cast_0 193 to192, cast_1 146 unchanged. The cast_1 joint loss is
therefore chiefly a type-selection issue; unchanged aggregate conditional counts
do not imply identical per-row targets. Matched targeting rescues/regressions and
intervals are retained in L00-analysis.json.

Movement remains weak. L00's990 joint movement errors are149 wrong types and841
wrong destinations after correct typing. All2,362 recorded move destinations are
inside the coordinate vocabulary, map and historical success mask. Conditional
movement improves by only four destinations. Continuing destinations improve
1,120 to1,123 and changing destinations311 to312; corresponding joint counts
improve1,053 to1,090 and263 to279. Better action choices explain much of the
joint gain. On the same natural TRAIN change rows, conditional correctness
actually falls6,616 to6,365; continuation improves24,345 to24,431. DEV shift alone
cannot explain this configuration's weak destination fitting.

Selected-checkpoint natural TRAIN accuracy is85.77%, macro F1 .685980 and NLL
.518443; augmented TRAIN accuracy is79.14%, macro .765404 and NLL .645436.
Natural membership is verified, but TRAIN predictions traverse the augmented
actor stream, affecting transition inputs and latent-filter cadence. These are
in-sample diagnostics, not a matched natural-cadence or isolated group-shift test.
Root-gap/engine/direction strata and genuine consecutive-root command windows are
reported. Engine3 DEV remains confounded with one group. Training trace losses
are online averages during updates, separate from these final fixed-checkpoint
scores.

Goal prediction is modest: over5,593 available DEV future-position targets, the
prior-weighted mean waypoint has mean Chebyshev error5.662 tiles versus5.788 for
holding the current position. Rounding that mean gives97 exact endpoints versus
560 for the hold control. Averaging multimodal goals is not an oracle choice of
the correct latent state. Continuous goal-density NLL (-.93125) is separate from
discrete command NLL. The four prior means are .0715/.4904/.3795/.0587 and median
maximum pairwise goal separation is7.17 tiles on known-origin rows. None of this
identifies Fish's true objectives, proves useful goal conditioning, or tests
persistence. L01 and the declared sensitivity checks remain necessary.

The fit selected round3/9 with5,227 selected and15,678 completed optimizer
updates, seed20261114, original .0001/patience6/max35 whole-DEV command-NLL rule.
All nine checkpoints and full TRAIN/DEV predictions/goals are preserved. The
150,599-parameter policy includes an unused frozen258-parameter legacy priority
layer; L00's151-parameter retention layer is inactive. The reused P05/context port
adds298,824 learned scalars: the complete exported neural bundle is449,423, not
just the goal network. The measured2450.36-second fit interval excludes data
loading and includes training, inference, serialization and evaluation.

Changed-input checks reuse immutable personal evidence:43 PRE cases across both
engines match active cached inputs exactly; P05 mode-logmass discrepancy is below
1.98e-6. Forward raw-PRE actor replay covers128 cases, with exact Torch/portable
commands, archived NLL discrepancy below4.30e-6 and portable/Torch NLL discrepancy
below2.39e-6. The portable arithmetic audit covers256 forward steps, including a
counterfactual persistence arithmetic check on control weights; that is not a
memory experiment. The retained P05 port reproduces all14,439 DEV integer modes
and its109/576 conditional successes. These are bounded host checks, not all-row
raw serving, nativeWASI, fullSDK or closed-loop certification.

The original absolute-log tolerance preflight remains FAILED on heavily masked
underflow slots (float32 spacing .00097656 near -1e4). The separately disclosed
meaningful-log/probability checks pass; no original success target was relaxed.
The initial P05 port-check harness also failed due to a utility-history mask
mistake; its correction and full-row port parity are preserved separately. It
did not affect training, exported weights or the old P05 predictor.

Successful-move mask rejections are zero. Blocked forecasts have38 mask
rejections, reported as attempted-outcome diagnostics. Other partial readiness
flags are attack1, cast_0 1, cast_1 2, recall1. They are not a full illegal-command
rate. Shops43 remain unassessed strict failures, with purchase arguments absent
from observed likelihood. Sparse altar/teleport/submit and ambiguous entity
identities remain uncertified. Fixed P05 modes impose a109/576 priority ceiling
on this pilot regardless of type learning; observation and runtime omissions are
listed in the immutable known-limits/input addenda. Original category, macro,
movement, likelihood and three-seed targets remain unmet.

The actor can dispatch learned commands and commit actual own outcomes, but the
eventual native bot/liveSDK observation bridge, draft policy and unresolved
purchase/target arguments remain unfinished. No complete bot, recovered Fish
strategy or playing-strength claim is made. Both75-game reserved partitions stay
sealed; no matches, proposed-action simulations, downloads, playing-bot edits or
deployment. Existing predictors and discontinued ward artifacts remain intact.
