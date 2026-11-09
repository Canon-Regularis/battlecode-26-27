**R02’s core measurements are valid, but the investigation has not yet identified a definitive root cause.** It establishes that the existing model can memorize these movement examples. It also exposes poor transfer, substantial command-support gaps, and weak selection among available commands.

I read the paginated [parent thread](<t3-thread://v2/7309f52a-c52b-4287-b6af-6acae8ea63d1/mcp:launch:c4185c930eca174d8d1afc1306852295d17ffddccc8ef520a6713bb41d411891>) and prior objections. I independently reproduced every final R02 prediction exactly, checked fit-only normalization, natural-mask membership, row/group separation and new artifact bindings. An independent likelihood calculation agreed within **0.00022 NLL per row**. I made no edits and ran no fits, simulations, downloads, reserved evaluations or PR actions.

The ranked findings are:

1. **High — Missing command support imposes hard ceilings on the current selector.**

   A00’s **2,817 DEV errors** partition cleanly into:

   - **1,301 unavailable commands — 46.18% of its errors.**
   - **1,516 available-but-not-selected commands — 53.82%.**

   Its fixed library plus G00 hard forecast has an overall oracle ceiling of **13,138/14,439 = 90.99%**, but category ceilings remain far below the requirements: movement **1,953/2,362**, blocked **8/110**, priority **71/576**, ward **12/112**, and `cast_1` **125/243**.

   Consequently, more training of this selector alone cannot meet the category targets. These are ceilings of this **library/decoder combination**, not of the observations or algorithmic methods generally.

   Several omissions are demonstrated mechanisms: absent ground-cast handling, inappropriate ward-placement proposals, ineffective priority proposals, and suppression of blocked attempts. C01/C02 partially address these on TRAIN but still fail their support gates. Their results cannot be presented as achieved accuracy or DEV improvements. See [R00 evidence](/F:/Code/battlecode-26-27/tools/action_predictor/experiments/v11/R00-saved.json).

2. **High — Selection and decoding remain major failures even where support exists.**

   A00 rescues only **135/1,628 = 8.29%** of library-covered G00 errors. For movement alone, A00 misses **623 commands already available** in its support, alongside **409 missing commands**.

   Previous results also show why aggregate gains were misleading:

   - Recall supplies **98 of A00’s 112 net improvements**.
   - Excluding recall, A00’s NLL worsens.
   - Most of D00’s improvement over action-first G00 comes from changing decoding: the matched G00 probability decoder already obtains **11,950** successes; D00 adds **89**.

   Thus weak selection, restricted support and decoding mismatch are distinct demonstrated bottlenecks. A01’s failure does not isolate candidate geometry: it also changed shared scoring, context size and parameter count.

3. **High — R02 demonstrates movement memorization, not complete-command memorization or policy recovery.**

   Final fitted strict accuracy is **1,687/1,981 = 85.16%**. Its **294 failures** are exactly:

   - **128** unavailable shop arguments;
   - **125** priority errors;
   - **18** blocked-destination errors;
   - **18** ward-destination errors;
   - **2** movement errors;
   - **2** `cast_1` errors;
   - **1** teleport error.

   This is strong evidence against a hard inability to fit the selected movement labels. It does **not** clear priority, ward or blocked fitting limitations. Priority exactness is only **3/128** despite perfect fitted action typing.

   Generalization deteriorates on both controls. Final strict accuracy is **31.09% on other rows from the same groups** and **32.78% on withheld groups**. NLL rises from **3.18 to 14.30**, and **3.16 to 17.20**, respectively, between updates 100 and 2,000.

   That is evidence of memorization and increasing overconfidence under this small-data protocol. It does not isolate group shift: the seen-group control is already poor, and the held-group point estimate is slightly better. Nor does it establish how the full-data models would perform on fresh folds. Preserve the fixed final checkpoint; do not retrospectively select update 100.

4. **Medium — R02 reintroduces a concrete blocked-attempt reporting error.**

   [capacity.py:45](/F:/Code/battlecode-26-27/tools/action_predictor/diagnosis/capacity.py:45) calls the legacy summary, whose [legality helper](/F:/Code/battlecode-26-27/tools/action_predictor/reliable_train.py:126) treats movement-mask rejection identically for `move` and `blocked`.

   Every one of the fitted set’s **117 reported “invalid” outputs** is a **blocked forecast rejected by the movement mask**. Successful-move forecasts have **zero** fitted mask rejections.

   The controls contain **134/105 blocked-forecast rejections**, separately from **6/10 successful-move rejections**.

   **Required correction:** add an immutable breakdown separating successful-move mask rejection, blocked-attempt mask rejection and other readiness flags. Preserve the strict destination/outcome scores. The existing aggregate cannot be interpreted as an illegal-command rate.

5. **High — The movement audit establishes compatibility, but does not identify goal, path or tie causes.**

   The DEV partition—**1,593 fixed-library covered, 295 additional greedy-optimal ties, 180 additional field-optimal moves, 294 remaining**—is useful. Its interpretation must stay narrow:

   - **295 does not mean “295 tie-breaking errors.”** It unions alternative optimal moves across several hypothesized goals.
   - **180 does not mean “180 pathfinding errors.”** The terrain field is an unverified uniform-cost route hypothesis.
   - **294 does not mean “294 hidden-intent decisions.”** Those rows remain unexplained by the tested goals, costs and stopping rules.

   Testing global `yx` versus `xy` ordering barely changes the fixed forecasts. There is no evidence that switching either global tie rule resolves the oracle gap.

   The persistence comparison is particularly confounded. [movement.py:42](/F:/Code/battlecode-26-27/tools/action_predictor/diagnosis/movement.py:42) compares nearest camp against history-based selection across **five goals**, changing objective choice and availability together.

   My matched decomposition finds:

   - Across all moves where both field forecasts exist: **435 → 504 correct**.
   - On direction changes where both exist: **211 → 220 correct across 566 rows**.
   - The advertised direction-change gain of **72** decomposes into **+9 on shared availability, +102 on newly available rows, −39 on lost rows**.

   Even the shared-row gain mixes objective choice with history. Furthermore, the code scores past movement against **current goal locations**; it does not retain a persistent historical objective identity.

6. **Medium — Representation loss is demonstrated; its causal contribution remains unmeasured.**

   D02 establishes omissions from legacy entity summaries, including **56.44% of visible living camps** in the sampled audit and missing entity attributes. R02 retains that representation and only 16 action-history entries.

   However, the grid preserves some aggregated entity information. Negative entity/history experiments also changed learning arrangements. Neither result establishes that omitted observations explain a particular fraction of errors.

   Having 16 available observations does not establish sufficient memory. Conversely, nearly unique encoded inputs and successful memorization do not establish sufficient information.

   **Observation sufficiency remains unresolved.** Missing observable context, compressed history, persistent state, stochastic behavior and policy variation remain distinguishable hypotheses—not established explanations.

7. **Medium — Natural sampling corrects the comparison, but does not explain the residual gap.**

   G00’s natural TRAIN accuracy is **81.79%**, versus **79.71% DEV**. Standardizing action, engine and movement-continuation cells gives **81.02% versus 79.71%**, with **zero unmatched DEV rows**.

   A00 similarly changes from **83.03% natural TRAIN** to **82.30% standardized TRAIN**, versus **80.49% DEV**.

   This repairs the misleading comparison with augmented TRAIN. It does not control maps, opponents, observation difficulty or Fish policy versions. TRAIN predictions remain in-sample.

   Engine-version attribution is especially weak: **all engine-3 DEV games belong to one group**. Engine version is also not evidence of a particular Fish policy version.

8. **Medium — Label/event/policy inconsistency remains an unfinished diagnostic category.**

   The previous encoded-input collision audit found few conflicting encodings, but almost all inputs were unique. That provides little power to reject policy variation or establish observation-level contradictions.

   No new R02 result establishes contradictory labels given equivalent full personal evidence. The report should explicitly mark this cause **unresolved**, while retaining known semantics problems such as attempted moves versus successful moves. Missing shop arguments remain a measurement limitation; sparse altar, teleport and submit results remain uncertified.

**The single most informative next experiment is a matched, TRAIN-only causal goal-history control, without another fit.** Generate the same five-goal candidates with identical planner, tie rule, stopping radii and availability handling. Compare a frozen current-observation selector against a forward history-based selector and a simple last-heading control. Freeze rules before assessment; report paired results on identical rows, especially direction changes, with availability gains separated.

That directly tests whether history adds predictive information after objective-family and availability changes are controlled. A gain would support useful causal history; it would still not prove Fish’s internal objectives. A failure would reject this particular persistence proxy without justifying another architecture phase.

The final diagnosis should therefore rank **support limitations and selection/decoding failures as demonstrated**, **small-subset memorization with poor transfer as demonstrated**, and **information insufficiency, persistent intent and policy inconsistency as unresolved**.
