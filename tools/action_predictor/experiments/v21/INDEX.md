# Current research status: model training only

No experimental model meets the original complete-command, category, macro-F1, movement, NLL, targeting and three-seed goals. Bot/runtime work is paused. PR #11 remains DRAFT and unmerged. Both 75-game reserved partitions stay sealed.

The ward study was discontinued by the user after P00, P01 and T00. T01 is unrun; the four-fit protocol was not completed. Earlier README sections describing remaining ward fits are historical, not current instructions.

## Demonstrated bottlenecks

1. **Current conditional outputs still limit complete commands.** The retained priority head supplies only 109/576 correct DEV integers even with the recorded action supplied. Changing family selection alone cannot repair those parameters. Oracle candidate support and achieved accuracy remain separate.
2. **Movement execution distributions remain weak.** The [U01 review](../v18/U01-review.json) reproduces 844 common-wrong movement modes and a conservative conditional reweighting bound of 1,518/2,362, below the binding 1,541-command movement point target. This freezes component distributions and past state; it is not an architecture or information ceiling.
3. **P05 fitting and transfer fail differently.** [PC00](../v19/PC00-REPORT.md) fits 128/128, but that 128×168 affine input matrix has rank 128 and permits interpolation. [PD00](../v20/PD00-REPORT.md) shows original natural TRAIN fitting continues from 24.6% to 41.9% while historical DEV loss worsens. [PC01](PC01-REPORT.md) fits 4,898/5,876 but both controls deteriorate from their warm start. All control targets have a represented absolute or available-residual explanation in the broader training population. Coverage alone does not explain the failure.
4. **The saved errors involve ranking as well as confidence.** Later read-only [PD01](../v20/PD01-REPORT.md) and [PD02](../v20/PD02-REPORT.md) locate poor conditional calibration, worse recorded-value ranks and co-adapted readout changes. They neither prove deficient observations nor select a replacement hybrid. These later diagnostics are outside PC01 review's declared coverage.

## Evidence and limits

[PC01's fresh Sol xhigh review](PC01-review.json) reproduces all 31,300 forecasts, normalized probabilities, cohort construction, optimizer counters and 84 completion bindings. Its reader returned `thread_not_found` for the parent, so it used the supplied brief, local evidence and saved reviews rather than the full conversation. A complete local message export is now available for subsequent reviewers.

The review identifies prospective source-gate dependency omissions, optimized-Python assertion removal, and raw-output archival after measurement. No contaminated PC01 execution or missing completed artifact was found. Historical PC00 uncommitted execution remains disclosed; subsequent hardening does not retroactively change it.

Both the frozen encoder and warm head previously saw the control rows. They are held out only from each new optimization, not untouched full-policy generalization. Information sufficiency, useful strategic intent, policy variation and the dominant cause of transfer failure remain unresolved. All 43 DEV shop arguments remain unavailable strict failures; sparse categories remain uncertified.

The [PC02 controlled contrast](../v22/PC02-REPORT.md) constrains displacement from warm P05 using one TRAIN-derived penalty strength. Population, architecture, initialization, arithmetic, optimizer and fixed endpoint stay unchanged. It fits 4,671/5,876, with controls 14/128 and 23/128 versus warm 25/128 and 28/128. Control losses improve against PC01 but remain worse than warm; its exploratory gate fails. No model is promoted, penalty sweep is selected, or policy replaced. Its fresh independent review is pending.

PC02's execution-hardening tests passed before optimization: static local dependency/test closure against committed bytes, optimized-Python refusal through the real entrypoint, optimizer tripwires on injected source errors, and raw-archive survival after injected measurement failure. These corrections do not retroactively turn older runs into committed-source executions. Restoring warm scores by preventing learning would not count as improvement, and no new architecture or identical seed repeats follow automatically.
