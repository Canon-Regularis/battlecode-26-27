# Shared signed priority correction

Current results: [V24 index](../experiments/v24/INDEX.md). RC00 has completed; its fresh review precedes the unrun RC01 treatment. The design-stage description below is retained, rather than treated as the current execution status.

This is an unfitted experimental component. No new policy prediction, training result or promotion is established by its contract tests.

For each available P05 point component with exact integer value `p`, construct the same 72 candidate-relative Boolean features: 24 own current/scheduled/latest/history relations and all 48 other-unit relations declared in OD03. A shared learned vector adds `w dot features(p)` to that component's original logit. Duplicate explanations at the same integer receive the same correction. The original P05 core is frozen.

Normalize all corrected point logits together with the retained logistic fallback component. Its raw logit, location and scale stay unchanged; its normalized mixture weight can change. Likelihood and integer MAP use the unchanged marginalized P05 probability arithmetic. No recorded integer, selected wrong alternative or intent label is an inference input.

The input uses exact int64 priorities, explicit availability, unit current/scheduled pairing and ally/enemy role. Unknown values do not participate. It does not restore champion attributes or every history interaction. No API legality or information-sufficiency claim follows.

The separately registered RC study will compare real versus matched shuffled scheduling inputs with identical own-history features and active parameterization, fresh group separation for the new correction fit, and fixed optimization. Both arms must use real causal inputs at primary inference. A shuffled training control tests decision-specific learning; it is not a policy that queries future rows at inference. The original warm model previously saw eligible TRAIN, so these groups cannot be called untouched-policy tests.

Any later complete-policy assessment must supply the features on every decision and recompute normalized joint commands. Conditional priority accuracy alone cannot demonstrate a policy gain. The original benchmark and success targets remain binding; reserved partitions remain sealed.
