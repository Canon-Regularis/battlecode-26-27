# Priority action-path history: inspection, not a fit

This note records source inspection while the independent V27 review runs. It changes no reviewed implementation, checkpoint, decoder, data or experiment protocol and authorizes no optimization.

An earlier direct-priority-input action-classifier design already exists in V8. `action_priority_head.ActionPriorityHead` combines the warm M01 affine action head with a zero-initialized, bias-free 41-to-15 affine term. Its additional inputs are the normalized 39 own-priority/history channels plus explicit unavailable/changed indicators derived from exact PRE integers. The matched control zeros those channels. The preparation receipt records 2,550 trainable parameters, exact initial-logit and prediction parity, and **zero new fits**.

The retained workspace has the plan, preparation, tests and initial roundtrips. At inspection there is no `experiments/v8/C01.json` or `C02.json`, and neither `.cambc/action-predictor/v8/runs/C01` nor `C02` exists. Thus there is no retained completed-fit evidence for that pair here. This bounded artifact check does not prove that no interrupted optimization ever occurred elsewhere. It must not be summarized as a failed measured comparison.

That old runner is not an appropriate command to launch unchanged. It trains with M01's class-weighted action cross-entropy and selects actions by marginal type argmax, then routes parameters through the predicted family. Its own frozen arguments are P05. A new controlled comparison inside L02/RC01 would need to preserve the current normalized joint-command objective and MAP decoder, account for latent-component family normalization, and keep causal upstream filtering and nonpriority conditional distributions controlled. Reusing a source component does not make those experiments equivalent.

The current GoalPolicy action path consumes `step['context']` through `execution.action`, after the observation/history/entity/public/goal paths. Its `causal_inputs` interface does not directly supply the separately recovered 39-channel own-priority/history block. That omission is a concrete interface fact; it does not establish that the block contains useful incremental action-choice information. Existing action histories, observations and latent state may contain correlated information.

V27's probability bound gives this question practical relevance: under frozen L02 family beliefs and other conditional distributions, at most 344 of 576 DEV priorities could win joint competition even with hypothetical priority conditional point mass one. This is a limit of those frozen scores, not an observation-sufficiency or architecture ceiling. It motivates investigating action-family learning alongside the still-imperfect integer distribution; it does not select a new feature treatment or justify another fit before the current review is considered.

Inspected source/receipt SHA256 values:

| File | SHA256 |
| --- | --- |
| `action_priority_head.py` | `6aa90922b3f20ceada98749c61670e54b7b1a5ef648ea3b2374944111c4753b1` |
| `action_priority_fit.py` | `79b52ee353942a951013762486eb9e2a3724c2b60408d5c90ec572c509839e69` |
| `experiments/v8/action-priority-plan.json` | `1b48da0eb1c52a6ed36ffcaf97e4ce9e9082f5a91c059da7ee34003842e8e9dc` |
| `experiments/v8/action-priority-prefit.json` | `6fd362817b8f3d5ce7022e970f653ee87521a341ef660b00015a108a740df04e` |
| `learned_policy/model.py` | `718a7af0d65890796a3c152eb1c8c2d51e073cd1755d24b74c832a25e404a768` |

The source inspection and artifact-existence checks used only the same root checkout and eligible local metadata. No model execution, fit, optimizer, replay restoration, engine query, reserved data, bot work or PR action was performed for this note. Original benchmark and success requirements remain unchanged.

## Existing event evidence reused

The completed V8 D01 analysis already counted current/scheduled PRE equality on all augmented TRAIN targets: all 14,816 priority targets had equal values. Equality was also present on 95,417 end targets, 68,722 recall targets and 8,924 ward targets. Difference appeared on 14,816 end, 11,026 recall and 1,918 ward targets. Those are category-conditioned observational counts from the existing report, not a new extraction, executable rule, intent label or validation generalization result. Equality alone plainly does not determine the action.

D01 separately found priority actions across several PRE channel values and showed that current channel identity is already encoded in M01. A new input study must not claim that channel information is wholly new. Its complete own-action-index evidence also rejects forcing an end after priority: same-turn successors included recall, ward, cancel and blocked actions as well as end. No such hard mask should be introduced.

The earlier prefit receipt identifies three all-zero normalized TRAIN columns: own-current availability, own-scheduled availability, and the added unavailable-pair indicator. Thus the nominal 41-channel interface has 45 inactive treatment weights on those TRAIN rows. Equal nominal parameter counts should not be described as equal active capacity when the control zeros the entire block. This is already disclosed in the original preparation and remains relevant to interpreting a future control; no control redesign is selected here.

The legacy `rich_data.history_vector` inspection also makes one omission precise. It retains prior action type, elapsed rounds, destination/displacement geometry and event flags, but does not encode a prior priority action's integer argument. Consequently, having the priority action type in this history does not establish access to the separately recovered exact prior integer values. This establishes loss in that particular history interface, not sufficiency of the recovered block or a causal explanation for a measured fraction of action errors.
