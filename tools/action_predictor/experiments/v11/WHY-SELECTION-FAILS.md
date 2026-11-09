# Why the selector does not choose the available correct command

There is a more specific answer than “the model cannot learn Fish.” **A substantial part is a mismatch I introduced between the trained mixture and its hard decision rule.** Some ranking is learned, then discarded by the router. A separate ranking/fitting problem remains; its ultimate cause is not yet isolated. No new fit, candidate library, replay extraction or architecture experiment was run for this investigation.

## 1. What happens in the 1,516 available-command failures

Using the original A00 checkpoint and all original DEV rows:

| Failure inside available support | Count |
|---|---:|
| Correct command is strictly first among point candidates, but the router uses the wrong G00 forecast | 886 |
| Wrong candidate ranks first; the router nevertheless uses the wrong G00 forecast | 571 |
| A wrong candidate is selected | 53 |
| Only G00's forecast is correct, but a candidate overrides it | 6 |
| Total | 1,516 |

The first 886 cases are not exact ties; an independent command-group calculation confirms the correct point command strictly outranks every wrong point command. This does **not** imply all 886 should be fixed by taking the best point candidate. The teacher may still assign a competing command higher probability in the full mixture, and a general rule must also handle rows where the best point candidate is wrong.

Among the 1,628 G00 errors that the library could rescue, the correct command is the highest-scoring point command on **1,021 rows (62.71%)**, but A00 actually rescues only **135 (8.29%)**. Thus the claim that the model never learned which candidate to favor is too broad. The action that is emitted loses much of its internal point ranking.

The mechanisms differ by category. For movement, 281 of 623 available-command failures have the correct point command ranked first but vetoed; 342 rank a wrong point command first. Recall has 477 vetoes among 514 available failures. Neither cast category has a correct-top-point veto in this breakdown; their available failures primarily involve wrong ranking. One global routing change cannot be assumed to solve every family.

## 2. The trained probability and the emitted decision are different

For command c, the fitted model represents:

`P(c) = fallback_weight × G00_probability(c) + sum(weights of point candidates emitting c)`

The original hard decoder instead compares the **entire fallback weight** with the weight of one point-command group. If the fallback wins, it emits G00's action-first hard command. The fallback weight belongs to a distribution over many commands; it is not the probability that G00's single emitted command is correct.

For example, a fallback weight of .8 and G00 command probability of .1 contribute only .08 to that command. A competing point command with weight .15 can be more probable, yet the hard router compares .8 with .15 and takes the fallback. The training objective does not require fallback weight to behave as a calibrated binary “trust the G00 hard forecast” score.

This is not merely theoretical. In **571 of the 1,516 available-command failures**, the recorded correct command has higher modeled mixture probability than the command actually emitted. This establishes a command-probability decision mismatch on those rows; it does not require knowing Fish's intent.

The already frozen D00 bounded probability decoder fixes **542 A00 errors** and introduces **125 regressions**, for **+417 net**. It still leaves 1,099 available-command failures. This is a no-fit comparison using the same A00 weights, not evidence that the remaining ranking problem has disappeared.

| Saved weights / decision rule | Strict DEV successes |
|---|---:|
| G00, original action-first hard forecast | 11,510 |
| G00 probability alone, same bounded command set | 11,950 |
| A00 mixture, original hard router | 11,622 |
| A00 mixture, bounded probability decoder (D00) | 12,039 |

The matched probability comparison isolates an additional **89 net successes** from the learned mixture, beyond the large decoding/search gain. Therefore it is also wrong to say no useful selection was learned. However, D00 lowers macro F1, loses priority/cast successes and gets no complete wards right. It remains unpromoted. Probabilities describe the modeled observed representation, including a marginalized shop bucket; they are not complete purchase-command probabilities or globally exhaustive MAP over API commands. All shops remain strict failures.

The original hard-router approximation was disclosed in the study. The new result quantifies its impact; it does not turn a disclosed approximation into an undisclosed implementation bug. It was nevertheless a poor training/decision contract for the goal of exact command selection.

## 3. The remaining problem is already visible on TRAIN

On all 288,801 identity-certified natural TRAIN rows, A00 captures only **3,814/28,903 rescuable G00 errors (13.20%)**, versus 8.29% on DEV. For movement, capture is **764/11,936 (6.40%)** on natural TRAIN and **18/635 (2.83%)** on DEV.

