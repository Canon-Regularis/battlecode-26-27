# Critical analysis of the leader-party state-machine plan

Reviewed 4 November 2026 against the current working-tree plan and CAMBC 4.0.0 rules/SDK. **The plan is not ready for faithful implementation.** Its strongest parts specify legal observations and local action boundaries. Its weakest parts demand coordination guarantees without transmitting the facts needed to enforce them, and allow valid states to persist without productive team progress.

The problem is not the use of a finite state machine. It is incomplete information contracts, missing liveness guarantees, and strategic priorities that are insufficiently connected to tributed-gem throughput. Adding more states will not fix those issues.

This is a critique, not a replacement specification. Recommendations below require design decisions; they do not allocate reserved bits, reintroduce runner/collector/escort roles, or silently change the user's confirmed commitment and leadership rules.

## Evidence and its limits

The [archived implementation](../../../bots/archive/state-machine-2026-11-04/README.md) scored **0 tributed gems and 40 earned gold** against the Python starter's **763 gems and 9,330 gold** in one prior 2,000-round release match on `00monolith`. Both had zero reported VM faults; captured C++ output contains four occupied-destination errors, with logging capped. These facts establish severe nonproductivity in that implementation. They do not establish its full root cause or performance across other maps.

Crucially, that implementation used runner assignments, eligibility offers and metadata absent from the revised plan, and released leadership during camp selection. The current plan explicitly changes those behaviors. The old result cannot honestly be presented as a controlled test of this plan. The occupied-camp goal handling is a concrete implementation defect; the current [pathfinding contract](strategies/pathfinding.md) already forbids it.

Primary references for this review are the [state tables](state_machine.md), [communication layout](communciation.md), [configuration](config.md), [combat principles](combat.md), [routing](strategies/route_planning.md), [game rules](../../cambc/GameRules.md), and [C++ API](../../cambc/api/BotAPICpp.md). Source versions matter: these are the unfinished working-tree documents, not just the branch's HEAD.

## 1. Blocker: the shared payload cannot satisfy its lifecycle contract

Communication allocates 41 bits to positions, message types, leader identity, counts and safety summaries. The remaining 23 bits are reserved. There is no allocated creator, attempt generation, timestamp or initialization marker, yet the rules require creator-only refresh, expiry cleanup, independent enemy-report freshness and protection against deleting a replacement.

Consider this legal sequence:

1. A creates `ATTACK(chunk 12)` and remembers it privately.
2. That request ends. B later creates a different `ATTACK(chunk 12)`.
3. A next reads the payload and decides whether to refresh or cancel its old request.

The visible type/chunk pair is identical in both attempts. A's private memory of the first request cannot distinguish B's replacement from its own surviving request. The same ambiguity occurs for two carriers banking at different altars in one chunk. Reading the latest word prevents stale-buffer overwrites, but cannot recover information that was never encoded. This is an ABA identity problem, even with sequential champion turns.

Similarly, a body that first sees `enemy_count=3, chunk=12` cannot determine whether it was reported now or many rounds ago. A private “first seen” clock measures the observer's discovery time, not report age. Unchanged refreshes are also invisible. Reliable initialization is unresolved: zero bytes resemble a real leader 0 and chunk 0, while the proposed empty payload uses different sentinels.

**Required decision:** either approve sufficient record identity/freshness/initialization information, or simplify the guarantees to ones the existing payload can support. Specify writers, replacement ordering, first-read validity, clock wrap, creator death and suspension. Draft memory is read-only during play and cannot hold changing timestamps. Do not transplant the archive's metadata into reserved bits as an undocumented fix.

**Acceptance case:** an old creator must be unable to clear or refresh a same-type, same-chunk replacement; a new observer must classify report freshness from an agreed contract. Until this is possible, dependent rally transitions cannot be implemented correctly.

## 2. Blocker: leadership identity does not guarantee a working planner

Only `LEAD_TEAM` runs the route planner. A healthy leader retains its identity in capture, protection, banking and other states. That is a confirmed policy, but the plan has not supplied its corresponding progress contract.

