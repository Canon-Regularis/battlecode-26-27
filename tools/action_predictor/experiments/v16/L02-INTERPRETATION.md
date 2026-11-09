# L02 interpretation: gate behavior changed, imitation did not improve

The controlled gradient-routing intervention worked mechanically. Retention
weights and bias receive command-only derivatives through the full eight-node
unroll; other parameters retain the original combined-loss derivatives before
the unchanged global clipping. Initialization, normalization, optimizer groups,
parameter order and Torch/NumPy RNG states match L01 at every shared round.
All nine checkpoints and the negative result are preserved.

Direct DEV per-root gate median rises from **.525874 to .986763**. Effective
gap-retention median rises from .259395 to .984659. The exact forward decay-age
feature median rises from .385509 to24.166998 roots. This is a large effect of
the intervention under this seed. It supports the hypothesis that auxiliary
derivatives contributed substantially to L01's short-retention training outcome.
It does not establish a true Fish objective lifetime or remove indirect auxiliary
effects through shared representations, recurrent state or shared clipping.
The two policies are separately trained: this does not isolate the effect of
turning up L01's gate while holding all other learned weights fixed.
The age feature is not the lifetime of every information pathway;325 DEV rows
hold an old world coordinate unchanged without current position.

Longer retention **does not improve complete-command imitation**. L02 gets
12,064/14,439 versus L01's12,079:40 rescues/55 regressions. Paired whole-group
accuracy difference is -.1848 to -.0140 percentage points. Macro F1 .610444
versus .612431 and observed joint NLL .656567 versus .655216 have difference
intervals spanning zero. These are five reused DEV groups after checkpoint
selection and one seed, not untouched/selection-adjusted/three-seed evidence.
The generic interval caption in L02-REPORT.md incorrectly repeats "accuracy in
fractions" on its NLL line: that interval is in observed command NLL units,
not accuracy. The numerical interval is correct; the original report is retained.

Execution remains demonstrably weak. Move joint correctness falls1,372→1,365
and all-true-family destinations1,437→1,428. L02 move errors split into149
wrong types and848 wrong destinations after correct typing. Of the848 typed
destination errors,818 lack a correct component mode;793 cannot be repaired by
any current nonnegative conditional reweighting with component distributions and
past state fixed. The conservative current-reweighting ceiling falls1,534→1,495
of2,362. This is not an architecture/data ceiling or achieved oracle accuracy.
All recorded move destinations remain inside the original representation and
historical success mask, so missing output vocabulary is not the explanation.

Components differentiate execution less: common movement modes rise2,214→2,267,
mode-union coverage falls1,481→1,462, and mean JS divergence falls.001452→.000787.
Mean conditional mixture usage becomes more concentrated (largest mean weight
.651→.881); component identities are not aligned across independently trained
fits. These measurements establish a frozen-execution bottleneck, without yet
identifying whether goal information, conditioning, optimization or representation
causes that bottleneck. Adjusting current mixture weights alone is insufficient.

The problem is present on TRAIN. On the same natural TRAIN membership under
original augmented traversal, conditional changes fall6,360→6,297 while
continuation rises24,437→24,489. Complete commands fall247,701→247,646.
Under separately matched natural cadence, L01 gets247,702 and L02 gets247,644;
NLL .518388→.519822. TRAIN remains in-sample. Neither comparison isolates group
shift, and no nonconsecutive sampled rows are treated as adjacent observations.

Future-position forecasting also deteriorates: over the same5,593 available
DEV targets, mean waypoint Chebyshev error rises5.703→6.819 tiles, versus5.788
for holding current position. Rounded endpoint exactness falls87→45 versus560
for holding. Continuous goal-density NLL worsens-.91149→-.54101. A receding
future-position target is not a verified persistent objective. This result does
not establish that persistent strategic objectives are unhelpful; it shows that
retaining this learned forecast longer does not solve the tested policy.

Category effects are mixed. Complete blocked improves3→4 and cast1 improves69→71,
while attacks894→892, cast0159→158 and recall3,002→2,996 regress. Priority stays
50/576, ward0/112. Priority/blocked NLL improve even without adequate exact
commands. Fixed P05 conditional modes remain109/576; perfect action choice with
all current conditional modes would reach only12,658/14,439. These are current
configuration limitations. The complete error ledger is1,242 wrong types,
1,091 wrong arguments after correct typing, and42 correctly typed shops with
unavailable arguments. Every43shop remains a strict failure. Sparse categories,
entity identity and full legality/calibration remain uncertified.

The next investigation should address **execution dependence on learned goal
information**, rather than repeat a retention/auxiliary-weight sweep. A useful
candidate is a prospectively fixed, bias-preserving pathway diagnostic: distinguish
variable waypoint geometry, uncertainty/availability and the learned constant
projection offset, while preserving other goal pathways and explicitly separating
fixed-state readout diagnostics from causally refiltered predictions. The earlier
zero-weight-and-bias intervention confounded these. This is proposed, not run or
selected as a replacement policy; the fresh review should challenge it against
other informative diagnoses. No next architecture or fit is predetermined.

Research continues automatically under the subsequent explicit user direction.
This result earns no promotion or seed replication. Fresh Sol6.1xhigh review
comes next; address findings and choose the next distinct controlled test.
Bot/runtime/native/SDK work stays paused. No matches, downloads, deployment or
reserved-partition access occurred; both75-game reservations remain sealed.
