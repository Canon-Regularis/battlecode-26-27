# V50: reject further affine code-head calibration

The user requested 85% inferred-code accuracy. V49 reaches 81.97% on the reused evaluation queries. V50 checks whether a small calibration of the existing output weights can further improve code prediction without changing the network or its inputs.

The experiment collects the original 2,945 fitting-query logits from their matching V49 held-game checkpoints. Four regularization strengths are tested. Each affine eight-logit map is fitted on three fold cohorts and scored on the fourth, using cross entropy plus squared distance from the identity map. Classes absent from fitting retain identity rows. Selection maximizes pooled correct predictions, then uses NLL and regularization strength as frozen tie-breaks; identity is eligible.

Any selected affine transform would be folded directly into the existing linear head: `W_new = A @ W_old`, `b_new = A @ b_old + c`. This adds no parameters or operations to inference. All non-code-head tensors remain fixed. Selection occurs without using evaluation labels.

| Calibration | Correct / 2,945 fitting-fold queries | Accuracy |
| --- | ---: | ---: |
| Identity | 2,431 | 82.55% |
| Regularization 0.001 | 2,387 | 81.05% |
| Regularization 0.01 | 2,401 | 81.53% |
| Regularization 0.1 | 2,412 | 81.90% |
| Regularization 1 | 2,421 | 82.21% |

**Identity wins.** All learned calibration maps are rejected. The V50 checkpoint has exactly the same model tensors as V49; its forecasts are preserved from V49 and **no new outer inference occurs**. The best retained result remains **573/699, 81.97%**, 22 correct predictions short of the 85% threshold. V50 does not provide an additional successful evaluation or independent replication.

Two focused tests cover algebraic folding into the original head, exact identity preservation, preservation of absent-class rows and finite optimization. Parent verification reconstructs all fitting logits, repeats all 16 calibration fits with exact maps and objective traces, reproduces the selection, checks every final tensor is unchanged, and verifies copied forecasts against V49's bound full-inference proof. The complete current focused suite contains 21 passing tests.

These calibration folds condition on base models that were trained using other fitting groups; they are not fully independent nested model validation. The original backbone and discovery also had fitting-group exposure, and the outer research data has been repeatedly examined. This negative calibration result rejects the tested correction family; it does not establish an accuracy ceiling or prove that the available observations are insufficient. The 85% target, reliable rare-code recognition, useful goal prediction and promotion remain unachieved.

Use the [V49 checkpoint and loader](../v49/REPORT.md) for the retained experimental model. Evidence is preserved in `plan.json`, `selection.json`, `result.json` and `verification.json`. No playing-bot changes, subagents or delegated reviews were used.
