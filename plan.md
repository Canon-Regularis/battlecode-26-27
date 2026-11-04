# C++ leader-party replacement: implementation plan

Status: implemented and benchmarked on 2026-11-04; release choices and coverage gaps are recorded in [implementation_results.md](docs/strategy/leader_party/implementation_results.md). Implementation language: **C++**, using the installed CAMBC 4.0.0 SDK and workspace build system. Target: `bots/leader_party`.

This plan applies the fixes recommended in the [critical analysis](docs/strategy/leader_party/critical_analysis.md). It deliberately changes several earlier policies, as listed below. During implementation, update the authoritative strategy documents and diagram to match these decisions before adding behavior. Preserve the [retired bot](bots/archive/state-machine-2026-11-04/README.md), its manifest and all unrelated local work.

## 1. Outcome and scope

Build a bot that repeatedly clears camps, captures rewards, spends gold and tributes gems, with recovery from death, danger, blocked paths and missing information. Team coordination must improve that functioning loop rather than become a prerequisite for it.

Retain the existing twelve states and add `EXPLORE`. Retain CAMP/BANK protection contexts, personal-vision restrictions, native movement geometry, engine-confirmed channels, and leadership as the only allocated role. Do not reinstate runners, assigned collectors or assigned escorts. Draft, shopping, combat and ability support must handle every champion body the bot can draft, including both linked bodies if that pick occurs.

Optional remote enemy concentration reporting is removed from this version. Local threat decisions always use current personal observations. Wards remain optional and cannot delay scoring or safety.

### Explicit changes from the previous plan

| Previous policy | Replacement |
| --- | --- |
| Reserved bits prevent implementing lifecycle metadata | Introduce the fully specified versioned 64-bit layout below; retire the old layout. |
| Refreshable rallies with unrepresentable freshness | Immutable, short-lived attempts with full creation round and creator identity. |
| Only `LEAD_TEAM` can run any objective planning | Leadership publishes bounded guidance independently of action state; idle followers have an autonomous fallback. |
| Leadership selection depends on unspecified hidden eligibility | Each candidate checks its own eligibility and claims in a deterministic election window. |
| No leadership expiry | Add a three-round heartbeat lease to recover from a nonexecuting leader. |
| Committed protection cannot retreat | Add explicit danger, deadline and no-progress exits, preserving pending bags. |
| Nearest camp regardless of yield or clear time | Compare a simple cycle-time/value router with the distance baseline. |
| Ranged attacks always take precedence | Travel and escape movement take precedence over discretionary attacks. |
| No complete exploration, small-node or banking-queue behavior | Implement the bounded local policies below. |

These changes supersede the conflicting sections of the earlier plan for this implementation. Keep old decisions documented as history rather than leaving two active specifications.

## 2. C++ structure and boundaries

Use the official C++ starter structure and existing [CMake configuration](cmake/CMakeLists.txt). Generate a fresh bot scaffold with `uv run --locked cambc new leader_party --lang cpp` after checking that the target does not already exist. Do not restore the archive into the active path or modify SDK files to accommodate bot mistakes.

Keep modules small enough to review, with one owner for each decision:

| Files under `bots/leader_party/src/` | Responsibility |
| --- | --- |
| `main.cpp`, `bot.h`, `bot.cpp` | Draft/game dispatch, turn lifecycle, bounded error reporting and clean yield. |
| `config.h`, `model.h` | One configuration, stable IDs, states, task context and progress counters. |
| `observations.h/.cpp` | Snapshot construction, visibility-safe SDK access and explicit unknown values. |
| `protocol.h/.cpp` | Packing, validation, initialization, election and immutable rally lifecycle. |
| `state_machine.h/.cpp` | Ordered transitions and entry/exit effects; sole transition authority. |
| `navigation.h/.cpp` | Free goal masks, native fields, movement/dash validation and congestion recovery. |
| `objectives.h/.cpp` | Camp value/cycle estimates, exploration and altar selection. No hidden state transitions. |
| `combat.h/.cpp` | State-permitted target/action selection and champion-specific ability adapters. |
| `economy.h/.cpp`, `draft.h/.cpp` | Capture/bank bookkeeping, shopping and deterministic legal draft fallback. |
| `telemetry.h/.cpp` | Bounded event/counter output; no per-turn log flood. |