For example, the leader starts protecting a contested camp. Other bodies finish their own jobs. They cannot choose another ordinary camp through F2 without visible leader camp activity, and cannot run the planner themselves. If the contest persists, the leader can remain valid and healthy while the team's next-objective pipeline stops. This is conditional starvation, not proof that every capture stalls: ordinary successful captures release quickly.

Election has a related ambiguity. Preference order is deterministic, but the information needed to decide whether a hidden preferred body can actually lead is not fully specified. Safety summaries contain neither exact Health nor leadership eligibility. If a low-Health preferred body clears the identity, a selection rule based only on alive/preference can repeatedly choose it again. F4 also follows banking, observed protection and rally entry, so even a selected body need not reach `LEAD_TEAM` immediately.

**Required decision:** define who may claim leadership, what locally or globally verifiable facts qualify it, and how the rest of the team makes progress while the identity holder cannot plan. Possible proposals include planning as a bounded responsibility independent of action state, or an explicit fallback for followers. Both need agreement; neither follows automatically from the current tables. Do not quietly introduce leases or forced leadership loss.

**Acceptance cases:** hidden preferred body below the leadership threshold; successor already capturing; healthy leader in a prolonged contest; no eligible planner. Each must have a deterministic, productive outcome or an explicit bounded wait.

## 3. High risk: commitment can turn a small reward into a team wipe

C3 enters committed protection before C4 checks Danger. A low-Health body stepping onto a cleared capture tile therefore becomes committed even when fresh observations show a losing fight. Protectors cannot voluntarily retreat; ATTACK responders likewise depend on the creator's cancellation or expiry even if their own view reveals danger first.

This is a strategic choice, not a missing global escape rule. Its cost is nevertheless substantial. The rules impose a 60-owner-turn respawn wait, transfer carried gems to a champion killer, and destroy them on a camp death. Sacrificing several bodies for a small camp can lose both current bags and many rounds of future farming. Numerical equality is particularly weak evidence of safety: items, current Health, range, cooldowns and camp damage matter. Camps are correctly excluded from champion counts, but cannot be ignored when estimating whether a fight is survivable.

Concrete counterexample: a nearly dead carrier with a valuable bag reaches a reward region occupied by an ally. C3 commits it before C4. Two healthy enemies approach. “Finish the objective” may now protect a much smaller reward than the bag and future income put at risk. An indefinitely contested camp also has no absolute protection deadline comparable to ATTACK's cap.

**Recommendation:** review commitment admission and release against bag value, remaining capture/channel time and credible survival. If fight-to-completion remains mandatory, explicitly accept and measure the resulting sacrifice rate. A protector's UNSAFE publication warns others; it does not rescue the protector or end the contest.

## 4. High risk: objective selection optimizes travel, not scoring

The [temporary router](strategies/route_planning.md) deliberately chooses travel distance without reward, difficulty or clear time. This is a confirmed baseline, but it can select a nearby expensive monster group over a slightly farther easy gem source. Once committed, dynamic reselection no longer corrects that choice. Grouping the party may improve clear speed, but can also spend several bodies' turns protecting a countdown that additional ordinary occupants do not accelerate.

The actual objective is tributed gems: carried gems do not score. A useful comparison is expected successfully banked gems divided by the full travel, fight, capture, altar approach, lock-clear, channel and recovery cycle, including the team turns consumed. This need not become an elaborate optimizer; it should at least be measured before “nearest camp” becomes the assumed successful strategy.

Reward splitting interacts with the per-body `BANK_GEM_THRESHOLD=20`. For illustration, if a reward of 20 gems is split evenly across five occupants, each receives four. One capture then produces no ordinary banking trigger; repeated captures, travel and risk are needed before any bag reaches 20. One collector would reach the threshold immediately. The current guard rule helps by keeping guards outside reward tiles, but does not fully define how simultaneous arrivals avoid multiple occupants. This observation does not justify silently appointing a collector role.

Conversely, very frequent banking wastes altar travel, while very large bags create long channels and greater death exposure. The plan has not evaluated that tradeoff or the requested turn-taking queue. A single shared BANK request can also advertise only one attempt; simultaneous carriers still need defined local behavior even when their own banking remains legal without a rally.

