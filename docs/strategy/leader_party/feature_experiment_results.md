# State-machine feature experiments: final results

Completed 2026-11-05; experiment began 2026-11-04.

**Retain `leader_party_tuned` (`g07_search`).** No tested addition demonstrated a winning improvement sufficient to replace it. The strongest training candidate, `c02_record_guard`, reduces logged SDK errors substantially but fails to confirm its training gain on reserved maps. The champion's source, tuning, release artifact and website submission are unchanged. All experimental bots and evidence remain available.

## Selected trial and fair comparison

The trial enables corrected bank-completion bookkeeping and channel-start guards. Guards check alive/stun/channel/completed-turn/start-state conditions and current round before starting recall or tribute. Accounting checks a tracked positive bag, the same life, ended channel, empty bag and sufficient team-score change. These are execution/bookkeeping changes; accounting is not a new farming or banking-threshold strategy. Extra queries, logging and compiler layout can affect fuel suspension and trajectories, so counter-only performance changes do not establish an economic mechanism.

The trial preserves the champion's original dispatch, combat, draft, Subhan camp-loop planner, native navigation/observations and every original configuration declaration. Banking remains bag 35/age 70; loop phase 3/beam 8 and other tuned values are unchanged. It adds no rallies, following or chunk inspection to the retained champion.

| Evaluation | Direct trial vs champion | Trial common wins | Champion common wins | Trial/champion matched error occurrences |
| --- | --- | --- | --- | --- |
| 32 training maps | 36-28 | 617/896 | 615/896 | 40/148 |
| 38 reserved validation maps | 37-39 | 712/1,064 | 729/1,064 | 27/97 |
| All 86 maps | 90-82 | 1,628/2,408 | 1,635/2,408 | 81/273 |

Common conditions use the same 14 opponents, map, side and deterministic seed for both bots. Each bot has zero VM faults in these normal-fuel matrices. Across common full-pool games the trial has 331 fewer deaths and 192 fewer logged error occurrences, but seven fewer wins. Its 90-82 direct result is 52.3%; the reserved direct result is 37-39. These results give no sound basis to promote it as a more successful strategy.

The trial's raw full-pool total is **1,718-862 across 2,580 games**, including 172 direct champion games. Champion's **1,635-773 across 2,408 games** excludes self-play. Those raw totals have different denominators; the matched common-opponent comparison above is the appropriate shared-pool comparison. Reduced-fuel and coverage games are excluded.

The common-win-rate difference's map-cluster 95% interval is approximately -2.03 to +1.45 percentage points over all 86 maps, and -4.42 to +1.32 points on reserved maps. The point estimates and uncertainty do not demonstrate an improvement. This is not proof that every possible implementation of these ideas is worse.

## Full opponent matrix

Every row below has 172 games per bot (86 maps, paired sides). The direct trial-champion result is 90-82, reported separately above.

| Common opponent | Trial W-L | Champion W-L |
| --- | --- | --- |
| `D1` | 154-18 | 151-21 |
| `complete_r08` | 158-14 | 156-16 |
| `g02_bank35` | 105-67 | 113-59 |
| `g03_recover20` | 103-69 | 96-76 |
| `g05_without_search` | 83-89 | 93-79 |
| `g05_without_team` | 82-90 | 90-82 |
| `g06_competition_cost_1` | 86-86 | 87-85 |
| `g08_comp6` | 87-85 | 81-91 |
| `g08_phase4` | 90-82 | 87-85 |
| `gold_diamond` | 146-26 | 149-23 |
| `larpbot` | 151-21 | 150-22 |
| `original` | 117-55 | 120-52 |
| `pool6` | 151-21 | 153-19 |
| `subhan` | 115-57 | 109-63 |

## Individual additions and combinations

The initial design freezes 20 feature profiles plus a disabled control, screens all 21 on 16 maps against four opponents (2,688 conditions), and expands qualifying profiles onto 32 training maps. Required protocol/leadership dependencies have explicit controls. Further decompositions, corrected priorities and interactions are independently frozen. [The complete feature inventory](evaluation/2026-11-04/features/feature-stage-summary.md) gives every profile's screen/training W-L and matched common results; [source/flag receipts](evaluation/2026-11-04/features/artifact-audit.json) identify all 34 audited formal experimental profiles.

