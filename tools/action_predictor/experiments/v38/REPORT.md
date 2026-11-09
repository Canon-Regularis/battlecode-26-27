# V38: movement-only neighborhood correction

Both arms completed their frozen eight-pass fits. The actual-neighborhood treatment N01 fails four of the 18 allocation conditions against both the matched center-only control N00 and frozen R00. Small favorable fitting differences do not meet the prospective improvement requirements. No transfer experiment, repeat, extension or promotion is supported by this result.

The reviewed V37 audit motivates testing whether surrounding terrain helps distinguish destinations. Both arms add the same 5,697-parameter correction to movement tile logits while freezing the 139,292-parameter reviewed R00 backbone. N00 repeats each destination's center terrain across the available patch slots. N01 will receive the actual 3x3 terrain patch with the same crop-availability mask. Both retain the same candidate features, shared context, original support mixture, observed-command likelihood and joint decoder. This is distinct from the earlier shared map-fusion intervention; it does not establish that the earlier failure was caused by shared gradients.

The population is all 1,085 existing contiguous fitting windows: 34,720 rows across 40 previously exposed groups. Neither arm selects the V37 error cohort. Each arm has eight passes, 277,760 row presentations and 272 optimizer calls, with seed 27 for the fresh correction, identical schedules, reset/detach every eight roots, and final-pass-eight selection only. The paired fitting/evaluation cap is 7,200 seconds; there are no repeats or extensions. N00 consumed 81.279811 seconds and N01 80.592744 seconds, totaling 161.872555 seconds. The actual Astra high N00 approval was bound before N01 ran.

## Final fitting results

| Fitting metric | Frozen R00 | N00 | N01 |
| --- | ---: | ---: | ---: |
| Complete commands / 34,720 | 26,717 | 26,726 | 26,739 |
| Complete moves / 5,472 | 2,924 | 2,922 | 2,936 |
| Complete changes / 2,669 | 258 | 261 | 272 |
| Complete continuations / 2,796 | 2,666 | 2,661 | 2,664 |
| Change coordinate NLL | 2.253202083 | 2.213696678 | 2.194434555 |
| Change within-alternative NLL | 1.617364970 | 1.609760849 | 1.585064628 |
| Balanced movement joint NLL | 1.725759753 | 1.716253537 | 1.698749474 |
| Full-command NLL | 1.246750918 | 1.245355751 | 1.242602216 |
| Macro-F1 | 0.351642256 | 0.351467071 | 0.351788610 |

For N00, four of the 18 frozen conditions fail against R00: complete-change gain (+0.1124 percentage points versus at least 5), complete-movement gain (-0.0365 points versus at least 1), change-coordinate NLL reduction (0.03951 versus at least 0.15), and within-alternative NLL reduction (0.00760 versus at least 0.05). Continuation protection and the remaining guards pass. These small fitting changes are not a qualifying movement improvement. The grouped interval for complete-change gain includes zero; favorable leave-one-group-out signs are overlapping fitting diagnostics, not independent replication.

N01's final comparisons fail the same four conditions against each required reference:

| Required gain or reduction | Minimum | N01 versus N00 | N01 versus frozen R00 |
| --- | ---: | ---: | ---: |
| Complete-change accuracy, percentage points | 5.0 | 0.4121 | 0.5245 |
| Complete-movement accuracy, percentage points | 1.0 | 0.2558 | 0.2193 |
| Change-coordinate NLL, nats | 0.15 | 0.01926 | 0.05877 |
| Within-alternative NLL, nats | 0.05 | 0.02470 | 0.03230 |

The other 14 conditions pass against both references, including continuation, targeting, command accuracy, full NLL, macro-F1 and movement false positives. Against N00, N01 gains 11 complete changes, 14 moves, three continuations and 13 commands. The grouped 95% interval for change accuracy spans -0.0369 to +0.9074 percentage points; the movement interval spans 0 to +0.5168 points. The paired full-command NLL difference is -0.0027535 nats per row. These are descriptive fitting differences, not a successful allocation or evidence of strategy. The conjunction of all conditions fails, regardless of the number of passing guards.

All category scores, movement false positives, paired group/window results, and probability decompositions are retained in `N00.json` and `N01.json`. Nonmovement conditional scores and likelihoods remain unchanged, while some complete-command predictions change because movement competes in joint decoding. Complete casts, priority, ward and several other categories remain zero; all shops remain strict failures because purchase arguments are unavailable.

The prefit code review verified all 26 tests, 101 source and 113 input bindings, matched initialization, full initial forecast parity, and update/normalization/budget gates. Initial forecasts reproduce R00 on all 34,720 rows. Both fits record exact frozen-backbone checks at every checkpoint and finite gradient norms at all 272 updates per arm; no update clipped. Parent verification reproduced all initial/final command and movement forecasts, summaries and comparisons exactly for both arms, and confirmed that precisely the six residual tensors changed. N00 received independent Astra high approval. N01's independent negative-result review remains pending.

## Interpretation

The specific neighborhood correction failed its allocation test at this model, residual seed, population and budget. This does not establish that surrounding terrain is irrelevant, that movement observations are sufficient, or that training longer would succeed. V37's structural readout restriction remains valid, but removing that restriction in this form did not deliver the required movement gains. Favorable likelihood or oracle-exclusion diagnostics cannot override the frozen behavioral gates. No automatic extension or transfer run follows.

This remains a one-seed, fitting-only correction on a warm, frozen fitting-trained model, using observed past actions and previously exposed, availability-enriched groups. Missing shop arguments, ambiguous entity targets, incomplete legality and new POST validation remain unresolved. No generalization, recovered intent, high-level strategy, playing-strength improvement or promotion is established. Strong G00/L02/JP02 references, category-90%, reliability and three-seed requirements remain binding.
