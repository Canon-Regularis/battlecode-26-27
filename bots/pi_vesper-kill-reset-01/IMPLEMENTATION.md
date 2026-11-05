# vkr01: same-call Vesper camp-kill continuation

Parent: `2f0f534e8311ee597e516b11c2afca1bbf608060` (`leader_party_tuned`). Candidate: `bots/pi_vesper-kill-reset-01/`. Implemented on the aarch64 Pi, 5 November 2026. Changes remain uncommitted. No matches, uploads, submissions, ranked changes, or repository-wide changes were performed.

## Hypothesis and scope

A Vesper ranged basic can kill the selected camp while spending both attack and movement. The original `fight` returns on that death, and the original `camp_action` then returns on `!me.can_move()`. A bounded reset and sibling basic inside that same `fight` can move work earlier. This does **not** establish an extra reset cycle, improved cumulative clearing, faster captures, better banking, survival, or win rate: the original next-turn reset could make cumulative work converge.

Read the current leader-party strategy overview, combat and state-machine documents, CAMBC game rules/API additions, and actual C++ SDK lifecycle, visibility, action, restriction, readiness and geometry implementations. In particular, SDK tests and documentation establish that dead camps lose their live info/visibility record, while `camp::state()` can positively establish death if the last occupied tile is in vision. Invisibility alone is insufficient.

## Production change

Only `src/combat.cpp` changes production behavior:

- Save the position from the existing first-basic position query, without an additional position getter. Preserve the original first-basic action and original surviving-target basic/reset/basic scheduler.
- At the original dead/invisible-target return, invoke a local helper only after this invocation actually attacked its selected ordinary task camp. Enemy and travel dispatches cannot enter it.
- Require Vesper, a valid cached task index, spent attack and unavailable movement, remaining cast allowance, living/nonchanneling actor, no attack/cast restriction, and a ready self-targeting attack reset. Reuse `ready`, including metadata and movement compatibility. Dash cooldown is irrelevant.
- Guard the saved tile with `vision::in_vision`, then require positive `killed.is_dead()` evidence. Expected camp query visibility/entity loss declines the continuation. Self, metadata, unrelated SDK errors and action errors propagate.
- Capture basic geometry once. Make one pass through `w.camps[task].group.camps()`, selecting one visible living positive-HP member in that geometry by lowest HP with strict `<` preserving membership tie order. Read candidate HP once. Hold both the selected camp wrapper and owning ability container through execution. No group loader, all-map search, persistent field, damage/CC scoring, dash, recursion or second retarget is added.
- Validate again before the single reset attempt. After success, recheck round/fuel, actor life/channel/restrictions, chosen target visibility/life/range, and actual `me.can_attack()` before one void-returning SDK basic. Query guards check the original epoch and strict `fuel_remaining() > Config::reserve` (5000) before/after validation, and actions have a final current check. Reset failure, post-reset invalidation or disappearance does not retry. `acted` remains true from the original basic.
- Bound the existing initial task-camp selection by `w.camps.size()` to reject an invalid positive task index in `fight` without accessing outside the vector. Normal valid-task behavior is unchanged. The unchanged caller retains its normal task ownership invariant; its invalid-task test uses the normal `-1` sentinel.

`Bot::camp_action`, navigation and all other production files are byte-identical to the cloned baseline. The caller still terminates at its original `!can_move` return. Added computation can consume fuel and change later trajectories. No new admission threshold or release logging exists.

## Native diagnostic and substitutions

`tests/run_kill_reset.py` includes the actual returned `src/combat.cpp` through `tests/kill_reset_native.cpp`, including the complete original `defend_cast`, actual `fight`, and new helper. It extracts the **complete** `Bot::camp_action` body directly from returned `src/bot.cpp`, asserts byte equality with the parent's original caller, and compiles that body as well. There are no copied combat predicates or alternate release branches. Caller body SHA256 (without trailing newline):

`ce09301aca62960dca553586d6f961aabf87ead3fa7f8883afd4ec96d9c96d05`

The diagnostic uses the real unchanged `sdk/cpp/cambc.h` and `imports.h`, with explicit native definitions for host imports. A small public native `Bot` shell exposes the actual `World`/`Memory` for fixture setup and substitutes unrelated caller dependencies. Observation is a fixed snapshot; navigation and world refresh count calls; danger returns false; abandonment clears the task. SDK masks use scripted 64x64 host storage with Chebyshev drawing. Static settings/design/map initialization uses minimal dummy data. Unselected damage/heal imports abort. No group-loader imports are provided, so accidentally introducing one would fail to link.

