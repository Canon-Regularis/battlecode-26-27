# V66 - learned goal-conditioned movement execution

Built and tested an opt-in movement executor that receives an explicit goal. It learns useful goal dependence in a hindsight diagnostic, but it does **not** pass the complete execution or usable-planner gates. No model was promoted and no autonomous strategy improvement is established.

## Diagnostic: the replay future destination is supplied

These results use **470 goal-movement pairs from 319 distinct evaluation queries**, with validated achieved positions 2, 4 or 8 own turns later supplied as goals. This is privileged future information. It is deliberately unavailable to the usable planner and must not be presented as ordinary movement accuracy or progress toward the original 80% target.

| Executor | Correct pairs | Accuracy | Movement NLL |
| --- | ---: | ---: | ---: |
| Frozen V59 direct | 272/470 | 57.87% | 1.316949 |
| Matched goal-blind residual | 262/470 | 55.74% | 1.295122 |
| Existing routing, same supplied goals | 359/470 | 76.38% | Not a probabilistic model |
| Learned goal-conditioned residual | 365/470 | 77.66% | 0.692925 |

Goal conditioning gains 103 correct pairs over the matched goal-blind network and lowers NLL. However, it gains only six over routing, below the prospective three-percentage-point requirement. The execution diagnostic therefore fails its conjunction. On far endpoints, it gets 99/130 versus 75/130 for the control and 98/130 for routing.

| Horizon in own turns | Learned executor | Routing |
| --- | ---: | ---: |
| 2 | 233/284 | 229/284 |
| 4 | 91/123 | 88/123 |
| 8 | 41/63 | 42/63 |

The goal-conditioned unique-query mean accuracy is 79.47%, averaging the available horizon examples within each of the 319 queries first. This remains a hindsight-only metric on a selected subset, not the 513-query target. The two-turn result exceeds 80% only with the future destination provided; the longer-horizon results do not demonstrate improved strategy.

## Usable planner: predicted goals only

V62's causal goal choices, identities, retention and abandonment are fixed. Both execution heads receive identical current inputs and selected goals, with the goal-blind arm masking the goal features. If no goal is selected, both use the unchanged direct predictor. No replay future positions enter this evaluation or the runtime API.

| Policy on the original 513 movement queries | Correct | Accuracy | Movement NLL |
| --- | ---: | ---: | ---: |
| V59 direct | 318/513 | 61.99% | 1.200119 |
| V62 routing | 310/513 | 60.43% | Not a probabilistic model |
| Goal-blind executor with same activation | 318/513 | 61.99% | 1.201553 |
| Goal-conditioned executor | 316/513 | 61.60% | 1.271635 |

Goals are active on 85 observed queries, including 69 movement queries. On those 69, direct/control get 47 correct, routing 39, and the goal-conditioned executor 45. The other 444 movement predictions are exact direct-model fallbacks. Relative to routing, the new executor rescues seven errors and introduces one, net +6. Relative to direct, it rescues six and introduces eight, net -2. Its NLL also fails the 0.01 degradation allowance. The overall success gate fails and **80% remains unmet**.

This supports a narrow conclusion: the network can exploit an externally supplied achieved destination, and the learned executor reduces some damage from the existing predicted-goal routing. It does not prove that the high-level selector is the only remaining bottleneck. Point goals versus region goals, goal meaning/horizon, limited data, execution quality and partial observability remain possible factors. Neither an achieved future position nor geometric progress identifies Fish's internal intention or the strategic value of a goal.

## Implementation and training

The existing V59 map/history/code/movement model and V62 objective head are frozen. A shared per-move 136-64-1 tanh residual adds 8,833 trainable parameters: 128 existing state/local geometry/history features plus eight supplied-goal geometry features. The final layer starts at zero, reproducing V59 exactly. The head can choose any supported move; it is not constrained to reduce path distance. Current legal-first-step support is preserved, without claiming full future-path legality.

The goal features encode relative goal location, current/next static route distance, next geometric distance, route progress, goal radius and availability. No future route, current action label or outcome appears in the current-state features. Future achieved coordinates are intentionally supplied only during supervised training and the explicitly marked diagnostic. Runtime goal geometry comes only from the causal selector.

Training uses 12,123 examples from 8,009 distinct fitting queries across all 32 fitting games: 7,004 at horizon two, 3,416 at four and 1,703 at eight. Every available horizon example has equal weight, so some queries repeat. Endpoints must be observed/alive, and integrated executed walking must agree with all available intermediate PRE positions. Observed death, inconsistent relocation and administrative-window crossings reject labels. Missing intermediate observations remain missing.

Both arms have identical tensor shapes, initialization, training examples, permutations, optimizer settings and checkpoint opportunities. Each fitting-game fold trains expanded windows from the other 24 games and validates canonical windows in eight held fitting games. Selection uses conditional movement correctness, NLL and earlier epoch, independently per arm. Control selects epoch 16; goal-conditioned selects epoch 12. Each is refitted once on fitting data. No evaluation result changes a checkpoint or acceptance condition.

Before optimization, `plan-r1.json` was preserved and the plan rebound to remove undefined routing-NLL report fields and strengthen the diagnostic with a direct-model comparison. Cache construction, inputs, models, training and selection stayed unchanged. No optimizer updates had occurred.

## Runtime

```python
from tools.action_predictor.behavior_segments.goal_execution_predictor import GoalExecutionPlanner

predictor = GoalExecutionPlanner()  # experimental; not promoted
result = predictor.predict(
    current, route, round_number,
    previous, previous_mask, state,
    previous_moves=completed_previous_turn_moves,
)
state = result['state']
move = result['goal_conditioned_movement']
```

`objective_movement` also exposes the new executor's move. `routed_objective_movement` preserves the old routing answer, while `conditional_movement` preserves V59. `goal_conditioned_probabilities` exposes the supported distribution. The API accepts no replay-goal override. Maintain separate state per actor and reset at actual gaps; inherited window/actor reset rules remain. `arm='control'` loads the matched goal-blind executor for research comparisons.

## Verification and limits

Parent verification reconstructed all 12,123 labels and all five fitting feature banks, identical initialization, initial V59 parity and finite backward gradients. It reproduced all 40 fold measurements, matched sampling schedules, 11812 optimizer-update records, selected weights, assessment features/logits, both full causal forecast sets and goal identities. Runtime parity passed 192 turns across both arms, including 42 active-goal queries. Twelve focused tests passed. No subagents or delegated reviews were used.

The preserved checkpoints and opt-in runtime are local research artifacts. This first execution experiment adds no outcome-value learner, neural goal termination or simulator reinforcement learning. It does not establish autonomous goal completion, strategic benefit, full-command/category performance or playing strength. Preexposed research partitions, inherited fitting-fold exposure, teacher-forced command histories, availability-selected future labels, point-to-region transfer, one paired seed and repeated query horizons remain limitations. Historical reliability and multi-seed requirements remain open.
