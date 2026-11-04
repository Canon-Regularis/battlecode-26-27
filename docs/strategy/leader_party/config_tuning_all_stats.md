# Complete configuration tuning

The preferred bot is `leader_party_tuned`, matching frozen **`g07_search`**. It combines the selected settings in one C++ bot using Subhan’s camp-loop planner. Original bots and every tuning generation remain intact.

All **31 configuration fields** received explicit probes across two full sweeps and combined-profile tests. The registry preserves **202 profiles**. Thirty fields affect gameplay; `attacks` is unused and both values compile to identical WASM. Keeping a default is a measured outcome, not an omitted stat.

The full experiment contains **26,288 completed replay files**, representing **24,679 distinct ordered WASM/map/seed conditions**. Cached conditions, artifact aliases and mirrored result views do not add independent evidence. Repeated deterministic scores agree.

## Final comparisons

| Frozen profile | Published maps, three opponents | Wider 15-bot suite | Ancestry suite |
| --- | ---: | ---: | ---: |
| `g07_search` | 409–107 | 178–2 | 103–77 |
| `g08_phase4` | 408–108 | 180–0 | 89–91 |
| `g05_without_search` | 403–113 | 178–2 | 86–58 |
| `g05_without_team` | 401–115 | 180–0 | 87–57 |
| `g08_comp6` | 392–124 | 180–0 | 100–80 |
| `g06_competition_cost_1` | 391–125 | 179–1 | 112–68 |
| `g02_bank35` | 381–135 | 180–0 | 60–84 |
| `g03_recover20` | 380–136 | 178–2 | 65–79 |

Published comparison: all 86 published maps, both sides, against untuned Subhan, D1 and gold_diamond (516 conditions/profile). The wider suite uses all 15 pre-existing opponent artifacts on six maps, both sides (180/profile); it is reported separately to avoid overweighting weaker bots. Ancestry games compare the surviving profiles to earlier G1/G2/G3 and G5 generations on 18 validation maps; self-games are skipped.

| Final bot opponent | Wins–losses |
| --- | ---: |
| `D1` | 151–21 |
| `gold_diamond` | 149–23 |
| `subhan` | 109–63 |

The closest full-pool contender is `g08_phase4`. The selected bot’s direct record against it on the same 86 maps is **87–85**. This diagnostic does not replace the predeclared common-opponent wins-first policy; a one-game full-pool gap is a near tie, not decisive superiority.

Wider-suite losses remain visible:

| Opponent | Map / our side | Gems |
| --- | --- | ---: |
| `archive/retired_bots/larpbot_baseline_20261013` | `00lanes` / teamA | 764–1003 |
| `D1` | `00lanes` / teamB | 984–1005 |

The final configuration was frozen before the nine reserved legacy maps. Its separate legacy robustness record is **44–10**; these map files differ from the published map pool. They are a robustness check, not random future-map confirmation.

## One combined configuration

| Compile-time field | Final value | Continuation probe values |
| --- | ---: | --- |
| `bank_bag` | `35` | `20`, `30`, `40`, `50` |
| `bag_age` | `70` | `40`, `55`, `85`, `100` |
| `stall` | `8` | `4`, `6`, `10`, `16` |
| `task_limit` | `90` | `45`, `70`, `110`, `150` |
| `max_clear` | `90` | `45`, `70`, `110`, `150` |
| `protection_limit` | `12` | `0`, `4`, `9`, `15`, `24` |
| `retry` | `10` | `0`, `3`, `7`, `13`, `25` |
| `wards` | `True` | `False` |
| `value_routing` | `False` | `True` |
| `recovery_low` | `0.35` | `0.0`, `0.2`, `0.3`, `0.4`, `0.5` |
| `recovery_high` | `0.55` | `0.4`, `0.5`, `0.6`, `0.75`, `1.0` |
| `recall_gold` | `300` | `150`, `200`, `400`, `600` |
| `competition_cost` | `4` | `0`, `2`, `6`, `8`, `10` |
| `loop_candidates` | `24` | `12`, `16`, `32`, `40`, `48` |
| `loop_altars` | `4` | `1`, `2`, `3`, `5`, `8`, `16` |
| `loop_beam` | `8` | `2`, `4`, `6`, `8`, `10`, `16`, `32` |
| `loop_length` | `5` | `3`, `4` |
| `loop_expansions` | `768` | `256`, `512`, `1024`, `1536`, `6144`, `20000` |
| `loop_reports` | `3` | `1`, `2` |
| `loop_gold` | `0.02` | `0.0`, `0.04`, `0.08` |
| `loop_opening` | `0.15` | `0.0`, `0.05`, `0.25`, `0.4` |
| `loop_risk` | `0.2` | `0.0`, `0.1`, `0.3`, `0.6`, `1.0` |
| `loop_service` | `7` | `0`, `4`, `10`, `14` |
| `loop_phase` | `3` | `0`, `1`, `3`, `4`, `5` |
| `rally_life` | `12` | `0`, `6`, `9`, `15`, `24` |
| `lease` | `3` | `0`, `1`, `5`, `8` |
| `reserve` | `5000` | `0`, `2500`, `5000`, `7500`, `10000`, `20000` |
| `field_admission` | `30000` | `20000`, `30000`, `40000`, `55000`, `80000` |
| `max_fields` | `3` | `1`, `2`, `4`, `5` |
| `coordination` | `False` | `True` |
| `attacks` | `False` | `True` |