Keep decision models independent of SDK handles where practical so real transition/protocol scenarios can run as native C++ tests. Use stable IDs, not cached live handles or pointers, in persisted tasks. No new third-party runtime dependencies.

Illustrative C++ interfaces, to be adapted to the actual SDK types:

```cpp
enum class RouteStatus { at_goal, step, wait, deferred,
                         no_route_now, static_unreachable, invalid_goals };
struct Decision { State next; TaskEffects effects; ActionIntent action; };
Decision decide(const Snapshot&, const BotMemory&, const Config&);
RouteResult plan_step(const NavigationRequest&, TurnBudget&);
ActionResult execute(const ActionIntent&, TurnContext&);
```

## 3. Information and shared-memory contract

Use one little-endian `std::uint64_t`. Validate widths, roster slots and chunk IDs before mutation. Coupled fields change together, preserving unrelated fields from a fresh read.

| Bits | Width | Meaning |
| --- | ---: | --- |
| 0–5 | 6 | Leader guidance chunk; 63 absent. |
| 6–8 | 3 | Leader roster slot; 7 absent, 6 invalid. |
| 9–11 | 3 | Existing leader message enum. |
| 12–17 | 6 | Rally chunk; 63 absent. |
| 18–19 | 2 | NONE, BANK, ATTACK; 3 invalid. |
| 20–22 | 3 | Rally creator roster slot. |
| 23–33 | 11 | Rally creation round, untruncated. |
| 34–45 | 12 | Six two-bit safety summaries. |
| 46–56 | 11 | Leader heartbeat round, untruncated. |
| 57 | 1 | Initialization complete. |
| 58–60 | 3 | Protocol version, initially 1. |
| 61–63 | 3 | Reserved, preserve as zero in version 1. |

The sum is 64 bits. Round fields cover the documented 2,000-round match without modular wrap. Check the actual round origin against the SDK; reject future timestamps and unsupported round ranges. For extended development matches beyond the field range, disable shared coordination and use the local scoring fallback; never truncate timestamps.

Stable slot 0 initializes once on its first gameplay execution, even if dead. It publishes a complete empty word with version/marker, absent leader/rally, invalid chunks and UNAVAILABLE summaries. Before initialization, other bodies perform safe local gameplay without interpreting or writing strategy fields. Invalid/unknown versions disable coordination with a bounded diagnostic; no destructive reinitialization during play.

### Immutable rally attempts

- Identity is `(creator slot, full creation round)`. Each body may create **at most one attempt per round**, with this guard retained across cancellation, death and state changes.
- ATTACK and BANK both expire at age 12 rounds. No refresh extends or changes an attempt. A BANK carrier can continue its own legal channel after request expiry; direct local protection does not depend on the request remaining live.
- Only the matching creator cancels its attempt. Any body may clear an expired attempt or one whose creator is confirmed dead. Compare the full saved identity against the latest word before clearing.
- BANK may replace ATTACK; a live same-type attempt retains the slot. Replacement must be a newly created identity and obey the per-body creation guard. Clearing is not itself a new attempt.
- An owner may issue another request after expiry only as a new attempt, with a three-round retry delay for unchanged contact/task. Expiry never resets the absolute lifetime of the old attempt.
- A responder never treats a chunk as an exact camp, altar or carrier. Resolve through current vision or a saved exact observation; bounded unsuccessful inspection declines the rally. Multiple same-chunk objectives do not permit guessing.
- Enemy observations are not transmitted in this version. Safety summaries are hints, never proof of current Health, death, support or eligibility.

