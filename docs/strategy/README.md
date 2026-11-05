# CAMBC 2026 — Strategy Research

## Latest design proposal — 15 October 2026

Start with [Anchor: strategy and implementation plan](ANCHOR_STRATEGY_AND_IMPLEMENTATION_PLAN_2026-10-15.md). It incorporates the live D1/gold_diamond failures, audits what past experiments actually implemented, and specifies safe farming, fight admission, linked-cat survival and bounded regrouping. It is a researched proposal, not a validated replacement bot.

Supporting evidence: [mechanics audit](MECHANICS_AUDIT_2026-10-15.md), [past experiments](PAST_BOT_AUDIT_2026-10-15.md), [implementation gaps](IMPLEMENTATION_GAP_AUDIT_2026-10-15.md), and [live top-team replays](LIVE_REPLAY_NOTES_2026-10-15.md).

The material below is the original 13 October research snapshot. Its draft recommendations and API assumptions must be read in that historical context; the latest plan and current SDK resolve later corrections.

> Event: `cambc2026a` · Status: **research / implementation blueprint** · Source snapshot: 13 October 2026

This directory records the team's strongest *candidate* strategies, mechanical interactions, implementation priorities, and experiments. Its purpose is to help build a reliable, adaptive winning bot—not to assume that an attractive paper exploit is guaranteed to work in live matches.

## Read in this order

| Document | Purpose |
|---|---|
| [MECHANICS_AND_EXPLOITS.md](MECHANICS_AND_EXPLOITS.md) | Rule interactions, abuse cases, prerequisites, counterplay, falsifiable tests |
| [CHAMPIONS_AND_BUILDS.md](CHAMPIONS_AND_BUILDS.md) | Champion comparisons, shard economics, draft recommendations and matchups |
| [BOT_PLAYBOOK.md](BOT_PLAYBOOK.md) | How to turn the ideas into a resilient, map-aware decision-making bot |
| [EXPERIMENTS.md](EXPERIMENTS.md) | Reproducible test matrix, baselines, metrics and promotion criteria |

## Current working thesis

**Prioritise secure gems per round, not raw kills, damage, or gold.** A first team to tribute 1,000 gems wins; after round 2,000, tributed gems, *lifetime gold earned*, then champion kills break ties. Unbanked gems can be stolen on champion death. A champion killed by a camp loses those gems entirely.

The most promising combined approach:

1. **Farm correctly and efficiently.** Fight complete camp groups, occupy a valid spawn tile, maintain five-round uncontested capture, and account for respawn timers and end-to-end travel.
2. **Convert money to throughput.** Buy useful damage/growth upgrades at the right times, especially on Tavi (field purchase) and multi-target Varg.
3. **Bank gems safely.** Shorter channels reduce risk, but long channels are sometimes acceptable behind good protection or with Marcella's stun immunity.
4. **Deny opponent conversion.** Altar locks, capture contests, attacks against rich carriers and selective respawn denial can outperform direct farming.
5. **Validate special interactions.** Capture-payout/tribute timing and ability/action combinations must survive local tests before becoming core logic.

## Strategy priority board

| Priority | Candidate | Why it is valuable | Evidence state |
|---|---|---|---|
| P0 | Reliable autonomous farming + capturing + tributing | Required to win at all; punishes inexperienced bots | **Rule-backed**; implementation untested |
| P0 | Map-aware camp routing and self-assignment | Reduces travel, target duplication and missed capture rewards | **Engineering hypothesis** |
| P0 | Tavi field shopping | Removes repeated return-to-spawn cost | **Rule-backed** |
| P1 | Varg splash farming | One attack damages several nearby camps | **Rule-backed**, map-dependent |
| P1 | Enemy altar-lock intervention | 10 gold can cancel an expensive enemy channel | **Rule-backed**, requires reach/access |
| P1 | Marcella courier / anti-stun role | Tribute ignores ordinary damage and she is immune to stun | **Rule-backed**, still vulnerable to death and locks |
| P1 | Camp theft / contest | Capture rewards depend on occupation, not who killed monsters | **Rule-backed**, circumstance-dependent |
| P1 | Gem-carrier interception | Kill steals carried gems and awards gold | **Rule-backed**, tactical execution untested |
| P2 | Tribute snapshot on capture payout | Bank a large capture reward using a channel started with 1–10 gems | **Rule-backed interaction**, geometry/timing untested |
| P2 | Cassi & Issac extra-body farming | One draft pick provides two acting champions | **Rule-backed**, severe linked-death risk |
| P2 | Vendetta kill-refresh chain | Each kill resets both ability cooldowns | **Rule-backed**, needs reliable last hits |
| P2 | Attack-reset lock removal / movement combos | Potential action economy edge | **Must test** |

### Champion shortlist

- **Default 3 picks:** Tavi / Varg / Marcella.
- **Isolated-camp variant:** Tavi / Stellar / Marcella.
- **4 picks:** Tavi / Varg / Marcella / Cassi & Issac **only if** the extra-body upside justifies the linked-death risk; Stellar, Vesper or Willow are safer alternatives by map/opponent.
- **5 picks:** Tavi / Varg / Marcella / Stellar / Cassi & Issac as an aggressive starting hypothesis, **not** a validated optimal roster.

The draft should adapt to geography, visible enemy picks and measured performance. Opponent teams are allowed to select the same champions as us; our own selections cannot repeat.

## Evidence labels used throughout

- **`RULE`** — Explicitly stated in `GameRules(1).md` or `BotAPIPython(1).md`. This does *not* certify our implementation.
- **`INFERENCE`** — Follows from documented rules under stated assumptions; outcome may be terrain- or strategy-dependent.
- **`TEST`** — An API or simulation interaction not decisively specified by the docs; must be verified in a local runner.
- **`COUNTER`** — A plausible response from another bot, not a guaranteed opponent behaviour.

### Important corrections / guardrails

- **No direct gem handoff.** Gems are awarded to champions present at capture and can move to a killer on champion death. Do not assume allied champions can transfer them on demand.
- **The draft phase does not provide `bc.game_map.camp_groups()`.** It returns empty during drafting, per the API. Draft precomputation should focus on map terrain, altars, spawn regions and anything otherwise *actually exposed*. Discover/assign camp groups during gameplay.
- **One successful ability cast per champion turn.** A kill-resetting ability does not enable a same-turn infinite-cast loop.
- **Ranged attack usually competes with ordinary movement.** Do not assume free kiting.
- **Starting a channel precludes other actions until completion or cancellation.** Do not plan to fight or move during a tribute.
- **A completed channel resolves at champion-turn start, after the round's capture phase.** A channel reaching zero at the end of a turn has not yet banked the gems.
- **Emblem passives do not stack across duplicates.** Shard stats do. Treasure + Vesper's passive is the documented additive exception.
- **Camp and player observations obey visibility restrictions.** Team vision is not automatically shared; eight-byte memory can communicate compact information.
- **Don't claim an engine exploit until measured.** Especially verify path legality, item edge cases, AoE visibility, channel state and any timer off-by-one interactions.

## Sources

Primary evidence: the user-provided `GameRules(1).md` and `BotAPIPython(1).md`, event `cambc2026a`. These research docs are self-contained and refer to their section headings. If those reference files are checked into the repo, link them here at their actual paths.

## Maintenance

After each test or rules change: record engine version, seed/map, both drafts, reproduction steps and outcome in [EXPERIMENTS.md](EXPERIMENTS.md). Promote a candidate from `TEST` to `RULE + OBSERVED` only when a repeatable local run demonstrates it. Do not erase failed hypotheses; document what falsified them.
