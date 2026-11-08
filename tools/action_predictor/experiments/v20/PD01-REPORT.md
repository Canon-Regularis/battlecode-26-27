# PD01: confidence and ranking both deteriorate on the controls

Read-only probability arithmetic reuses the frozen neural outputs of warm P05, PC00 and PC01 on the same three 128-row cohorts. No calibration, threshold, optimizer, neural forward or replacement selection runs. The recorded action family is supplied; this is conditional integer calibration, not complete-policy calibration.

| Control | Model | Exact /128 | Mean mode probability | Mean probability on wrong modes | Mean recorded-value rank |
| --- | --- | ---: | ---: | ---: | ---: |
| Same fit groups | Warm P05 | 25 | .191 | .172 | 13.26 |
| Same fit groups | PC00 | 10 | .672 | .672 | 25.52 |
| Same fit groups | PC01 | 13 | .612 | .614 | 40.04 |
| Disjoint groups | Warm P05 | 28 | .175 | .151 | 14.65 |
| Disjoint groups | PC00 | 12 | .653 | .650 | 27.31 |
| Disjoint groups | PC01 | 16 | .628 | .610 | 46.12 |

Ranks are among distinct existing point/fallback-mode candidates, not all integers. Mode probabilities use the original normalized P05 distribution, marginalizing duplicate explanations. Both controls were previously seen by the frozen encoder and warm head. They are excluded only from the new optimization; these are not untouched generalization results.

PC01's fixed-bin conditional ECE is .5101/.5026 on the controls, versus warm P05's .0966/.0577. The reported Brier diagnostic is binary mode-correctness Brier, not the full integer-distribution Brier. Empty bins and empty correct/wrong subsets retain null means. Ten equal-width bins were fixed before this calculation; there is no fitted calibration or bin/threshold selection. Small reused cohorts limit calibration estimates.

The deterioration includes sharper wrong predictions and worse recorded-value ranking. A strictly increasing recalibration of the final complete-integer probabilities preserves ordering, so it cannot by itself improve conditional exact integer predictions. This statement does not apply to arbitrary changes in component logits or to joint action-family decisions, which can change after probability adjustment.

Mean recorded-target probability on the disjoint-group control actually increases .1028 to .1300 from warm P05 to PC01, while NLL worsens. The arithmetic mean hides rows receiving very small target probabilities; it does not replace the proper log score or establish improved likelihood. Mean confidence also cannot distinguish useful confidence on correct commands from confident errors.

The original 128 fitted rows show a different pattern: PC00 is 128/128 with mean confidence .9991; PC01 is 102/128 with .7373. These are in-sample rows in both studies. No information-sufficiency claim follows from this fit.

The result locates defects in the saved distributions; it does not establish why learning produced them. Coverage, context diversity, representation, optimization and forgetting remain unseparated. No new architecture or strategy is inferred. The PC01 independent review was already underway when this separate later diagnostic ran; do not present it as approved by that review unless the reviewer explicitly covers it.

Reproduce once into absent immutable destinations: `.venv-action-predictor/Scripts/python.exe -m tools.action_predictor.priority_diagnosis.calibration`. All source outputs and dependencies are bound in PD01-plan.json and the additive completion receipt. Both reserved partitions remain sealed; no DEV payloads, matches, downloads or bot/runtime work are used.