Full-round identity plus no same-owner same-round reuse resolves same-payload replacement without a small wrapping generation counter. Tests must include cancellation followed by replacement at the same type/chunk and resumption many rounds later.

## 4. Leadership and autonomous progress

Store the stable preference order in draft/static planning data: Heart of Ruin, Ren, Marcella, then descending starting Health and stable slot. Do not query hidden current Health to elect another body.

When no valid leader exists, round modulo roster size selects one preference rank's claim window. That body claims only if self is alive, above 50% Health, outside recovery/escape and able to perform bounded planning. Dead or ineligible candidates skip their window. A healthy candidate therefore gets an opportunity within at most six rounds. No body nominates a hidden ally.

The current leader keeps identity through ordinary task changes and updates its heartbeat each executed turn. Clear identity on self death, Health at/below 50%, or a heartbeat older than three rounds. A resumed former leader must re-read identity before publishing; it cannot overwrite a successor. A healthy current leader is not preempted merely because a more preferred body returns.

Leadership guidance runs as bounded background work before optional actions, regardless of the leader's action state. It cannot cancel a channel, move a protector or consume reserved movement computation. If no useful new route estimate is affordable, publish current observed activity and defer planning.

A free follower uses visible leader work when safe and personally resolved. After two rounds without useful reachable guidance, it selects a local camp or explores autonomously. It periodically rejoins useful leader activity when uncommitted. Existing local tasks survive leadership changes. This is individual objective selection, not allocated nonleader roles.

## 5. Complete state and progress policies

Write complete ordered tables before coding their executor. Apply death/channel truth first, then state-specific safety/termination, then recovery/banking, then rallies/camp work/exploration. Keep all transitions in the state-machine module and corresponding document.

### Camp work and protection

- Check safety before entering protection. Visible champion disadvantage, low Health under a threat, or conservatively estimated lethal incoming basic damage permits disengagement from both capture and protection. Camp attacks contribute damage risk, not enemy champion count.
- Keep the existing 35%/55% recovery hysteresis. Treat next-action damage estimates as conservative heuristics with explicit unknowns, not predictions of all hidden spells.
- If an ally already occupies the cleared reward region, remain outside it and guard only when safe. If vacant, each body rechecks current occupancy immediately before entering. An existing occupant remains the collector; no collector assignment is created. An additional Capture Emblem occupant may join only when it reduces the remaining timer and does not block safety/access.
- Release CAMP protection after 12 rounds without confirmed completion. Release capture work after eight rounds without useful task progress or 30 total rounds on the attempt. Moving between equivalent guard tiles, publishing status and state churn do not reset these clocks.
- Useful progress means reduced route distance to the current exact goal, observed damage to the objective, a verifiable capture-countdown decrease, or confirmed completion. Where the engine does not expose a countdown, do not invent one; use observations plus the absolute deadline.
- Put an abandoned exact objective on a ten-round local retry cooldown. Material new observations may release it early. Saved positive-bag banking survives escape; death clears lost-bag tasks.
- Small gold/gem clusters use the same local clear/capture policy as other groups. Passing does not force the whole party to stop, but a free follower may select one independently. No special runner protocol.

### Exploration

Enter `EXPLORE` when a completed candidate evaluation finds no eligible camp, or guidance/search remains unresolved past its bound. A deferred computation is not “no camp.” Prefer reachable least-recently-observed camp approaches, then unseen legal viewpoints, tied by distance and canonical ID. Stagger equal choices by stable slot.

Exit for death, danger/recovery, banking, a personally resolved useful camp, or a joinable rally, in that order. Reconsider a viewpoint after eight turns or three turns without approach progress, and try another rather than looping forever. Keep occluded/temporarily blocked areas unknown. Exhausted exploration still reobserves reachable camps around their estimated respawn times.

### Banking and protection

Start banking at bag 20, an immediately winning bag, 40 rounds since first acquiring the current positive bag, or when remaining match time approaches estimated altar travel plus channel duration plus five rounds. Inactivity during camp work for eight rounds also prioritizes a positive bag. All thresholds are configurable starting values.