This is not solely a held-out generalization failure. The current model-plus-decoder does not exploit most training opportunities either. On natural TRAIN there are 15,422 correct-top-point vetoes, 9,829 wrong-point-ranking failures and 61 cases where only G00 is correct but is overridden.

Replaying the 23 saved A00 checkpoints on a fixed 8,192-row natural TRAIN sample and every DEV row shows limited, unstable rescue capture throughout. The original selected round 17 has 13.53% sample-TRAIN capture and 8.29% DEV capture. Round 22 reaches 16.43% and 9.21%, but has worse DEV NLL under the frozen selection rule; round 23 falls to 9.42% and 4.55%. These are descriptive trajectories, not permission to retrospectively select a different checkpoint. “Just train it longer” is not supported by this trace.

The earlier R02 memorization test used the larger existing M01 joint model, not A00's selector. It demonstrates that selected movement labels can be memorized by that configuration; it does not establish that this particular selector has fit its available-command task.

## 4. What the loss and inputs establish—and do not establish

**The correct supervision is present.** The loss sums every candidate explanation matching the recorded command; it does not invent one true algorithm label. Analytic derivatives at the stored scores still push correct candidate mass upward on rescuable TRAIN rows (mean derivative of their summed correct-slot logits about −.211) and push fallback weight downward (mean about +.170). This is not a case of training being given no signal to correct those examples.

There is substantial opposing pressure. On 41,662 natural TRAIN rows, no point candidate matches at all, so the loss must favor the fallback. Eight paired local gradient measurements at the selected checkpoint have whole-parameter cosines around −.91 to −.93 and input-layer cosines around −.61 to −.66 between rescuable rows and fallback-only rows. These are **local competition measurements**, in evaluation mode without dropout. They do not prove unavoidable interference or establish whether inputs, model capacity, initialization or optimization are the dominant cause. A sufficiently expressive conditional router could satisfy both populations.

**The initialization is strongly conservative:** its natural-TRAIN median fallback weight is 99.67%, and its minimum is 99.10%, from the fixed +4/−4 biases. At the selected checkpoint, rescuable DEV errors still have median fallback weight 89.17%. This is consistent with conservative behavior, but no controlled initialization intervention has established how much of the failure it caused.

**Optimization may be constrained, but that is not yet a causal finding.** About 48.5% of hidden tanh activations exceed .99 in magnitude on the fixed natural sample. Only .047% of normalized input elements are clipped. Saturation can attenuate gradients, but these measurements alone do not establish a stalled optimizer or explain the ranking errors.

**A00 does not directly score the current proposal.** Its scorer sees 253 current features plus eight earlier action encodings; candidate availability masks its logits. It does not receive the candidates' coordinates, actual generating goal locations, route improvements or costs. It must infer which fixed slot is useful from compressed global context. This is a concrete information/design limitation, not a quantified causal error share. A01 added local candidate descriptors but simultaneously changed context size, parameter count and shared scoring; its negative result does not isolate whether proposal information helps.

An exact routing-input consistency test also found no additional forced errors in the repeated natural TRAIN signatures among available-support rows: 332 repeated groups/664 rows all share at least one correct routing option. Signatures include the actual clipped selector inputs and decoder alias pattern. Almost all inputs are unique, so this has low power: it neither proves the observations sufficient nor explains the remaining errors as contradictory labels.

## Conclusion and next step

The strongest supported answer is: **we trained useful point preferences, but used a hard router inconsistent with the fitted command probabilities; the remaining candidate ranking is also underfit on TRAIN.** It is not evidence that choosing correctly is intrinsically unlearnable.

I cannot yet honestly assign the residual ranking failures mainly to missing history, limited inputs, conservative initialization, optimization or capacity. The evidence above narrows those alternatives without pretending to settle them.

Before another fit, the decision rule and modeled probabilities must be evaluated under the same contract, with the matched G00 probability decoder and category guards retained. D00 is evidence for that requirement, not a deployable fix. The most informative unresolved-cause test remains the previously specified **no-fit matched causal goal-history control**: identical candidates, planner, ties, stopping rules and availability, varying only the causal selection evidence against current-observation and last-heading controls. No new architecture or optimizer is allocated here.

Evidence: [S00 plan](S00-plan.json), [scores/gradients/epoch traces](S00-selection.json), [exact-input and independent veto checks](S01-routing-inputs.json). No large training, replay download, match, proposed-action simulation or reserved evaluation occurred. Original checkpoints and reports remain frozen. Both reserved partitions are sealed; production training stays paused.