**Recommendation:** retain the replaceable router interface, compare the distance baseline against a simple cycle-time/value alternative, and measure capture-to-bank delay and occupancy splitting. Resolve queue admission and interrupted-attempt precedence after checking actual engine concurrency. Do not mistake an unimplemented queue for an engine prohibition on simultaneous banking.

## 5. Blocker: combat principles do not yet define one legal action policy

“Lowest Health,” “strongest attack,” and “maximum area target count” can choose different actions. With one successful ability cast per turn, a damaging spell also competes with a shield, heal, dash or attack reset. The current [combat document](combat.md) correctly marks those choices unresolved, but implementation would still have to invent their precedence.

Ranged attack priority has a specific progress risk. Walking and ranged basic/damaging attacks share allowance under the rules. A ranged follower that always attacks an available permitted target may never close formation or reach an altar guard tile. A ranged carrier repeatedly attacking a nearby threat may make no banking progress even without triggering numerical Danger. That needs an explicit state-sensitive action order and a definition of “reachable target”: attackable now, or reachable after movement, are different predicates.

The damage-triggered shield policy also requires an observation contract. A net Health change can combine incoming damage, healing and maximum-Health purchases; an unchanged value does not prove no damage occurred. Dash landings require legal geometry, useful progress and a safety test, and a missing walking route cannot prove the dash route is impossible.

**Required decision:** specify deterministic target/action comparisons, cast priorities by state, damage evidence/window, healing policy, and dash admission. Validate the available SDK evidence before promising accurate damage-type inference. Use action legality checks and fresh observations after each successful action, as the plan already requires.

## 6. Blocker: the normal fallback path is unfinished

The route helper can return an exploration request, but there is no agreed `EXPLORE` transition table, ownership or goal policy. This is a normal match situation when camps are unavailable, unseen or respawning. It cannot safely be filled with an implicit helper transition because `state_machine.md` is explicitly the sole transition authority.

Single-resource-node passing is also unresolved. The leader walks past, but whether followers clear and capture is undefined. Treating that as “skip the node” may discard easy income; treating it as an independent follower job changes entry behavior. Banking turn-taking and numeric ATTACK initiation remain open for the same reason: these are behavior definitions, not tuning constants.

**Required decision:** finish those paths before implementing a purportedly complete bot, or explicitly approve a smaller first version with the unfinished feature disabled. Distinguish `DEFER`, `NO_ROUTE_NOW`, and “no camp qualifies”; otherwise a fuel shortage can masquerade as a strategic exploration decision.

## 7. High risk: bounded work does not establish bounded waiting

The pathfinding plan improves substantially on the archive: free goals, SDK geometry, observation refresh, and separate deferred/dynamic/static failures. But retry limits and cache rebuilding alone do not guarantee progress.

Two allies meeting in a narrow corridor with a nearby passing pocket may both have no route under the current occupied mask. Rebuilding the same field every three turns changes nothing. Strict descent is valid on a complete field and can route around static obstacles; the unresolved issue here is coordinated yielding when the bodies themselves prevent any path. Staggered patrol choices reduce collisions but provide no general corridor-yield rule.

CAPTURE_POINT also retains temporarily blocked or uncertain objectives. With C5 limited to invalidity/permanent unreachability and C6 retrying, a body can remain in the same valid job indefinitely. Inspection exhaustion means unknown, correctly, but the caller still needs a bounded response to repeated unknown results. Several objectives in one chunk worsen this: refusing ambiguity is safe, yet can make a nearby responder permanently unable to join.

**Recommendation:** define task-progress counters and bounded recovery decisions for temporary obstruction, repeated ambiguous inspection and contested objectives. Consider deterministic local yielding without role allocation. Progress must mean useful movement, damage, capture countdown or bank completion; publishing status and switching states are not productive progress by themselves.

## 8. High risk: fuel quotas can starve essential movement

The native backend permits three combined field computations per own turn. Threat/support checks, altar scoring, movement, chunk inspection and initial ward-direction construction share that quota. They often need different masks, and movement/reveals invalidate dynamic caches. A legal call count does not prove calls fit the 100,000-fuel C++ turn budget; a native call's expansion count is available only after completion.

