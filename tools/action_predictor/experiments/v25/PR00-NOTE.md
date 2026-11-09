# Retained P03 reference on identical TRAIN rows

The historical P03 head does not beat warm P05 on this particular cohort. Its stronger original DEV exact-integer score should not be generalized to every population, nor should P05 be called the strongest retained head on every metric.

| Population | Rows | Retained P03 exact | Warm P05 exact | P03 mean integer NLL | P05 mean integer NLL |
| --- | ---: | ---: | ---: | ---: | ---: |
| All broad natural TRAIN | 5,876 | 1,325 | 1,463 | 3.230220 | 3.002684 |
| RC correction-fit groups | 4,208 | 954 | 1,051 | 3.241946 | 3.003191 |
| RC correction-held groups | 1,668 | 371 | 412 | 3.200640 | 3.001405 |

On the 1,668 correction-held rows, P03 rescues 92 warm-P05 errors and introduces 133, for a net loss of 41. The exploratory paired whole-group accuracy difference interval is [-3.695, -0.848] percentage points, and the mean NLL difference interval is [+0.16192, +0.23014] nats. Both models previously saw these TRAIN games. These are retained-model comparisons on reused evidence, not an untouched test or an independently trained control.

P03 retains its original absolute-point plus logistic-fallback architecture, normalization, selected checkpoint and decoder tie rule. No weights, temperatures, thresholds, inputs, checkpoint selections or policy decoders change. P03 and P05 use identical frozen M01 contexts and causal 39-channel own-priority inputs on identical rows. P03 has no P05 residual-point mechanism. This assessment does not isolate why their predictions differ.

All 5,876 raw P03 outputs were saved before measurement; integer forecasts were saved before target scoring. An independent NumPy reconstruction checks every integer mode and normalized target likelihood. It consumes recorded targets only after forecasting. Full raw-observation serving, action selection and complete commands are not assessed. No DEV/reserved payload, new engine query, fit, optimizer, match or bot work occurs.

The [plan](PR00-plan.json) freezes this comparator assessment before its forwards. The [result](PR00.json) binds sources, inputs, raw outputs, predictions and arithmetic checks. Reproduce only into absent destinations with `python -m tools.action_predictor.priority_reference.evaluate`; do not overwrite this immutable completed run.

This is later evidence outside the already running RC00 independent review. It does not select a new model or change the registered RC01 comparison or original success criteria. RC01 remains unrun pending that review. Any future complete-policy assessment must include relevant retained comparators and normalized joint decoding, rather than infer policy benefit from conditional integers.
