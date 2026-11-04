# Champion state machine

Historical pre-implementation strategy; superseded by the [current bot documentation](../../README.md).

Current leader-party design; documentation only. This file alone defines state transitions. Read with [configuration](config.md), [communication](communciation.md), and the [editable diagram](state_machine.mmd).

## States at a glance

| State | Job | Safety interruption | Debug colour |
| --- | --- | --- | --- |
| LEAD_TEAM | The current leader runs the route planner when in this state. | Escape / Recover | Blue #2563EB |
| FOLLOW_LEADER | Follow; if current leader is 111, auto-select the next leader using configured preference. | Escape / Recover | Cyan #06B6D4 |
| CAPTURE_POINT | Fight a camp, then approach its cleared capture region. | Escape | Orange #F97316 |
| PROTECT_POINT | Guard/occupy a camp capture or guard a bank attempt. | * | Purple #9333EA |
| PREPARE_GEM_BANKING | Travel to an altar, clear a lock if appropriate, request escorts. | Escape / Recover | Gold #CA8A04 |
| BANK_GEMS | Maintain the carrier's tribute channel. | Channel | Yellow #FACC15 |
| RALLY | Answer ATTACK or BANK. | ATTACK: *; BANK travel: Escape / Recover | Pink #DB2777 |
| RUN_AWAY | Reach a safe friendly; otherwise retreat to spawn. | — | Red #DC2626 |
| RECALL | Channel a safe return to spawn. | Escape | Indigo #4F46E5 |
| HEALING | Remain on spawn until full Health. | Spawn defense | Green #16A34A |
| DEFEND_SPAWN | Fight from spawn without chasing away from it. | — | Dark red #991B1B |
| DEATH | Publish unavailable; perform permitted shopping; await respawn. | — | Grey #6B7280 |

**Key**

| Label | Meaning |
| --- | --- |
| Escape | May enter RUN_AWAY under the state's listed danger conditions. |
| Recover | May enter RECALL or HEALING under the listed conditions. |
| * | No voluntary escape/recall while the objective remains valid. Fight until completion, invalidation, or the specified cancellation. Death still overrides. |
| Channel | While the engine says tribute is active, maintain it. An interrupted channel is handled by its own table. |
| Spawn defense | If currently on spawn and a local threat needs fighting, enter DEFEND_SPAWN. |
| — | Use the state's explicit exits. |

Colours are for debugging, not shared bits. Draw both the state name and colour so similar colours remain distinguishable.

