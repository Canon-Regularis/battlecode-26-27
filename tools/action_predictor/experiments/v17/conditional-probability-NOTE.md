# Stable conditional-probability helper

The existing decoder derives a conditional parameter log probability by
subtracting marginalized type log mass from joint log mass. For rare
hypothetical families, float32 cancellation caused Q01's original normalization
check to fail. An additive helper instead normalizes latent component weights
conditional on the family before marginalizing parameter probabilities. The
formulas are equivalent in exact arithmetic; the new helper is not integrated
into any retained predictor, training runner or decoder.

The protocol and source hashes were frozen before numerical assessment, in
commit `bc6e22c`. Three focused tests check independent probability arithmetic,
command-loss gradient equivalence and tiny-family/zero-head-probability cases.
They pass. The assessment uses every saved Q01 worst-normalization batch for
both checkpoints, across every spatial family. This is a selected numerical
cohort with repeated contexts across branches/scopes, not a fresh performance
sample. It requires no replay extraction or optimizer operations.

| Check | L01 | L02 |
| --- | ---: | ---: |
| Saved batches | 26 | 26 |
| Real case rows, including repeats | 792 | 790 |
| Conditional distributions checked | 7,128 | 7,110 |
| Original maximum normalization error | 4.74294e-6 | 5.26456e-6 |
| Stable maximum normalization error | 3.87872e-7 | 4.72712e-7 |
| Independent float64 normalization error | 8.88e-16 | 1.33e-15 |
| Conditional-mode changes, old versus stable | 0 | 0 |
| Conditional-mode changes, stable versus independent | 0 | 0 |
| Reconstructed complete-command mode changes | 0 | 0 |
| Maximum observed-NLL difference | 4.77e-7 | 9.54e-7 |

The stable calculation meets the prospectively retained 2e-6 criterion on
this cohort. The original Q01 check remains failed. No historical output is
replaced, no new policy is selected, and no imitation improvement is claimed.
These bounds do not establish behavior on every raw input, future trained
distribution or numerical tie. Component outputs and stored states are reused;
this does not independently reproduce the neural encoder or causal filter.
The helper requires positive total family mass, as documented. Fully impossible
families need an explicit caller contract rather than an invented conditional.

Reproduce from repository root with the pinned interpreter:

```powershell
& .venv-action-predictor/Scripts/python.exe -m unittest tools.action_predictor.learned_policy.test_conditional_probability
& .venv-action-predictor/Scripts/python.exe -m tools.action_predictor.learned_policy.conditional_assessment --freeze
& .venv-action-predictor/Scripts/python.exe -m tools.action_predictor.learned_policy.conditional_assessment
```

The immutable plan binds the new sources and retained numerical cohorts. The
assessment binds the plan, execution commit, checkpoints and saved contexts.
The exact score definitions, all original rows, shop failures, blocked-attempt
accounting and sealed partitions remain unchanged. No fits, matches, downloads,
bot work, reserved accesses or PR mutations occurred. This small correctness
follow-up does not resolve the demonstrated execution-learning bottleneck.