| Addition | Measured outcome and decision |
| --- | --- |
| Shared protocol; stable leader; preferred action order | Shared publication regressed on training; leadership's screen gain did not hold. Original action order with leadership tied the control. Priority-only also regressed. Excluded. |
| Visible following; remote chunk inspection; strict leader-only planning | Screen direct results 12-20, 3-29 and 3-29, with substantially fewer common wins. Engine traces confirm these paths executed. Excluded. |
| BANK rally publication/response/protection | Screen 11-21 direct and 57/96 common versus 69/96 control. Actual requests, accepts and escorts recorded. Excluded. |
| ATTACK rallies | Original screen 12-20; corrected accepted-commitment version 34-30 on training but 152/192 common versus 161. Actual publish/accept/arrival traces recorded. Excluded. |
| Exact CAMP/BANK commitment | Corrected training results 36-28 with 157/192 common, and 30-34 with 156/192; control 161/192. Excluded. |
| Local protection patrol; enemy reports | Executed but did not improve the screen. Enemy reports alone measure publication/overhead without inventing a remote-information consumer. Excluded. |
| Bank-carrier reacquisition | Promising direct result; full training 652/960 and 617/896 common versus 615. Considered as a finalist, not selected over 653-win guarded accounting. |
| Redispatch; ally retreat; escape hysteresis | Training common 150, 154 and 155/192 versus 161; direct 24-40, 25-39 and 30-34. Excluded. |
| Channel guards | Training ties 32-32 and 161/192 with fewer logged channel errors. Kept for interaction testing as a reliability improvement. The selected combination failed winning validation. |
| Legal target range; terrain-aware wards | Range's screen gain did not hold on training (159/192 versus 161); ward screen 62/96 versus 69. Range/guard interaction 158/192. Excluded from retained champion. |
| Damage/AoE selection | Training 158/192 versus 161. Normal first-five draft has no AoE spell, so default-draft score changes cannot be attributed to area spells. Separate forced-kit coverage verifies casting. Excluded. |
| Bank completion accounting | Original V5 strong screen signal did not hold in the full training pool: 642/960 and 609/896 common versus 615. Minimal accounting is a separate decomposition. No counter-based economic benefit claimed. |
| Own safety publication; safety-aware support | Own publication regressed on training. Support consumer failed the fixed expansion criteria on screen. Excluded. |

V5 commitment fact suppression still permitted higher-priority spawn/healing/banking interruptions. The corrected V7 CAMP/BANK/accepted-ATTACK profiles fix that ordering before retesting;1,536 native interruption cases pass. An intermediate V6 disabled build drifted from champion and is preserved as engineering history with no strength games. V7's disabled artifact again matches champion byte-for-byte. Earlier pilots are excluded from final selection.

All four planned interactions were tested: range+guards, accounting+guards, reacquisition+guards, and all three banking additions. The triple finishes 194/256 versus simpler guarded reacquisition 195/256, with the same 34 direct wins, one fewer common win and more errors; it was not expanded. Four finalists received the full 15-opponent 32-map training pool:

| Frozen finalist | Training wins/960 | Direct vs champion | Common wins/896 | Matched errors |
| --- | --- | --- | --- | --- |
| Accounting + guards (`c02_record_guard`) | 653 | 36-28 | 617 | 40 |
| Reacquisition (`v5_f11_reacquire`) | 652 | 35-29 | 617 | 148 |
| Reacquisition + guards (`c03_reacquire_guard`) | 647 | 34-30 | 613 | 50 |
| Original accounting (`v5_f20_bank_record`) | 642 | 33-31 | 609 | 143 |

The [primary selection receipt](evaluation/2026-11-04/features/primary-selection.json) freezes C02 source/WASM and complete input receipts before reserved evaluation. No alternate candidate was chosen using reserved outcomes. C02's screen-map rows in the final inventory were first evaluated during the final matrix, after selection; map-split labels do not imply those outcomes existed during selection.

## Verification and limits

