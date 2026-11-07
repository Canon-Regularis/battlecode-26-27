# Causal priority recovery: completed data milestone

All 433,071 existing training targets (470 games, 94 groups) and 14,439 original development targets (25 games, five groups) remain unchanged. All 495 eligible games completed recovery and independent verification. No model has been fitted in V8; predictive quality has not improved merely by extracting inputs.

Own current-round and scheduled next-round priorities are available on every target row. Inputs retain exact signed integers, explicit availability, the actual earlier priority arguments within the last 16 own actions, and the latest earlier argument even when outside that window. Historical arguments come from complete own-action indexes, not adjacent sampled turns. Current target headers and recorded POST state do not enter input arrays.

The completed audit verifies the frozen jobs, raw/index/target evidence, exact query, extraction-code and Node receipts, and outputs. It independently reconstructs every input row from the earlier own-action index. Membership and offsets cover every row exactly once; all merged slices match their verified per-game arrays byte for byte. Original extractor sources and receipts remain intact.

| Check | Result |
|---|---:|
| Recorded setter POST checks | 306,834 / 306,834 match |
| Round-rollover checks | 403,135 / 403,135 match |
| Development priority targets | 576 |
| Available latest earlier setter | 570 |
| Latest setter outside 16-action window | 132 |
| Exact current-priority copy | 0 / 576 |
| Exact scheduled-priority copy | 0 / 576 |
| Exact latest-argument copy | 0 / 570 |
| Training target vocabulary | 518 integer values |
| Training/development target range | −812 to 817 |
| Development values absent from training targets | −671, 547, 784; four rows |

Vocabulary and residual statistics use only the 14,816 existing training priority targets. Additional earlier setter evidence is context/audit evidence, not added supervised target rows. Some common training residuals relative to the latest argument are −7, +7, +1400, −1400, −5 and −6. A small-residual-only design is insufficient; residual/multimodal output designs will be separate controlled experiments.

There were no recorded unchanged setter roots. This does not establish whether unchanged calls were never made or omitted by recording. The zero-copy result applies to the recorded setter targets, not every internal bot API call.

Seven input/verification tests pass, including signed integer limits, zero versus missing, temporal alignment, stale cache metadata, row permutations, offset coverage and canonical masks. These tests and input roundtrips establish extraction correctness, not model quality. Full-model probability parity, including the float16 candidate-grid path, remains work for the V8 inference implementation.

M01 still has 13/576 exact priority parameters and 10/576 joint successes. With its action decisions frozen, even perfect priority parameters can yield at most 343/576 joint successes (59.55%). The next isolated logistic-head comparison must be reported as a parameter experiment; a separate action-discrimination experiment is required.

The original category-wise ≥90% joint goal, three-seed requirement, support counts and regression guards remain unchanged. All 43 purchase argument sets remain unassessed failures. Neither altar nor teleport can be certified from two examples. All 75 new validation and 75 final-test games remain sealed; the old exposed test remains unused. No matches, deployments, playing-bot edits or downloads occurred.

Evidence and hashes: [priority-recovery-audit.json](priority-recovery-audit.json), [priority-chain-verification.json](priority-chain-verification.json), [priority-data-ready.json](priority-data-ready.json), [priority-extraction-plan.json](priority-extraction-plan.json), [priority-training-vocabulary.json](priority-training-vocabulary.json). Exact commands are retained under `.cambc/action-predictor/v8/commands.jsonl`. The auditor ran only after full recovery; it runs the independent verifier before generating statistics.

```powershell
.venv-action-predictor/Scripts/python.exe -m tools.action_predictor.priority_data --audit
.venv-action-predictor/Scripts/python.exe -m tools.action_predictor.priority_data
.venv-action-predictor/Scripts/python.exe -m unittest tools.action_predictor.test_priority_inputs tools.action_predictor.test_priority_verify -v
.venv-action-predictor/Scripts/python.exe -m tools.action_predictor.priority_verify --probes
.venv-action-predictor/Scripts/python.exe -m tools.action_predictor.priority_audit
```

The milestone now requires a fresh GPT-6.1 Sol EXTRA HIGH completed-data review before any fitting. Prior review approvals covered implementation and probes only.
