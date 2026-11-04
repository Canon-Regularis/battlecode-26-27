# Release configuration

The preferred bot is `leader_party_tuned`, matching frozen **`g07_search`**. It combines the selected settings in one C++ bot using Subhan’s camp-loop planner. Original bots and every tuning generation remain intact.

| Compile-time field | Value |
| --- | ---: |
| `bank_bag` | `35` |
| `bag_age` | `70` |
| `stall` | `8` |
| `task_limit` | `90` |
| `max_clear` | `90` |
| `protection_limit` | `12` |
| `retry` | `10` |
| `wards` | `True` |
| `value_routing` | `False` |
| `recovery_low` | `0.35` |
| `recovery_high` | `0.55` |
| `recall_gold` | `300` |
| `competition_cost` | `4` |
| `loop_candidates` | `24` |
| `loop_altars` | `4` |
| `loop_beam` | `8` |
| `loop_length` | `5` |
| `loop_expansions` | `768` |
| `loop_reports` | `3` |
| `loop_gold` | `0.02` |
| `loop_opening` | `0.15` |
| `loop_risk` | `0.2` |
| `loop_service` | `7` |
| `loop_phase` | `3` |
| `rally_life` | `12` |
| `lease` | `3` |
| `reserve` | `5000` |
| `field_admission` | `30000` |
| `max_fields` | `3` |
| `coordination` | `False` |
| `attacks` | `False` |

Settings are compiled into the bot. The unused `attacks` field has no callers. Protocol lifetimes matter only with coordination enabled. Movement still uses the existing native distance fields; Subhan’s planner selects camp loops. See the [full evaluation](config_tuning_all_stats.md) for measured ranges and limitations.
