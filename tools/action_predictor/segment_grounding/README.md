# Personally observed identity inputs — preparatory, unfitted

This helper supports a later controlled grounding experiment. It is not imported by the frozen H00/H01 pair and changes no current training inputs or forecasts. There is no learned selector, target assignment or execution policy here yet.

The memory refreshes every personally observed champion/camp identity, including an entity that stops being the nearest or highest-ranked hypothesis. Unknown current entries cannot overwrite old dynamic fields. Known death is recorded as last-observed evidence, and a later known reappearance refreshes it; stale death or position is never asserted to be a current fact. Actual own-root ordinals, gaps and unavailable prefix remain explicit. Episode/actor boundaries require reset.

Numeric entity identifiers are audit-only lookup keys. Learned inputs contain reviewed entity features plus explicit current availability, memory age, gap/prefix availability and null/unknown/entity/death flags. No nearest-k pruning, camp ranking, strategy labels or goal survival assumptions are introduced. Any later use needs exact row/token identity binding, a matched grounding control and separate learned selection/execution evaluation.

```text
python -m unittest tools.action_predictor.segment_grounding.test_memory -v
```
