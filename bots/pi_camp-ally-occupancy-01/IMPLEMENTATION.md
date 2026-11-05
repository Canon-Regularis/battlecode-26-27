# cao01: task-scoped ally occupancy

Review candidate only. Base commit: `87144776ee5402991fbc05d2ccd67ffc74e05bd6`; parent source: `bots/pi_dominant-live-progress-01/`. Changes remain uncommitted for the bridge. No games, uploads, submission, promotion or release build were performed.

## Hypothesis and source scope

Retaining the last personally observed ally position during one committed living-camp task should prevent a hidden stationary ally from repeatedly reopening an apparent choke shortcut. When a complete current navigation attempt proves no route with uncertain evidence, forgetting those exact uncertain versions on a later round's normal attempt should release a phantom obstruction.

This implements the supplied occupancy hypothesis. It makes no new health/progress claim: zero visible spawn tiles still skip World::refresh, and the parent's health/progress implementation is unchanged.

Production differences, compared byte-for-byte with the exact base parent's source:

- New `src/ally_occupancy.h`: SDK-independent private cache with owned observation batches, scope keys, exact versioned attempt tokens and conditional deferred deletion.
- `src/observations.h/.cpp`: capture ally identities and tile value positions from the same owning tile/champion_at enumeration used by SDK vision::champions. Keep the existing champion list for existing consumers. Complete the batch only across successful round/revision guards; publish staged cache updates only across a second bounded guard pair. Retain current visibility values for clear-tile evidence. The small adapter queries only roster handles' is_alive for hidden retained entries.
- `src/navigation.h/.cpp`: optional uncertain-mask input and overlay-empty result flag. Canonical current blockers are filtered independently before unioning uncertainty. Existing field search, distance ordering, walking/dash selection, checked moves, yield behavior, retry and admission limits remain in place. A stale/incomplete occupancy observation or stale field returns deferred. Defaults preserve ordinary callers.
- `src/bot.cpp`: initialize the private roster adapter, synchronize life/task/task_started scope and clear on abandonment or nonliving/absent task. Feed only living-camp travel an overlay and return exact attempt feedback. Observation publication also runs after movement, so a fresher same-round sighting supersedes pending deletion. Reward navigation uses the existing ordinary call behavior.

No edits to objectives, combat, economy, draft, protocol, tuning constants, other bots, SDK, repository tools or settings. `Config::coordination=false`, inherited eight-byte wire format, stall8/task90 and action/health-based progress rules remain unchanged. `SOURCE_SHA256SUMS` now describes this candidate's source, including the new header.

Reviewed strategy overview, state machine, navigation and camp-selection documents, historical meta strategy, SDK compatibility notes, game rules and actual C++ champion/vision/distance-field declarations.

## Policy and bounds

One entry per actual allied roster identity excluding self; unknown and enemy identities cannot insert records. Each entry holds at most one positive tile, original observation round/revision, private version, alive-probe round and one pending exact-version deletion. Scope changes clear applicability internally. There is no age TTL, enemy history, shared position protocol, camp-member ledger or persistent map history. The existing 90-round task limit bounds applicability.

A complete current positive replaces the old identity position; old-tile visibility without that identity removes it. Current occupants remain in Snapshot::blocked independently. A positive observation provides that round's alive evidence. Otherwise a retained hidden entry gets at most one new is_alive query per round, including an unknown/error response. Probe-attempt accounting survives rejected publication; stale death/position evidence does not. Expected api_not_in_vision/api_not_found probes remain unknown; unrelated errors propagate. No hidden position or live-info query is added.

Storage is O(roster), apart from the current observation's owned positives and current visible-tile values. The latter are snapshot data, not accumulated map history. Batch collection uses two round/revision boundaries, not a guard per getter. Cache preparation uses another two boundaries. No field is added by the module. Existing maximum three fields and admission/reserve constants remain unchanged. A failed complete field uses one normal field; overlay-only elimination of nonempty fresh goals needs zero. Relaxation never triggers an immediate retry or a second field.

Feedback schedules only uncertain records matching the attempt's scope, observation and full record token. Current visible records cannot be scheduled. Same-round calls retain scheduled records. Later-round normal preparation applies deletion only after incorporating new positives, so a fresh revision wins. Observation-only publication never applies pending deletion. Reusing a hidden record never renews its observation timestamp. Deferred/stale results, wait, at_goal and movement do not schedule deletion; already-empty goals provide no inference. Failure, retaining and forgetting never directly alter progress/distance/task timestamps.

## Checks actually run on Pi

Host: aarch64, GCC 13.3.0. All commands below passed from repository root:

