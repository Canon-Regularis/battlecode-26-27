# Personal observation-history experiment (V7)

Retain M01. The bounded observation-history experiment does not meet all fixed development targets consistently; no final-test selection.

**2 of at most 6 substantive fits completed.** Seed26 observation history versus fresh action+gap control: exact movement 61.43% versus 60.25% (+1.19 pp); joint movement 54.53% versus 54.28%; observed joint NLL 0.8447 versus 0.8670 (2.57% relative reduction).

## Fixed experiment and causal evidence

The protocol in [plan.json](plan.json) was frozen before fitting. Targets and current inputs are byte-identical: 433,071 training actions from 470 games/94 whole groups; 14,439 original development-validation actions from 25 games/5 groups. Payload hashes and groups are disjoint. All 75 new validation games and all 75 final-test games remain sealed. The previously exposed old test is unused.

Recovered 1,889,036 unique earlier personal PRE snapshots: 362,291 reused and 1,526,745 additionally recovered from eligible games only; 3,960 cached snapshots independently reproduced. Missing recoverable observation frames: 0; no target rows dropped. Prefix padding is explicit. Full whitelisted personal snapshots and supplements remain as gzip evidence; neural history uses the existing 253-field M01 representation (including its existing aggregation/truncation), not an exhaustive encoding of every entity field.

Each frame is the acting champion's own personal PRE observation paired with that earlier recorded action. Its PRE precedes its action, which precedes or equals the current prediction PRE, which precedes the target action. Full indexes preserve unsampled own roots; sampled turns are never concatenated as adjacent frames. Inputs contain no target label, future snapshot, omniscient dynamic state, raw replay cursor distance or intent label. Round gaps, ages, own-turn boundaries, frame presence and observation availability are common to both arms. Personal movement/restriction queries and public static geometry were available to the champion at that PRE.

M01 current encoder, GRU hidden size64, fusion and every prediction head remain unchanged. Only history input is widened from24 to61: 24 prior-action fields, 32 projected earlier-observation fields and5 common gap fields. Control zeros normalized observation values before the same Linear(253,32)+ReLU projection. Both fresh arms have119,392 nominal parameters versus104,160 in M01 (+15,232; +14.62%). Control projection weights (8,096 parameters) cannot learn observation content; its bias can learn an availability-conditioned constant. Thus nominal capacity/computation match, while effective information and feature-dependent capacity differ. Both arms execute the same dense projection and GRU; theoretical history multiply count increases by243,200 per row relative to M01 (excluding activations/biases). Measured paired training times and steps appear below; original M01 timing was not recorded comparably.

Both arms start from the same seed-preserved M01 initialization, not trained M01 weights; new GRU input columns start at zero. M01 training normalization, class weights, losses, data order/shuffle RNG, AdamW settings and minimum-validation-joint-NLL checkpoint rule are retained. Training stops at35 epochs or patience6; movement peaks never choose checkpoints.

## Validation results

| Model | Seed | Action accuracy | Macro F1 | Joint action+parameter | Move exact | Joint move | Move top3 / top5 | Joint NLL |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| M01 | 26 | 88.73% | 63.24% | 79.03% | 59.44% | 54.49% | 86.07% / 95.05% | 0.8728 |
| M02 | 27 | 89.23% | 61.77% | 79.57% | 59.86% | 54.23% | 86.41% / 94.45% | 0.8591 |
| M03 | 28 | 89.18% | 58.68% | 79.29% | 58.85% | 53.05% | 85.86% / 94.83% | 0.8734 |
| H01 | 26 | 88.09% | 61.94% | 78.68% | 60.25% | 54.28% | 86.16% / 94.79% | 0.8670 |
| H02 | 26 | 88.39% | 61.42% | 79.04% | 61.43% | 54.53% | 86.96% / 94.58% | 0.8447 |

Only one matched seed was fitted because the frozen continuation rule failed. Seed robustness is unestablished; this is not evidence that all possible observation-history encoders are ineffective.

