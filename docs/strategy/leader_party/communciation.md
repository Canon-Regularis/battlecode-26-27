# Team communication: bits and meanings

Current leader-party proposal; **not implemented**. The filename communciation.md is retained from the original request. Read with [state_machine.md](state_machine.md), [team_plan.md](team_plan.md), and [config.md](config.md).

Capacity: **8 live shared bytes = 64 bits**, plus 1,024 bytes of draft memory that becomes read-only during play. Each bot has private state and vision. Sources: [rules](../../cambc/GameRules.md), [Python API](../../cambc/api/BotAPIPython.md).

## What the code currently writes

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
| 0–5 | 6 | Leader / command anchor chunk | Current leader; narrowly permitted retained-work publisher while no leader exists. |
| 6–8 | 3 | Leader roster slot | Current owner handing over, highest eligible claimant, or validated dead/stale-owner cleanup. |
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
| 41–46 | 6 | One leadership-eligibility offer per body | Each body writes its own bit only. |
| 47–63 | 17 | **Reserved; no signal assigned yet** | Preserve until the protocol is finalized. |

All six roster slots stay reserved even on smaller teams. Ignore nonexistent slots.

### Budget change

| Change from the original coordinate proposal | Bits |
| --- | ---: |
| Leader coordinates: 14 -> chunk ID: 6 | Save 8 |
| Rally coordinates: 14 -> chunk ID: 6 | Save 8 |
| Enemy chunk ID: 7 -> 6 | Save 1 |
| New leader identity | Spend 3 |
| New leader messages | Spend 3 |
| New eligibility offers for Health/role-based election | Spend 6 |
| Fixed payload: 52 -> 47 | Net save 5 |
| Unallocated: 12 -> 17 | 17 bits remain |

Six-bit leader/rally locations save **16 coordinate bits**, and the enemy chunk saves one more bit. Leadership identity/messages/eligibility use 12 bits. Relative to the immediately preceding seven-bit chunk proposal, this is three additional free bits: payload 50 -> 47, reserved 14 -> 17. Eligibility offers are a design choice because safety summaries cannot establish hidden Health/role eligibility.

No freshness fields are silently included in this table. The reserved space still needs a complete ownership/expiry/assignment design; the payload is **not yet an implementation-ready protocol**.

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

## Leader slot: bits 6–8

Read binary as bit 8, bit 7, bit 6.

| Binary | Value | Meaning |
| --- | ---: | --- |
| 000 | 0 | Roster body 0 owns leadership. |
| 001 | 1 | Body 1. |
| 010 | 2 | Body 2. |
| 011 | 3 | Body 3. |
| 100 | 4 | Body 4. |
| 101 | 5 | Body 5. |
| 110 | 6 | Reserved invalid value; never nominate it. |
| 111 | 7 | NONE: no current leader. |

Only the slot owner can run LEAD_TEAM. A nomination is not permission to ignore self Health, safety, or a committed task; the nominee rechecks before acting.

Stable slots come from all allied champion handles sorted by integer identity, including hidden/dead bodies. Never renumber from the visible subset or after death. Cassi and Issac each occupy a slot.

## Leader message: bits 9–11

Read binary as bit 11, bit 10, bit 9.

| Binary | Value | Message | Anchor chunk means |
| --- | ---: | --- | --- |
| 000 | 0 | NONE | Ignore anchor as an actionable order. |
| 001 | 1 | MOVING | Current actual leader chunk; follow/inspect. |
| 010 | 2 | WORK_CAMP | Assigned camp group's chunk; find exact assigned group and enter capture when allowed. |
| 011 | 3 | PROTECT_CAMP | Cleared group's chunk; confirm allied capture and protect. |
| 100 | 4 | BANK_APPROACH | Intended altar chunk; assistance subject to ordinary eligibility/range. |
| 101 | 5 | BANK_CHANNEL | Altar chunk with a reported channel; confirm local carrier/channel before protection. |
| 110 | 6 | HOLD | Party waiting/formation anchor; still use FOLLOW_LEADER, not a REGROUP state. |
| 111 | 7 | OBJECTIVE_FINISHED | Last objective chunk; inspect own saved task before releasing it. |

Setting bit 9 alone means MOVING; bit 10 alone means WORK_CAMP; both mean PROTECT_CAMP. Setting bit 11 alone means BANK_APPROACH. These are mutually exclusive values, not multiple simultaneous announcements.

An outgoing leader publishes a camp order before entering CAPTURE_POINT and relinquishing leadership. A successor preserves an unfinished order. With no leader, the original publisher may maintain **only its matching retained work record**. Its exact replacement token/age is still to be encoded.

