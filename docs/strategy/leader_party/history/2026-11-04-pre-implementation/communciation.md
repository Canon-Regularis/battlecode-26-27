# Team communication: bits and meanings

Leader-party binary specification, based on commit 66b1cd6 with the user's explicit corrections; **not implemented**. The filename communciation.md is retained from the original request. Read with [state_machine.md](state_machine.md), and [config.md](config.md).

Capacity: **8 live shared bytes = 64 bits**, plus 1,024 bytes of draft memory that becomes read-only during play. Each bot has private state and vision. Sources: [rules](../../cambc/GameRules.md), [Python API](../../cambc/api/BotAPIPython.md).

## What the committed starter writes

| Memory | Current starter use |
| --- | --- |
| Shared bits 0–31 | Last written round number, little-endian unsigned 32-bit integer, written by each starter body. |
| Shared bits 32–63 | Unassigned by the checked starter. |
| Draft bytes 0–10 | Literal UTF-8 hello world. |

Sources: [bot.py](../../../bots/starter-python/src/bot.py), [draft.py](../../../bots/starter-python/src/draft.py). Replace the starter round write when implementing this protocol; it would overwrite strategy fields. This documentation does not change bot code.

## Revised payload layout

Bit 0 is the least significant bit of byte 0; bit 63 is the most significant bit of byte 7. Interpret the buffer as one little-endian unsigned 64-bit word. All bodies use these same fixed offsets.

| Global bits | Width | Field | Writer |
| --- | ---: | --- | --- |
| 0–5 | 6 | Leader / command anchor chunk | Current leader. |
| 6–8 | 3 | Current leader | Current leader clears to 111 on low Health; the next leader selects itself using the existing preference logic. |
| 9–11 | 3 | Leader message | Same writer as anchor chunk. |
| 12–17 | 6 | Rally target chunk | Verified rally owner, eligible replacement, or expiry cleanup. |
| 18–19 | 2 | Rally type | Same rally writer. |
| 20–25 | 6 | Enemy concentration chunk | Any body with an eligible new observation and sufficient fuel. |
| 26–28 | 3 | Enemy champion count | Writer of the matching concentration report. |
| 29–30 | 2 | Safety slot 0 | Body 0. |
| 31–32 | 2 | Safety slot 1 | Body 1. |
| 33–34 | 2 | Safety slot 2 | Body 2. |
| 35–36 | 2 | Safety slot 3 | Body 3. |
| 37–38 | 2 | Safety slot 4 | Body 4. |
| 39–40 | 2 | Safety slot 5 | Body 5. |
| 41–63 | 23 | **Reserved; no signal assigned** | Preserve; do not allocate extra flags or metadata without a user decision. |

All six body slots stay reserved even on smaller teams. Ignore nonexistent slots.

### Bit budget

The existing locations, current-leader identity, leader message, rally type, enemy count, and six safety summaries occupy bits 0–40: **41 bits used, 23 bits reserved**. Bits 29–40 retain their committed meaning as safety summaries, not report ages.

There are no leadership offers, report-age slots, runner assignments, acknowledgements, shared handover cooldowns, rally-owner fields, timestamps, or initialization-marker bits added to this layout.

## Reading and changing fields

A numeric field's lowest bit has weight 1; later bits have weights 2, 4, 8, and so on. Set bits contribute their weight. Enums must be replaced as whole fields, not combined as independent flags.

    value = (word >> start) & ((1 << width) - 1)
    mask = ((1 << width) - 1) << start
    replacement = (word & ~mask) | ((value << start) & mask)

Validate values before writing. Read the latest buffer immediately before mutation, preserve unrelated fields, and update coupled fields coherently. If execution resumed in a later round, discard the old buffer and re-read. Do not assume an old read/modify/write can safely span suspension.

## One global chunk model

Leader/command, rally, and enemy reports use the **same map-specific chunk IDs**, defined in [strategies/chunking.md](strategies/chunking.md): a balanced grid with maximum side 15, at most 7×7 = 49 chunks, and fixed six-bit location fields. Read that file for the exact integer mapping, inverse bounds, canonical camp anchors, and bounded inspection algorithm.

The contract it must satisfy:

| Requirement | Meaning |
| --- | --- |
| Deterministic mapping | Every body maps the same tile to the same ID on the same map, including odd dimensions. No gaps, overlaps, or rounding disagreement. |
| Packing limit | Valid IDs are 0 through chunk_count - 1, at most 0–48. ID 63 means absent/invalid; other out-of-range values are invalid. |
| Lookup | Given an ID, resolve its bounds/tiles and one or more legal inspection positions. A geometric centre may be blocked or unwalkable. |
| Visibility | Every chunk tile is within seven Chebyshev steps of the nominal centre. Radius-eight champion vision covers it in open terrain. Use SDK hypothetical vision to assess occlusion at legal alternatives. |
| Search fallback | If target is not visible at the first position, inspect other reachable positions within a configured budget. Do not treat invisibility as death or objective completion. |
| Dynamic targets | Leader/enemy may have moved since publication. Re-read the report; do not chase a permanently cached chunk. |
| Static targets | Resolve the intended altar/camp from visible or draft-known map information. Multiple objects inside one chunk need a disambiguation rule. |