Joint accuracy restricted to parameterized commands (coordinate, priority or shop) keeps the same fixed denominator:
- Seed 26: observations 53.13%; control 52.06%; support 4670 (including 43 unassessed shops counted as failures).

Move exact/top-k condition the coordinate head on the recorded action family; joint movement also requires predicting move. Overall joint accuracy follows the unchanged encoded-parameter accounting, with unassessed shops always failing strict joint correctness. Spatial targets are recorded coordinates, not reconstructed intent or guaranteed entity-ID recovery. Observed joint NLL includes only reliably encoded parameters; it is not a complete likelihood for unavailable shop arguments. High overall accuracy includes common end/utility actions; macro F1 and parameterized results must be read alongside it.

| Model | Move error (Chebyshev cells) | Error coverage | Penalized error | Partial observable violations | Best epoch / epochs | Train seconds / steps |
|---|---:|---:|---:|---:|---:|---:|
| M01 | 0.6211 | 2362 | 0.6211 | 109/7084 (1.54%) | 13 / 19 | unrecorded |
| M02 | 0.6152 | 2362 | 0.6152 | 182/7115 (2.56%) | 15 / 21 | unrecorded |
| M03 | 0.6283 | 2362 | 0.6283 | 118/7050 (1.67%) | 6 / 12 | unrecorded |
| H01 | 0.6101 | 2362 | 0.6101 | 158/7069 (2.24%) | 13 / 19 | 522.7 / 32148 |
| H02 | 0.5898 | 2362 | 0.5898 | 147/7126 (2.06%) | 20 / 26 | 684.2 / 43992 |

Unknown/out-of-window predicted coordinates receive the original16-cell penalty in penalized error. Full engine illegal-action rate remains **unassessed**. The unchanged partial metric checks the personal movement mask and selected readiness/resource rules; it cannot certify all target rules. No matches or action execution were used to evaluate legality.

## Unchanged targets and repetition decision

Original targets: macro F1 >=65%; exact movement >=65.21% (fixed strongest simple persistence 55.21% +10pp); observed joint NLL <=1.0449 (10% below original strongest fixed baseline E02); no targeting coordinate regression >2pp against frozen family references. Strongest retained/fresh action-history baseline NLL is 0.8591, making its stronger 10%-reduction threshold 0.7732. Historical loss-gate success alone does not establish improvement over these stronger action-history baselines. The prior frozen map candidate S01 (not retained because targeting regressed) remains intact and is not part of this matched history comparison; its previously measured joint NLL is 0.8003.

All original targets met across three pairs: **False**. All targets including stronger controls: **False**. No thresholds were changed.

The separately named exploratory allocation trigger was frozen as >=2% loss reduction OR >=1pp exact/joint movement gain OR >=3pp direction-change/near-obstacle exact gain with >=200 move rows, plus every guard relative to both fresh control and M01. Guards: NLL <=1.01*reference, exact/joint movement drop <=0.5pp, macro F1 drop <=1pp, attack/cast0/cast1 coordinate AND family-joint drops <=2pp. This trigger is not a success target.

Seed26 trigger: **True**; all guards and trigger permit repeats: **False**. Exact decision and every failed guard: [repeat-decision.json](repeat-decision.json). The frozen rule stopped this study after the first pair; no replacement fits or seed searches were run.

Failed seed26 regression guards: retained_M01/macro_f1, retained_M01/targeting.

## Whole-group paired uncertainty

95% percentile intervals use2,000 paired resamples of the same five original development groups, keeping all games/actions in each group together. These quantify group variation on this reused development benchmark, not uncertainty from an untouched test. They condition on the selected checkpoints and do not rerun training/checkpoint selection for each resample. Rare-context empty resamples are explicitly counted as unsupported; they are not assigned zero accuracy. Only five independent groups limits generalization.