Use the current distance/risk/lock altar scorer with switch hysteresis. An opposing lock is removable with basic attacks, not permanent terrain. Start BANK_GEMS only from a fresh `is_submitting_gems()` observation. Preserve an active channel unless interrupted, complete, or a concrete lethal-threat escape is available and cancellation is legal; damage alone does not interrupt tribute.

Implement turn-taking as a **local courtesy policy**, not an assumed engine restriction. Observe an existing channeling carrier and wait off its approach tiles. Among mutually visible waiting carriers, prefer larger bags, then stable slot. Yield immediately if another channel is observed. A nonchanneling waiter loses local precedence after three stalled rounds; another altar can be selected. Hidden independent arrivals are not covered by a global exclusivity guarantee. Verify actual concurrency with an engine scenario before finalizing the API adapter.

BANK protection follows one exact observed carrier/altar. It can exit for danger, observed completion/abandonment, two failed reacquisition turns, or three rounds without a channel/retry making progress. An active carrier's protection deadline follows its observed/estimated channel duration plus three rounds, rather than imposing a 12-round cap on a legitimately longer tribute. Unrelated score changes never prove this carrier banked.

## 6. Objective value and action ordering

Keep distance-only routing as an A/B baseline. The replacement ranks eligible gem camps by estimated gems per complete scoring-cycle round: approach, remaining clear time, capture, altar approach/lock clearing, tribute. Use SDK reward metadata where available and explicit conservative estimates otherwise; measure and refine clear-time estimates from completed encounters. Compare integer ratios by cross multiplication, with deterministic travel-distance/canonical-ID ties.

Gold-only camps remain eligible when funding the next initial build batch or when no useful gem camp is reachable. Prefer their estimated gold per clear/capture round. Do not present gold as tributed gems. Respect known respawn-at-arrival estimates while keeping hidden current lifecycle state unknown.

Combat and movement order:

1. Preserve active channels and obey death/stun/action legality.
2. In escape, prefer a legal safety-improving dash or move, then a useful defensive heal/shield, then permitted attacks. Re-evaluate between actions.
3. In travel/banking/exploration, take useful safe movement before discretionary ranged attacks. An immediately threatening enemy may require defense; do not chase unrelated targets.
4. In camp work/protection, prioritize immediate threatening champions over the assigned camp. Prefer a legal kill, then effective damage to the lowest-current-Health permitted target; area-hit count breaks equal primary outcomes. Remaining ties use stable target ID and ability slot.
5. Cast priority outside escape is: avert conservatively estimated lethal damage with a legal useful heal/shield, secure a legal kill, satisfy required mobility, then maximize effective damage or a useful attack reset. Each successful cast consumes the single cast allowance.

Implement actual champion ability legality and damage/effect formulas from the C++ SDK/rules; do not classify arbitrary abilities only by slot number. Prefer a visible ally heal that prevents estimated death, then greatest effective missing-Health restoration, tied by slot. A shield uses currently visible incoming threat; net Health loss is only supporting evidence and is invalidated by recovery/purchases. Do not claim to infer exact damage type from a Health delta.

Dash endpoints must be SDK-legal, free, inside state bounds and no riskier than permitted walking endpoints. Travel dashes must reduce task distance; escape dashes must improve the escape safety tuple. Failure of walking alone does not establish that no dash route exists.

Initially disable ATTACK creation. Enable it only after the scoring loop passes: creator must be above 55% Health, have a visible enemy within two tiles at/below half Health, no other visible nearby enemy, and locally verified support at least matching enemies. Permit creation only from LEAD_TEAM, FOLLOW_LEADER or EXPLORE with no pending banking. Responders may leave on their own danger, target loss or expiry. These conservative rules are heuristics, not proof that hidden reinforcements do not exist.

## 7. Navigation, fuel and suspension

Use native `Bitboard`/`DistanceField` geometry. Exclude known occupied camp tiles from approach goals; clear only self from occupancy. Distinguish deferred work, temporary obstruction and proved static disconnection. Refresh after moves/casts/reveals and rebuild only affected dynamic caches.

