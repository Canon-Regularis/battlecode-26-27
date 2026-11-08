# Neural semi-Markov movement policy — implementation in progress

This namespace replaces waypoint/proposal-retention persistence with a learned discrete state and explicit duration distribution. `filter.py` currently implements a differentiable causal forward filter: observation-conditioned transitions, state/age-dependent termination, and command-likelihood posterior updates only after the demonstrated command occurs. It contains no strategy labels, camp preferences or future-position auxiliary target.

The finite age support is an explicit computational truncation, not a Fish duration rule. Self transitions are excluded so renewing the same anonymous state cannot masquerade as a different duration. Only actual non-self transition logits and nonterminal hazard-age parameters are represented; inactive diagonal/forced-terminal parameters are not counted as trainable capacity.

Missing own roots reset to a learned joint distribution over state and age. The filter does not apply the current observation retrospectively to unobserved roots or assume a segment survived a gap. Unknown-prefix ages are distributions, not a fabricated age zero. A matched direct sequence control must reset at the same gaps. This conservative reset loses potentially useful long-term state; that limitation must be measured and cannot be called complete gap marginalization.

`StateExecutionCondition` supplies learned multiplicative/additive state-conditioned contexts. The future training integration must update the observation encoder, action head and spatial executor jointly. Reweighting frozen L02/G00 movement distributions is explicitly insufficient. No fit runner has yet been allocated or launched here; numerical tests are not evidence of Fish imitation.

The initial controlled study will separate direct sequence learning from explicit duration structure using the same personal-PRE information and comparable trainable capacity/update allocation. Exact parameter counts, initial states, likelihood/decoder and full evaluation rules must freeze before optimization. No receding endpoint auxiliary is used as the sole segment supervision: causal forward sequence likelihood marginalizes variable-length latent segments.

Entity grounding is a separate design question, not supplied by an HSMM. V9 tokens omit identity, so persistent selection of a particular camp requires a causally bound identity sidecar from existing eligible personal observations, with explicit no-target, unknown/unavailable and death handling. IDs may serve only as within-stream identity keys, never learnable numeric features. No entity objective meaning is inferred from a state index. A grounding treatment must have its own matched control before attributing gains to it.

References motivate architecture, not Fish results: [recurrent neural semi-Markov inference](https://ijcai.org/proceedings/2018/339), [CompILE](https://proceedings.mlr.press/v97/kipf19a.html), [latent plans from play](https://proceedings.mlr.press/v100/lynch20a.html). Bidirectional training recognition, if added later, must remain separate from all causal reported forecasts. The current filter uses no future recognition network.

Tests enumerate the state/age transition distribution, check gap resets and demonstrate gradient paths through termination, transitions and state-conditioned execution without optimizer updates:

```text
python -m unittest tools.action_predictor.segment_policy.test_filter -v
```

Original benchmark, all DEV rows, both sealed partitions and every prior negative result remain preserved. No new priority fits, matches, downloads, bot/runtime or deployment work. AB01's outstanding fresh review is independent of this new implementation and must not certify it by implication.
