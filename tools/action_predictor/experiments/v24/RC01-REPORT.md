# RC01: shared signed priority correction

The P05 core is frozen. Only 72 shared signed relation weights are trained on all available point components, with original duplicate marginalization and full-support logistic fallback. Own-history features are identical between arms. RC00 uses matched shuffled other-unit information during optimization; RC01 uses real information. Both use real causal inputs for every primary assessment. No alternative decoder or recorded-label router is used.

| Update | Real-input fit exact /4,208 | Real-input held exact /1,668 | Fit NLL | Held NLL | Actual optimization-input fit NLL |
| --- | ---: | ---: | ---: | ---: | ---: |
| 0 | 1051 | 412 | 3.003191 | 3.001405 | 3.003191 |
| 100 | 1237 | 487 | 2.875604 | 2.872415 | 2.875604 |
| 500 | 1456 | 575 | 2.690084 | 2.682164 | 2.690084 |
| 1000 | 1534 | 617 | 2.624513 | 2.610761 | 2.624513 |
| 2000 | 1541 | 618 | 2.613734 | 2.597713 | 2.613734 |

| Population/reference | Rescues | Regressions | Net | Mean NLL difference | Paired accuracy interval |
| --- | ---: | ---: | ---: | ---: | --- |
| fit / warm | 648 | 158 | 490 | -0.389457 | [0.10247068410879835, 0.12839562410587227] |
| fit / RC00 | 172 | 62 | 110 | -0.091466 | [0.02060855979360915, 0.0319129087478249] |
| held / warm | 281 | 75 | 206 | -0.403691 | [0.10513992796813315, 0.14218480393971933] |
| held / RC00 | 81 | 30 | 51 | -0.082701 | [0.01889189355294696, 0.04441494525082552] |

The correction fits 4,208 natural-priority decisions from 40 groups; 1,668 decisions in 15 groups are excluded from this optimization. The split is fixed by group seed 20261125, not label difficulty. Every one of the original 5,876 broad rows remains in the tables. The frozen encoder/head/vocabulary previously saw these eligible TRAIN games, and prior diagnostics inspected the population. This is not a fresh full-policy test. Legacy 128-row controls and DEV are not evaluated in this study.

Both arms have the same 72 supported, active trainable weights and zero initialization. No new integer vocabulary or hidden layers are introduced. Both current and scheduled per-unit values remain exact int64 with availability masks; unknown values never match. Raw fallback location, scale and component logit stay fixed, while its normalized mixture weight may change with point corrections. Own/history relations and selected alternatives from OD03 are not treated as true-intent labels.

The fixed endpoint is 2,000 full-population mean-gradient updates, accumulated through 256-row chunks, AdamW .003 then .001, zero decay, clip 5, inherited lambda 3.029750319831723e-5 times summed squared new weights. No group, strength, threshold, relation, seed or checkpoint is selected from held outcomes. Interim assessments are descriptive; the warm baseline is a retained comparator, not an alternative selected endpoint.

With zero correction initialization, fixed full-population order and frozen inputs, this fit is deterministic for its split and corruption. Merely changing the Torch seed would not provide independent full-policy seed consistency. No robustness or three-seed claim follows from this diagnostic.

RC00 actual optimization-input fitting and real-input TRAIN performance are distinct quantities. The control corruption stays within group/engine/availability blocks and never crosses correction fit/held membership. Neither primary evaluator requests donor information at inference. Singleton or numerically unchanged corruption rows remain included.

Context tables include unavailable other-unit information, correction-fit unseen integer values, current/scheduled differences, earlier argument availability and historical engines. Unseen refers only to this correction fit, not to the warm model vocabulary. Engine and group/context differences are confounded. Empty strata remain explicit with null metrics. Conditional confidence bins and mode-correctness Brier do not establish global calibration.

This is conditional integer prediction with the recorded priority family supplied. It does not report action-type PRF, macro F1, correctly-typed conditional parameters or complete-command accuracy. Those require predicted family choices and normalized joint redecoding with new inputs on every decision. Existing predictors remain unchanged. No policy is promoted; original category/movement/macro/NLL/targeting and three-seed requirements remain unmet. Shops, sparse actions, entity identity and full legality retain their original limitations.

Fit source `92cc3abf667306c170567a3e7c55fadb5d8146b7`; trainable weights 72; completed updates 2000; presentations 8416000. Measured time includes training, assessments and serialization after preflight, not pure optimization or serving. All initial/raw forecasts and states precede their checks. The original core fingerprint and all fallback raw fields remain unchanged.

Registered exploratory allocation checks: `{'held_exact_gain2pp_over_warm': True, 'held_exact_gain1pp_over_control': True, 'held_NLL_lower_than_both': True, 'majority_held_groups_net_positive_over_warm': True}`. Passing is not original success or robustness.

Reproduce only into absent destinations: `python -m tools.action_predictor.relational_priority.fit RC01`, then `python -m tools.action_predictor.relational_priority.results RC01`. Do not rerun completed fitting. A fresh Sol xhigh post-fit challenge follows each arm before another substantive fit. No matches, downloads, new replay queries, reserved accesses, bot/runtime work or deployment.


Additional frozen-configuration diagnostic: all held integers have point support, but at least 763/1668 cannot become MAP under any shared correction weights with these base distributions and feature values fixed. The conservative conditional upper bound is 905/1668. Most witnesses are same-zero-feature candidates whose existing ordering cannot change. This is not an observation or architecture ceiling; retraining the core or changing features/context invalidates it. It does not select a replacement configuration.


Bounded nonzero-head input parity: passed `True` on32distinct personal-API input cases, with batch256padding and separate batch1 checks. Exact other-unit fields are rebuilt from saved getter records; own history and M01 contexts reuse validated caches. This is not full raw-observation encoder/filter or native serving certification. Original numerical criteria and any failures remain preserved.
