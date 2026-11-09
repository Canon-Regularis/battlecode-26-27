# V61: objective selection and adaptive abandonment

Implemented a learned scorer for concrete objectives and an adaptive retain/switch/abandon policy. **Objective utility improves over the declared simple references, but movement fails the acceptance gate.** V59 remains the preserved direct movement predictor; no promotion or playing-bot change occurred.

| Same 513 research evaluation moves | Correct |
| --- | ---: |
| V59 direct movement | 318 (61.99%) |
| Learned objective, reselect every query | 216 (42.11%) |
| Learned objective, adaptive retention | 219 (42.69%) |

On 146 evaluation queries with valid four-turn supervision, the chosen objective's mean recorded progress per executed walking step is **0.1102**, versus **-0.0377** for the nearest candidate and **-0.0226** for equal weighting of available candidates. Abstention counts as zero rather than disappearing from the denominator. The retrospective best candidate is 0.6998; this uses future knowledge and is not achievable accuracy or a policy ceiling.

The utility condition passes. The movement condition requires adaptive retention to exceed both V59 and always-reselect; it fails. The three-move gain over reselect alone does not demonstrate reliable termination learning or justify replacing V59. These scores are not a comparison with V60's different waypoint targets, horizons or label population.

## Goal representation and abandonment

Candidates are currently known living camps and enemies, public altars, and home/enemy-home regions. Entity identities maintain continuity across observations but never enter learned numerical inputs. Entity positions are refreshed from the current observation. Goal regions use attack or submit range as appropriate. Reached and statically unreachable candidates are excluded.

The scorer consumes frozen V59 recurrent state/soft code plus twelve current candidate features: type, relative location, distances, interaction radius and health fractions. A small neural network predicts expected progress toward each goal over four own turns. Targets use the integrated executed walking path; current/future commands never enter the score input. Future observed positions must agree with recorded walking, using the existing interval validation.

The termination policy reevaluates the remembered identity on every available PRE. It retains it when its predicted utility is positive and within 0.15 of the best available candidate. Otherwise it switches; when all predicted utilities are nonpositive it abstains and falls back to direct movement. Unavailable or reached objectives invalidate the old identity. Actor/window resets clear state; missing observations preserve the remembered identity until it can be reevaluated. This is **a learned utility estimate combined with explicit termination rules**, not a separately supervised neural termination head.

Routing uses static shortest-path distance to the goal region and the actual current first-step movement support. V59 probabilities break ties between progressing steps; if no progressing step is available, the direct V59 prediction is used. It does not model future dynamic occupancy or guarantee a safe complete route.

Evaluation decisions across 699 observed queries were: 83 selections, 465 retentions, 61 switches, 80 abstentions and 10 unavailable-goal cases. Persistence and switching counts show execution of the mechanism, not strategic benefit.

## Fitting and verification

The prospective fitting-only audit found candidate reducing-step coverage on **569/609 (93.43%)** eligible canonical movement queries, and a best retrospective progress of at least 0.5 on **593/701** labeled canonical queries. Both eligibility thresholds passed before optimization. This is oracle coverage, not model performance.

Training uses **3,960 fitting queries / 42,959 candidate examples**. Four whole-game fitting folds use all expanded other-game windows and original canonical held windows. Epoch twelve is selected from four, eight, twelve and sixteen by pooled held candidate-utility MSE (0.57229). The full model is then refitted once; no evaluation result selects weights, the retention margin, candidates or checkpoint. Candidate examples, rather than queries, weight the regression objective and validation MSE; queries weight the reported utility metric.

The parent verifier reconstructs every candidate and utility label, all five feature banks, all sixteen validation measurements and checkpoint selection. It verifies initialization, exact sampling schedules, finite optimizer states and final checkpoint identity; reproduces all saved evaluations; and checks 64 streaming turns. Focused tests cover retain/switch/abandon, invalidation, supported routing, future-label separation and finite gradients. No subagents or delegated reviews were used.

The opt-in `ObjectivePredictor` returns `objective`, `objective_decision`, `objective_scores` and `objective_movement`; `conditional_movement` stays V59. It requires the same completed-turn `previous_moves`, descriptor/mask and per-actor state as V59. Reset state at genuine gaps. Experimental weights are `.cambc/action-predictor/v61/selected.pt`. Source, protocol, assessment and artifact bindings are saved alongside the result.

## Limits

Recorded progress toward a goal is an imitation proxy, not verified Fish intent, achieved game reward or proof that the goal is worth pursuing. Candidates may be useful geometrically without explaining a particular move. Moving entities are held at their current positions when computing supervision and routes. Partial visibility, four-turn interval selection, teacher-forced histories, inherited fitting-group exposure, repeated research evaluation and one seed limit interpretation.

No autonomous rollout, goal completion under model-generated actions, category/full-command reliability or playing-strength gain is established. The implementation supplies selection and abandonment machinery, but the combined system still **does not demonstrate improved longer-term movement strategy**.
