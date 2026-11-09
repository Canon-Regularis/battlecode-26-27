# Fixed-exposure cadence probe: movement allocation gate failed

Both arms completed their frozen 16 passes over the same 8,192 fitting rows,
using identical initial weights and window schedules. Each presented 131,072
rows. U00 made 128 updates; U01 made 512. Both results are final pass 16; no
intermediate checkpoint was selected. Combined recorded fitting/evaluation time
was approximately 85.36 seconds, within the two-hour cap.

This is an exposed fitting subset, not a generalization evaluation. It does not
replace any existing predictor or establish strategic behavior.

| Final metric | U00 control | U01 frequent updates | U01 minus U00 |
|---|---:|---:|---:|
| Complete commands / 8,192 | 6,060 | 6,365 | +305 |
| Complete moves / 1,321 | 659 | 647 | -12 |
| Complete changes / 642 | 28 | 40 | +12 / +1.869 pp |
| Complete continuations / 677 | 631 | 607 | -24 / -3.545 pp |
| Change coordinate NLL | 3.083191 | 2.655008 | -0.428183 |
| Balanced movement joint NLL | 2.222501 | 1.857657 | -0.364845 |
| Full modeled-command NLL | 1.536403 | 1.163098 | -0.373305 |
| Macro-F1 | 0.272204 | 0.373202 | +0.100998 |

The complete-change gain fails the required five-percentage-point threshold.
The continuation loss fails the one-point allowance. The other five frozen
conditions pass: change-coordinate NLL falls by more than 0.15 nats, balanced
movement joint NLL improves, full NLL and complete-command accuracy satisfy
their guards, and change-coordinate NLL improves after deleting each group.
The leave-one-group-out coordinate-NLL differences range from -0.441009 to
-0.416648 nats. These are descriptive in-sample results, not held-out evidence.

Most complete-command gain comes from attacks: 100 to 335. End gains 81 and
recall gains 19; cancel loses 18 and movement loses 12. Every other category's
complete count is unchanged. Casts, priorities, wards, blocked commands and
other sparse families remain weak; all 81 shops remain strict failures because
purchase arguments are absent. Full per-category and conditional metrics,
false positives, paired group results and windows are retained in `U01.json`.

On changes, conditional destination correctness rises from 35 to 45 of 642.
The median gold-destination rank remains four. Repeated previous-vector modes
fall from 487 to 428. The exact-repeat/complement loss decomposition improves
both terms: group NLL 0.905995 to 0.679108 and within-alternative NLL 2.177195 to
1.975900. Forcibly excluding repetition gets 89 versus 115 changes correct;
this is an oracle diagnostic, not a deployable improvement or complete ceiling.

U00 clips 0 of 128 updates; U01 clips 3 of 512. Parent checks verified all 38
U01 run-file hashes, matching initial tensors and RNG, all 16 window schedules
and RNG states, exact row coverage/exposure, 256-row treatment denominators,
finite norms, final-pass selection, and changes in every parameter tensor.
The completed U00 control already passed independent review. U01 and this
report now require independent postfit review.

This rejects the specified cadence intervention as a movement remedy at this
budget. It does not prove an architectural ceiling or that optimization never
matters. The treatment changes batch noise, update frequency, Adam moments and
cumulative weight decay together. Its larger general command-fitting gains
cannot override the failed movement guards.

Do not run the proposed full-population cadence experiment, extend this probe,
switch selectors or promote U01. Any later intervention needs a new hypothesis
and separately reviewed protocol. Destination ranking and the execution inputs
remain candidates for bounded diagnosis; the result does not establish missing
information as the cause. Original strong-reference, category-90%, reliability
and three-seed requirements remain, alongside the existing missing-argument,
entity-ambiguity, legality and outcome-validation limitations.
