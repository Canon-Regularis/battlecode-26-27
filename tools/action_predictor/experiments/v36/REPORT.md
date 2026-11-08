# Movement-gradient routing: negative fitting result

R01 does not pass the frozen movement allocation gate. Projecting conflicting
change and continuation coordinate gradients adds five complete changes but
loses 33 continuations, 28 complete moves and 15 complete commands. No transfer
experiment, repeat, extension or model promotion follows from this contrast.

Both arms use the same fresh seed-27 initialization, 139,292 parameters, 34,720
fitting rows from all 1,085 contiguous windows and all 40 fitting groups. Each
completes eight passes, 277,760 row presentations and 272 updates. Final pass
eight is the sole result; neither online loss nor assessment data selects it.
The combined recorded fitting/evaluation time is 345.331 seconds, including
final comparison and archive hashing before the validated publication time.

| Metric | R00 control | R01 projection |
| --- | ---: | ---: |
| Complete commands /34,720 | 26,717 | 26,702 |
| Complete moves /5,472 | 2,924 | 2,896 |
| Complete changes /2,669 | 258 | 263 |
| Complete continuations /2,796 | 2,666 | 2,633 |
| Full-command NLL | 1.246751 | 1.245048 |
| Balanced change/continuation joint NLL | 1.725760 | 1.695383 |
| Macro F1 | 0.351642 | 0.350577 |
| Change coordinate NLL | 2.253202 | 2.098193 |
| Change within-alternative NLL | 1.617365 | 1.577532 |

Four of the 18 allocation checks fail:

- Complete changes gain 0.187 percentage points, below the required five.
- Complete moves lose 0.512 points instead of gaining at least one.
- Complete continuations lose 1.180 points, exceeding the 0.5-point allowance.
- Change within-alternative NLL falls 0.039833 nats, short of the required 0.05.

The other 14 checks pass. Change coordinate NLL falls 0.155009 nats, meeting
the 0.15 threshold; balanced joint NLL also improves. Full-command NLL, complete
accuracy and macro F1 remain within their allowed losses. All attack/cast
conditional and complete targeting guards pass. Movement false positives fall
by 33 on 29,248 nonmovement rows. After removing any one group, change accuracy
gains remain positive (0.115 to 0.268 percentage points), and change coordinate
NLL deltas remain negative (-0.156657 to -0.153176). These are fitting diagnostics;
they do not override the four failed conditions or establish generalization.

The treatment is active: both runs have 261 conflicting updates out of 272;
R00 projects none, R01 projects all 261. Neither run clips a gradient. The
projection changes update magnitude and direction, and need not protect
continuations under AdamW or the remaining-task gradient. This negative result
does not establish that gradient interference is irrelevant in every model.

Conditional change destinations improve 288 to 309, while conditional
continuations fall 2,792 to 2,763. On change rows, repeat modes fall 2,061 to
1,969 and median gold rank stays three. Repeat/complement group NLL improves
0.635837 to 0.520661, with a smaller within-alternative improvement. Forcing a
nonrepeat destination gets 901 versus 953 changes correct; that oracle uses
unavailable change knowledge and is not achievable policy accuracy or a ceiling.

Outside movement, complete attacks gain five and recalls gain nine, while ends
lose one; other category counts are unchanged. Complete casts, priority, ward
and several rare categories remain zero; all 353 shops are strict failures.
Correct 32-root windows increase 28 to 29 out of 1,085. Every category, paired
group/window result, false positive and probability diagnostic remains in the
saved reports; small isolated improvements do not change the negative verdict.

The prefit implementation and completed R00 received independent Sol xhigh
approval. Parent R01 checks verified all 92 source, 94 input and 22 run-archive
bindings, identical initial weights/RNG, eight matched schedules and exact row
coverage, update denominators, finite gradient records and changed selected
parameters. Initial/final saved summaries and the complete paired comparison
reproduce exactly. A 1,024-row causal forecast probe matches each checkpoint's
saved predictions exactly. R01 and this report now require independent review.

Both reserved partitions remain sealed. There are no new held-data evaluations,
matches, replay downloads, bot/runtime changes or deployment. These exposed
fitting windows, one seed and observed past actions cannot establish strategic
intent, playing strength or transferable movement. Missing shop arguments,
ambiguous entity targets and incomplete legality/new-POST validation remain.
Original strong-reference, category-90%, reliability and three-seed requirements
remain binding. Continuing research requires a distinct hypothesis and separately
reviewed protocol; this routing rule has failed its specified allocation test.
