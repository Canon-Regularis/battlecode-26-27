# V40: neutral movement-bias initialization

Z01 shows modest favorable fitting differences, but fails the four required gain thresholds and therefore fails the frozen allocation test. It does not establish a strategy improvement or qualify for transfer/promotion. The other 14 guards pass.

The treatment starts only the 289 movement tile biases at zero. Movement special-bucket biases and every other initial tensor match the completed R00 control exactly, including RNG state. All 139,292 parameters train normally. The reviewed R00 run is reused without repeating it; the treatment calls the unchanged R00 unprojected gradient engine. This tests initialization during learning, rather than deletion of a learned bias after fitting.

Both runs use the same 1,085 contiguous fitting windows, 34,720 rows, 40 groups, eight schedules, 277,760 row presentations and 272 optimizer updates. Memory resets/detaches every eight roots; losses use whole-batch denominators of 1,024 or 928. AdamW settings and clipping are unchanged. Only final pass eight is evaluated as the result. Z01 took 168.087657 seconds; with the archived control's 178.258053 seconds, the combined time is 346.345710 seconds under the 7,200-second cap. There are no repeats, extensions or checkpoint switches.

| Fitting metric | R00 control | Z01 neutral bias |
| --- | ---: | ---: |
| Complete commands / 34,720 | 26,717 | 26,755 |
| Complete moves / 5,472 | 2,924 | 2,955 |
| Complete direction changes / 2,669 | 258 | 276 |
| Complete continuations / 2,796 | 2,666 | 2,679 |
| Conditional change destinations / 2,669 | 288 | 313 |
| Conditional continuation destinations / 2,796 | 2,792 | 2,796 |
| Change-coordinate NLL | 2.253202083 | 2.200065145 |
| Within-alternative NLL | 1.617364970 | 1.578323854 |
| Balanced movement joint NLL | 1.725759753 | 1.688918766 |
| Full-command NLL | 1.246750918 | 1.236638988 |
| Macro-F1 | 0.351642256 | 0.352329559 |

The four failed conditions are:

| Condition | Required | Observed |
| --- | ---: | ---: |
| Complete-change accuracy gain | at least 5 percentage points | 0.6744 points |
| Complete-movement accuracy gain | at least 1 point | 0.5665 points |
| Change-coordinate NLL reduction | at least 0.15 nats | 0.05314 nats |
| Within-alternative NLL reduction | at least 0.05 nats | 0.03904 nats |

The grouped 95% interval for complete-change gain spans -0.2464 to +1.4931 percentage points. For movement it spans +0.1079 to +0.9903 points. Full-command NLL improves by 0.01011 nats per row. These remain fitting-set diagnostics on one seed, not independent generalization evidence or a substitute for the predeclared thresholds.

Continuation protection, balanced NLL, full-command NLL/accuracy, macro-F1, movement false positives, attack/cast conditional and complete targeting guards, and change accuracy/NLL leave-one-group-out signs all pass. Targeting guards permit bounded losses: cast-0 conditional correctness changes 369 to 368 and cast-1 143 to 141. Complete casts, priority, ward and several other categories remain zero. Shops remain strict failures because purchase arguments are unavailable. Every category and paired group/window result remains in `Z01.json`.

The original weight finding was real: arbitrary initial direction biases persisted. This treatment suggests neutral initialization can modestly help this fitting configuration, but it does not explain or resolve the main direction-change problem. Z01 still selects the exact previous displacement on 2,076 of 2,669 change rows, compared with R00's 2,061. Better aggregate scores do not demonstrate that the learned repeat preference is now correctly conditioned. The oracle-excluding-repeat statistic improves from 901 to 966; that requires unavailable knowledge and is not achieved policy accuracy or a ceiling.

The user explicitly requested continuing without code review. No replacement code review was started and the interrupted V39 review is not treated as approval. All 26 parent-run protocol tests passed, including exact nonintervention initialization/RNG and unchanged other-family formulas. Parent postfit verification is recorded separately. Negative training-result interpretation retains the user's GPT-6 Astra high preference.

The result remains a one-seed, fitting-only contrast on exposed, availability-enriched groups with observed histories. Missing shop arguments, ambiguous entity targets, and incomplete legality/new POST validation remain. G00/L02/JP02 references, category-90%, reliability and three-seed requirements are unchanged. No further fit is justified automatically by this failed allocation; no model is promoted and the playing bot remains unchanged.
