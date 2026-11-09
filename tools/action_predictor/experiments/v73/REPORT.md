# V73 - nested cross-fitted goal inputs

Cross-fitting is implemented with a genuinely game-excluded goal selector and a same-size in-sample control. It improves the matched evaluation count **302 to 308/513** (six movements), but remains below direct V59 **318/513**. It also fails the goal-present two-point guard. The complete gate fails; no default replacement, promotion or strategic benefit is established.

## Why the selector changed

The previous goal selector consumed a learned V59 state/code representation with historical exposure to the fitting games. Merely refitting its final goal head would not make the complete goal predictor game-excluded. V73 therefore uses a fresh 660-64-1 tanh selector on 648 deterministic current geometry, observed-position heading and completed-prior-turn movement features, plus 12 current candidate features. There is no learned input encoder, fitted normalizer, pretrained state/code, game identity or current/future action in the selector inputs.

These features are geometric/history summaries; they are not a lossless full-map representation. This changes the selector family relative to V70. Both V73 arms use the new family, so the matched contrast tests cross-fitting within it. Comparisons to older selectors do not isolate cross-fitting. The shared executor architecture and frozen direct predictor stay unchanged.

## Exclusion and matching

The existing 32 fitting games form four 8 game folds. For each outer held fold:

- Cross-fitted training goals for groupG use a selector trained on 16 games, excluding both the outer fold andG's fold.
- The size-matched control also uses a 16 game selector, excluding the outer fold and a different inner fold. Its training data includeG.
- Both arms validate with the same 24 game selector excluding the outer fold. Their held goal tensors are identical.

The six pair-excluded models are reused across symmetric jobs because their data, deterministic features and initialization are identical. Four single-fold-excluded models and one full 32 game model bring the total to 11 selectors. Group counts are matched, not necessarily candidate-example counts; both arms use the same collection of trained selectors.

For final executor training, cross-fitted goals use 24 game selectors excluding the predicted game's fold. The control rotates to another 24 game selector that includes that game. Both runtime variants use the same 32 fitting-game selector. No evaluation game enters selector or executor updates. Membership is archived in `selectors.json`; each of 123,180 movement-input checks verifies the intended exclusion/inclusion.

## Training and selection

Selector inputs reconstruct from 18,177 observed fitting queries, with 42,959 candidate utility examples. Existing four-turn replay progress provides supervision only. All 11 selectors start from identical fresh seed 73001 weights and train 12 passes with AdamW lr 0.001, batch 256, clip 5, weight decay 0.01. Selector training accounts for 14,148 updates. No excluded-group scores choose selector checkpoints. The legacy scale 0.5/shift-0.25 and retention 0.15 are fixed rather than retuned.

Both shared executors use all 12,318 fitting movement examples, matching initialization seed 70001,16 passes, AdamW lr 0.001, batch 128, clip 5 and checkpoint opportunities 0/4/8/12/16. Only their training-goal predictions differ. Fitting-game validation selects control epoch 16 with 1239/1,997 and crossfit epoch 12 with 1243/1,997. Each full refit uses its selected duration. Different selected durations are part of the compared procedures, not an isolated same-duration effect.

The candidate-weighted raw utility MSE on fitting games is **0.327104** when selectors trained on those games and **0.569608** when those games are excluded. This confirms more optimistic in-sample predictions in this selector family. It does not prove that this mismatch was the sole movement bottleneck or measure true Fish intent. Full-refit goal availability is 7,239 control versus 7,003 crossfit movement examples. Weight inspection confirms finite, changed executor tensors in both arms.

## Fixed evaluation

| Same 513 movement queries | Correct | Movement NLL |
| --- | ---: | ---: |
| Same-size in-sample control |302|1.170869|
| Cross-fitted goals |308|1.179437|
| Preserved direct predictor |318|1.200119|

Crossfit rescues 13 control errors and introduces 7, net+6. Against direct it rescues 15 and introduces 25, net-10. NLL improves relative to direct but worsens relative to control. On the shared goal-present cohort it gets 160/252 versus direct 166, a 2.38 point loss, failing the two-point guard. On no-goal movements it gets 148/261 versus direct 152, inside the guard. One exposed research evaluation and one seed do not establish a reliable generalization gain.

## Runtime and verification

```python
from tools.action_predictor.behavior_segments.crossfit_goals_predictor import CrossfitGoalPlanner
predictor = CrossfitGoalPlanner(arm='crossfit')  # experimental, not promoted
```

The existing causal predict interface and actor state are retained. `shared_movement`/`objective_movement` expose the new executor; direct and routed movement remain separately available. The selector reads only deterministic current-map/history features. Replay future coordinates or utility labels are never runtime inputs.

Twenty-three focused tests pass. Parent verification checks 11 fresh selector initializations, all selector schedules/RNG/optimizer counts,42,959 target/feature rows,123,180 exclusion checks, identical held goal tensors,40 goal-window probes, all 40 executor fold measurements and 12,028 executor updates. Saved forecasts reproduce;192 streaming turns include 70 goal-present and 6 located no-goal queries. No subagents or optimizer replay were used.

Goal-model update exclusion is real, but the overall experiment is not fresh certification: executor backbone exposure, previously studied recipes/partitions, fixed historical calibration, teacher-forced histories, proxy utilities and a single seed remain limitations. No mixture-of-goals, latent-plan or autonomous rollout change is included in this controlled first step. The original stronger direct weights remain preserved.