| Seed | Exact movement delta (pp) | Joint movement delta (pp) | Macro F1 delta (pp) | Joint accuracy delta (pp) | Joint loss reduction (%) |
|---:|---|---|---|---|---|
| 26 | [+0.08, +2.46] (2000/2000 draws) | [-1.36, +2.01] (2000/2000 draws) | [-2.00, +2.01] (2000/2000 draws) | [-0.19, +0.92] (2000/2000 draws) | [+1.65, +3.72] (2000/2000 draws) |

Remaining measured target gaps:
- Seed 26: macro F1 61.42% versus65%; move exact 61.43% versus65.21%; observed joint NLL 0.8447 versus stronger-baseline threshold 0.7732. Failed original gates: macro_f1, movement. Targeting deltas below identify which families trade off against movement.

## Targeting and action support

The following coordinate and joint changes are observation history minus the matched control, and minus the retained seed-matched M01/M02/M03. All targeting families and zero-support cases remain in [parameters.csv](parameters.csv) and [targeting-regressions.csv](targeting-regressions.csv). Negative changes are regressions; sparse support is not proof of safety.

| Seed | Family | Support | Exact change vs control / retained | Joint change vs control / retained |
|---:|---|---:|---:|---:|
| 26 | attack | 985 | -0.20 pp / +0.10 pp | +1.52 pp / +0.20 pp |
| 26 | cast_0 | 213 | +0.94 pp / +0.94 pp | +7.98 pp / +7.04 pp |
| 26 | cast_1 | 243 | -1.23 pp / -2.47 pp | -1.23 pp / +0.82 pp |
| 26 | ward | 112 | +0.00 pp / +0.00 pp | +4.46 pp / +2.68 pp |
| 26 | submit | 22 | +0.00 pp / +0.00 pp | -9.09 pp / -4.55 pp |
| 26 | altar | 2 | +0.00 pp / +0.00 pp | +0.00 pp / +0.00 pp |
| 26 | teleport | 2 | +0.00 pp / +0.00 pp | +0.00 pp / +0.00 pp |
| 26 | blocked | 110 | -3.64 pp / -3.64 pp | +1.82 pp / +3.64 pp |
| 26 | priority | 576 | unassessed | +1.74 pp / +1.39 pp |
| 26 | shop | 43 | unassessed | +0.00 pp / +0.00 pp |

Paired group intervals for the primary targeting guards (pp):

| Seed | Target | Exact vs control | Joint vs control | Exact vs retained | Joint vs retained |
|---:|---|---|---|---|---|
| 26 | attack | [-0.78, +0.42] (2000/2000 draws) | [-0.34, +3.30] (2000/2000 draws) | [-0.70, +0.95] (2000/2000 draws) | [-2.57, +2.32] (2000/2000 draws) |
| 26 | cast_0 | [+0.00, +2.07] (2000/2000 draws) | [+3.48, +15.15] (2000/2000 draws) | [-0.89, +2.57] (2000/2000 draws) | [+3.32, +9.19] (2000/2000 draws) |
| 26 | cast_1 | [-3.47, +1.55] (2000/2000 draws) | [-3.77, +1.73] (2000/2000 draws) | [-6.00, +1.27] (2000/2000 draws) | [-10.31, +11.86] (2000/2000 draws) |

Seed26 per-action precision, recall, F1 and support (all seeds and full confusion matrices are exported):

