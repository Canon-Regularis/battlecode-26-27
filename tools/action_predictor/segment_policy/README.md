# Neural semi-Markov movement policy — implementation in progress

This namespace replaces waypoint/proposal-retention persistence with a learned discrete state and explicit duration distribution. `filter.py` currently implements a differentiable causal forward filter: observation-conditioned transitions, state/age-dependent termination, and command-likelihood posterior updates only after the demonstrated command occurs. It contains no strategy labels, camp preferences or future-position auxiliary target.

The finite age support is an explicit computational truncation, not a Fish duration rule. Self transitions are excluded so renewing the same anonymous state cannot masquerade as a different duration. Only actual non-self transition logits and nonterminal hazard-age parameters are represented; inactive diagonal/forced-terminal parameters are not counted as trainable capacity.

Missing own roots reset to a learned joint distribution over state and age. The filter does not apply the current observation retrospectively to unobserved roots or assume a segment survived a gap. Unknown-prefix ages are distributions, not a fabricated age zero. A matched direct sequence control must reset at the same gaps. This conservative reset loses potentially useful long-term state; that limitation must be measured and cannot be called complete gap marginalization.

`model.py` integrates trainable current/action-history and observation-history encoders, personally known entity/public tokens, action choice and spatial execution. `StateExecutionCondition` supplies learned multiplicative/additive state-conditioned contexts. `fit.py` runs one arm, and `protocol.py` freezes the initial matched contrast before optimization. Reweighting frozen L02/G00 movement distributions is explicitly insufficient. Numerical tests are not evidence of Fish imitation.

The initial controlled study compares H00 direct command-updated recurrence with H01 explicit duration/state-conditioned execution using the same personal-PRE information, identical common initial tensors and comparable capacity (148,986 versus149,194 trainable parameters). Both reset recurrent state at missing own roots, while retaining the same explicitly available earlier observation windows. The executable protocol specifies likelihood/decoder, allocation and evaluation before optimization. No receding endpoint auxiliary is used: causal forward sequence likelihood marginalizes variable-length latent segments.

Entity grounding is a separate design question, not supplied by an HSMM. V9 tokens omit identity, so persistent selection of a particular camp requires a causally bound identity sidecar from existing eligible personal observations, with explicit no-target, unknown/unavailable and death handling. IDs may serve only as within-stream identity keys, never learnable numeric features. No entity objective meaning is inferred from a state index. A grounding treatment must have its own matched control before attributing gains to it.

References motivate architecture, not Fish results: [recurrent neural semi-Markov inference](https://ijcai.org/proceedings/2018/339), [CompILE](https://proceedings.mlr.press/v97/kipf19a.html), [latent plans from play](https://proceedings.mlr.press/v100/lynch20a.html). Bidirectional training recognition, if added later, must remain separate from all causal reported forecasts. The current filter uses no future recognition network.

Tests enumerate the state/age transition distribution, check gap resets and demonstrate gradient paths through termination, transitions and state-conditioned execution without optimizer updates:

```text
python -m unittest tools.action_predictor.segment_policy.test_filter -v
python -m unittest tools.action_predictor.segment_policy.test_model tools.action_predictor.segment_policy.test_entry -v
python -m tools.action_predictor.segment_policy.protocol
python -m tools.action_predictor.segment_policy.fit H00
```

Original benchmark, all DEV rows, both sealed partitions and every prior negative result remain preserved. No new priority fits, matches, downloads, bot/runtime or deployment work. AB01's completed fresh review closes that negative study and does not certify this implementation. After each new fit a separate fresh Sol xhigh review is required; no automatic multi-fit script exists.