Keep three native-field calls per own turn, reserving capacity for required movement and one hidden-obstruction retry before admitting discretionary scoring, inspection or ward work. Use conservative geometric danger checks if an optional SENSE query would consume needed movement capacity. Same-snapshot forward fields can score multiple objectives. No full-map field per candidate.

Start with the existing 10,000 critical fuel reserve and native-call admission at 45,000 plus reserve. Measure worst-case cost on 100×100 maps before admitting more calls; raise admission thresholds or reduce work if one call can consume the reserve. Call quotas alone are not a fuel guarantee.

After three blocked movement turns, try a bounded legal side-step into a passing pocket using stable-slot right of way: higher slot yields to lower when a mutually visible conflict is identifiable. A yielding step may temporarily increase goal distance, must remain safe and obey task bounds, and is limited to two turns. If unresolved, abandon/reselect the task under its deadline instead of indefinitely recomputing the same route.

At every execution boundary, compare current round with the snapshot round. Discard stale observations, action intentions, native-query results and pending shared writes. Keep persistent intent/progress separately from turn-local data. Protect read/modify/write sections with a measured bounded fuel admission check and immediately fresh shared read; no expensive SDK work between that read and write. Test forced low-fuel resumption specifically. If the SDK cannot safely resume a critical section, redesign that boundary before enabling coordination.

Publish essential status before optional ward/debug work. Bound action-triggered state changes to four and return dispatch to once per turn. Expected stale/illegal-action errors stop the affected action and refresh facts; unexpected programming errors produce bounded diagnostics and fail verification rather than being silently treated as ordinary obstruction.

## 8. Implementation sequence and checkpoints

- [x] **P1 — Contracts and scaffold.** Verify SDK action/round/channel APIs and altar concurrency; update state tables, protocol, combat, config, routing, exploration and diagram to this plan. Create the fresh C++ scaffold and native test target. Build through the actual workspace CMake/CLI path.
- [x] **P2 — Local scoring loop.** Implement observations, free-goal navigation, camp selection/capture, shopping, banking, death/recovery and exploration. Shared coordination and ATTACK stay disabled. Demonstrate repeated captures and at least two completed tributes in a controlled scenario with sufficient available rewards.
- [x] **P3 — Safety and progress.** Add bounded protection, bag-age banking, useful action ordering, abilities, congestion recovery, exact task outcomes and progress telemetry. Exercise losing fights, stalled tasks, ranged travel and interrupted channels.
- [x] **P4 — Team protocol.** Add initialization, version checks, immutable rally identities, election/heartbeat, background leader guidance and autonomous fallback. Verify identical-payload replacement and late-reader scenarios before enabling BANK assistance.
- [x] **P5 — Optional coordination.** Add bounded chunk inspection, local bank courtesy ordering, guarded ATTACK initiation and optional wards one feature at a time. Each feature must preserve the local loop when its information or fuel is unavailable.
- [x] **P6 — Matched evaluation.** Run the suite below, inspect regressions and adjust documented configuration. Record results in `docs/strategy/leader_party/implementation_results.md`, including limitations. Do not declare success solely because the bot builds or beats the retired implementation.

## 9. Validation and completion criteria

Use native C++ scenario tests for protocol identities/timestamps, state transitions, deadlines, election windows and action-order decisions. These must exercise counterexamples, not just reproduce packing formulas. Use actual CAMBC matches/scenarios for legality, visibility, abilities, channel timing, movement and fuel behavior that mocks cannot establish.

Required cases include occupied monsters/hidden blockers; same-type/chunk replacement after creator cancellation/death; timestamps near round 2,000; unsupported round ranges; hidden low-Health preferred candidates; leader expiry and resumption; collector displacement/enemy claim; multiple same-chunk objectives; simultaneous carrier arrival/lock interruption; ranged move-versus-attack; passing-pocket congestion; exhausted exploration; and forced fuel suspension with a pending mutation.