For example, a SENSE query and altar-selection estimate can consume two fields, leaving one for movement and none for an obstruction retry. If earlier discretionary queries continually consume the quota, an essential task can repeatedly return DEFER. Restarting after fuel suspension also requires an actual implementation mechanism for abandoning stale continuations, not just an instruction to refresh observations.

**Recommendation:** specify admission order and reserved capacity for essential actions/publication, measure worst-case calls on large maps, and keep optional work deferrable across rounds. Record the reason for each DEFER and each resume. The state-change cap and once-per-turn return dispatcher prevent runaway processing; they do not guarantee that the next turn makes progress.

There is also a small documentation inconsistency: the chunking fuel section still refers to provisional Python values, while configuration and the implementation target are C++. That should be reconciled when finalizing the execution contract.

## What is worth retaining

The plan explicitly separates state transitions from combat, routing and navigation. CAMP/BANK task context avoids creating dozens of nearly identical states. Engine-confirmed tribute start, exact saved carrier/group identity, own-vision restrictions, group-specific reward confirmation, and refusal to infer death from invisibility are sound. So are native movement geometry, free legal goals, bounded helpers, reserved critical fuel, and the distinction between missing information and proved unreachability.

Keep those contracts. The principal simplification should remove unsupported coordination promises and unproductive waiting, rather than removing the safeguards that prevent illegal actions.

## Recommended decision and implementation order

1. **Close information blockers:** approve a realizable shared-memory lifecycle and initialization contract, plus deterministic election behavior. Work out same-payload replacement and clock-wrap examples before coding.
2. **Close ordinary behavior gaps:** exploration, single-node handling, combat/cast priority, dash criteria and banking admission. Record decisions in their authoritative documents and keep the diagram aligned.
3. **Review liveness and economic policy:** what the team does while its leader is committed; whether losing protection can end; how blocked/unknown jobs recover; how long valuable bags may remain unbanked. These are proposed policy reviews, not accepted changes.
4. **Build a minimal complete scoring loop:** acquire a camp, clear it, capture it, travel to an altar, confirm a channel, complete tribute, repeat; include death/recovery and unavailable-objective fallback. Keep optional rallies, sophisticated inspection and ward scoring out of the first measurement unless explicitly required for that loop.
5. **Add coordination one feature at a time:** compare each change to the working loop using identical maps, seeds, opponents and swapped team sides. Do not use the broken archive as the only performance baseline.

## Evidence required before calling the replacement successful

| Scenario | Required evidence |
| --- | --- |
| Occupied living monster tile and hidden blocker | No move into a known occupied destination; reveal/retry stays bounded. |
| Same-type/chunk rally replacement; creator death; late first reader; clock wrap | No unauthorized refresh/clear or invented freshness. |
| Low-Health preferred successor; hidden leader; committed successor | No repeated ineligible election or unbounded planner starvation. |
| Contested camp, collector death, displacement and enemy claim | Correct task outcome; bounded next decision under the agreed commitment policy. |
| Several camps/altars in one chunk | No wrong-objective commitment; explicit resolution or recovery from ambiguity. |
| Multiple carriers, interruption, opposing lock, simultaneous score changes | Legal admission/channel handling; no false success from another carrier's score. |
| Ranged travel with a recurring attack opportunity; corridor congestion | Measured task progress or a deliberate bounded policy, rather than endless attacks/waiting. |
| Maximum map, changed visibility and fuel suspension | Essential coordination completes; stale buffers are discarded; optional work cannot repeatedly consume required movement capacity. |

Track tributed gems per 100 rounds, time to first tribute, clear/capture/bank cycle times, deaths and lost bags, gold earned/spent, no-progress dwell by state, action-error counts, and fuel/defer reasons. Report distributions across maps, seeds and team sides rather than one aggregate win rate. High-scoring short smoke tests do not establish full-match reliability; zero VM faults do not establish a functioning economy.

The first milestone should be a repeatable scoring cycle with explainable failures. The present plan spends considerable detail on coordination and inspection before establishing that milestone. Finishing the missing contracts and measuring productive progress offers more value than expanding the state list.