**A single centre cannot guarantee full chunk visibility on every map.** Walls and bushes occlude vision. Keep the shared grid fixed and use private bounded inspection routes instead of subdividing terrain into extra shared IDs. Failed inspection means unknown, not proof of absence.

This replaces both the old ten-tile grid and the intermediate unspecified seven-bit chunk proposal. All bodies must adopt the new six-bit offsets/sentinel together. Static altars and camps are indexed from map data; a chunk with several objectives still needs exact task identity.

For each six-bit chunk field, low-to-high weights are 1, 2, 4, 8, 16, 32:

| Field | Bits in increasing weight order |
| --- | --- |
| Leader / command | 0, 1, 2, 3, 4, 5 |
| Rally | 12, 13, 14, 15, 16, 17 |
| Enemy | 20, 21, 22, 23, 24, 25 |

For example, chunk ID 42 is binary 101010: set offsets +1, +3, +5 within whichever chunk field is being written. It is valid only on maps with at least 43 chunks. On 100×100 it is row 6, column 0.

## Current leader: bits 6–8

Read binary as bit 8, bit 7, bit 6.

| Binary | Value | Meaning |
| --- | ---: | --- |
| 000 | 0 | Allied body 0 is the current leader. |
| 001 | 1 | Body 1. |
| 010 | 2 | Body 2. |
| 011 | 3 | Body 3. |
| 100 | 4 | Body 4. |
| 101 | 5 | Body 5. |
| 110 | 6 | Reserved invalid value; never select it. |
| 111 | 7 | NONE: no current leader. |

**User correction:** these three bits are the current leader's identity, not a separate roster-allocation mechanism. When the leader reaches the configured low-Health leadership threshold, it writes **111** and follows the state machine for recovery. The next leader auto-selects using the existing configured preference logic; there are no offers, nominations, or shared eligibility bits.

Entering capture, protection, banking, a rally, or another state does not by itself change the current leader. Leadership identity and the body's current state are separate. Bodies already capturing continue their own state-machine behavior across a leader change. A dead leader cannot remain current; the existing death cleanup clears its identity to 111.

The body numbers come from all allied champion handles sorted by integer identity, including hidden/dead bodies. Never renumber from the visible subset or after death. Cassi and Issac each occupy a slot.

## Leader message: bits 9–11

Read binary as bit 11, bit 10, bit 9.

| Binary | Value | Message | Anchor chunk means |
| --- | ---: | --- | --- |
| 000 | 0 | NONE | Ignore anchor as an actionable order. |
| 001 | 1 | MOVING | Current actual leader chunk; follow/inspect. |
| 010 | 2 | WORK_CAMP | Camp currently being worked; resolve the observed group and use the state machine. |
| 011 | 3 | PROTECT_CAMP | Cleared group's chunk; confirm allied capture and protect. |
| 100 | 4 | BANK_APPROACH | Intended altar chunk; assistance subject to ordinary eligibility/range. |
| 101 | 5 | BANK_CHANNEL | Altar chunk with a reported channel; confirm local carrier/channel before protection. |
| 110 | 6 | HOLD | Party waiting/formation anchor; still use FOLLOW_LEADER, not a REGROUP state. |
| 111 | 7 | OBJECTIVE_FINISHED | Last objective chunk; inspect own saved task before releasing it. |

Setting bit 9 alone means MOVING; bit 10 alone means WORK_CAMP; both mean PROTECT_CAMP. Setting bit 11 alone means BANK_APPROACH. These are mutually exclusive values, not multiple simultaneous announcements.

Leader messages report current activity; they do not allocate runners, collectors, escorts, or inherited work. Only the current leader publishes its leader message/anchor. If the current-leader field is 111, there is no current leader to follow; a previous message must not force a new assignment.

The anchor cannot simultaneously hold the leader location and an objective location. Its meaning comes from the message enum, as in the committed chunk-based layout. Keep the exact observed local camp/altar privately when resolved.

No leader message is proof of hidden success. There is no "gold submitted" game action: gold/gems are **collected** from camps; gems are **submitted** at altars. OBJECTIVE_FINISHED is an advisory event, not a global accounting update for every carrier/collector.

## Rally type: bits 18–19

Read binary as bit 19, bit 18.

| Binary | Value | Meaning |
| --- | ---: | --- |
| 00 | 0 | NONE; ignore rally chunk. |
| 01 | 1 | BANK; ask eligible nearby bodies to approach/escort a carrier at an altar. |
| 10 | 2 | ATTACK; ask eligible nearby bodies to join the fight. |
| 11 | 3 | Reserved invalid value. **REGROUP removed.** Treat as no joinable request; diagnose as invalid. |

ATTACK -> BANK requires clearing bit 19 and setting bit 18. Do not OR them and accidentally produce 11.

