# Retired state-machine implementation

Archived on 4 November 2026 at the user's request after poor implementation and local performance. This is a preserved experiment, not the active starter or an implementation of the current leader-party specification.

## Contents and preservation

- [starter-cpp/src](starter-cpp/src): the complete former `bots/starter-cpp/src` tree, unchanged.
- [manifest.json](manifest.json): original paths, sizes, SHA-256 hashes, branch and HEAD at archival. All **56 files / 14,765,900 bytes** in the original directory were moved and verified, including hidden files and generated build artifacts.
- [cambc.toml.snapshot](cambc.toml.snapshot): workspace configuration at archival, using CAMBC SDK 4.0.0.
- [match-evidence.json](match-evidence.json): compact extraction from the existing local match summary; no match was rerun for this archive.

The source was untracked working-tree work on `state_machine`, with HEAD `18c9c002b477958b70f12b79c167df45606fffb5`. Checking out that commit alone will not reproduce this bot. The manifest records the actual preserved bytes. Existing ignore rules still exclude generated `.cambc/` files and `compile_commands.json` from Git; they remain on disk. Generated build commands can contain the old absolute location and should be regenerated before rebuilding.

Only this folder contained the custom state-machine source. `starter-python` remains active. Other bot folders contain existing compiled artifacts and were left untouched; their behavior was not inferred from their names.

## Why it was retired

One prior 2,000-round release match on `00monolith` produced:

| Metric | Custom C++ state machine | Python starter |
| --- | ---: | ---: |
| Tributed gems | 0 | 763 |
| Lifetime gold earned | 40 | 9,330 |
| Gold spent | 0 | 8,040 |
| Champion kills | 0 | 0 |
| Deaths | 0 | 45 |
| Reported VM faults | 0 | 0 |

The local replay is `replays/starter-cpp-vs-starter-python-1793749116896.repl26a`; the original summary is `.cambc/audit-release-summary.json`. These are ignored local artifacts, so the compact evidence above is retained here. Package/SDK version 4.0.0 and the replay's engine version string `2.0.0` are separate version identifiers.

Captured C++ output contains four `run_state.capture_point` errors reporting `Known occupied destination`. Logging was capped, so four is not a complete error count. No VM faults does not establish correct behavior: caught errors and a nonproductive state loop can continue for an entire match.

`move_to_goals` in [bot.cpp](starter-cpp/src/bot.cpp) explicitly permits camp-occupied goal tiles and clears goals from its blocked mask. That conflicts with the revised plan's requirement to approach free legal tiles. This is a concrete defect consistent with the logged error, but the complete cause of the scoring failure has not been isolated.

## Relationship to the current plan

[protocol.h](starter-cpp/src/protocol.h) uses report stamps, eligibility offers, runner assignments, a rally owner and an initialization bit. The current plan restores safety summaries and reserves bits 41–63, forbids nonleader role allocations, and retains leadership through state changes. The archived code also releases leadership during camp selection. It must not be treated as the current specification's reference implementation.

The [critical analysis](../../../docs/strategy/leader_party/critical_analysis.md) evaluates the revised plan separately. One map and opponent establish a serious regression signal, not a tournament ranking or proof that state machines themselves are unsuitable.

To revisit the experiment, copy the preserved source into a separately named active bot directory and regenerate its build files with a compatible SDK. Preserve this archive unchanged as the comparison point.