```sh
python3 bots/pi_camp-ally-occupancy-01/tests/run_occupancy.py
python3 bots/pi_camp-ally-occupancy-01/tests/run_native.py
g++ -std=c++20 -Wno-changes-meaning -include cmath -fsyntax-only -I sdk/cpp bots/pi_camp-ally-occupancy-01/src/*.cpp
```

The new runner compiles the actual module with `-std=c++20 -O2 -Wall -Wextra -Werror`. It extracts unmodified production prepare_camp_occupancy, observe, navigation declarations/TurnBudget, move_to and camp_action bodies; explicit host adapters supply SDK values, a small walking BFS field and action results. Memory, Config and task_expired are actual production code. No copied cache estimator or parent occupancy receipt stands in for the candidate. Generated headers and binaries stay in temporary directories.

Verified module identity filtering, invalid/out-of-bounds/future/incomplete batches, retained hidden timestamps, moved/clear/dead evidence, all key transitions, exact uncertain-only feedback, same-round retention, next-round deletion, fresh same-round revision protection, and stale/incomplete/other feedback rejection. Actual call-count assertions: zero alive probes for positive visible entries; one for the first hidden use, zero additional probes on same-round reuse; one on the following hidden round; one unknown-result probe across same-round revisions; one stale-post-probe attempt without publishing its death or repeating that round's query.

Production integration checks cover rollover before/during/after ally collection, field round/revision rollover, no stale move, expected query failures versus propagated unrelated errors, actual camp_action no-route/deferred/empty-goal/overlay-empty/at_goal/wait paths, and unchanged progress. The phantom corridor consumes one field on its failed invocation, retains uncertainty on another same-round invocation, and walks on the next round after relaxation. Movement reducing distance credits progress; failed/forget-only paths do not. Actual task_expired enforces stall8 and task90. Necessary backtracking is permitted. Ordinary navigation ignores private uncertainty, reward/respawn/absent-task transitions clear applicability, and current blockers remain blocked.

The inherited runner additionally passed 84 dominant metadata/selection checks, protocol/state scenarios, 19 production combat/reference scenarios and committed refresh/progress regressions. Those health regressions are inherited compatibility checks, not occupancy or release evidence. Early new-test runs exposed host-adapter compilation mistakes; those were corrected before the final passing run.

## Native PC geometry adapter

Compile without SDK or replay assets:

```sh
g++ -std=c++20 -O2 -Wall -Wextra -Werror \
  -I bots/pi_camp-ally-occupancy-01/src \
  bots/pi_camp-ally-occupancy-01/tests/occupancy_adapter.cpp \
  -o /tmp/cao01-occupancy-adapter
/tmp/cao01-occupancy-adapter < observations.txt
```

Whitespace-delimited commands, one process per champion:

- `roster SELF COUNT ID...`: initialize actual allied roster, including self.
- `key LIFE TASK TASK_STARTED`: synchronize committed living-camp scope; use TASK=-1 for death, absent task, reward or respawn.
- `batch ROUND REVISION COMPLETE WIDTH HEIGHT NORMAL NP [ID X Y]... NV [X Y]... NA [ID ALIVE]...`: complete owned current positives, current visible tiles and independent hidden-alive answers. ALIVE is 1/0/-1 (alive/dead/unknown). NORMAL=0 publishes an observation; NORMAL=1 prepares a normal navigation attempt and permits due deletion. COMPLETE=0 cannot publish. The adapter treats the supplied round/revision as the host's current epoch.
- `feedback OUTCOME ROUND REVISION COMPLETE`: feed back the last emitted attempt token. OUTCOME=0 for every nonfailure, 1 for complete no_route_now, 2 for goals eliminated solely by uncertainty. Stale/incomplete feedback is rejected by the same module.

Every batch emits `mask CURRENT ALIVE_QUERY_COUNT N [ID X Y OBS_ROUND OBS_REV RECORD_VERSION]...`, listing uncertain records whose tiles must be unioned with the independent current blocker mask. The runner compiles this adapter and smoke-tests positive -> hidden -> failed feedback -> next-round empty mask. PC geometry must supply official visibility and its existing movement/goal controls; this adapter contains no invented replay coordinates or visibility reconstruction.

## Remaining review gates

Native tests use explicit host adapters, not the official VM or shadowcasting. Full WASM linking, engine fuel/runtime costs, official-visibility continuation geometry, frozen A/B walk bounds, actual first divergence, replay cycle audit, champion damage/capture/bank timings, VM/SDK-error receipts and the four Vault games were not run. No native result establishes those gates or a simulated bot win. The PC reviewer and campaign owner retain geometry/replay controls and the frozen release protocol. Do not queue or expand this review draft on native passes alone.
