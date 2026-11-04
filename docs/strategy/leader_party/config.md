# Release configuration

Source of configurable switches: `bots/leader_party/src/config.h`. These are measured starting policies, not global optima.

| Setting | Value |
| --- | --- |
| Bag threshold / age | 20 gems / 40 rounds |
| Task no-progress / absolute lifetime | 8 / 90 rounds |
| Maximum estimated solo clear | 90 basic-damage equivalents |
| Camp protection / retry | 12 / 10 rounds |
| Experimental rally lifetime / leadership lease | 12 / 3 rounds |
| Critical fuel reserve / native field admission | 10,000 / 55,000 |
| Maximum native fields per own dispatch | 3 |
| Shared coordination / ATTACK initiation | off / off |
| Distance routing / optional wards | on / on |

Other implementation constants: recovery 35%/55%; leadership eligibility >50%; equipment recall >=300 gold with empty bag and no visible enemy; five shards per purchase phase; at most 40 purchases per call; banking courtesy wait three rounds; blocked altar retry three rounds; exploration viewpoint eight rounds; carrier reacquisition two rounds. These remain explicit constants in the decision/execution modules and are not dynamically tunable.

Noncommitted camp lifecycle observations are staggered over eight rounds before full-map bitboard operations. The committed camp is refreshed after relevant actions. Optional work is skipped when fuel is insufficient. Very small custom fuel quanta can prevent the 55,000 admission threshold from ever being reached; the release targets the engine default budget.
