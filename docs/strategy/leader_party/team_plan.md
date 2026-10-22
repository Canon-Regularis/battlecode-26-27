# Team plan: leader and travelling party

Status: current design, not bot implementation. [State transitions](state_machine.md) define interruptions; [configuration](config.md) owns every tunable value; [communication](communciation.md) defines shared fields. The older parent meta_strategy.md is historical.

## Roles

| Role | Responsibility | Selection |
| --- | --- | --- |
| Team leader | Own the leadership slot and run LEAD_TEAM's existing route planner. | Fixed roster precedence plus current eligibility. |
| Followers | Stay near the leader; join its confirmed camp objective; protect an observed allied capture. | Available bodies not assigned another job. |
| Runner | Clear and collect one passed gold/gem group, then bank or rejoin. | One specifically nominated body per skipped node, from RUNNER_PREFERENCE. |
| Camp collector | Occupy the reward region once the group is cleared. | Existing collector first; otherwise one deterministic selected body. |
| Bank carrier | Bring its own gems to an altar and channel. | Each body's own banking need; Marcella is the preferred gem collector when present. |
| Bank escorts | Guard a visible carrier at its saved altar. | Eligible nearby followers or BANK rally responders. |

Roles are task data, not additional states. A leader stops being leader when it leaves LEAD_TEAM. A collector/escort may be healthy and still be ineligible to lead because its task must finish.

Draft composition is not being changed by this rework. Heart, Ren, and Marcella are leadership preferences **when drafted**, not a requirement to draft all three. Analysis of picks remains in [analysis.md](../analysis.md).

## One leader and a deterministic baton

Compute LEADER_PREFERENCE once: named types first, remaining bodies ordered by maximum starting Health, ties by stable roster slot. Do not sort by mutable item Health each turn. Current Health is an eligibility check, not the ranking.

A body offers leadership only when all of these are true:

| Check | Required condition |
| --- | --- |
| Alive and ready | Alive, not channeling, not at spawn needing healing/defense. |
| Health | Health fraction > LEADER_MIN_HEALTH_FRACTION. |
| Safety | No Danger and not currently RUN_AWAY, RECALL, HEALING, or DEFEND_SPAWN. |
| Job | In FOLLOW_LEADER, or the current LEAD_TEAM owner; no higher-priority banking, rally, camp, protection, or recovery transition is due. |
| Handover delay | Its LEADER_RECLAIM_DELAY_ROUNDS has elapsed. |

Publish this offer in the dedicated eligibility bit. It is distinct from AVAILABLE safety status: a healthy protector must finish its job; an uncommitted 45%-Health follower might be locally safe but cannot lead at a 50% threshold.

| Event | Required behaviour |
| --- | --- |
| Startup / no leader | From fresh eligibility offers, the highest-ranked eligible body is the only body allowed to claim an empty leader slot. If offers are unknown, wait for publication; do not assume all-zero memory means eligible. |
| Leaving LEAD_TEAM for **any** state | Before publishing the new state, withdraw own offer and release the leader slot. Nominate the highest-ranked remaining fresh eligible body, or leave NONE. Retain a pending work command as described below. |
| Leader Health reaches or falls below threshold | Hand over even if above the recall threshold. Then follow, flee, bank, or recover according to the normal transition table. |
| Nominee's next turn | Recheck its own conditions before running the planner. Reject the nomination if no longer eligible and select the next fresh eligible offer. |
| Leader dies | Its death hook releases leadership. If it has not run yet, another body may release a slot whose referenced champion is confirmed dead. |
| Leader/report expires | Discard routing permission from that report, then elect from fresh offers. A missing heartbeat is not proof of death. |
| Former preferred leader recovers | Offer leadership again, but do not displace a current valid leader merely because the preferred body returned. Take over at the next vacancy. |
| No eligible bodies | FOLLOW_LEADER waits safely near the last valid party anchor, otherwise spawn. Higher-priority danger/recovery/banking still runs. Do not force a committed or injured body into leadership. |

Every bot re-reads the leader slot immediately before executing LEAD_TEAM actions. Only the owner may run them. A former owner's private state can still say LEAD_TEAM until its next turn; it has no permission to act as leader after the shared slot changes.

A nominee that selects a different state before ever entering LEAD_TEAM must also release its nomination. Apply this invariant after every state decision: **if self owns the leader slot but the selected state is not LEAD_TEAM, hand over before acting**. Otherwise an injured nominee could leave the slot occupied while recalling.

**Freshness is essential:** the communication document allocates eligibility bits, but the age/initialization mechanism is still a protocol decision. Do not implement election from indefinitely old bits.

## Handover must preserve the group's objective

A camp work order is set **before** the initiating leader leaves LEAD_TEAM to attack. Followers must not miss the order just because the next leader has already been appointed.

| Leader message | What the party should do |
| --- | --- |
| MOVING | Follow the current leader; no new camp order implied. |
| WORK_CAMP | Locate and confirm the saved camp task; eligible followers start CAPTURE_POINT. |
| PROTECT_CAMP | Join protection of an allied collector at the saved camp; do not split rewards unnecessarily. |
| BANK_APPROACH / BANK_CHANNEL | Locate the carrier/altar; enter through ordinary BANK rally or direct visible-carrier checks. The message itself does not prove the carrier/channel is visible. |
| HOLD | Keep a safe formation while runners return or leadership is being settled. |
| OBJECTIVE_FINISHED | Hint to inspect the current task for completion; never proof of reward or submission. |
| NONE | No actionable command. |