Combat is scripted: ranged basics reduce HP by fixture Strength and consume attack/movement; reset success consumes cast, sets cooldown 8, restores attack unless a failure control disables it, and **does not restore movement**. Basic remains SDK `void`, with errors propagated. Vendetta uses range 1, preserves movement and scripts cooldown refresh on kill. These are controlled substitutions, not an engine combat or movement counterfactual. Fuel is a scripted integer with injected threshold transitions, **not measured engine fuel**. Host queries can inject epoch changes, visibility loss or errors. Hidden live lifecycle queries throw; SDK hidden live-record getters return visibility errors rather than private data.

Both appendix fixtures use constructed pre-kill HP 120, not a measured pre-hit value. Actor position, HP/max HP, Strength, membership order, listed sibling HP/positions, reset cooldown 0, dash cooldown 5, no visible enemy, and normal initial allowances follow the appendix. Unlisted same-group members are modeled unavailable, not claimed hidden in the replay. Group 14's visible 40/42 are present as lower-HP cross-group controls. Fixture 1013 selects 54; fixture 1044 selects 34. No future original replay actions are assumed invariant.

Coverage includes:

- Public complete caller: `basic64 -> reset -> basic54` and `basic90 -> reset -> basic34`, then zero navigation, zero refresh, and only the caller/first-fight observation calls. Cross-group camps are untouched; equal-HP ties choose earlier cached member 48.
- Surviving initial target retains `basic64 -> reset -> basic64`; absent/dead/hidden/out-of-range siblings, absent first target/first basic, invalid task, enemy priority and travel decline unsupported work.
- Chosen sibling disappearing after selection or reset; post-reset target death/range loss; killed camp tile losing vision and hidden surviving first target. Positive lifecycle death is required. Expected camp query failures decline, while unrelated lifecycle/self/metadata/action errors propagate.
- Cooling reset, unavailable cast, channel, death, attack/cast restrictions, already restored attack, available movement, another champion, missing reset metadata, wrong target mask, and movement-exclusive reset controls. Restrictions are also injected after the original first basic and after reset.
- Dash cooldown 5 and 0 produce identical continuation without dash; available movement with cooling dash declines. Vendetta melee kill/refresh stays outside scope and proceeds through the original movement path.
- Reset returning false, and successful reset that does not restore attack, each retain the acted first basic and caller's terminal path without a second basic.
- Systematic round rollover and fuel-to-5000 injection at every traced host validation point in the bounded successful path, including candidate scanning, target validation, reset and final attack checks. No further action occurs after invalidation; successful reset plus rollover yields no stale basic or retry. Fuel 5001 admits the continuation; 5000 declines.
- One captured geometry; bounded sibling live-record/lifecycle query counts; one additional same-group pass including unavailable members; at most one reset and extra basic. No hidden lifecycle queries or cross-group reads occur.

## Commands and results

Run from repository root:

```sh
python3 bots/pi_vesper-kill-reset-01/tests/run_kill_reset.py
```

The runner prints the exact absolute native diagnostic compiler command and hashes. Native command, expressed relative to repository root:

```sh
g++ -std=c++20 -O2 -fpermissive -Wall -Wextra -Wno-misleading-indentation -include cmath -ffunction-sections -fdata-sections -I sdk/cpp -I bots/pi_vesper-kill-reset-01/src bots/pi_vesper-kill-reset-01/tests/kill_reset_native.cpp -Wl,--gc-sections -o bots/pi_vesper-kill-reset-01/tests/.kill-reset-build/kill_reset_native
bots/pi_vesper-kill-reset-01/tests/.kill-reset-build/kill_reset_native
```

Result: **143 scenarios, 1050 assertions passed**. The same runner compiles all 11 returned production translation units to native objects against the actual SDK, using the same compiler options, replacing the diagnostic source/link arguments with `-c <src/file.cpp> -o <candidate>/tests/.kill-reset-build/<file>.o`.

Compiler: Ubuntu g++ 13.3.0 on aarch64. GCC requires `-fpermissive` for pre-existing SDK `team team()` declarations. Native object checks also use `-include cmath` because the unchanged baseline `objectives.cpp` uses `std::ceil` without including `<cmath>`. Neither SDK nor unrelated production code was edited to accommodate these host compiler differences. Initial strict native attempts exposed these two existing portability issues; the final focused commands explicitly accommodate them.

