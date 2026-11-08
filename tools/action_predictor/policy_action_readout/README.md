# Prospective action-belief readout

This small component is untrained and has no fit runner or selected feature treatment. It prepares a probability contract for an evidence-led action-selection comparison after the V27 independent review. No experiment outcome or benefit is claimed.

Given frozen family beliefs, it learns an affine correction from explicitly supplied causal features and normalizes all 15 family probabilities together. Existing conditional command distributions remain fixed. Its loss uses the recorded command only as supervision, while decoding ranks each family's actual conditional mode mass multiplied by the learned family probability. It never normalizes mode scores or chooses arguments using the recorded family.

This is a marginal-family correction. It is not the original per-goal action readout, a newly trained recurrent filter, or evidence of strategic learning. A future protocol must explicitly hold or recompute filtering, freeze input schemas and active-capacity controls, use full original denominators and checkpoint rules, compare complete commands and every category, and receive fresh post-fit review. The component itself allocates no fit.

No-update contract command:

```text
python -m unittest tools.action_predictor.policy_action_readout.test_model -v
```

Tests use synthetic distributions and do not update parameters. They establish arithmetic and interface properties, not quality. No reserved data, matches, bot/runtime or deployment work is used.