Build and smoke commands:

```powershell
uv run --locked cambc build leader_party
uv run --locked cambc run leader_party starter-python --map 00ambush --rounds 100
uv run --locked cambc run leader_party starter-python --map 00monolith --release
```

Before implementation benchmarking, inspect the CLI's actual seed/output options and use those supported arguments rather than inventing flags. Select six fixed maps covering open terrain, narrow corridors, occlusion and long altar travel; include the two maps above. Run two recorded seeds with swapped sides for 24 full release matches per comparison. Compare the working P2/P3 loop, final bot and Python starter under identical conditions; compare the two routing policies separately. Broaden the map set when a failure reveals an uncovered geometry.

Track tributed gems per 100 rounds, time to first tribute, completed scoring cycles, lost bags/deaths, earned/spent gold, task/state dwell, unknown/blocked/deferred reasons, action errors and fuel/resume events. Save compact summaries and replay paths; throttle logs so errors remain observable.

Completion requires:

- Repeatable capture-to-tribute cycles, correct channel/death accounting, and no reproducible illegal-action loop or VM crash in the required scenarios.
- Every indefinitely repeatable wait has a bounded recovery outcome; optional coordination failure leaves the local scoring loop available.
- The paired evaluation shows the final coordination layer improves scoring over the local baseline without introducing a systematic map-specific stall. If it regresses, retain the working simpler behavior and fix or disable the responsible optional feature before reporting completion.
- Results distinguish measured performance from untested assumptions; no promise of universal wins or guaranteed survival.
- All active docs/diagram agree with the actual C++ behavior. The archive and unrelated files remain preserved. Commit/push/PR are separate actions, outside this planning task.

## 10. Implementation disposition (2026-11-04)

The user subsequently authorized implementation and incumbent testing. Checkboxes track core module delivery and evaluation with these deviations, not exhaustive verification of every proposed case.

- P1: official C++ scaffold, normal/release builds and native tests delivered. Dedicated simultaneous-channel concurrency remains unverified; courtesy is a local heuristic.
- P2/P3: repeated engine-confirmed scoring cycles, recovery, shopping, action ordering and bounded tasks delivered. Task and estimated-clear limits increased to 90 because the initial thresholds excluded every ambush gem camp. The eight-round no-progress and 12-round camp-protection limits remain.
- P4: packing, election, heartbeat, immutable BANK publishing and visible leader guidance implemented. Guidance slightly reduced scoring in paired tests, so release coordination is disabled. No proof of every pending-write forced-suspension interleaving is claimed.
- P5: direct visible carrier protection, courtesy and optional wards delivered. Remote chunk inspection, ATTACK initiation and BANK-over-ATTACK replacement are disabled/unimplemented. The release does not depend on them.
- P6: incumbent screen, local/value/distance comparisons, 24 final incumbent matches, starter comparison and additional geometry tests recorded. The CLI has no seed override: two repetitions use the same recorded map seed, with swapped sides. They establish reproducibility, not independent seed coverage.
- Distance routing is retained after 11/12 exploratory incumbent wins versus 10/12 for value routing. Shared guidance is disabled after a small scoring regression against the autonomous baseline. The final combined configuration is tested separately.
- Camp observation is staggered before costly full-map bitboard operations, fixing the reproduced lanes/expanse fuel starvation. Spawn defense requires actual estimated incoming basic threat rather than nearby vision alone, fixing the spiral wait.
- Generic unseen viewpoints, cross-hole dash search, learned clear-time estimates, full AoE center search and exhaustive fallback/linked-body matches remain coverage/feature gaps. Active docs describe the implemented behavior.
- A 50,000-fuel stress run had no unexpected errors but admitted no 55,000-fuel native queries and made no movement progress. The release targets the normal engine budget; smaller custom budgets are an explicit limitation.

The archive and unrelated local files remain preserved. No commit, push or PR is part of this implementation request.