**One body, one active state.** PROTECT_POINT has CAMP/BANK task data. **Re-evaluate** means the bounded [return decision](#return-decision), not an unfinished implementation or a persistent state.

## How to run the tables

Read rows from top to bottom and take the first match. A "stay" row is a real self-transition and is intentionally retained. Tables cover decisions at the start of the turn and after an action changes a relevant fact; they are not restricted to turn end.

| Order | Work | Why |
| --- | --- | --- |
| 1 | Check self death; if current leader is self and Health <= LEADER_MIN_HEALTH_FRACTION, write 111; read current channel/Health/task facts. | A dead body cannot keep fighting, and an already finished channel must not be restarted accidentally. |
| 2 | Check the current state's table, including rally cancellation/replacement and observed objective completion. | Select the correct state before spending movement or actions. |
| 3 | Apply exit/entry effects: leadership handover, saved task, channel bookkeeping. | Entering another state does not release leadership. The low-Health/death check clears the current-leader bits to 111 independently of the selected state. Escaping must preserve pending banking. |
| 4 | Execute that state's actions. Attack targeting and path requests are limited to actions the state permits. | A tribute carrier cannot use normal combat actions. A protector cannot choose an escape path. |
| 5 | After a successful move/attack/cast, refresh affected visibility and action availability before another action. Recheck a newly triggered transition within MAX_STATE_CHANGES_PER_TURN. | Moving can expose an enemy; attacking can wake a camp; actions can consume other actions. Never act from the old snapshot. |
| 6 | Publish state-derived safety and current leader/rally information; reserve fuel to yield. | Coordination and channel/death correctness take priority over extra scouting. Safety is checked from current local observations. |
| 7 | If fuel exceeds the configured threshold plus critical reserve, calculate/publish enemy concentration. Debug drawing is lower priority. | Optional work must not prevent essential state actions and communication. |

Mandatory deadline/ownership checks also run before refreshing an owned rally. Fuel checks use the C++ SDK's fuel_remaining and preserve the configured reserve. Run shopping before leaving spawn (or from DEATH), then required state actions and mandatory publication, then optional wards/enemy reporting/debug work. Re-evaluate local danger after ward vision changes.

The previous term **"locked state"** meant a committed action: PROTECT_POINT, BANK_GEMS while channeling, or a live ATTACK rally. It did **not** mean an altar lock or a separate state. There is no unconditional global rule that sends every injured/outnumbered body fleeing. Each table decides whether safety can interrupt that particular job.

If execution resumes after fuel suspension in a later round, discard old observations and pending read/modify/write buffers, then restart the essential checks before acting. An old local snapshot is not a current turn.

### Common death transition

**G0: From every living state, if the engine reports self dead, enter DEATH before any other row.** Each living-state table explicitly includes G0. On death, if self is the current leader write 111, invalidate lost-bag banking, and clear only a still-owned matching rally. No movement, attacks, recall, or tribute while dead.

## LEAD_TEAM

Only the body identified by the current-leader bits may run the route planner. The leader keeps that identity when entering capture, protection, banking, or other states. If its Health fraction reaches or falls below LEADER_MIN_HEALTH_FRACTION, it writes 111 and then follows the state machine for recovery. The existing death cleanup also clears a dead leader. Other bodies auto-select the next leader using configured precedence; no shared eligibility offers, nominations, lease expiry, or handover cooldown is used.

A body already capturing continues its task through leadership changes. There are no allocated nonleader roles or inherited-work assignments.

| Transition | Exact condition | Destination / effect |
| --- | --- | --- |
| **Death** · G0 | Self dead. | DEATH. |
| **Defend spawn** · L0 | On spawn and Spawn threatened. | DEFEND_SPAWN. |
| **Heal on spawn** · D1 | On spawn; Health missing. | HEALING. |
| **Escape danger** · D2 | Danger. | RUN_AWAY; retain pending banking. |
| **Recall safely** · D3 | Low Health and Recall safe. | RECALL. |
| **Find recall safety** · D4 | Low Health and not Recall safe. | RUN_AWAY. |
| **Prepare to bank** · D5 | Banking needed or saved positive-bag banking. | PREPARE_GEM_BANKING. |
| **Lose leadership** · L1 | Current-leader bits no longer identify self, or Health fraction <= LEADER_MIN_HEALTH_FRACTION. | FOLLOW_LEADER; if still current leader at low Health, write 111 first. |
| **Answer rally** · D6 | Joinable rally. | RALLY. |
| **Work camp** · L3 | Planner selects a valid reachable camp; entry safe; route policy selects an ordinary stop rather than passing a single gold/gem node. | Report current camp activity; CAPTURE_POINT (or PROTECT_POINT for an already active allied capture). |
| **Continue leading** · L4 | No earlier row. | LEAD_TEAM; run the dynamic route planner described in strategies/route_planning.md. |

A successor chooses its own objective using current observations and the route policy. An old leader's reported activity does not allocate a task or bypass this state table.

## FOLLOW_LEADER

Use visible leader first; otherwise use its reported chunk to approach and inspect. A chunk centre is a search destination, not proof of visibility. If the leader is absent, this state also handles election/waiting; no separate waiting state is required.

| Transition | Exact condition | Destination / effect |
| --- | --- | --- |
| **Death** · G0 | Self dead. | DEATH. |
| **Defend spawn** · F0 | On spawn and Spawn threatened. | DEFEND_SPAWN. |
| **Heal on spawn** · D1 | On spawn; Health missing. | HEALING. |
| **Escape danger** · D2 | Danger. | RUN_AWAY; retain banking. |
| **Recall safely** · D3 | Low Health and Recall safe. | RECALL. |
| **Find recall safety** · D4 | Low Health and not Recall safe. | RUN_AWAY. |
| **Prepare to bank** · D5 | Banking needed or saved positive-bag banking. | PREPARE_GEM_BANKING. |
| **Protect observed capture** · F1 | Valid available camp reward; whole group dead; allied occupant is capturing; exact group known. | PROTECT_POINT — CAMP; save collector/group. |
| **Join camp work** · F2 | Confirmed visible leader camp activity; exact group personally resolved; camp entry safe. No role assignment is required. The exact single-resource-node passing behavior has not yet been clarified. | CAPTURE_POINT; save exact observed group as private task context. |
| **Protect observed banking** · F3 | Intended carrier visibly channeling at a known altar; self already within configured guard distance; no higher-priority task. | PROTECT_POINT — BANK; save carrier/altar. A rally is not required. |
| **Answer rally** · D6 | Joinable rally. | RALLY. |
| **Accept leadership** · F4 | Self is already current leader, or current leader is 111 and self becomes the next leader under the existing configured preference logic. | LEAD_TEAM. |
| **Continue following** · F5 | Current leader exists; no earlier row. | FOLLOW_LEADER; approach a free formation tile or inspect the reported chunk. |
| **Wait for leader** · F6 | Current leader is 111 and self has not become the next leader. | FOLLOW_LEADER; wait safely at last valid party anchor, otherwise approach spawn. Recheck next turn. |

A report of leader camp activity helps resolve the exact group but is not a work assignment. Existing CAPTURE_POINT/PROTECT_POINT tasks continue independently of leader changes. Ordinary new camp entry retains the visible-leader requirement in F2; passing-node behavior will be specified after clarification.

## CAPTURE_POINT

Includes fighting a living group **and** approaching its empty cleared capture region. Rallies, lost leader vision, and ordinary recall requests do not interrupt it. Danger can.

| Transition | Exact condition | Destination / effect |
| --- | --- | --- |
| **Death** · G0 | Self dead. | DEATH. |
| **Release claimed camp** · C1 | This group's reward confirmed claimed or group in post-claim respawn countdown. | Re-evaluate; finish the camp task. |
| **Approach cleared camp** · C2 | Whole group confirmed dead; reward available; **no allied occupant** in its capture region; legal approach exists; no Danger. | CAPTURE_POINT; self may approach a legal vacant spawn tile, rechecking current occupancy before moving. There is no selected collector; observed allied occupants trigger C3. |
| **Protect active capture** · C3 | Whole group dead; reward available; an ally, **including self**, occupies a legal capture tile. | PROTECT_POINT — CAMP. Commitment starts before the C4 safety check. |
| **Escape danger** · C4 | Danger while fighting or approaching an as-yet unoccupied capture. | RUN_AWAY; save group for optional resumption. |
| **Release invalid camp** · C5 | Group invalid or permanently unreachable. Temporary occupancy/lost vision is not permanent invalidity. | Re-evaluate; end camp task. |
| **Continue capture work** · C6 | No earlier row. | CAPTURE_POINT; fight living monsters/contesters, inspect uncertain group state, or retry approach. |

"Being captured" means an allied occupant is attempting capture; an enemy occupant alone does not qualify. A contest may reset the engine timer, but allied occupants still trigger protection.

**Camps never contribute to Outnumbered.** Camp damage remains a separate danger check at low Health. A low-Health body threatened by an awake camp may escape even when there are no enemy champions.

## PROTECT_POINT

Committed: fight until this objective completes, becomes invalid, or a listed recovery of the objective applies. Ordinary low Health/outnumbering does not cause retreat or recall. Save objective kind CAMP/BANK plus the exact group/collector or altar/carrier. Death still overrides.

**Quiet protection means a close patrol.** When no enemy champion is currently visible and no immediate hostile action needs a response, guards patrol within PROTECT_PATROL_RADIUS_TILES (initially one tile) of the protected point. For CAMP, use the visible collector's position, otherwise the saved reward region; for BANK, use the saved exact altar. Choose a different legal adjacent guard tile each own turn when one exists, stagger initial choices by stable roster slot, and keep every step inside this close patrol area and the existing camp/bank guard limit. Do not take a route outside the area to connect patrol positions. If blocked, hold the closest legal guard position and retry; terrain does not justify drifting away.

The collecting body stays on its capture tile, and a channeling carrier stays still. Patrolling guards stay outside camp reward tiles, leave the carrier's tile and access clear, and do not approach an unrelated awake camp. A visible enemy ends the quiet patrol: resume the committed protection actions below without chasing away from the objective. Patrol movement is optional after required actions and uses remaining movement only.

### CAMP: guard the collector and reward region

| Transition | Exact condition | Destination / effect |
| --- | --- | --- |
| **Death** · G0 | Self dead. | DEATH. |
| **Finish collection** · PC1 | Reward claimed, including an enemy claim, or reward objective definitively invalid/respawned. | Re-evaluate; clear task. Only confirmed allied income counts as success. |
| **Replace dead collector** · PC2 | Saved collector confirmed dead; reward remains available; no other allied collector already occupies the region. | CAPTURE_POINT; approach the currently vacant capture region dynamically. |
| **Recover vacant capture** · PC4 | Collector left/displaced; reward available; no allied occupant remains. | CAPTURE_POINT; reclaim the point. This is not ordinary retreat. |
| **Continue protection** · PC3 | Capture still active/contested, including a replacement ally already occupying it. | PROTECT_POINT; update collector identity; fight, or patrol closely when no enemies are visible. The collector holds its capture tile. Publish UNSAFE when appropriate without leaving. |

A route leader's death alone does not invalidate a living collector's job. PC2 refers to the **objective's collector**. This avoids dropping rewards whenever leadership changes.

The engine requires the entire connected group dead and an uncontested occupant. Empty/contested regions reset capture progress. Extra allied occupants split rewards; a Capture Emblem holder additionally caps the remaining capture countdown at three, including when joining mid-capture. This never increases a shorter timer and persists while another ally keeps capturing. Additional occupants without the emblem do not speed capture up. Confirm reward state; do not assume exactly five bot calls means completion.

### BANK: guard the local banking attempt

Once protection begins, the saved carrier/altar and direct observations control it. **Rally expiry, cancellation, or replacement does not end an otherwise valid bank protection.**

| Transition | Exact condition | Destination / effect |
| --- | --- | --- |
| **Death** · G0 | Self dead. | DEATH. |
| **Finish bank protection** · PB2 | Carrier's tribute completion confirmed. | Re-evaluate; end protection. |
| **Release dead/empty carrier** · PB1 | Carrier confirmed dead, or visible carrier no longer channeling and bag = 0 without confirmed success. | Re-evaluate; end protection. Check Danger before following/election via the return tree. Do not record success. |
| **Support interrupted bank** · PB3 | Carrier confirmed alive and visible near saved altar; bag > 0; channel interrupted but attempt not abandoned. | PROTECT_POINT; fight/clear an opposing lock as permitted while carrier retries. No rally required. |
| **Find hidden carrier** · PB4 | Carrier temporarily hidden; death not confirmed; fewer than BANK_REACQUIRE_TURNS own search turns elapsed. | PROTECT_POINT; move to a legal nearby observation/guard tile to restore sight; fight as needed. Do not assume alive/channeling from time alone. |
| **Release unconfirmed/abandoned attempt** · PB5 | Search limit reached with no live attempt re-established, or living visible nonchanneling carrier has left the altar vicinity/explicitly abandoned this attempt. | Re-evaluate; mark outcome unknown/abandoned, not dead/successful. |
| **Continue bank protection** · PB6 | No earlier row; observed active channel or still-valid local attempt. | PROTECT_POINT; fight even when outnumbered, or patrol closely around the altar when no enemies are visible. Preserve the carrier's channel and approach. |

The C++ SDK's ally handle `is_alive()` works without vision. Health, bag, position, and other live getters still require visibility. If death cannot be confirmed, use PB4/PB5; never infer death from an UNAVAILABLE summary or a vanished sprite.

A leader completion message is only a hint. It cannot distinguish another carrier's bank, a death, or a different camp in the same chunk.

## PREPARE_GEM_BANKING

Save the bank task and altar. Travel, request BANK assistance when permitted, and handle locks within this state. A locked altar can be cleared and is **not automatically discarded**. The [temporary altar baseline](strategies/altar_selection.md) supplies selection, lock handling, and channel confirmation.

| Transition | Exact condition | Destination / effect |
| --- | --- | --- |
| **Death** · G0 | Self dead. | DEATH. |
| **Release empty bag** · P1 | Bag = 0. | Re-evaluate; clear task and only a still-owned matching rally. |
| **Defend spawn** · P0 | On spawn and Spawn threatened. | DEFEND_SPAWN; retain positive-bag banking. |
| **Heal on spawn** · P2 | On spawn; Health missing. | HEALING; retain banking. |
| **Escape with gems** · P3 | Danger, or Low Health and not Recall safe. | RUN_AWAY; retain banking. |
| **Recover with gems** · P4 | Low Health and Recall safe. | RECALL; retain banking. |
| **Start tribute** · P5 | Within Chebyshev distance 1 of altar; enemy lock absent; start attempted; fresh engine state confirms is_submitting_gems(). | BANK_GEMS; record starting bag, life, and score. A normal submit_gems return alone is not confirmation. |
| **Handle altar obstruction** · P6 | Altar locked, path temporarily blocked, or selection requires replacement. | PREPARE_GEM_BANKING; clear lock, wait/reroute, or select another altar using the temporary altar baseline. A lock alone does not require replacement. |
| **Continue approach** · P7 | No earlier row. | PREPARE_GEM_BANKING; travel, preserve task, maintain/request BANK rally. |

P6/P7 remain separate self-transitions for readability, as requested. Another live BANK rally keeps the shared slot, but does not prevent this carrier approaching or banking. Saved banking resumes with any positive bag even below the normal threshold.

## BANK_GEMS

The carrier channels; escorts fight. No normal combat or voluntary flee/recall during an active tribute.

| Transition | Exact condition | Destination / effect |
| --- | --- | --- |
| **Death** · G0 | Self dead. | DEATH. |
| **Finish tribute** · B1 | Own tribute complete. | Re-evaluate; clear banking and still-owned matching rally. |
| **Continue channel** · B2 | Tribute still active, including zero timer awaiting resolution. | BANK_GEMS; maintain channel. |
| **Retry interrupted tribute** · B3 | Alive; channel inactive; bag > 0. | PREPARE_GEM_BANKING; its next safety check may escape. |
| **Release empty attempt** · B4 | Channel inactive; bag = 0; completion not confirmed. | Re-evaluate without claiming success. |

Tribute needs max(1, ceil(starting bag / 10)) owner turn-end ticks, including the starting turn, then completes at the next owner turn start after zero. It submits the current bag, including intervening captures. Damage alone does not interrupt it; stun, death, or a new opposing lock can.

## RALLY

Only ATTACK and BANK exist. REGROUP has been removed; ordinary regrouping uses FOLLOW_LEADER. Entry range is configurable per type and checked on joining/replacement, not used to eject a responder every turn.

| Transition | Exact condition | Destination / effect |
| --- | --- | --- |
| **Death** · G0 | Self dead. | DEATH. |
| **Creator cancels attack** · R1 | Still owns ATTACK record; Outnumbered, target confirmed dead, contact loss reaches limit, or absolute lifetime reaches cap. | Cancel matching record; Re-evaluate. |
| **Release ended rally** · R2 | Joined record cancelled/completed/expired. | Re-evaluate; stop private pursuit. |
| **Handle replacement** · R3 | Shared record replaced by another live request. | RALLY if replacement Joinable; otherwise Re-evaluate. Never clear another creator's replacement. |
| **Defend spawn during bank travel** · R0 | BANK request; currently on spawn and Spawn threatened. | DEFEND_SPAWN. |
| **Escape bank travel** · R4 | BANK and Danger. | DEFEND_SPAWN if on threatened spawn; otherwise RUN_AWAY. |
| **Recover bank travel** · R5 | BANK and Low Health. | RECALL if safe; otherwise RUN_AWAY, or DEFEND_SPAWN if already on threatened spawn. |
| **Become bank escort** · R6 | Intended carrier visible and actively tributing; self at a valid guard position. | PROTECT_POINT — BANK; save carrier/altar. |
| **Hold bank position** · R7 | BANK; at guard position; channel not started yet; request remains live. | RALLY; wait/fight as state permits. |
| **Continue attack** · R8 | Live ATTACK; no earlier row. | RALLY; approach/fight. No independent escape/recall while commitment remains. |
| **Continue response** · R9 | No earlier row. | RALLY; approach appropriate participation tile and inspect the chunk when needed. |

BANK can replace ATTACK; a live same-type request retains the slot. The creator ends ATTACK when outnumbered, but another responder might detect danger first. Under the chosen commitment rule it must wait for cancellation/expiry. The absolute cap applies even during combat.

## RUN_AWAY

Seek a visible reachable friendly that is not unsafe/unavailable; otherwise head for spawn. Seeing a friendly alone does not prove escape is complete.

| Transition | Exact condition | Destination / effect |
| --- | --- | --- |
| **Death** · G0 | Self dead. | DEATH. |
| **Defend spawn** · E1 | On spawn and Spawn threatened. | DEFEND_SPAWN. |
| **Recover at safe spawn** · E2 | On spawn; no current spawn threat. | HEALING if Health missing; otherwise Re-evaluate. |
| **Recall after escape** · E3 | Escape cleared; Recovery needed; Recall safe. | RECALL. |
| **Resume after escape** · E4 | Escape cleared; no recovery needed. | Re-evaluate; saved banking is considered before ordinary following. |
| **Approach safe friendly** · E5 | Suitable visible reachable ally; approach does not walk into a visible threat. | RUN_AWAY; approach. Prefer AVAILABLE on equivalent paths, then shortest path, then stable slot. |
| **Fall back to spawn** · E6 | No suitable friendly, or recovery remains unsafe and no better retreat exists. | RUN_AWAY; path toward spawn; if blocked, reduce exposure with a legal move or fight a reachable threat. |

E3 only says recall when safe. Otherwise the existing E5/E6 escape actions continue; no extra "seek recall-safe position" state is implied.

## RECALL

Any visible enemy champion blocks recall; numeric advantage is irrelevant. An awake camp outside its current attack range cannot chase and does not itself block recall.

| Transition | Exact condition | Destination / effect |
| --- | --- | --- |
| **Death** · G0 | Self dead. | DEATH. |
| **Defend arrival** · Q0 | On spawn and Spawn threatened. | DEFEND_SPAWN. |
| **Arrive at spawn** · Q1 | On spawn; no spawn threat. | HEALING if Health missing; otherwise Re-evaluate. |
| **Escape interruption** · Q2 | Enemy champion visible, or Camp can hit. | Cancel recall if legal; RUN_AWAY. |
| **Continue recall** · Q3 | Recall active; no Q2 threat. | RECALL; do not restart because Health changed mid-channel. |
| **Skip unneeded recall** · Q4 | Channel inactive; Health fraction >= RECALL_EXIT_FRACTION. | Clear recovery; Re-evaluate. |
| **Start/retry recall** · Q5 | Inactive; below exit threshold; Recall safe. | RECALL; start once legal. |
| **Find recall safety** · Q6 | Inactive; recall cannot safely start. | RUN_AWAY; retain recovery and pending banking. |

Recall takes five owner turn-end ticks, or three with Home. Damage, stun, or death interrupts it. After arrival, stay through turn end to receive spawn healing.

## HEALING

Remain on spawn until full Health is observed. Use the [temporary shop baseline](strategies/shop.md) when permitted. Spawn combat belongs to DEFEND_SPAWN.

| Transition | Exact condition | Destination / effect |
| --- | --- | --- |
| **Death** · G0 | Self dead. | DEATH. |
| **Defend spawn** · H2 | On spawn and Spawn threatened, at any Health. | DEFEND_SPAWN. |
| **Wait for healing** · H1 | On spawn; Health missing; no spawn threat. | HEALING; remain through turn end. |
| **Finish recovery** · H3 | On spawn; full Health; no spawn threat. | Clear recovery; Re-evaluate. |
| **Escape displacement** · H4 | Outside spawn and Danger. | RUN_AWAY. |
| **Return to recovery** · H5 | Outside spawn; Health missing; no earlier row. | RECALL if safe; otherwise RUN_AWAY. RECALL checks its exit threshold. |
| **Release unneeded healing** · H6 | Outside spawn; full Health. | Re-evaluate. |

## DEFEND_SPAWN

Enter only while currently on an allied spawn tile and a local threat needs defense. Stay within spawn, attack legal threats, shop when permitted, and receive healing. Do not chase beyond spawn or answer ordinary rallies.

| Transition | Exact condition | Destination / effect |
| --- | --- | --- |
| **Death** · G0 | Self dead. | DEATH. |
| **Handle displacement** · S1 | No longer on spawn. | Re-evaluate; ordinary danger/recovery decisions apply. |
| **Continue spawn defense** · S2 | On spawn and Spawn threatened. | DEFEND_SPAWN; hold/fight even if outnumbered. |
| **Heal after defense** · S3 | Threat gone; Health missing. | HEALING. |
| **Finish defense** · S4 | Threat gone; full Health. | Clear recovery; Re-evaluate. |

Spawn threatened is a **local** threat, not a distant enemy visible through a ward. This state does not force valid camp/bank protection elsewhere to abandon its objective.

## DEATH

This is a real state. Use the [temporary shop baseline](strategies/shop.md) every dead turn; no position/Health query is required for dead shopping.

| Transition | Exact condition | Destination / effect |
| --- | --- | --- |
| **Remain dead** · X1 | Engine still reports self dead. | DEATH; publish UNAVAILABLE; perform allowed shopping; no living actions. |
| **Respawn** · X2 | Engine reports self alive. | Clear old life-specific attack/capture/protection tasks and lost-bag banking; Re-evaluate. Follow an existing leader, become the next leader using configured preference, otherwise wait in FOLLOW_LEADER after higher-priority recovery/safety checks. |

The death-entry cleanup runs once per death, not repeatedly as a new death every turn.

## Return decision

Run only on startup, explicit Re-evaluate, or respawn. It does not interrupt a valid committed objective. Use current cached observations and one small roster scan; do not run full-map pathfinding inside this dispatcher.

| Priority | Exact condition | Destination |
| --- | --- | --- |
| 1 | Self dead. | DEATH. |
| 2 | On spawn and Spawn threatened. | DEFEND_SPAWN. |
| 3 | On spawn; Health missing. | HEALING. |
| 4 | Danger. | RUN_AWAY. |
| 5 | Recovery needed. | RECALL if safe; otherwise RUN_AWAY. |
| 6 | Saved positive-bag banking or Banking needed. | PREPARE_GEM_BANKING. |
| 7 | Still-owned valid ATTACK or other Joinable rally. | RALLY. |
| 8 | Saved camp personally revalidated, entry safe, and current leader visible or an existing local capture task still valid. | CAPTURE_POINT; C3 may then enter protection if already occupied. |
| 9 | Self is current leader, or current leader is 111 and self becomes the next leader under configured precedence. | LEAD_TEAM. |
| 10 | Otherwise. | FOLLOW_LEADER; follow the current leader or wait for auto-selection. |

Do not resume an old abandoned camp merely because it was once visible. Clear invalid/completed task flags **before** this tree. Clear satisfied recovery requests at/above RECALL_EXIT_FRACTION before checking row 5. Run at most RETURN_DISPATCH_MAX_PER_TURN; if another return is requested that turn, defer discretionary work to the next turn. Safety/death/channel bookkeeping still has priority.

Rally range is a bounded path query with the configured limit. If no valid bound/path result is available within the budget, decline a new optional rally this turn. Do not scan a 100-by-100 map just to decide whether to answer it.

## Shared conditions

| Term | Exact definition |
| --- | --- |
| Health fraction | Current Health / current maximum Health. Exclude shields. |
| Low Health | Fraction <= RECALL_ENTER_FRACTION. |
| Recovery needed | Low Health, or saved recovery request while fraction < RECALL_EXIT_FRACTION. |
| Nearby enemy | Visible enemy champion within LOCAL_THREAT_RANGE of a reachable attack/approach position; wall-separated proximity alone is not supportable combat contact. Use pathfinding baseline's same-snapshot distance queries when needed; fuel deferral is not proof that a visible nearby threat is unreachable. |
| Enemy visible | Any enemy champion in current own/ward vision, regardless of numbers. Used for recall and contact-loss escape checks. |
| Camp can hit | Visible living awake camp can attack the current tile at the next camp action. Exclude sleeping/out-of-range camps; refresh after waking one. |
| Enemy count | Distinct nearby **enemy champions only**. No camp ever counts. |
| Friendly count | Self plus visible living allies within LOCAL_SUPPORT_RANGE who can participate. Exclude active recall/teleport/tribute, HEALING, DEATH, UNSAFE, UNAVAILABLE. An in-range fighting protector may count without assuming it leaves its point. Self counts even while fleeing. |
| Outnumbered | Enemy count > Friendly count. Equality is not a guarantee of safety. |
| Danger | (Nearby enemy AND (Outnumbered OR Low Health)) OR (Camp can hit AND Low Health). Camps affect immediate damage risk, never numerical disadvantage. |
| Recall safe | No visible enemy champion; no camp can hit; legal recall position; no incompatible channel to cancel first. |
| Escape cleared | No camp can hit, and either no visible enemy champion for FLEE_CLEAR_TURNS consecutive own turns, or a nearby enemy is visible, friendlies no longer outnumbered, and Health above the recall-entry threshold. |
| Spawn threatened | Currently on spawn and (Nearby enemy OR Camp can hit). |
| Banking needed | Bag >= BANK_GEM_THRESHOLD, or bag > 0 and submitted team score + bag reaches victory. |
| Camp entry safe | Valid personally resolved reachable camp objective; no Danger at current/approach position. No runner or collector allocation is required. |
| Live rally | BANK/ATTACK; valid chunk; fresh independent timestamp; no known cancellation/completion; ATTACK below absolute lifetime cap. |
| Joinable rally | Live rally; current state allows response; self is not intended BANK carrier; bounded legal path to a useful resolved participation position <= configured type range. An unresolved chunk centre alone cannot certify this range. |
| Reward claimed | Specific group becomes post-claim respawning or equivalent group-specific confirmation. Bag/gold increases elsewhere do not prove it. |
| Own tribute complete | Tracked channel ended, same living life, bag = 0, and team submitted score rose by at least tracked starting bag since start. Score alone is insufficient. |

Seeing one dead monster is not confirmation that the whole group is dead. A legal engine group-state query can confirm the whole group's reward-available state when a spawn tile is in vision. Unknown camp/collector/carrier facts otherwise require inspection, not invented values.

## Saved tasks, coordination, and limits

Keep current state, CAMP/BANK kind, exact objective/collector/carrier identities, pending banking/recovery, contact/search counters, and owned-rally signature/deadline privately. Store one suspended objective plus recovery; no unlimited stack.

Safety summaries do not dictate state transitions. An outnumbered protector publishes UNSAFE and still protects. Stable body numbers come from all allied handles, not the visible subset.

Leadership and rally communication requirements are in communciation.md; it cannot add transitions to this file. The requested C++ implementation target is `bots/leader_party`. There are no allocated nonleader roles, inherited work allocations, or runner acknowledgements. The [chunking plan](strategies/chunking.md) defines map mapping and inspection; the other strategy documents provide temporary MVP baselines to tune from full matches.

These tables replace the earlier state description. They retain explicit self-transitions, add DEATH and DEFEND_SPAWN, and remove REGROUP. Update the diagram and configuration whenever these behaviours change.


## Current leader and automatic replacement

Current-leader bits hold one body number or 111. The leader clears them at Health fraction <= LEADER_MIN_HEALTH_FRACTION and continues its normal safety/recovery transitions. Death cleanup clears a dead leader. No other state change, missing heartbeat, report age, or return of a preferred champion displaces the current leader.

After 111, select automatically using the existing configured leadership order: Heart of Ruin, Ren, Marcella, then remaining bodies by descending maximum starting Health and stable body number. This is selection logic, not six shared eligibility flags. Bodies already in capture continue their task; a change of leader does not force them out of it.

## Banking observation choices

A bank protector patrols the saved exact altar. Keep an already observed saved carrier until PB1-PB6 release it. For a new protection task with several visible channeling carriers, prefer the matching BANK owner, otherwise stable roster slot. Another carrier does not prolong or replace that commitment automatically. This is local task context, not an allocated escort role. The user requests taking turns banking; admission/queue behavior remains to be specified after verifying engine concurrency.

## Requested exploration extension (details not yet agreed)

When no camp qualifies, enter an exploring state looking for/reobserving camps instead of waiting. The exact EXPLORE entry/exit table, leadership ownership, and exploration goals remain pending clarification. Do not invent transition precedence in the route helper or diagram.
