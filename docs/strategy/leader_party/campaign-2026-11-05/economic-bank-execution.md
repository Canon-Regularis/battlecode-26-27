# Banking execution inside the shared action owner

Later evidence addendum: the [bounded native duration contract](tribute-duration-native-contract.md)
adds 20 actual starts at the pinned default settings, with zero or one completed
Tribute emblem. All tested cases fit upward rounding of ordinary duration,
followed by the completed Tribute reduction and a second upward rounding:
11 gems remains 2 turns with Tribute; 31 gems changes 4 to 3. Use that tested
model for supported estimates, not a percentage applied before the first
ceiling. This does not prove all numeric boundaries or other settings/passive
combinations. The raw snapshot `submissionDuration` field was zero throughout
these cases and supplies no predictive permission or duration evidence.

Both completion traces fixed duration from the starting bag of 11, retained
timer 2 after ten more gems arrived, ticked to 1/0 at owner-end 149/150, and
submitted all 21 at owner-start 151. A bag increase during submission must not
restart/reprice the active channel or be mistaken for its completion. Use the
observed channel timer for execution, and keep final bag/deposit attribution
separate from the earlier duration estimate. These are offline sandbox-native
contracts; live SDK adapter and release coverage remain required.

5 November 2026. Primary-source-backed **construction proposal**, not dispatched or strength-tested. Complements [selected B](economic-core-selection.md), [lifecycle/fallback](economic-task-lifecycle-contract.md), [integration audit](combined-core-integration-audit.md) and [stage2 brief](economic-core-stage2-brief.md). Replace old `bank()` ownership; reuse public SDK operations inside the same fresh-scene/action ledger. No production changes, games, uploads or STATUS edits.

Later [actual shared-altar evidence](shared-altar-channel-foundation.md) now confirms a recorded engine3start on a free adjacent tile while another ally remains submitting at the same recorded altar with timer1. This supports the selected removal of unconditional channel courtesy-wait, not a universal legality/safety or strength claim. Keep fresh public start guards and actual no-start/lock/error/rollover integration checks.

## Established semantics versus policy choices

Primary sources inspected: current [SDK](../../../../sdk/cpp/cambc.h) SHA256`5d175d6af2ccdb12c693db1dbfceefb0c096c7d482efe4e8683de7ea2d4516bf`; [rules](../../../cambc/GameRules.md) SHA256`336009e76b0675b8e068a50690dbb7b56eb8a5130dbf143cc34ce19ba589b974`; original [economy.cpp](../../../../bots/leader_party_tuned/src/economy.cpp) SHA256`2d9c3ddfb8e7600fe2d3e5a13d9682d6b06bec0421a37e8d2d3d02fbced9efb7`.

