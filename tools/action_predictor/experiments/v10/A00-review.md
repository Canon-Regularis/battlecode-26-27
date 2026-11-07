**A00’s saved measurements are usable, but the evaluation is incomplete and the current command support cannot meet the category targets. Do not promote it or allocate repeat seeds.**

I read the complete handoff and current [parent thread](<t3-thread://v2/7309f52a-c52b-4287-b6af-6acae8ea63d1/mcp:launch:c4185c930eca174d8d1afc1306852295d17ffddccc8ef520a6713bb41d411891>), the specified reports, code, checkpoints, and prior objections. I made no edits, trained nothing, accessed no reserved payloads, and preserved the frequency preparation.

I independently reproduced:

- TRAIN and DEV selector weights exactly from round 17.
- All saved decoded predictions and fallback decisions.
- TRAIN normalization exactly.
- Mixture NLL within `1.7e-7` per row using an independent probability calculation.
- Round-17 selection and the six-round patience stop.
- Current source, candidate-cache, and plan bindings.

There is no demonstrated current-answer leakage in selector inference. Duplicate explanations are marginalized correctly. Using G00’s predicted-family coordinate for fallback is correct. Missing shop arguments remain strict failures and absent from observed argument likelihood. The explicit unavailability of all-true-family parameter accuracy is appropriate.

1. **High — The present decoder has structural category ceilings that further selector training cannot overcome.**

   The decoder can emit only a library point command or G00’s existing hard command. See [algorithmic_fit.py:59](F:/Code/battlecode-26-27/tools/action_predictor/algorithmic_fit.py:59).

   I calculated the oracle union of those options on DEV. Even perfect routing could obtain only:

   - Blocked: **8/110**.
   - Priority: **71/576**.
   - Ward: **12/112**.
   - `cast_1`: **125/243**.
   - Move: **1,953/2,362**, still below 90%.
   - Altar, teleport, and shop: **zero**.

   These are **support ceilings for this decoder**, not ceilings imposed by the data or algorithmic methods generally.

   The TRAIN coverage allocation criterion justified a small pilot, but it did not establish adequate support across categories. Repeating A00, increasing its capacity, or improving its selector alone cannot complete the objective. Future plans need explicit category-level support accounting before fitting.

2. **High — The library misses important command mechanisms, including most ground-target casts.**

   In [library.py:68](F:/Code/battlecode-26-27/tools/action_predictor/algorithmic/library.py:68), casts are constructed only by ranking entities whose unit bit intersects the target mask. There is no branch for ground targeting.

   DEV contains **158 `cast_1` rows with ground-only mask 16**; the library covers **none**. It also covers neither of the two mask-19 examples. This explains much of the low `cast_1` coverage without requiring speculation about hidden intent.

   Other concrete omissions:

   - `priority/zero` matches **zero TRAIN rows**.
   - `ward/self` matches **zero TRAIN rows**.
   - The early missing-position return at [library.py:42](F:/Code/battlecode-26-27/tools/action_predictor/algorithmic/library.py:42) unnecessarily removes every utility candidate. This accounts for the **319 uncovered DEV end commands**.
   - Combat and utility emitters do not fully apply readiness, channel, restriction, and resource conditions.

   The last point is incomplete executable-command validation, not proof that A00’s selected point commands are illegal: its point overrides passed the available partial readiness checks.

   Improve these mechanisms using TRAIN evidence. Preserve separate attempted-move/outcome accounting; do not repair blocked coverage by duplicating every destination under both outcomes.

3. **High — C00’s roundtrip does not validate A00’s serving pipeline.**

   [algorithmic_verify.py:15](F:/Code/battlecode-26-27/tools/action_predictor/algorithmic_verify.py:15) regenerates candidate caches. It does not reconstruct the selector’s inputs, history, G00 fallback, normalization, probabilities, and final command from raw personal PRE evidence.

   Meanwhile, [algorithmic_fit.py:36](F:/Code/battlecode-26-27/tools/action_predictor/algorithmic_fit.py:36) consumes prepared features and archived G00 predictions.

   My checkpoint reproduction establishes cached-input correctness. It does **not** establish a deployable causal runtime.

   Add a read-only PRE-to-command implementation and focused parity check spanning both engines, missing position/history, utility actions, movement changes, targeting, priority, and both routing outcomes. Reuse the existing extraction evidence; another unchanged 495-game audit is unnecessary.

4. **High — The aggregate improvement is much narrower than the headline suggests.**

   A00 fixes **135** G00 errors and introduces **23**, for **+112** strict successes. Recall contributes **+98**, or **87.5% of the net gain**.

   Excluding recall:

   - Strict improvement is only **14 commands across 11,355 rows**.
   - Observed NLL **worsens**, from **0.7616545 to 0.7662567**.

   Recall’s loss reduction exceeds the total improvement because deterioration elsewhere offsets it. Priority, blocked, ward, and both cast categories have worse summed NLL.

   Movement improves by **12 joint commands**, entirely on direction changes:

   - Continuation: **1,053 → 1,053**.
   - Change: **263 → 275**.

   These are joint counts. G00’s **1,120 continuing / 311 changing** figures are true-family destination counts and must not be compared directly with A00’s joint counts.

   Ward discrimination improves in some respects—false positives fall **282 → 229**, and recall→ward errors fall **257 → 208**—but correct ward types fall **35 → 33**, and complete wards **7 → 5**. This is a tradeoff, not a solved ward problem.

5. **High — Required comparison and uncertainty reporting is missing.**

   [algorithmic_fit.py:26](F:/Code/battlecode-26-27/tools/action_predictor/algorithmic_fit.py:26) bootstraps absolute accuracy. That is not the requested paired uncertainty for improvement against G00.

   Using the original **2,000 paired whole-group resamples, seed 20261106**, I obtain:

   **A00−G00 strict gain: +0.609 to +0.912 percentage points.**

   Net gains are positive in all five groups: **24, 21, 27, 27, 13**. This supports the observed DEV improvement, conditional on selected checkpoints and five repeatedly reused groups. It is not untouched, selection-adjusted, or three-seed evidence.

   The report also needs:

   - Paired loss and category/context comparisons, including empty-support handling.
   - Rescue/regression counts and opportunity capture.
   - Partial legality with explicit coverage and full legality marked unassessed.
   - Priority rare/unseen preservation and error diagnostics.
   - Calibration and relevant achievable simpler controls.

   The current partial check flags **110 rows**, including **91 blocked-forecast movement-mask rejections** and **zero successful-move mask rejections**. Those blocked flags must not be presented as illegal successful moves.

6. **Medium — The disclosed decoder approximation materially separates the training objective from command selection.**

   The approximation is accurately documented; it is not an undisclosed MAP claim.

   Nevertheless, comparing a point group’s mass with the **entire fallback weight** at [algorithmic_fit.py:66](F:/Code/battlecode-26-27/tools/action_predictor/algorithmic_fit.py:66) ignores how fallback probability is distributed across commands and how it overlaps point commands.

   For a particular command, the relevant mixture probability is:

   `fallback_weight × G00_probability(command) + matching_point_weights`

   Therefore, lower mixture NLL need not produce better hard routing. A00 still routes **13,255/14,439 rows** to G00.

   Before another fit, evaluate a prospectively specified decoder that ranks actual mixture command probabilities over a documented command set. Call it a bounded approximation unless global MAP—including priority support—is established. Preserve A00’s original decoder and results; do not retrospectively select whichever decoder scores best.

7. **Medium — The selector does not directly inspect the candidates it scores.**

   The MLP receives global features and eight action encodings; candidate availability is applied afterward. See [algorithmic_fit.py:33](F:/Code/battlecode-26-27/tools/action_predictor/algorithmic_fit.py:33) and [algorithmic_fit.py:41](F:/Code/battlecode-26-27/tools/action_predictor/algorithmic_fit.py:41).

   It does not directly receive each candidate’s destination, chosen objective, target attributes, route improvement, or geometry. This makes it difficult to learn *when this particular candidate is good*.

   The opportunity is substantial: the selected library covers **1,628 G00 errors**, but A00 fixes only **135**, leaving **1,493 covered errors unfixed**.

   A shared candidate-conditioned scorer is a justified distinct hypothesis. Feed bounded causal descriptors of each emitted command and its generating objective, rather than merely adding more global capacity.

   Also, A00 selected the geometric control. It has not established that learned terrain planning or persistence improves prediction, nor recovered Fish’s internal algorithm.

8. **Medium — Coverage and routing summaries do not isolate the value of the structured components.**

   The libraries have equal nominal slot counts, but differing output diversity and shared components. Their coverage comparison supports the geometric library’s higher oracle coverage; it does not isolate a pathfinding effect.

   Likewise, **89.27% point accuracy versus 79.71% fallback accuracy** compares different selected subsets.

   On the same **1,184 point-routed rows**, G00 gets **945** correct and A00 **1,057**. Report that matched comparison. Of those overrides, **749 are recall**, **312 attack**, and **88 movement**; no DEV point output is ward, priority, or either cast.

   Add unique rescue contributions, overlap/abstention reasons, and context coverage. These distinguish useful algorithmic support from utility-action corrections and redundant hypotheses.

9. **Medium — The claimed causal input boundary is broader than the receipt says.**

   [study.py:53](F:/Code/battlecode-26-27/tools/action_predictor/algorithmic/study.py:53) passes the entire supplemental row to `emit`. Those rows can contain POST-derived `transaction_label`; I confirmed its presence in eligible TRAIN and DEV supplements.

   The emitter does **not currently read it**, so this is not demonstrated leakage. But the roundtrip’s claim that no label/future evidence reaches the emitter is too strong.

   Pass an explicit allowlist of permitted PRE fields, following the existing compact-supplement pattern. That makes the causal boundary enforceable instead of relying on current implementation discipline.

10. **Medium — Reproducibility and complexity accounting need completion.**

    [algorithmic_fit.py:105](F:/Code/battlecode-26-27/tools/action_predictor/algorithmic_fit.py:105) binds the selected checkpoint but does not hash the saved prediction archives in the final report.

    Add an immutable completion addendum covering predictions, checkpoints, runtime/input dependencies, commands, update counts, and measured cost. The selector has **30,624 parameters**, but serving also requires candidate construction and G00; “small selector” is not a measurement of total predictor cost.

**Recommended next work, in order:**

1. Complete the non-fitting evaluation, causal serving parity, decoder analysis, and immutable receipts.
2. Use the remaining pilot for **candidate-conditioned scoring over the same frozen library**, holding loss, history, fallback, sampling, selection, and decoder fixed. Compare against retained A00 and G00. This isolates a concrete selection hypothesis; it is not a route to all-category certification.
3. Separately develop a TRAIN-only library revision addressing ground casts, meaningful priority proposals, ward placement, position-independent utilities, and blocked attempts. Measure support before allocating another fit.
4. Then test persistent goals through forward causal filtering over genuine personal history, with explicit gaps and unavailable memory. Do not combine persistence, new support, new decoding, and new sampling in one unexplained package.

A00 remains a useful first pilot. Its **macro F1 0.6407**, **movement 56.31%**, and **6.23% NLL reduction against G00** miss the relevant targets. Preserve the result, obtain the missing evidence, and pursue distinct hypotheses rather than repeating this configuration.