Protocol lifetime/lease probes explicitly enable coordination; those settings are dormant when it is disabled. Search serialization allows at most five camps and three reported routes. The four-altar default is not a packet cap: eight/sixteen altars, 48 candidates, beam widths up to 32 and expansion limits up to 20,000 were tested.

## Method and limits

The first pass tuned banking/recovery and a few search choices. The continuation screened independent lower/upper probes for every active field, expanded the best probe for every field to 17 training maps (including losing probes), then tested positive-setting combinations, whole-family combinations, feature flips and leave-one-family-out ablations. Shortlists used 18 separate validation maps. A second full sweep refined the best combined parent, tested legal zero/endpoints and repeated combination/validation before the final common-opponent matrix. Six final targeted profiles checked the strongest validated planner-start boundary and its interactions with competition penalty and retry timing; the best two joined the identical final matrices without changing the earlier frozen receipts. Executable hashes deduplicate finalist aliases. The final selection uses common-opponent wins with zero VM faults; wider and ancestry results break exact ties.

Published maps were reused adaptively. Fixed seeds are deterministic. These results identify the strongest measured configuration in this experiment; they cannot prove a global optimum or future ladder performance. Native scenarios cover configured banking, task expiry and protocol timing, not every possible gameplay situation.

The final published matrix recorded **0 candidate VM faults** and **32 bounded `LP_ERROR` log entries**. Nonfatal action errors remain; truncated logs do not measure exact total action errors. Original gameplay source hashes and all frozen clone source/artifact hashes are checked. Generated gameplay source differs only in `config.h`. Normal/release builds and native scenarios pass; the promoted release WASM exactly matches the selected artifact.

In **27** final published conditions both teams submitted zero gems; their outcomes still follow the engine’s gold/kills tie-break rules. Such wins count toward match performance but do not demonstrate successful banking.

## Evidence and reproduction

- [Selection and complete final matrices](evaluation/2026-11-04/tuning/complete-tuning-selection.json)
- [Champion configuration and hashes](evaluation/2026-11-04/tuning/champion.json)
- [All generations](evaluation/2026-11-04/tuning/generations.json)
- [Per-field coverage](evaluation/2026-11-04/tuning/all-settings-coverage.json)
- [Deduplicated audit](evaluation/2026-11-04/tuning/complete-tuning-audit.json)
- [Reserved-map results](evaluation/2026-11-04/tuning/complete-tuning-legacy-robustness.json)
- [Native checks for combined/refined profiles](evaluation/2026-11-04/tuning/combined-refinement-native.json)
- [Final targeted design](evaluation/2026-11-04/tuning/generation08-targeted-design.json)
- [Final targeted native checks](evaluation/2026-11-04/tuning/generation08-native.json)
- [First-pass history](config_tuning_first_pass.md)

```powershell
uv run --locked cambc build leader_party_tuned --release
& bots/leader_party_tuned/tests/run.ps1
```

Use `tools/tune_leader_party.py` to preserve/build clones and resume match matrices, `tools/tune_all_settings.py` for the frozen two-sweep sequence and `tools/finalize_config_tuning.py` for validation/promotion/auditing. Large builds and replays remain ignored locally. No platform submission changed.