| Source-owned fact | Implementation consequence |
| --- | --- |
| [`void champion::submit_gems(vec2 altar)`](../../../../sdk/cpp/cambc.h:4010) requires self and checks the host result. No inspected `can_submit`/`can_channel` helper exists. | Guard known prerequisites; normal return is **not** a Boolean channel-start result. Invalidate, refresh and verify actual submitting state/timer. Never increment banked score on a call. |
| [Rules228-236](../../../cambc/GameRules.md:228): stand within Chebyshev1 with gems; channel length uses starting bag, completion submits current bag; ticks owner-end, resolves next owner-start after zero. | Reaching an altar is not depositing. Same-turn captures can change the eventual amount; zero timer is pending until resolution. Use actual SDK range/duration constants and verified Tribute modifier in estimates. |
| [Rules242/246](../../../cambc/GameRules.md:242): allied lock permits own tribute; enemy lock blocks it; tribute attempts against locks may become attacks. SDK has error125`invalid_action_submit_gems_altar_locked`. | Do not use submission as a lock-removal probe or assume every normal return starts a channel. Explicitly inspect/clear a visible enemy lock, then reobserve before submission. The wrapper alone does not specify every engine auto-attack/error branch. |
| [`altar_lock`](../../../../sdk/cpp/cambc.h:3372) is an immutable **visible snapshot**, with `position()`, relative `team()`, `hits_remaining()`. [`vision::altar_locks()`](../../../../sdk/cpp/cambc.h:5130) returns owning visible snapshots. | These lock fields are scalar historical observations, unlike live champion/camp wrappers. Still refresh after action. No public lock-handle accessor is needed or assumed. Hidden/list absence alone does not prove an altar unlocked. |
| [`void champion::attack(const altar_lock&)`](../../../../sdk/cpp/cambc.h:3911); [rules240](../../../cambc/GameRules.md:240) say five basic hits, SDK `constants::altar_lock_hits` supplies settings. | Remove locks by legal basics and observed hit-count changes, not Strength/Focus/HP damage arithmetic or guessed spell targets. |
| [`consumable::use(vec2)`](../../../../sdk/cpp/cambc.h:2912) returns bool; count2902, cost1949, carry-limit1951, `can_buy(consumable_type)`3886. | Own lock placement is a real checked inventory action. No cast allowance is documented for it; use consumable restrictions/inventory/actual host outcome. Do not equate a lock with an ability slot. |
| [Rules118/277](../../../cambc/GameRules.md:277): active channel blocks actions; tribute is manually cancellable, damage does not interrupt it, stun/death/new enemy lock can. [`cancel_submit_gems()`](../../../../sdk/cpp/cambc.h:4017) checks submitting state then calls cancel. | Preserve a useful channel; mere damage or low-HP latch is not proof it should be cancelled. Teleport cannot be manually cancelled. Shared ledger enforces one submission start/cancellation per turn. |
| [`constants::winning_gems`](../../../../sdk/cpp/cambc.h:113), [`global_submitted_gems(team)`](../../../../sdk/cpp/cambc.h:4524), [victory rules29](../../../cambc/GameRules.md:29). | Winning threshold comes from current settings, not hardcoded1000. A start is not an immediate win: minimum channel duration is positive. Team score and own bag are public inputs; no ally gold is used. |

The original executor chooses altars again every3rounds, invokes old movement/combat, waits for any nearby submitting ally or a larger-bag/lower-ID ally, waits3rounds before rotating when multiple altars exist, attacks a lock, places its own lock, then submits. **Its ally queue is a courtesy policy.** The inspected SDK/rules expose neither an engine per-altar queue nor a documented one-tributer exclusivity prerequisite. Do not infer such a restriction from that source. The proposal below ties waiting to physical access/progress and permits a checked submission from a free supported position without a courtesy delay solely because an ally submits nearby.

Existing native capability control: bge01 Ren walks116/1768/0, places own lock116/1769/0, starts tribute116/1770/0, deposits7at117/1780/7. [Official decoded actions/local probes](../../../../.cambc/campaign-2026-11-05/replay-decoder/bge01-swirl-all-local165.json), [identity/audit](bge01-swirl-mechanism.md). This demonstrates move→lock→submit in that case, not guaranteed simultaneous ally submission, general safety or strength; bge01's rejection remains unchanged.

## One bank obligation, finite phases

Keep `NeedsConversion(actual_bag)` separate from the current altar access attempt. Use phases `Approach`, `ObserveLock`, `ClearEnemyLock`, `WaitForAccess`, `PlaceOwnLock`, `StartSubmission`, `Channeling`, `ReconcileDisposition`. Return typed results: `ApproachProgress`, `AtAltar`, `LockHit`, `LockRemovedObserved`, `QueueProgress`, `QueueStalled`, `NoAccessNow`, `ChannelStartedObserved`, `ChannelContinued`, `ChannelInterrupted`, `DispositionUncertain`, `Deferred`, `Stale`, `ContractError`.

Every actual action goes through the existing shared action owner; no `fight()`/ward/shop/footer follows a claimed bank stop. Full epoch/allowance/reserve guards surround query batches and actions; after every move, lock hit, reset, lock placement or channel mutation acquire a fresh owned scene. A second operation is a new decision, not an authorized sequence. Old route/queue recreation cannot clear exhaustion. Resource deferral is not blocked access or useful bank progress.