The anchor cannot simultaneously store a distant new leader location and an old camp location. During a retained work order it stores the **objective**, deliberately. Followers already assigned continue that work instead of pursuing a new moving leader.

No leader message is proof of hidden success. There is no "gold submitted" game action: gold/gems are **collected** from camps; gems are **submitted** at altars. OBJECTIVE_FINISHED is an advisory event, not a global accounting update for every carrier/collector.

## Leadership eligibility: bits 41–46

Bit 41 + roster slot is that body's offer:

| Bit | Meaning |
| --- | --- |
| 0 | Not offering leadership, or unknown/uninitialized. |
| 1 | At last valid publication, all team_plan.md leadership conditions passed. |

Conditions include Health strictly above LEADER_MIN_HEALTH_FRACTION, no immediate danger, no committed job or higher-priority transition, and completed handover cooldown. An available safety summary does not substitute for this bit.

Use fixed configured precedence to choose among **fresh** offers. Only the body writes its own offer; cleanup/election must not fabricate another body's Health. Clear own bit before leaving LEAD_TEAM, entering a committed task, dying, or becoming otherwise ineligible. A nominee verifies conditions again on its own turn.

Freshness/first-report validity is unresolved. Do not implement election by trusting an indefinitely set bit.

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
| Identity | Retain creator/target/task identity privately; verify a shared replacement token before any refresh/clear. No final token field has been allocated yet. |
| Refresh | Only the still-owning creator refreshes an ongoing attempt. Responders do not prolong a dead creator's request. |
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

## Safety summaries: bits 29–40

Slot i starts at bit 29 + 2*i. Read its pair as high bit then low bit.

| Binary | Value | Status | Meaning |
| --- | ---: | --- | --- |
| 00 | 0 | AVAILABLE | Active, locally safe, uncommitted. Consider as a reunion destination only after local checks. |
| 01 | 1 | COMMITTED | Doing a camp/protection/banking/rally job. Cannot assume it will leave to help. |
| 10 | 2 | UNSAFE | Fleeing, locally threatened/outnumbered, or defending a threatened spawn. Avoid as a safe escape destination. |
| 11 | 3 | UNAVAILABLE | Dead, recalling, or healing; unsuitable for immediate help. Not proof of death. |

Publish in this order: DEATH/RECALL/HEALING -> UNAVAILABLE; RUN_AWAY/DEFEND_SPAWN or current danger/outnumbering -> UNSAFE; ongoing objective/channel/rally -> COMMITTED; otherwise AVAILABLE. An outnumbered protector stays in PROTECT_POINT and publishes UNSAFE.

Example slot 0: bit 29 alone = COMMITTED; bit 30 alone = UNSAFE; both = UNAVAILABLE. Replace 01 with 10, rather than adding a flag and producing 11.

Safety has no exact Health value and is not a state ID. The state debug colour remains private/drawn information. First-report validity and stale writers require the final metadata contract.

## Initialization, validity, and remaining space

Proposed empty payload: leader slot NONE (7), leader message NONE, all three chunk fields 63, rally NONE, count zero, all safety slots UNAVAILABLE, all eligibility bits zero, reserved bits zero. A designated initializer must write this once before normal use. **Who initializes and how others know it is complete are still to be finalized.** All-zero bytes must not be interpreted as a live leader at chunk zero.

| Outstanding contract | Why it is needed |
| --- | --- |
| Independent leader/command freshness | A dead or suspended publisher must not leave a permanent live command. |
| Eligibility/status freshness | Election must not use old Health offers; safety summaries cannot masquerade as current reports. |
| Independent rally freshness and absolute creation/deadline | Refresh must not reset attack lifetime; a later observer must still be able to expire it. |
| Enemy report freshness | Unrelated leader/rally writes must not refresh old sightings. |
| Replacement identity | Prevent an old publisher clearing a new same-type/same-chunk record. No owner ID is allocated yet. |
| Party side-job delivery | Exact runner/group assignment, acknowledgement, skipped-node counter, and handover persistence; prevent duplicate runners or the party assisting a detached job. |
| Exact objective resolution | Multiple camps/altars/targets in one chunk cannot be distinguished by chunk ID alone. |
| Wraparound / suspension / initialization | Short modulo timestamps must never revive old messages after a wrap; resumed old writes must be rejected. |

**Bits 47–63 remain unassigned**, not a promise that every item above fits in 17 bits. Consider carefully designed scheduling/leases, immutable draft data, or revising the payload. Do not quietly omit a required field or invent a private value as if it were team-wide.

Chunk mapping and inspection are specified in the chunking strategy. The metadata/assignment design remains an explicit next review topic. This document defines the proposed values and budget without claiming those unresolved contracts are solved.