| Lifecycle rule | Required behaviour |
| --- | --- |
| Priority | BANK may replace ATTACK. An existing live same-type request retains the slot. |
| Range | Before joining, resolve a useful target/participation tile and use configured per-type path distance. A near chunk centre does not prove a far edge target is in range. |
| Identity | Retain creator/target/task identity privately; verify a shared replacement token before any refresh/clear if such a token is later approved. No token field is currently allocated; its encoding is unresolved. |
| Refresh | Only the creator of the current attempt refreshes it. Responders do not prolong a dead creator's request. |
| Attack end | Creator cancels for Outnumbered, target death, contact-loss limit, or absolute lifetime cap. Expiry ends commitment even during combat. |
| Replacement | Old creator must not delete a replacement, even if type and chunk happen to match its former request. |
| Cleanup | Any body may clear a **provably** expired request. |
| Local protection | Once in PROTECT_POINT — BANK, direct carrier/altar observations govern protection. Rally changes alone do not release it. |

A "matching BANK request remains live" used to mean the same locally saved carrier/altar request, still fresh and unexpired. Comparing type/chunk alone is insufficient, especially with multiple altars in a chunk. **The revised protection transitions no longer depend on this condition.** Rally ownership still needs reliable record identity for responders and creators.

## Enemy report: bits 20–28

Chunk and count form one observation. Count bits 26, 27, 28 have weights 1, 2, 4. Binary is displayed as bit 28, bit 27, bit 26.

| Binary | Count |
| --- | ---: |
| 000 | 0: no positive report; ignore chunk as a threat target. |
| 001 | 1 |
| 010 | 2 |
| 011 | 3 |
| 100 | 4 |
| 101 | 5 |
| 110 | 6 |
| 111 | 7 |

Count distinct **visible enemy champions** in the chunk, never camps. Three bits avoid conflating three enemies with four or more. One observation is a lower bound under partial vision; it is not the total number of opponents in that area.

When optional fuel permits: group visible enemies by chunk, nominate the greatest count, break local ties by smallest chunk ID. Replace stale reports with a positive sighting. While a report is fresh, prefer a larger count; refresh the same chunk only if observing at least its stored count. Do not sum different reporters' overlapping counts or erase a remote warning because no enemies are visible locally.

The report needs independent freshness. Skipping this optional computation does **not** skip essential local danger/attack decisions. Local fight counts cross chunk boundaries, and camps never count toward Outnumbered.

## Safety summaries: bits 29–40 (unchanged from the last commit)

Slot i starts at bit 29 + 2*i. Read its pair as high bit then low bit.

| Binary | Value | Status | Meaning |
| --- | ---: | --- | --- |
| 00 | 0 | AVAILABLE | Active, locally safe, uncommitted. Consider as a reunion destination only after local checks. |
| 01 | 1 | COMMITTED | Doing a camp/protection/banking/rally job. Cannot assume it will leave to help. |
| 10 | 2 | UNSAFE | Fleeing, locally threatened/outnumbered, or defending a threatened spawn. Avoid as a safe escape destination. |
| 11 | 3 | UNAVAILABLE | Dead, recalling, or healing; unsuitable for immediate help. Not proof of death. |

Publish in this order: DEATH/RECALL/HEALING -> UNAVAILABLE; RUN_AWAY/DEFEND_SPAWN or current danger/outnumbering -> UNSAFE; ongoing objective/channel/rally -> COMMITTED; otherwise AVAILABLE. An outnumbered protector stays in PROTECT_POINT and publishes UNSAFE.

Example slot 0: bit 29 alone = COMMITTED; bit 30 alone = UNSAFE; both = UNAVAILABLE. Replace 01 with 10, rather than adding a flag and producing 11.

Safety has no exact Health value, is not a state ID, and is not a leadership offer. The state debug colour remains private/drawn information. First-report validity and stale writers require the final metadata contract.

## Initialization, validity, and remaining space

Proposed empty payload: current leader NONE (111), leader message NONE, all three chunk fields 63, rally NONE, count zero, all safety slots UNAVAILABLE, reserved bits zero. A designated initializer must write this once before normal use. **Who initializes and how others know it is complete are still to be finalized.** All-zero bytes must not be interpreted as a live leader at chunk zero.

The existing rally lifetime and observation-validity rules still need implementation handling. This document does not allocate additional owner, age, epoch, or marker fields to solve them. If implementing an existing rule requires a change to the shared layout, raise that specific issue instead of silently spending reserved bits.

Chunk mapping and inspection remain as in strategies/chunking.md. A chunk containing several camps or altars needs personal observation to resolve the intended objective; no exact static-objective ID encoding is substituted for the existing chunk fields.

## Confirmed dynamic-team behavior

There are no nonleader role allocations. Leader messages and rallies remain informational/coordination signals; state_machine.md alone defines transitions. Bank protection keeps one observed carrier and patrols the current altar as requested. No new shared carrier/escort assignment field is introduced.