## Approach and submission preflight

Approach targets are actual usable cells within `constants::submit_gems_range` of a static public altar, excluding the altar itself and current physical blockers. Use retained route intent, finite repair and shared field allowance. Unknown later occupancy/risk keeps a route conditional. Never assume a locked or camp-blocked altar becomes clear for free.

At a currently reached candidate, own scalar scene/preflight must establish:

1. Same actor/life/round/revision, alive, not completed/stunned, actual bag>0; no active recall/submission/teleport. Both observed `submit_gems_started` and shared start ledger show this turn's start unused. There is no `buff_restrictions::channel` bit: zero restrictions alone is not permission; `can_move/can_cast/can_attack` is not a submission-readiness test.
2. Target is an actual in-bounds public altar; current self position is within actual SDK submission range. Require current altar visibility in this conservative adapter so lock absence is observable. Current invisible/unknown lock state produces observation/access work, not a blind submit.
3. One fresh all-team lock snapshot has no enemy lock at the altar. An allied lock is compatible. Do not call `has_altar_lock()` to certify absence on a hidden tile: its implementation returns false on not-in-vision/not-found paths too.
4. Supported current banking safety: fresh risk coverage, zero observed awake-camp exposure and zero visible enemy basic-response exposure at the start position; inherited actual health/evasion preemption has been resolved. This conservative start policy is an engineering choice, not an engine legality condition or future-safety guarantee. Ordinary camp farming uses the different service admission contract.
5. The action can be admitted within remaining calibrated reserve. An unknown/unsupported guard cannot be converted into a successful start or an exact safe-delivery estimate.

Issue `self().submit_gems(altar)` once, record the attempted operation, invalidate, then refresh. `is_submitting_gems()` plus a legal current `remaining_channel_time()` observation establishes `ChannelStartedObserved`; query the timer only when channel state supports it. No channel after normal return is `StartNotObserved`/reclassification, **not success**: inspect changed attack allowance/lock hits/resources only from fresh facts. Do not loop on submit until a channel appears. If return crosses an epoch/round, stop and reconcile later without issuing another start. `submit_gems_cancelled` is not itself a documented engine start prohibition; nevertheless this initial policy does not voluntarily cancel/restart a submission in the same turn merely to change targets.

## Enemy lock service and own lock placement

An observed enemy lock becomes a named local access subtask. Supported removal requires alive/current unchannelled actor, no stun/attack restriction, current `can_attack`, fresh visible enemy lock at the altar, Chebyshev attack range, and the same conservative local banking safety. `attack_tiles()` is range only. Prefer direct scalar range checks over per-candidate host masks. No move onto the altar is allowed/needed.

Issue `attack(lock_snapshot)`; refresh; count a hit only from a coherent observed decrease in that altar/team episode's `hits_remaining`, or visible disappearance with correct before/action/after evidence. A missing lock outside current vision is unknown. `LockRemovedObserved` requires a freshly visible altar and no enemy lock, not merely predicted last-hit arithmetic. A reset→second basic is permitted through the shared typed reset path only with fresh guards, one successful cast total and at most2basics; each hit is separately observed. No ability spell is presumed to target a lock. Do not consume a new route field for stationary lock hits.

Starting with observed`h`hits remaining supplies finite work: each successful hit must lower that counter; at most`h`such decreases can finish that observed episode. A new/increased lock is a new factual obstruction, not silently continued old progress or permission to restart the entire bank budget. Missing allowance yields to the next turn; no available useful hit/contact returns a reasoned blocked/unsupported result. Failed/unchanged hits do not refresh progress. Use persistent route/access effort limits and specific reopening facts; do not farm the same lock indefinitely under a renewing generic timer. If removal is unsafe or no supported attack/contact exists, record this altar's access failure and consider another finite option; retain the bag obligation and eventual independent gold fallback.

