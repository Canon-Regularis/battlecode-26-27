# C++ replacement: implementation and measured results

Implemented on 2026-11-04 in `bots/leader_party`, on branch `state_machine`, using CAMBC SDK/CLI 4.0.0 (engine summary version 2.0.0). The active bot clears/captures camps, buys equipment, recovers, and banks gems. The retired state-machine bot and all three incumbent binaries remain unchanged. No commit or push was made.

Final result: **22/24 wins against gold_diamond** in the main six-map suite; **5/8** on four additional geometry maps; **12/12** against the official Python starter. All **44 final matches scored positive gems with zero VM faults and zero unexpected LP_ERROR entries**. The six-map incumbent games completed at least two engine-confirmed tributes per game. These results support a stronger tested replacement, not a universally winning bot.

## Selecting the incumbent

The preserved D1, larpbot and gold_diamond WASM artifacts were screened in all three pairings on ambush, monolith and packs, with swapped sides: 18 games total. gold_diamond won 9 of its 12 games, larpbot 5/12 and D1 4/12. gold_diamond is the strongest in that screen; this is not a claim of a full tournament ranking. Source was unavailable for those artifacts, so the harness packaged their original WASM bytes with CLI manifests. Artifact hashes are recorded in [manifest.json](evaluation/2026-11-04/manifest.json).

## Final paired scores

Scores below are replacement-incumbent. Each row was repeated identically twice. The CLI exposes no seed override; repetitions use the same recorded fixed map seed, and are not independent seed samples. Swapping sides supplies twelve distinct map/side conditions.

| Map | Replacement as A | Replacement as B | Wins across two repeats |
| --- | ---: | ---: | ---: |
| 00ambush | 941-544 | 945-673 | 4/4 |
| 00expanse | 817-903 | 1011-738 | 2/4 |
| 00interlock | 1010-330 | 1003-181 | 4/4 |
| 00lanes | 1014-862 | 1001-784 | 4/4 |
| 00monolith | 1116-295 | 1018-255 | 4/4 |
| 00packs | 1002-376 | 1002-270 | 4/4 |

Additional geometry checks (one fixed seed, both sides):

| Map | Replacement as A | Replacement as B |
| --- | ---: | ---: |
| 00great-wall | 1011-314 | 408-142 |
| 00reverse-spiral | 14-166 | 199-272 |
| 01big-world | 936-590 | 765-494 |
| 01corridors | 398-648 | 544-434 |

Main-suite mean scoring rate: 59.77 submitted gems per 100 rounds (mean of per-match rates). First tribute ranged from 69 to 258 rounds; completed tributes ranged from 26 to 79 per game. Deaths, gem losses, earned/spent gold, fuel pauses, seeds, task/state telemetry and replay paths are retained in the JSON evidence.

## Feature comparisons and release decisions

Exploratory matched comparisons used the same six maps and both sides against gold_diamond. Value routing with shared guidance won 10/12 (10,835 submitted gems; mean rate 58.53/100 rounds). Disabling guidance with value routing also won 10/12 (11,157 gems; 59.28/100). Distance routing with guidance won 11/12 (11,476 gems; 58.52/100). These intermediate variants exposed rejected-move/reset errors subsequently fixed; their result files preserve that evidence. They are directional comparisons, not statistically independent estimates.

The release retains distance routing and disables shared guidance, consistent with the plan instruction to retain the simpler functioning policy when coordination regresses. The final combination was tested separately. Direct visible camp/carrier protection and optional wards remain enabled. Versioned shared-memory packing, election/heartbeat and BANK publication code remain present for later experiments. Remote chunk responders and ATTACK creation remain disabled/unimplemented.

## Failures fixed during implementation

- Repeated snapshot copies and expensive camp scans starved movement. Use stable cached snapshots and stagger noncommitted camp work before full-map bitboard intersections. Lanes improved from zero scoring to completed cycles; the final geometry assertions catch a recurrence.
- A dangling pointer into a temporary camp vector corrupted combat targets. Retain an owning selected camp wrapper through execution.
- The 25-turn clear cutoff and 30-turn task cap excluded all ambush gem camps even after shopping. Use 90-turn estimated/absolute caps, while preserving eight-turn no-progress exits.
- Blocked altar routes retained an unusable choice. Apply a bounded retry cooldown and reselect.
- Spells exclusive with movement, attack-reset availability and resumed rounds require explicit checks immediately before casting. Raw SDK readiness alone is insufficient.
- Known occupied moves invalidate observation and retry within the field budget; movement allowance is also checked against active buff restrictions.
- Nearby enemies across spiral walls caused permanent spawn defense. Require actual estimated incoming basic threat for that state. Spiral now scores but remains a strategic weakness.

