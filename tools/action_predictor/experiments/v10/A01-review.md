**VERDICT: CHANGES — correct the evidence/reporting issues before pushing. A01’s core measurements are valid; I found no bug invalidating its saved accuracy, likelihood, checkpoint selection, or demonstrated causal serving parity. No promotion or repeat seeds are justified.**

I read the [parent thread](<t3-thread://v2/7309f52a-c52b-4287-b6af-6acae8ea63d1/mcp:launch:c4185c930eca174d8d1afc1306852295d17ffddccc8ef520a6713bb41d411891>), paginated the handoff and results, inspected the staged diff and prior objections, and confirmed all **36 staged files match their working-tree bytes**. I made no edits, ran no fits or simulations, accessed no reserved payloads, and performed no PR actions.

I independently verified:

- All A01 checkpoint/prediction hashes in its completion addendum.
- Full TRAIN/DEV descriptor reconstruction and TRAIN normalization.
- Exact saved selector weights, routing, and decoded commands on **433,071 TRAIN + 14,439 DEV rows**.
- Independent mixture NLL within **6.1×10⁻⁸** per row.
- Round-10 selection, six-round patience, and optimizer counts: **8,460 selected / 13,536 completed updates**.
- The **386 raw-PRE serving cases**, retaining the reported **4.17×10⁻⁷** maximum weight discrepancy.
- All D00 decoded commands; independently calculated candidate probabilities differed by at most **3.40×10⁻⁷**, consistent with numerical precision.

The concrete findings follow.

1. **Medium — D00’s changed-command count is wrong.**

   [algorithmic_decoder.py:54](F:/Code/battlecode-26-27/tools/action_predictor/algorithmic_decoder.py:54) compares every coordinate and priority storage slot, including arguments unused by the predicted action. D00 canonicalizes those unused slots, while A00 retains fallback values.

   Consequently, [D00.json:505](F:/Code/battlecode-26-27/tools/action_predictor/experiments/v10/D00.json:505) reports **13,257 changed commands**. Comparing action type and only its required arguments gives **1,052 semantic command changes**: **894 type changes and 158 argument changes within the same type**.

   **Minimal fix:** add an immutable correction using family-aware command equality. Preserve the original receipt. Strict accuracy and NLL are unaffected.

2. **Medium — The priority error diagnostics still score unused argument fields.**

   [algorithmic_analysis.py:28](F:/Code/battlecode-26-27/tools/action_predictor/algorithmic_analysis.py:28) calculates MAE over every true-priority row, including rows where the joint decoder emits another action. Its accompanying reason correctly says those leftover scalars are not priority predictions, but the numerical error metrics nevertheless use them.

   For A01, the reported MAE is **143.491 over 576 rows**. On its **340 correctly typed priority commands**, MAE is **144.068**, with maximum error **1,489**. A00 similarly reports **144.991**, versus **147.880 over 334 correctly typed rows**.

   **Minimal fix:** leave undefined all-true-family errors null; report correctly typed MAE/max error with explicit coverage, including rare/unseen strata. Keep the valid joint counts. This corrects diagnostics without changing predictions.

3. **Medium — A01’s completion addendum contains A00 reproduction commands and omits its serving receipt.**

   [algorithmic_analysis.py:37](F:/Code/battlecode-26-27/tools/action_predictor/algorithmic_analysis.py:37) hardcodes `algorithmic_fit` and `algorithmic_roundtrip` for both identifiers. Thus [A01-completion-addendum.json:26](F:/Code/battlecode-26-27/tools/action_predictor/experiments/v10/A01-completion-addendum.json:26) does not provide the commands that produced A01; `serving_receipt` is also null.

   The artifacts themselves reproduce, and the index lists the correct modules. The completion receipt remains inaccurate.

   **Minimal fix:** add an A01-specific correction naming `algorithmic_conditioned` and `algorithmic_conditioned_roundtrip`, binding its descriptor and serving receipts, and distinguishing shared prerequisites from A01 execution. Do not rewrite historical hash-bound receipts.

4. **Medium — The main A01-versus-A00 comparison lacks paired evidence.**

   [algorithmic_analysis.py:17](F:/Code/battlecode-26-27/tools/action_predictor/algorithmic_analysis.py:17) always compares against G00. A00 is the direct predecessor for A01’s architecture hypothesis.

   Using the same **2,000 paired whole-group draws, seed 20261106**, I obtain:

   - **54 rescues / 108 regressions** against A00.
   - Strict-accuracy difference interval: **−0.578 to −0.148 percentage points**.
   - Mean-NLL difference interval: **+0.00577 to +0.01318**.
   - Macro-F1 difference interval: **−0.00867 to +0.00181**.
   - Group net command differences: **−18, 0, −16, −14, −6**.

   This supports the stated negative command/loss result on reused DEV. It does **not** establish a reliable macro-F1 regression.

   Excluding recall, A01 gains only **two commands** against A00; its small NLL improvement has an interval spanning zero.

   **Minimal fix:** add the direct paired comparison, retaining the checkpoint-selection/five-reused-groups qualification.

5. **Medium — D00 needs a matched G00 probability-decoding control.**

   [algorithmic_decoder.py:50](F:/Code/battlecode-26-27/tools/action_predictor/algorithmic_decoder.py:50) changes the command decision rule as well as using learned mixture weights. Comparing only with G00’s action-first hard forecast obscures that distinction.

   As a new review diagnostic, I ranked **G00 probability alone over exactly the same bounded command set**, without selector weights or point mass. It achieves **11,950 strict successes, 82.7620%, macro F1 0.621075**.

   D00 achieves **12,039**, adding **89 net successes** over this control through **196 rescues / 107 regressions**. Its paired strict-gain interval is **+0.485 to +0.744 percentage points**. D00’s macro-F1 point estimate is lower; that paired interval spans zero.

   Therefore, much of D00’s gain over the original G00 forecast comes from changing decoding. The learned mixture contributes additional measured improvement.

   **Minimal fix:** retain this clearly labeled posthoc control and comparison. Do not promote it or reinterpret it as a prospectively confirmed experiment.

6. **Medium — D00’s “exact command probability” wording needs the observed-representation qualification.**

   [algorithmic_decoder.py:36](F:/Code/battlecode-26-27/tools/action_predictor/algorithmic_decoder.py:36) assigns shop candidates their action probability without purchase-argument probability. D00 emits **51 shop forecasts**, whose original purchase arguments remain unavailable.

   Thus its bounded ranking is exact for the implemented **observed command representation** where modeled, including a marginalized shop bucket. It is not exact probability ranking over complete original API commands. Coordinate agreement also retains the disclosed entity-identity ambiguity.

   **Minimal fix:** qualify the decoder description and confidence field accordingly. Keep every shop a strict failure; do not invent arguments.

7. **Low — A01’s measured training-time field has an unclear scope.**

   The timer starts after data loading, descriptor preparation, and normalization at [algorithmic_conditioned.py:63](F:/Code/battlecode-26-27/tools/action_predictor/algorithmic_conditioned.py:63), and ends after final inference, prediction serialization, and evaluation.

   Its **56.626 seconds** therefore describes that mixed interval. Recorded round times sum to **44.324 seconds**, themselves including DEV inference. Neither is pure optimization time or total experiment cost.

   **Minimal fix:** document the measured scope additively. Keep unmeasured A00 wall time unavailable. The serving timings include actual forwards and correctly exclude initialization/history replay; differing case sets do not establish a speed advantage.

**The A00 response substantially resolves the serving and causal-boundary findings.** The PRE allowlist, command-parity evidence, paired G00 comparisons, matched override subsets, support ceilings, and explicit legality limitations are useful additions. Calibration remains unassessed; route-weight bins do not replace command calibration. The priority diagnostics and receipt defects above prevent calling the evaluation response complete.

**The remaining research constraints are substantial.** A01 still inherits the hard decoder’s ceilings: blocked **8/110**, priority **71/576**, ward **12/112**, `cast_1` **125/243**, and movement **1,953/2,362**, even with perfect routing. These constrain this support/decoder combination, not the underlying data or algorithmic approach.

A01 captures only **69 of 1,628 library-covered G00 errors**, versus A00’s 135. Its lower TRAIN performance also means the result cannot be explained solely as DEV overfitting. The disclosed architecture change—**15,778 versus 30,624 parameters**, shared scoring, and smaller global context—prevents attributing failure specifically to candidate geometry.

**Ranked next work:**

1. **Complete the non-fitting corrections above.** Preserve all current checkpoints and results; no refit is needed.
2. **Develop C01 support on TRAIN first.** Prioritize ground casts, meaningful causal priority proposals, ward placement, utilities without position, and attempted movement with explicit outcome forecasts. Verify historical semantics and freeze category support criteria before DEV or another fit.
3. **Separate decoder effects from learning effects.** Include the matched G00 probability decoder in any future frozen comparison; retain macro/category guards alongside aggregate accuracy.
4. **If further scorer work earns a separate budget, use a matched architecture control.** Hold context size, parameterization, static descriptors, loss, support, and decoder fixed while varying causal geometry/objective information. Add actual generating-goal and route-improvement descriptors; A01 currently provides an objective category plus local grid features.
5. **Then investigate persistent goals through forward causal filtering.** Use genuine ordered personal history with explicit gaps and unavailable memory. Keep persistence separate from simultaneous support, sampling, and decoder changes.

A01 remains a valid negative result against A00. The original category, macro, movement, likelihood, and three-seed success requirements remain unsatisfied. Shops remain unassessed strict failures; sparse altar/teleport/submit results remain uncertified.

PR https://github.com/Canon-Regularis/battlecode-26-27/pull/11, head 7a7e4d4761823306dc3ff072f3c4e552df98372b, checks and reviews 0/0 in supplied evidence; staged changes require the reporting corrections above.
