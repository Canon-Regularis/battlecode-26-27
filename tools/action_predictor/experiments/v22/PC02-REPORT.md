# PC02: warm-start-regularized P05 contrast

One controlled diagnostic retains PC01’s population, architecture, inputs, initialization, seed, optimizer, full-population accumulation and fixed endpoint. It changes only the training objective by penalizing squared displacement from the warm P05 weights and bias.

`loss = mean normalized integer NLL + 3.02975031983e-05 × sum squared parameter displacement`

The strength is .5 times PC01’s initial broad TRAIN NLL divided by its final squared parameter drift. This is one TRAIN-derived prospective allocation rule for PC02, not a control-selected strength, sweep, or universally optimal regularization setting.

| Update | Broad fit /5,876 | Original fit /128 | Same-group control /128 | Disjoint-group control /128 | Penalty |
| --- | ---: | ---: | ---: | ---: | ---: |
| 0 | 1463 | 34 | 25 | 28 | 0.000000 |
| 100 | 3744 | 76 | 20 | 23 | 0.047592 |
| 500 | 4515 | 93 | 14 | 23 | 0.155988 |
| 1000 | 4645 | 98 | 13 | 22 | 0.200096 |
| 2000 | 4671 | 99 | 14 | 23 | 0.209981 |

| Cohort | Warm NLL | PC01 final NLL | PC02 final NLL | PC02 mean bounded rank |
| --- | ---: | ---: | ---: | ---: |
| broad_fit | 3.002684 | 0.606291 | 0.816277 | 1.683 |
| original_fit | 2.894059 | 0.701733 | 0.921480 | 1.859 |
| same_fit_groups | 3.147922 | 8.920198 | 6.119575 | 31.133 |
| held_groups | 3.051521 | 8.772601 | 5.879614 | 38.602 |

Named exploratory gate passed: **False**. Checks: `{'broad_fit_gain': True, 'both_control_NLL_lower': False, 'both_control_exact_not_lower': False, 'some_control_gain5': False}`.
This requires substantial fitting improvement, both control losses below warm, no control exact decline, and at least five additional exact values on one control. Merely preventing learning to recover warm scores is insufficient. The gate does not replace any original complete-command/category or three-seed target.

The full-population mean gradient is accumulated across chunks before one optimizer update. The displacement penalty is added exactly once per update. AdamW is unchanged (.003 then .001, 1,000 updates each; zero decay, clip 5); all 207,816 head parameters remain trainable. No threshold, calibration, alternative endpoint or seed is selected.

Both the frozen encoder and warm head previously saw the controls. They are excluded only from this new optimization. Results cannot establish untouched generalization, sufficient observations or a definitive cause of the original P05 failure. Rank is among distinct existing point/fallback-mode candidates, not every integer. Explanation shares marginalize equivalent outputs and are not Fish-intent labels.

The source gate binds static repository-local import closure and explicit prerequisite test modules. Optimized Python is explicitly refused. Real-entrypoint tests inject previously omitted-source mismatches and install an optimizer-construction tripwire. A separate injected measurement exception verifies that raw arrays survive. Assessments archive each complete cohort raw matrix before scoring it. These corrections are prospective; earlier incidents and frozen reports remain unchanged.

Fit source commit: `da1c7e3658a6a62f0c8b0d47487312dcc938df18`. Seven focused tests passed before optimizer creation. The prior approved accumulation check and identical cohort are reused; no repeated 495-game extraction audit. Timing includes optimization, assessment and serialization after preflight; it is not pure optimization or production serving cost.

This supplies the recorded priority family for conditional evaluation. The complete policy is not replaced. Any future integrated comparison must recompute normalized joint command probabilities and winning families. No full-command improvement, promotion or robustness claim follows. Original shop/sparse-category/identity/legality qualifications remain.

Both 75-game reserved partitions remain sealed; no DEV payloads, matches, downloads, bot/runtime work or deployment. Fresh Sol xhigh review follows.

Reproduce once into absent immutable destinations: `python -m tools.action_predictor.priority_regularized.experiment`, then `python -m tools.action_predictor.priority_regularized.results`. Do not rerun completed fitting.
