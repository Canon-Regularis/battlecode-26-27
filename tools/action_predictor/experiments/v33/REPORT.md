# Restored-history horizon study: negative movement result

All three frozen arms completed 12 rounds and 897 optimizer updates each. A resets
extra recurrent memory every eight roots; B carries memory with eight-step
gradients; C carries memory with 32-step gradients. Initial tensors, rows,
sampler schedules, update counts and checkpoint opportunities matched. All arms
retain explicit 16-root command/observation history. No existing predictor is replaced.

## Primary selection: assessment groups

The primary tuning rule selects round 12 for every arm. Counts below use the
same 16,389 assessment rows. Complete moves include the action family and destination.

| Arm | Complete commands | Moves / 2,672 | Changes / 1,370 | Continuations / 1,298 | Balanced move NLL | Full modeled NLL | Macro-F1 |
|---|---:|---:|---:|---:|---:|---:|---:|
| A | 12241 | 1308 | 110 | 1197 | 1.757776 | 1.271067 | 0.383421 |
| B | 12213 | 1317 | 105 | 1211 | 1.768623 | 1.282356 | 0.377539 |
| C | 12229 | 1293 | 105 | 1188 | 1.786022 | 1.259465 | 0.383197 |

B minus A gains nine moves but loses five changes and 28 complete commands.
It fails movement, change, balanced-NLL, full-NLL, macro-F1 and submit guards.
C minus B loses 24 moves and 23 continuations, with no change gain. Its full NLL
improves, but movement, change, continuation and balanced-movement NLL guards fail.
C minus A loses 15 moves, five changes and nine continuations. No matched contrast
passes the frozen allocation gate. Both memory-carry arms have ten fully correct
32-root assessment windows, the same as A, out of 280. These windows are teacher-forced.

## Secondary selection and historical regressions

The full-NLL tuning rule selects round 11 for A/B and round 12 for C. C gains
41 moves over A and 51 over B under this separate rule, but loses 19 and 15
direction changes respectively. Its change guard fails both comparisons.
This is not grounds to switch selectors. The full artifacts retain every category,
false positive, targeting guard, bootstrap interval and leave-one-group-out result.

On the original 14,439-row DEV, primary A/B/C have 1,177/1,194/1,169 complete
moves. All remain below L02 (1,365) and JP02 (1,364). The fresh models have different
training exposure and initialization from those references; this comparison is a
regression panel, not an isolated causal effect. Priorities, casts and wards remain
weak. Missing shop arguments keep every shop a strict complete-command failure.

## Fitting-only diagnostic for the next iteration

The frozen primary A checkpoint gets only 356 of 5,032 fitting direction changes
fully correct; 410 have the correct destination conditional on the true family.
Of 4,676 complete-change failures, 4,622 have a wrong conditional destination;
only 54 have a correct destination with a wrong family. In 3,331 of those 4,622
destination errors, the conditional mode repeats the previous movement vector.
All 5,032 recorded change destinations lie inside the current movement mask.
3,751 change rows have all 16 earlier observations; 63 have none.

These are descriptive fitting-set facts, not proof that history causes the error
or that observations are sufficient. Weak fitting performance and still-improving
late training loss leave execution representation and optimization as live hypotheses.
The next step is a bounded fitting-only audit of destination ranking, continuation
probability and optimization evidence. Do not repeat the horizon study or launch
another architecture solely because this result is negative. Any new fit needs its
own concrete hypothesis, frozen comparison and review.

## Evidence and limits

The parent verified all C run bindings, matching initial weights/RNG, all twelve
sampling schedules and RNG states, identical updates/coverage, both selector choices,
nine finite gradient snapshots and changes in every selected floating tensor.
A/B already have independent approvals. C and this additive report await review.
The immutable `summary.json` binds the three result manifests and this producer.
It includes both selection rules, paired reports and the fitting-only diagnostic.

One seed, previously exposed availability-enriched research groups, actual past
commands, ambiguous entity targets, incomplete legality/new POST validation and
missing shop arguments limit the conclusions. No reserved games, matches, downloads,
runtime changes, extra fits or model promotions occurred in this reporting step.