- All 34 frozen source archives/current sources/release WASM profiles pass the [artifact audit](evaluation/2026-11-04/features/artifact-audit.json). Eleven navigation/planner/draft/observation files remain byte-preserved, and all original configuration declarations are retained. Champion matches its complete frozen baseline.
- Disabled V5 and V7 controls match champion WASM exactly. All 96 matched disabled-control common scores/deaths/errors/seeds match champion; identical-code direct screening is 16-16.
- [Final production contracts](evaluation/2026-11-04/features/native-contracts-final.json): 466,621 feature-policy assertions, protocol/state scenarios, and 1,536 commitment-priority cases pass. [Exact-source target-filter checks](evaluation/2026-11-04/features/legal-range-contract.json): 1,872 cases, 255 recovered legal targets.
- Normal-draft combat probe: 21 extended-target events, no AoE events. Forced Prism/Stellar fixture: 31 AoE evaluations and 26 successful casts, zero faults/errors. Shared/channel probe: 30 verified same-round shared-memory round trips, eight allowed starts and three blocked starts, zero faults/errors. All 20 coverage-only games are excluded from strength results; instrumentation changes fuel/trajectories and is not performance evidence.
- [Reduced-fuel diagnostics](evaluation/2026-11-04/features/c02_record_guard-stress-60000.json): 12 games over six maps, paired sides, 60,000 fuel. Trial 14,551 fuel pauses; champion 13,895. Both finish with zero VM faults and zero logged errors. This exercises suspension under reduced fuel, not an exhaustive proof of every resumed branch.
- [Final matrix audit](evaluation/2026-11-04/features/final-matrix-audit.json) verifies exact condition sets, cache identities, 10,556 replay archives/summary checksums and identical reused validation/training rows in the final matrix. This archive count includes controls and multiple profiles, not that many independent samples for the final trial.

The 86 published maps were historically used in earlier work; validation is reserved within this experiment, not a previously unseen map population. Map/opponent correlations, adaptive training selection and multiple comparisons limit generalization. Error counts are logged occurrences under equal log limits, not a guarantee of zero remaining SDK defects. Inherited action-error categories remain in normal games. Capped/deduplicated feature events prove observed branch execution, not objective success or benefit by themselves. Do not sum cached phase totals as independent games.

## Retained code and reproduction

Retained/submitted champion: [`bots/leader_party_tuned`](../../../bots/leader_party_tuned/README.md), unchanged. [Retention receipt](evaluation/2026-11-04/features/retained-bot.json).

Champion WASM SHA-256: `a24ef0c56844e506694c48ed34e698c083a18fe7d9d74bf6c12ae355d1b448ac`.

Preserved primary experiment: [`bots/lp_feature_c02_record_guard`](../../../bots/lp_feature_c02_record_guard/README.md), flags `bank_record,channel_guards`, mask 278528. Trial WASM SHA-256: `605207958ed3f3dc778f03b0b122dfa9c7469f09e19dd7b48c979a47532e73d7`. Frozen source/ZIP receipts identify all other clones. No bot was committed, pushed or submitted during this experiment.

CAMBC 4.0.0 release, default fuel for strength games, log-limit 200000/team, deterministic map-derived seeds, paired sides. [Environment receipt](evaluation/2026-11-04/features/environment-receipt.json) freezes CLI, SDK, 86 maps and 15 opponent artifacts. Later [user-authorized CPU policy](evaluation/2026-11-04/features/load-policy-revision-reserved-core.json) reserves one physical core (both logical threads) and runs 14 workers on the other 7 cores at below-normal priority. Earlier sequential scheduling is documented in the chronological experiment record; artifacts/fuel/seed identities stay fixed.

From the repository root (PowerShell):

```powershell
.venv/Scripts/python.exe tools/experiment_party_features.py integrity
powershell -NoProfile -File bots/leader_party_feature_lab/tests/run.ps1
.venv/Scripts/python.exe tools/report_party_feature_stages.py
.venv/Scripts/python.exe tools/report_party_features.py champion-pool-training-control reacquire-train-pool finalists-train-pool reacquire-guard-train-pool
.venv/Scripts/python.exe tools/report_party_features.py champion-pool-all selected-validation
.venv/Scripts/python.exe tools/report_party_features.py champion-pool-all selected-all-pool
.venv/Scripts/python.exe tools/validate_party_feature_selection.py
```

The last command verifies the frozen trial and resumes/reuses the existing validation, full-pool and stress receipts. Preserve `.cambc/features/*-source.zip` and artifact ZIPs for frozen-artifact reproduction; game replays are in `replays/leader-party/tuning/cache`. See [the chronological experiment record](feature_experiments.md) for implementation revisions and individual expansion decisions.
