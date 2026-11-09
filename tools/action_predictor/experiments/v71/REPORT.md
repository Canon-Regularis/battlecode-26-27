# V71 - direct shared-executor weight edits

Twenty fitting-selected weight edits did not improve evaluation decisions. The selected edit multiplies the nine first-layer goal/availability/utility input columns by0.75 and leaves the output scale at1. Exactly576 scalar weights change; all other weights and biases remain exact. Goals remain enabled and the executor continues to run on all located queries.

The frozen grid used goal scales0.25/0.5/0.75/1 and output scales0.25/0.5/0.75/1/1.25. It never disables correction or goals. Four matching fitting folds select by movement count, then NLL, then edit norm, with direct-NLL and original-cohort guards. The selected edit changes held fitting correctness from1,246 to1,247/1,997. All20 settings were selected without evaluation answers or optimizer updates.

On the fixed evaluation it remains **311/513 (60.62%)**, versus V70 original311 and direct318. There are zero rescues and zero regressions versus V70. NLL is1.180828, slightly below V70's1.182086. It fails both required accuracy gains. No promotion or strategic gain follows.

The fitting-only margin probe motivating this study found54rescues and45regressions from V70 vsdirect, with median original logit gaps0.219/0.182. It did not prove overcorrection as the cause. Shrinking these connections does not solve the accuracy issue under this test.

Direct verification reproduces all20 settings, selection, exact576weight changes and saved forecasts, plus96streaming turns including21active and15located no-goal queries. Three focused edit tests cover immutable originals, exact changed columns, nonzero scales and readout-scaling arithmetic. Opt-in runtime: `CalibratedSharedPlanner`; previous models remain preserved. No subagents or fitting steps occurred.

These are reused research groups and one seed, with observed history and inferred goals. Weight norms and fitting gains are not demonstrations of strategy. See [V70](../v70/REPORT.md) for the shared executor and [V72](../v72/REPORT.md) for the next readout-only fit.