Once the altar is freshly unlocked, placing an **already carried** own lock is optional compatible preparation retained from original policy. Require no visible lock of either team, actual carried count>0, no consumable restriction, alive/uncompleted/nonstunned/no-channel state, documented range2 and checked epoch/reserve. `use(altar)` is not `void`: false invalidates/reobserves and consumes a failed-attempt ticket; do not pretend protection exists. Normal success is followed by fresh inventory/allied-lock observation before submission. At most one placement attempt per actor-turn; no placement during an active channel. No reserve/capacity for placement means skip the optional preparation if the fresh submission remains supported—do not delay banking solely to use/buy a lock.

Natural shopping may retain the original carry-one lock purchase through actual `can_buy`, metadata cost/carry-limit and observed inventory/spend, with fresh invalidation. No bank trip is lengthened into a purchase detour, no remote consumable-shopping exception is invented, and a used lock is not a bank event. Range2 is the documented current supported lock-use subset; metadata/engine changes outside that contract must be reported rather than guessed.

## Local queue priority and finite waiting

**Do not wait solely because another ally is submitting if self already has a safe unoccupied legal start position.** Starting a different actor's channel does not physically consume self's tile. This proposal removes the old broad courtesy delay; actual current-engine construction tests must exercise this assumption, and an unexpected host refusal is a contract finding rather than silently reintroducing an unbounded queue.

When all supported approach cells are actually occupied, preserve useful active channels/holders on their tiles. Among visible unchannelled waiting carriers, use the original deterministic local order: larger actual bag first, then lower public actor ID. This is a voluntary access preference, not a reservation, command or promise of another actor's action. Do not mark an empty tile blocked for a presumed private assignment. An ally may be adjacent to multiple altars; the inspected SDK has no public channel-target-altar query, so do not assert which altar its channel targets. Its actual occupied tile is the relevant access fact.

Queue waiting applies to relevant **observed allied** occupants. An enemy, damaging camp, physical wall or unknown obstruction is a different access/defense/service result; it does not become an allied queue merely because no approach is free.

For a blocked approach, record one queue episode keyed by altar/approach and the observed blockers, with the following finite rules (engineering choices):

- A higher-priority nonchanneling carrier gets at most the original3eligible-turn courtesy allowance, **only while fresh actual progress occurs**: movement along a comparable approach toward access, starting submission, or observed removal of the blocking lock. One initial observation opportunity is permitted; unchanged occupancy/bag/intent on the next eligible turn ends the courtesy as `QueueStalled`. New field distance or simply still having a larger bag is not progress.
- For an observed active blocking channel timer`t`in round`r`, allow a fixed observation deadline`r+t+1`: the extra round accommodates whether this ally's current owner-end tick has already occurred. Require fresh timer decrease/actual channel transition on subsequent eligible observations; it is a bounded opportunity to observe access, **not a prediction the ally will vacate**. Completion without vacancy does not open a route.
- A real first channel start can promote the initial courtesy episode once to that timer-derived deadline. Channel restart, new blocker, bag increase or repeated same progress fact cannot repeatedly extend the same episode. Loss of visibility is unknown; it does not establish departure. A zero timer can resolve before a later observation, but is not current vacancy.
- Deadline/stall returns `QueueStalled` for that wait option. Try a distinct currently supported approach/altar under the finite access ledger; no round%3 rotation or same-task recreation reset. Actual newly observed vacancy/changed physical access can reopen the affected option once. No safe access after finite alternatives produces `NoAccessNow`, then the lifecycle's safe independent-output fallback while retaining the bag.

Queue waits themselves need a supported safe current position; necessary recovery preempts them. No unaccounted escort/attack/ward follows a wait. Prior ally channel progression can explain useful waiting; it cannot be credited as this actor's bank/work or treated as guaranteed future vacancy.

## Preserve channels and define winning submission precisely

An active own submission belongs to the action owner. Keep its altar identity from the actual own start record, current bag, observed timer and uncertainty. Do not retarget/cancel for better approximate rate, another ally's bag priority, shopping, gold balance or mere positive damage; damage does not interrupt tribute. Ordinary low-health latch remains recorded for **after** the channel, not an automatic discretionary cancellation.