| Action | Support | Control precision / recall / F1 | Observation precision / recall / F1 |
|---|---:|---:|---:|
| <unknown> | 0 | 0.00% / 0.00% / 0.00% | 0.00% / 0.00% / 0.00% |
| altar | 2 | 0.00% / 0.00% / 0.00% | 0.00% / 0.00% / 0.00% |
| attack | 985 | 88.92% / 90.46% / 89.68% | 88.87% / 92.39% / 90.59% |
| blocked | 110 | 32.87% / 42.73% / 37.15% | 36.22% / 41.82% / 38.82% |
| cancel | 2589 | 93.50% / 97.72% / 95.56% | 92.36% / 98.11% / 95.15% |
| cast_0 | 213 | 86.53% / 78.40% / 82.27% | 75.00% / 87.32% / 80.69% |
| cast_1 | 243 | 40.48% / 69.96% / 51.28% | 40.69% / 67.49% / 50.77% |
| end | 4096 | 98.04% / 96.66% / 97.34% | 98.57% / 95.92% / 97.23% |
| move | 2362 | 93.63% / 88.40% / 90.94% | 93.46% / 87.17% / 90.21% |
| priority | 576 | 61.25% / 57.64% / 59.39% | 70.51% / 62.67% / 66.36% |
| recall | 3084 | 91.87% / 79.12% / 85.02% | 92.77% / 79.83% / 85.81% |
| shop | 43 | 79.25% / 97.67% / 87.50% | 83.67% / 95.35% / 89.13% |
| submit | 22 | 27.40% / 90.91% / 42.11% | 23.68% / 81.82% / 36.73% |
| teleport | 2 | 20.00% / 100.00% / 33.33% | 11.11% / 50.00% / 18.18% |
| ward | 112 | 10.70% / 28.57% / 15.57% | 13.45% / 41.07% / 20.26% |

## Available history and objective contexts

Direction change compares the recorded move direction sign with the most recent earlier successful own move. Near-obstacle means a public static blocked/out-of-bounds tile within Chebyshev distance2 at personal PRE. Visible-set change uses only personally visible entity identities. These evaluation contexts never enter labels or selection as invented intent. Context findings are exploratory diagnostics; no context is removed from aggregate evaluation.

| Seed | Context | All-action rows / move support | Control exact / joint move | Observation exact / joint move | Exact delta interval (pp) |
|---:|---|---:|---:|---:|---|
| 26 | history_0 | 6 / 4 | 75.00% / 50.00% | 50.00% / 50.00% | [-50.00, +0.00] (1983/2000 draws) |
| 26 | history_1-3 | 17 / 5 | 60.00% / 40.00% | 60.00% / 40.00% | [+0.00, +0.00] (1980/2000 draws) |
| 26 | history_4-7 | 20 / 4 | 100.00% / 75.00% | 100.00% / 75.00% | [+0.00, +0.00] (1844/2000 draws) |
| 26 | history_8-15 | 69 / 15 | 80.00% / 66.67% | 80.00% / 66.67% | [+0.00, +0.00] (2000/2000 draws) |
| 26 | history_16 | 14327 / 2334 | 60.03% / 54.20% | 61.27% / 54.46% | [+0.08, +2.61] (2000/2000 draws) |
| 26 | direction_change | 1158 / 1158 | 26.08% / 22.71% | 28.15% / 24.01% | [+0.66, +3.92] (2000/2000 draws) |
| 26 | same_direction | 1198 / 1198 | 93.32% / 84.89% | 93.74% / 84.14% | [-0.70, +1.54] (2000/2000 draws) |
| 26 | no_previous_move | 6 / 6 | 50.00% / 33.33% | 33.33% / 33.33% | [-30.00, +0.00] (2000/2000 draws) |
| 26 | zero_displacement | 0 / 0 | unavailable / unavailable | unavailable / unavailable | unavailable (0 supported draws) |
| 26 | near_static_obstacle | 7898 / 1378 | 56.97% / 51.09% | 58.78% / 52.25% | [+1.00, +2.79] (2000/2000 draws) |
| 26 | away_from_static_obstacle | 6212 / 984 | 64.84% / 58.74% | 65.14% / 57.72% | [-1.18, +2.57] (2000/2000 draws) |
| 26 | unknown_position | 329 / 0 | unavailable / unavailable | unavailable / unavailable | unavailable (0 supported draws) |
| 26 | visible_set_changed | 2304 / 157 | 48.41% / 36.94% | 53.50% / 45.22% | [+1.81, +9.09] (2000/2000 draws) |
| 26 | visible_set_unchanged | 12129 / 2201 | 61.06% / 55.52% | 62.02% / 55.20% | [-0.34, +2.43] (2000/2000 draws) |
| 26 | visible_history_unavailable | 6 / 4 | 75.00% / 50.00% | 50.00% / 50.00% | [-50.00, +0.00] (1983/2000 draws) |
| 26 | new_own_turn | 4090 / 218 | 57.34% / 42.20% | 63.76% / 49.08% | [+3.30, +9.23] (2000/2000 draws) |
| 26 | same_own_turn | 10343 / 2140 | 60.51% / 55.51% | 61.21% / 55.09% | [-0.29, +1.77] (2000/2000 draws) |

