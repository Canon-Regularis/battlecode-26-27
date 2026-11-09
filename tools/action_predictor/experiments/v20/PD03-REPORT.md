# PD03: omitted scheduling information has a verified personal-API path

The original observation whitelist drops other champions' current and scheduled priorities. P05 later recovers own priorities/history, but its 39 additional channels and the entity-token representation do not include other champions' scheduling values.

In the same two previously audited TRAIN games, 1,245 of 1,472 selected decisions contain at least one known-public other champion; that is 41 of 44 recorded priority decisions. The 3,011 known-other-champion records contain zero current/scheduled-priority fields. This bounded inventory is not an estimate for all games or a measurement of prediction gains.

Historical repository SDK source already exposes non-self priority getters. That wrapper evidence alone did not certify engine-2/3 availability, so a bounded check restored actual recorded PREs and called the pinned engine's scoped `Game_API_Champion_GetPriority` export. No action, branch, bot executable or new match was used.

| Historical engine | Recorded PREs | Exact own queries | Differing current/next cases | Successful known-other queries | Rejected unknown queries |
| --- | ---: | ---: | ---: | ---: | ---: |
| 2.0.0 | 18 | 36/36 | 2 | 66/66 | 150/150 |
| 3.0.0 | 18 | 36/36 | 2 | 110/110 | 142/142 |

Own controls include 62 negative integer results across both engines. Every successful known-other result agrees with its personal snapshot; unknown-champion queries return error 97 and their values are never retained. Recorded headers and personal snapshots remain identical before and after queries. These checks establish a real available input in these cases, not a license to use unknown/omniscient values or assume availability everywhere. Any extraction must query per row and retain explicit availability.

The first probe failed its signed-own control because the output reader omitted DataView's explicit little-endian flag. That error is in this new probe, not the old validated P05 extraction path. Its original source, plan and raw failure remain preserved. Version 2 changes only the explicit little-endian int32 read and repeats the same cases. No model consumed the failed result.

Case selection was fixed from TRAIN PREs: sixteen evenly spaced existing observations per game plus the first current/next-different and negative-current examples. No recorded answer or outcome selected a case. This is an API/causality check, not command-accuracy evaluation; it cannot certify category reliability or prove that Fish uses these values.

The result distinguishes a demonstrated representation omission from an untested explanatory claim. Other-champion action-order information is personally queryable and absent from current features. Whether adding it improves learning requires the matched information contrast recommended by the PC02 review. No new command candidates, fitted predictor, DEV evaluation or policy replacement is produced here.

Reproduction: `python -m tools.action_predictor.priority_diagnosis.available_inputs`; `python -m tools.action_predictor.priority_diagnosis.order_prepare`; the original Node command intentionally fails its preserved signedness check. The corrected sequence is `python -m tools.action_predictor.priority_diagnosis.order_prepare_v2`, then `node tools/action_predictor/priority_diagnosis/order_availability_v2.cjs tools/action_predictor/experiments/v20/PD03-api-v2-plan.json`. Completed outputs are immutable; do not overwrite or rerun them into existing destinations. Both reserved partitions remain sealed.