## Validation and limits

Normal/release builds and native C++ protocol/state scenarios pass. Tests cover same-payload replacement, full timestamp boundaries/future timestamps, protocol version rejection, leader expiry, channel/death priority, danger before protection, recall safety, banking priority and task/bag deadlines. Main and broadened engine matches validate actual scoring, purchases, abilities, movement, death/recovery and repeated tribute events. Benchmark assertions require positive scoring, zero unexpected errors and zero faults. Engine gemSubmission/gemCollection events, rather than vanished camps or unrelated score changes, establish outcome counts.

The final bot still loses expanse as A and both spiral sides, and one corridor side. It is tuned on a limited deterministic map sample. Very low custom fuel is unsupported: a 250-round 50,000-fuel stress run had no unexpected errors but made no movement because native-query admission requires 55,000 remaining fuel. Dedicated simultaneous-channel, every hidden-blocker/congestion arrangement, linked-body/fallback champion combinations, and experimental shared pending-write suspension scenarios are not exhaustively verified. Generic unseen viewpoints, cross-hole dash optimization, learned clear times, full AoE center search and Capture Emblem co-occupant optimization remain feature gaps.

## Reproduce and inspect

```powershell
uv run --locked cambc build leader_party --release
& bots/leader_party/tests/run.ps1
.\.venv\Scripts\python.exe tools/benchmark_leader_party.py pack leader-party-local-build bots/leader_party/.cambc/build-release/bot-injected.wasm
.\.venv\Scripts\python.exe tools/benchmark_leader_party.py pack gold_diamond-local bots/gold_diamond/.cambc/build/bot.wasm --language python
.\.venv\Scripts\python.exe tools/benchmark_leader_party.py run fresh-run .cambc/leader-party-local-build.zip .cambc/gold_diamond-local.zip --repeat 2 --require-scoring
```

The installed pinned executable was used directly because uv cache lock access failed in this environment. Give each run a fresh label; the CLI refuses existing replay outputs. Replays remain under `replays/leader-party/validated-{incumbent,geometry,starter}/`; compact results are tracked below while replay/build outputs stay ignored.

- [Final incumbent results](evaluation/2026-11-04/validated-incumbent-results.json)
- [Additional geometry](evaluation/2026-11-04/validated-geometry-results.json)
- [Python starter](evaluation/2026-11-04/validated-starter-results.json)
- [Incumbent screen](evaluation/2026-11-04/incumbent-results.json)
- [Value/guidance comparison](evaluation/2026-11-04/leader-party-v2b-results.json)
- [Local/value baseline](evaluation/2026-11-04/leader-party-local-results.json)
- [Distance comparison](evaluation/2026-11-04/leader-party-distance-results.json)

The archive manifest reverified all 56 original files. Preserved D1, larpbot and gold_diamond modules match their benchmark packages byte for byte. Pre-implementation strategy documents are preserved in `history/2026-11-04-pre-implementation/`; active references and the diagram describe the shipped behavior.

## Direct comparison with D1

The user identified D1 as the previous best bot. A direct follow-up used the unchanged final replacement artifact and preserved D1 WASM across the same six fixed maps, with both sides: **10/12 wins (83.3%)**, with zero unexpected errors and zero VM faults for either bot. These are twelve distinct map/side conditions, one recorded fixed seed per map, without duplicate repetitions. This result also shows why the small earlier incumbent screen should not be treated as a definitive ranking.

Each score is replacement-D1.

| Map | Replacement as A | Replacement as B |
| --- | ---: | ---: |
| 00ambush | 962-566 | 896-621 |
| 00expanse | 786-1004 | 1011-842 |
| 00interlock | 792-1001 | 1034-284 |
| 00lanes | 1004-818 | 1003-847 |
| 00monolith | 1013-101 | 1016-234 |
| 00packs | 1012-896 | 1005-183 |

Total submitted gems: 11534 for the replacement versus 7397 for D1. Losses were expanse as A and interlock as A. Both binaries were verified byte for byte against their source build/preserved artifact before reporting.

[Direct D1 results and replay paths](evaluation/2026-11-04/validated-d1-results.json). Replay bundles are under `replays/leader-party/validated-d1/`.
