# V39: direct weight and activation inspection

The clearest checkpoint-local bottleneck is a strong learned preference for the previous displacement, combined with weak discrimination among alternative destinations. The new neighborhood correction usually changes a wrong pair's score in the favorable direction, but is too small to overturn the existing winner. This identifies how the saved models make these errors; it does not establish why optimization learned this solution or which retraining change will fix it.

This audit reads R00, N00 and N01 initial/final weights and traces the causal contexts for the same 34,720 fitting rows, including 5,472 recorded moves. It performs no optimization. All three reconstructed movement distributions match the saved forecasts exactly, with zero probability error and zero mode disagreements. Current commands are assimilated only after collecting their contexts.

## The learned repeat preference is behaviorally dominant

R00 gets 288 of 2,669 direction-change destinations correct conditionally, versus 2,792 of 2,796 continuations. Among its 2,381 wrong change predictions, 2,061 choose the exact previous displacement. These counts concern destination selection given movement, not complete-command accuracy.

The grid exposes two direct previous-move features: exact equality to the previous displacement and Chebyshev distance from it (`rich_data.py`, channels 18 and 19). In a diagnostic intervention, zeroing those two channels while preserving the actual history/context raises correct changes from 288 to 635, but reduces correct continuations from 2,792 to 747. Change-coordinate NLL falls from 2.2532 to 1.8189; continuation NLL rises from 0.5092 to 1.8483. Total conditional correctness falls from 3,080 to 1,382.

This demonstrates strong checkpoint dependence on those features. Removing them is not a usable fix: they carry essential continuation information, and the intervention is out of distribution. The unresolved problem is learning when to override repetition while ranking the new destination correctly. Alternative errors remain even when repetition is excluded, as the earlier audits already showed.

## The neighborhood correction is active but too weak on most wrong pairs

For the 2,381 wrong change predictions, the median baseline score advantage of the wrong winner over gold is **1.6501 logits**. N01's median correction to that same wrong-minus-gold margin is only **-0.07191 logits**. It favors gold on 1,816 pairs, but exceeds the original margin on only 37. Overturning that particular pair does not guarantee gold becomes the overall winner; other destinations still compete.

Across all fitting movements, the median score range over supported candidates is 2.8277 for R00's dynamic candidate score, 1.6661 for its destination bias, and 0.1993 for N01's correction. These are descriptive distributions, not additive attribution percentages. The global mathematical bound from N01's final readout weights is much larger (4.3624 logits for a pair), so this is an observed checkpoint behavior, not a proof that the architecture can never express a larger correction.

All six correction tensors changed during training; the backbone was intentionally frozen. V38 therefore did not retrain the existing repeat preference. It added a comparatively small correction to it, which helps explain why lower likelihood losses produced few additional correct changes.

## Random destination biases persist, but removing them does not solve movement

`JointModel.offset_bias` is an `nn.Embedding`, with random initial destination biases. Across its 289 movement tile entries, the final/initial correlation is 0.999842 and the RMS update is 0.02335. Most of those entries are outside ordinary movement support, so the more relevant check is the eight supported neighboring offsets: correlation **0.998912**, initial standard deviation **0.62180**, and RMS update **0.04935**. Their final biases range from -1.0969 to +0.5692, creating an approximately 5.29-fold odds factor between extremes before the learned feature score is included.

For 1,768 change rows where the strongest incorrect nonrepeat supported alternative outranks gold, the mean margin is 0.8080 logits: dynamic features contribute +0.2428, initial bias +0.6194, and learned bias updates -0.05421. In 716 such pairs, the dynamic term alone favors gold. These are target-selected error-pair decompositions; they are not population-wide causal attribution.

Crucially, removing all final movement offset biases changes correct direction changes only from 288 to 291. Subtracting only their actual initial random component gives 285. Other wrong alternatives and repetition still win. This falsifies a simple explanation that random biases alone cause the poor movement accuracy. A neutral-bias initialization remains a plausible separately controlled hypothesis, not a demonstrated remedy; post-hoc deletion is not equivalent to retraining.

## Saturation is not the main failure in the inspected movement layers

On supported fitting candidates, the original candidate tanh has mean derivative **0.9536**, minimum 0.4532, and no derivatives below 0.1. It is mostly in its responsive, near-linear region rather than saturated. N01's correction tanh has mean derivative **0.8679**; 0.662% are below 0.01. Severe saturation is therefore not widespread in these inspected layers. This does not audit every recurrent gate or establish that all upstream representations are adequate.

Removing the current additional-memory projection changes correct changes only from 288 to 289; removing the observation-history-plus-priority projection gives 297. Both preserve the explicit command-history encoder and the original causal state trajectory. Their effects are modest at this checkpoint and do not prove history is useless or that a policy retrained without memory would behave the same way.

## What this supports next

Prioritize the mechanism that decides when the strong previous-displacement score should yield to an alternative, and verify whether the alternative scorer can learn the correct ordering at those moments. Do not infer that a larger generic model, more memory, removing history, a repeat penalty, or longer training will solve it. Earlier failed mixture, hierarchy, cadence and gradient-routing interventions still constrain the next design. A neutral-initialization contrast is another concrete hypothesis exposed by these weights, but its weak post-hoc effect prevents treating it as the explanation or launching an automatic fit.

These are fitting-only, single-checkpoint interventions on observed histories, with previously exposed groups, missing shop arguments, ambiguous entity targets and incomplete legality/outcome validation. They establish neither strategy nor playing strength. All checkpoints and the deployed bot remain unchanged.

## Reproduction and limitations

The prospective diagnostic plan fixes the population, interventions and parity checks. Four focused synthetic tests cover the support mixture/fallback, additive margins, strata arithmetic and cohort aggregation. The first attempt completed its forecast archives but failed final aggregation because a cohort-name prefix also matched a longer cohort name. Its plan and archives are preserved. The corrected run uses exact component names; its first preflight then rejected duplicated path-separator bindings before data loading. Rejected bytes are preserved, and normalized bindings passed. Neither issue caused optimizer updates or selected a favorable model. `audit.json`, `supported-offsets.json` and the bound local arrays retain the results; independent code/evidence review is pending.
