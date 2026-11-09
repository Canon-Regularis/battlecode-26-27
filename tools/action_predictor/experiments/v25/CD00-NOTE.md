# Frozen correction dependence and remaining errors

RC00's 1,101 held-group conditional integer errors divide into 763 with sufficient any-weight impossibility witnesses and 338 for which this diagnostic found no certificate. The latter are not proved reachable or learnable. The limitation belongs to the frozen core, feature values and correction family, rather than to observations or learned policies generally.

| Fixed weight intervention | Fit exact /4,208 | Held exact /1,668 | Held mean integer NLL |
| --- | ---: | ---: | ---: |
| Zero all correction weights: warm P05 | 1,051 | 412 | 3.001405 |
| Retain own-history weights only | 1,445 | 578 | 2.683395 |
| Retain other-unit weights only | 1,038 | 404 | 2.998583 |
| Full saved RC00 | 1,431 | 567 | 2.680414 |

Most of the full model's observed improvement depends on its own-history weight block. Adding the saved other-unit block to the own-only intervention loses 11 exact held integers while reducing NLL by 0.002981 nats. These are fixed-weight substitutions in a co-adapted model trained with shuffled other-unit inputs, not retrained input ablations. No intervention is selected as a replacement. They neither identify the outcome of real-information training nor demonstrate that other-unit information is useless.

The representation split is also informative. On the 993 held rows where the recorded integer matches none of the 72 tested candidate-relative relations, warm P05 gets 199 correct and full RC00 167. On the 675 rows with at least one such relation, the corresponding counts are 213 and 400. The net changes are -32 and +187, yielding +155 overall. Zero target features means none of these particular relations match; it does not mean that the observation contains no information. The frozen base still consumes its original context and priority features.

| Full RC00 residual partition | Fit errors | Held errors |
| --- | ---: | ---: |
| Sufficient fixed-configuration impossibility witness | 1,931 | 763 |
| No certificate found | 846 | 338 |
| Total | 2,777 | 1,101 |

The full intervention reproduces all archived RC00 raw and decoded arrays exactly. The zero intervention reproduces warm P05 raw and prediction arrays exactly. Every intervention has zero correct answers in the certified-unreachable subset. All raw arrays precede measurement, and all decoded arrays precede consistency checks. No optimizer is constructed, no parameters are trained, and no new queries or reserved payloads are accessed.

The [plan](CD00-plan.json) names all four fixed-checkpoint interventions before their forwards. The [result](CD00.json) binds the sources, saved checkpoint, proof witnesses and new raw/prediction archives. Reproduce only into absent destinations with `python -m tools.action_predictor.priority_reference.correction_diagnosis`. All 5,876 rows remain accounted for. The recorded priority family is supplied; action selection and complete-command improvement remain unassessed. Warm heads and encoders previously saw these eligible TRAIN games, and prior research inspected the population.

This later evidence is outside the already running RC00 review. It does not modify that experiment, select a replacement, change the registered RC01 protocol, or establish Fish intent. The pending real-versus-shuffled training contrast remains the appropriate comparison for its separately named information hypothesis. Original complete-policy success targets remain unmet.