**Root construction choice: strict active-submission preservation.** The initial combined implementation does not voluntarily cancel own tribute for a new recovery/rate/queue/shopping decision. The inspected recovery parent has no submission-cancellation branch, and this redesign has not established an actual-engine beneficial cancel/escape case. Record danger and revalidate after natural completion/interruption; do not mislabel preservation as guaranteed survival. A narrow emergency cancel followed by a freshly supported lower-risk escape remains a separately testable later hypothesis, requiring real channel/cancel/permission evidence before inclusion. This choice does not change the reviewed explicit recall-cancellation behavior or teleport ownership.

Use an exact current-data predicate named `WinningSubmissionAvailable`:

```text
score = observed global_submitted_gems(ally)
threshold = constants::winning_gems
score < threshold
actual_self_bag >= threshold - score
all current StartSubmission guards above pass at this actual altar/position
```

Use wide/subtraction-safe arithmetic and no forecast extra capture, ally private intent, unseen loot or assumed lock removal. It prioritizes this supported start over a new farm/gold task or voluntary courtesy wait; it does not override dead/stale/channel ownership, required safety or actual legal permissions. A remote bag large enough to win is a valuable **conversion obligation**, not this presently executable predicate. An already active own channel with sufficient current bag is `WinningChannelInProgress` and should be preserved under the same channel rule.

Neither predicate means victory now: even a1tick submission completes at a later owner-start and can be interrupted. Actual team score reaching threshold is team victory evidence. The SDK's self bag/team cumulative score do not expose exact per-actor cumulative deposits; preserve inferred own completion/loss uncertainty as required by the integration audit. Concurrent ally deposits or receipts cannot be assigned wholesale to self.

## Errors, bounded cost and construction controls

Relevant current SDK enum classes:45cant_channel,46no_gems,47bad_altar,48out_of_range,114already_used,125altar_locked; lock118bad_altar/119out_of_range/120already_locked; attack39-43; cancellation115/116/124; generic33cannot_act/34recalling/35submitting/123teleporting. Validate against exact current enum names. A thrown checked operation is not a Boolean obstruction success: stop continuation, report its class and coherent facts, invalidate/reconcile; do not blanket-catch arbitrary errors or issue a second channel start from the old scene. Expected false movement/consumable results are distinct. There is no invented `restrictions.channel`, `can_submit`, lock spell overload or ally-gold query.

Query visible lock snapshots once per relevant epoch (one all-team list, not duplicate filtered calls), copy nearby visible ally position/bag/channel/timer once, then use scalar comparisons. Bounds are shared with scene/actor capacities; excess yields incomplete, never omitted blockers. Stationary lock/queue/start needs no new whole-map field; approach/repair uses the existing shared job budget. Count host operations, refreshes, actual hits/placement/start/cancel and waits, including the cost of SDK vector/count calls. No native timing proves WASM fuel.

Required actual-adapter tests: move→fresh lock check→start; locked altar→hit→reset/fresh hit, correct removal then own lock→refresh→submit; cast already spent; ranged move consumes attack; unknown/hidden lock; allied lock permits own start; occupied approach versus free adjacent access with another submitting ally; larger-bag priority with progress and no-progress/restart/deadline cases; lost sight not vacancy; real newly clear access reopens once; active channel preserved despite changed rates/HP with no lethal danger; separately labelled emergency-cancel alternative; same-turn start/cancel limits; normal submit return without observed channel; code45/125 classification; stale/rollover before/inside/after action with no second operation; current winning threshold versus remote/locked/unsafe/forecast-only negatives; own disposition uncertainty and exhausted access→independent gold work. Add native construction coverage of lock placement plus submission, without treating the historical bge01 mechanism as a new strength result.

Root must freeze queue details, emergency cancellation, actual-engine free-approach/shared-altar behavior and resource reserves before turning this proposal into Pi instructions. Intermediate construction requires legal real execution and bounded useful outcomes; it has no standalone win threshold. Completed-design competitiveness remains separately evaluated.
