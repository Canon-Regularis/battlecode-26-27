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

H00 is now completed and negative against JP02; see `experiments/v30/H00-REPORT.md`. H01 is unrun. Before that contrast, the effective previous-integer information difference must be resolved: direct recurrence encodes earlier priority values, while the original hierarchy's fixed integer likelihood cancels from its posterior. `input_contract_probe.py` and its saved report demonstrate this limited mechanism. The original protocol/sources remain preserved; an explicit amendment is required before a repaired hierarchy fit. Preparatory entity-grounding helpers and bounded cache checks remain outside this frozen fit pair.

The reviewed repair is in separate `history_model`, `history_filter`, `history_inference` and `hierarchy_fit` modules. Only transitions and hazards gain21previous-command inputs, with336additional nominal trainable weights (149530total versus148986forH00). The initial-state layer retains128inputs. Original columns/biases, all shared tensors and the original initializer RNG are preserved; added columns startzero. The buffer is written after prediction and cleared at the same missing-root/actor-start boundaries. The original `fit H01` entry is disabled; historical H00 sources remain exactly available at its execution commit341ee3413cb680a4ee0ca2c9e7dd1c95b20fed0d.

Corrected exit diagnostics weight applied hazards by the previous posterior and leave reset boundaries unassessed. Current-prior ages are separately named. This combined architecture contrast cannot isolate explicit duration: DEVselectedruns neverreach16roots, and training detaches every8selectednodes. A matched age-independent state comparison would be required for duration attribution if the hierarchy package helps.

```text
python -m unittest tools.action_predictor.segment_policy.test_history tools.action_predictor.segment_policy.test_hierarchy_entry -v
python -m tools.action_predictor.segment_policy.amendment
python -m tools.action_predictor.segment_policy.hierarchy_fit H01
```

Amendment creation occurs before optimization and is immutable. The entrypoint requires the actual fresh H00review, its resolved findings, the committed amendment/input/source bindings and live prerequisites. It preserves the original data/optimizer/checkpoint rule and performs one fit only. Gradient-scale logging is read-only measurement. No subsequent fit or result is approved by H00's review.