Measured context diagnosis (exact movement changes versus the fresh matched control):
- Seed 26: direction_change +2.07 pp (n=1158); same_direction +0.42 pp (n=1198); near_static_obstacle +1.81 pp (n=1378); away_from_static_obstacle +0.30 pp (n=984); new_own_turn +6.42 pp (n=218); same_own_turn +0.70 pp (n=2140); visible_set_changed +5.10 pp (n=157).

Available-history support, including absent prefix frames, is recorded exactly in [causal-data-audit.json](causal-data-audit.json). Any empty history bin has no measured accuracy; unavailable values are not evidence of benefit. Per-group supports, all paired targeting intervals and joint-loss/context results are in the per-seed context JSONs and [contexts.csv](contexts.csv). Interpretation should distinguish within-turn context from new-turn context, and direction changes from repeated-direction movement.

## Verification, provenance and retained artifacts

Seven causal/matching/accounting tests passed before fitting. Real replay-to-offline-inference roundtrip passed on 75 fixed targets per checked model across25 original development games: all four model input tensors match bitwise, and saved batch action/parameter decoding and observed joint NLL agree. This is separate from the measured prediction results above. See [inference-roundtrip.json](inference-roundtrip.json), [causal-data-audit.json](causal-data-audit.json) and [sealed-test-audit-after.json](sealed-test-audit-after.json).

Offline inference uses `ObservationPredictor` with one instance per actor/game. Call `observe` for every actual earlier own action in exact order, preserving its personal PRE snapshot; use `observation=None` for an unavailable snapshot instead of skipping the action. Call `predict` with the current personal PRE before the next action. Forecasts are never appended as if observed. The interface rejects backwards/future cursors and mixed actors/perspectives, but relies on the caller supplying the complete own-action stream; the replay preparation verifies completeness against the full recorded index. No robustness claim is made for silently missing actions or for missing observations beyond the measured prefix support.

Python 3.12.10, torch 2.15.0+cpu, numpy 2.5.4; deterministic CPU training with4 threads. Every previous study file and baseline checkpoint remains unchanged. Every fit's selected/best model weights, latest resumable optimizer/RNG state, training history, failure receipts if any, evidence and command ledger are retained under `F:\Code\battlecode-26-27\.cambc\action-predictor\v7`. Nothing was launched as a match, deployed, downloaded or submitted as a PR.

Exact top-level commands (additional per-game Node extraction commands and query hashes are in `v7/commands.jsonl`):

```powershell
.venv-action-predictor/Scripts/python.exe -m tools.action_predictor.observation_study
.venv-action-predictor/Scripts/python.exe -m tools.action_predictor.observation_data --audit
.venv-action-predictor/Scripts/python.exe -m tools.action_predictor.observation_data
.venv-action-predictor/Scripts/python.exe -m tools.action_predictor.observation_validate
.venv-action-predictor/Scripts/python.exe -m tools.action_predictor.observation_train
.venv-action-predictor/Scripts/python.exe -m tools.action_predictor.observation_roundtrip H01 H02
.venv-action-predictor/Scripts/python.exe -m tools.action_predictor.observation_report
```

Full dataset, code/configuration, snapshot, reader/WASM, checkpoint and command hashes: [execution-lock.json](execution-lock.json), [data-ready.json](data-ready.json), [report-provenance.json](report-provenance.json). Reproduction uses the frozen local replay evidence; the extraction command never downloads games. Existing frozen studies and reserved partitions must not be regenerated or inspected to improve this result.
