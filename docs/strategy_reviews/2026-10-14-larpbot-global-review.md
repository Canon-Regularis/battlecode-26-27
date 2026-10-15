# LARPBOT Global Strategy Review — 2026-10-14

## Decision

Keep G2 (`bots/larpbot`) as the only promoted generation. None of the tested challengers showed a repeatable, broad improvement over it. The tested mission remains a local evaluation only; no official submission or ranked action was performed.

## Current champion evidence

G2 wins 16 of 18 fixed map/side matchups against `starter-python`, with 17,707 submitted gems, 18,608 collected gems, 254 deaths and zero reported bot faults. This is the best validated candidate in the workspace. It loses Interlock A and Monolith A in that matrix. The local runner does not expose a seed flag, so these fixed scenarios should not be represented as independent randomized trials. Matches used the 2,500,000-per-turn budget and completed without faults. Exported statistics do not show peak fuel use, so the unused margin is unknown; that is a telemetry gap, not evidence that G2 fails the stated budget.

## Challenger and proxy results

| Candidate | Evidence | Decision |
|---|---|---|
| E01 `larpbot3` | 0/4 vs G2 on Corners/Interlock; lower submitted gems, more deaths and fewer kills | Reject. Soft camp deconfliction likely over-spread the team, but summary data do not prove the cause. |
| E02 `economic_farmer_proxy` | 2/4 vs starter and 2/4 vs G2 on Corners/Interlock; zero faults but high deaths and side-sensitive scores | Retain only as a mixed-strength economy/roster proxy. It is not evidence of a stronger economic opponent. |
| E03 `vesper_gold` | 1/4 vs G2; 3,264 submitted gems and 62 deaths versus G2's 3,684 and 54 | Reject the general roster swap. |
| E04 `varg_monster` | 4/8 vs G2 on four maps, near-equal aggregate score and deaths; then 0/2 vs starter on Interlock | Reject for universal promotion. No evidence supports a map-specific default yet. |

All recorded E01–E04 matches used 2,500,000 fuel and reported no faults. Raw JSON/source snapshots are in `bots/archive/rejected_experiments/`; replay bundles remain under `replays/`.

## Strategic read

G2's strongest evidence remains broad performance against the starter baseline. The current experiments suggest that isolated economy, roster, or camp-damage changes do not reliably improve scoring. The losses on Interlock and Monolith, plus candidate death counts, make hostile-champion interactions and gem loss plausible areas to inspect. This is a hypothesis, not a demonstrated root cause.

The next useful benchmark is a separate carrier-hunter proxy with an economic fallback. It should be evaluated on both sides of Interlock and an open map against G2, recording submitted and collected gems, deaths, gold, and faults. Inspect existing replay/event evidence first so the proxy reflects an observed failure mode. Keep the champion unchanged until a candidate improves repeatably across sides and at least one distinct opponent archetype.

## Competitive intelligence and submission

The official event site describes a live ladder, but available read-only access did not expose current standings or reliable public team/match details. No claim about current competitor strategy is made from that evidence. [CAMBC 2026 official event site](https://2026a.battlecode.co.uk/)

For a manual submission, use the verified local bundle `bots/larpbot_submission_final.zip` or build directly from `bots/larpbot`. Do not use any challenger directory as the submission source. The bundle contains the seven `src/*.py` files expected for this bot and matches the protected G2 source snapshot. This review does not perform an upload or official submission.

## 2026-10-14 follow-up — current meta signal and rally tests

The user reports that strong teams split for farming, then regroup to submit and cross dangerous areas. This is a user-provided observation, not independently verified live ladder data.

E05A (Cassi & Issac / Stellar / Tavi) reached 8/18 vs G2 while collecting slightly more gems than G2 but submitting fewer and dying more. E05B (Cassi & Issac / Varg / Vendetta) went 7/18. E06's increased pair retreat threshold went 5/18. E07's bag recall had the same aggregate as E05A. E08 local-vision rally and E09 shared-memory position beacon each matched E05A's 8/18 result and aggregate against G2; their same-roster comparisons were tied overall. All reported zero faults. The new meta behavior is therefore not validated as useful by our current policy implementation.

**Direction:** keep G2; preserve local artifacts; instrument actual beacon writes/reads and escort actions; create dedicated carrier-hunter and altar-lock proxies; retest rally timing against those adversaries. These fixed, deterministic-if-supported scenarios are screening evidence, not independent statistical samples. Continue to prohibit official submissions and ranked actions.