The message has an **anchor chunk**: leader's current chunk for MOVING/HOLD; objective chunk for work/protection/banking/completion. That distinction is necessary when a new leader is elsewhere. The field is named leader/command chunk in communication.md.

A successor inherits a valid pending work order. Before planning a different destination, it joins that task when entry conditions allow; joining CAPTURE_POINT relinquishes the baton again. This can leave **no active leader while everyone is capturing/protecting**, which is valid. Their saved tasks continue. On completion, a free eligible body becomes leader and resumes routing.

The outgoing work publisher may maintain that same work record while no leader exists, after verifying its local record token still matches. It must stop writing when a new leader takes over or the record is replaced. This is not permission to run LEAD_TEAM.

A chunk and message cannot identify which of two camps in the same chunk is intended. Use a locally observed leader attack/assignment or an already saved group identity. If ambiguous, move to inspect; do not choose a random group. The exact objective identity/replacement token needs the final protocol or a shared draft-time camp ordering. This is recorded as an open contract, not hidden in follower code.

## Joining camp work and protection

A visible, confirmed leader attack on a camp creates a party assignment for available followers. If the SDK cannot expose the attack target after the leader's action, publish the work order before attacking and resolve it against visible camp groups; do not infer an attack from mere proximity.

Followers transition to CAPTURE_POINT on that assignment, unless an earlier safety/banking transition applies. A follower that sees an allied body already capturing a cleared group's rewards may instead enter PROTECT_POINT for that group. A hostile occupant is not an allied capture.

The runner's detached job is excluded from automatic party assistance: a leader who intentionally walked past it continues the main route. Followers seeing that **known detached runner** do not all turn around. Ambiguous assignments must be resolved before dispatch; the feature is gated on the runner assignment contract below.

## Passing small nodes repeatedly

Use an iterative counter; no recursive function is needed. A "node" is a connected camp group, eligible only if **every** monster is a gold/gem cluster.

| Step | Decision |
| --- | --- |
| 1. Detect | Passing within SIDE_NODE_DISTANCE of a small group, safe approach, no visible enemy champion or awake camp that can damage the runner on that approach. |
| 2. Check cap | Consecutive skipped nodes < SIDE_PASS_MAX_CONSECUTIVE. |
| 3. Check party | Moving party size > SIDE_PASS_MIN_PARTY_SIZE, counted before detaching. |
| 4. Choose runner | First eligible body in RUNNER_PREFERENCE, excluding leader and already detached bodies. Must be in FOLLOW_LEADER, meet Health/distance limits, have no pending recovery or bank-worthy bag, and be safe/uncommitted. |
| 5. Assign once | Save exact group and runner identity. Only that runner enters CAPTURE_POINT. Increment the skip counter only after the assignment is accepted. |
| 6. Continue | The reduced party follows the leader to the next node. Repeat while every check remains true. |
| 7. Stop | At the first node where the cap/party/runner checks fail, the party takes the node together if entry is safe. If the node itself is unsafe, avoid it; the limit never forces a dangerous capture. |
| 8. Rejoin | Runner finishes collection, banks if needed, otherwise follows the leader. After the main stop completes, hold safely for absent surviving runners up to PARTY_REJOIN_WAIT_ROUNDS; then continue. Reset the skip counter when the main stop completes. |

Example: five moving bodies, minimum remaining size two, maximum consecutive skips one. The party skips node A with one runner; the remaining four stop at node B. With maximum skips three, it may send one runner to A, one to B, one to C, and the last two stop at D. Fewer eligible runners or party-size limits stop the sequence earlier.

A handover must not reset the counter or forget detached assignments. These are **party-wide facts**, not just the old leader's private memory. Their transport/acknowledgement is not yet encoded in the eight-byte layout. Until that contract is finalized, repeated dispatch and automatic protection around detached collectors are not ready to implement. The completed state tables do not solve assignment delivery.

Equal-speed runners cannot catch a party that walks forever. Main-party camp fights plus the bounded hold create rejoining opportunities. The hold may expire without everyone returning; it is not a guarantee of reunion.

## Collector replacement and reward ownership

If a living allied collector is already occupying the cleared group's capture region, keep it. Otherwise the task assignment chooses one present eligible collector using the configured gem/gold precedence and stable slot tie-break. Guards stay outside spawn tiles so they do not split income. Do not independently elect from different visible subsets: collector identity and replacement must use the same acknowledged task-assignment contract as runner identity. Recheck occupancy immediately before moving onto the region.

If the collector dies or leaves and **no ally remains in the region**, guards return to CAPTURE_POINT; its actions elect/approach a collector and later return them to protection. Never wait forever for a dead collector. An enemy standing on the group does not count as the friendly collector.

Death of a route leader alone does not abandon an unrelated valid protection job. The relevant death is that of the collector or carrier for the protected task.

## Detailed strategy files

The [chunking strategy](strategies/chunking.md) specifies balanced chunks of at most 15×15, six-bit area addresses, objective indexing, and visibility-aware inspection. [Pathfinding](strategies/pathfinding.md), [altar selection](strategies/altar_selection.md), [ward placement](strategies/ward_placing.md), and [shopping](strategies/shop.md) now contain temporary MVP specifications, clearly marked for later replacement. Native navigation temporarily uses call/fuel limits instead of a resumable hard expansion cap. The existing leader route planner still chooses objective order.