Existing state/protocol smoke check:

```sh
g++ -std=c++20 -O2 -Wall -Wextra -I bots/pi_vesper-kill-reset-01/src bots/pi_vesper-kill-reset-01/tests/decisions.cpp bots/pi_vesper-kill-reset-01/src/state_machine.cpp -o bots/pi_vesper-kill-reset-01/tests/.kill-reset-build/decisions
bots/pi_vesper-kill-reset-01/tests/.kill-reset-build/decisions
```

Result: `PASS protocol and state scenarios`.

Additional wrapper-lifetime/error checking compiled and ran the same actual-code diagnostic:

```sh
g++ -std=c++20 -O1 -g -fpermissive -include cmath -fsanitize=address,undefined -fno-omit-frame-pointer -ffunction-sections -fdata-sections -I sdk/cpp -I bots/pi_vesper-kill-reset-01/src bots/pi_vesper-kill-reset-01/tests/kill_reset_native.cpp -Wl,--gc-sections -o bots/pi_vesper-kill-reset-01/tests/.kill-reset-build/kill_reset_sanitized
ASAN_OPTIONS=detect_leaks=0 bots/pi_vesper-kill-reset-01/tests/.kill-reset-build/kill_reset_sanitized
```

Result: **143 scenarios, 1050 assertions passed**, no AddressSanitizer/UBSan findings. The initial run with default leak detection exited with `LeakSanitizer does not work under ptrace`; leak detection remains unverified in this environment. The successful rerun explicitly disabled only leak detection.

Scope verification compared every other cloned file with `leader_party_tuned`: only `src/combat.cpp` and the candidate `.gitignore` differ among existing files. Added files are this report and the two native diagnostic files. Changed/new text has no trailing whitespace; tracked repository diff is empty because the bridge-created candidate is initially untracked.

Generated binaries, objects, extracted body and local logs stay in the candidate's ignored `tests/.kill-reset-build/` directory. Existing test files are unchanged.

## Source hashes

SHA256:

| File | Hash |
| --- | --- |
| `src/combat.cpp` | `6fc26c0a6a4049e723c39f360250a0368e387db087fcd3109e84c88b4fc01603` |
| `src/bot.cpp` (unchanged) | `a2bf0118854c076a7f70d4b8b8bab8f860f3c6ff1899fd738bb5f7bdf99a0737` |
| `tests/kill_reset_native.cpp` | `fac2a0452104561e2935419be29b10fd4101c621863e4c4d8bd3fc136c286c7d` |
| `tests/run_kill_reset.py` | `c19d3b8bfa7c8645d54a35753ef126dd5685e78004ec9e7c6e4a4a1370a0d2a4` |
| Actual repository `sdk/cpp/cambc.h` (unchanged) | `5d175d6af2ccdb12c693db1dbfceefb0c096c7d482efe4e8683de7ea2d4516bf` |
| Actual repository `sdk/cpp/imports.h` (unchanged) | `5ed1833b9059ee59aed3ab69cafc7d682642d9937f3334331d18a69e37c2a64c` |

## Remaining evidence and gaps

No CAMBC/WASI compiler/CLI was available on this Pi. Actual production bodies compile and execute natively against the repository's actual SDK with a host shim, and all production files compile to native objects; a full production WASM build/link remains for the PC. No installed external SDK/toolchain build, engine match, replay exposure or measured engine-fuel result is claimed.

The PC must run the frozen 80-game panel and establish the release mechanism using the supplied deterministic condition/round/actor/input ordering. The replay source/WASM/ZIP hashes and observed original 1013/1044 paths in the job were fixture provenance supplied by the job, not independently downloaded/revalidated here. Exact actor-local frame checks, task/source inference, immediate/subsequent basic/reset work and convergence, collection/clear/capture timing, banking, gem loss, deaths, spending, fuel suspensions and duration remain unmeasured.

Do not expand on native success or wins alone. The frozen screen still requires zero VM faults, direct >=9/16, common >=35/64, common banking >=44512, common gem loss <=2352, and deaths <=548, plus diagnosis of newly introduced repeatable caught SDK errors. Inspect Swirl/C02 A/B first for mechanism exposure, then the remaining conditions only if needed; earlier trajectory divergence need not reproduce baseline 1013/1044. Promotion and broader confirmation remain separate frozen PC work. No online/ranked action is authorized by this implementation.
