# LARPBOT Global Strategy Review — 2026-10-13

## Competitive position

G2 remains the strongest validated local generation: 16/18 versus `starter-python` across the nine-map, both-sides matrix, with zero reported faults. That result establishes a useful starter-level floor; it does not establish competitiveness against leading teams. Interlock A and Monolith A remain losses in the recorded matrix, and Interlock A also lost the latest smoke test by a wide margin. Per-turn fuel headroom remains unmeasured.

E01 tested whether local visibility could be used for soft camp assignment. The challenger built, then lost all four direct matches to G2 on Corners and Interlock. Across those matches it secured 1,678 gems to G2's 4,038, collected 2,080 to 4,338, and recorded 60 deaths to 39. The challenger was on both sides on both maps. These are four fixed local scenarios, not independent seeded trials. This result rejects the heuristic; it does not show that all coordination or assignment algorithms are bad.

## Competitor evidence

The mission's supplied public pages identify the ladder, WHIM's team page, and two WHIM match groups. The web reader could not extract those client-rendered detail pages; its read-only browser inspection also timed out. Search results exposed the official event overview, which describes a live ladder, but did not expose current ranks, rosters, match statistics or replays. Therefore there is no verified current evidence here about WHIM's composition or behavior. Do not present the historical note that Vendetta is common as a current observation.

No direct local opponent artifact for a leaderboard team is present in the inspected workspace. Future local archetypes must be labeled proxies, not reproductions of private logic.

### Follow-up economic proxy screen (2026-10-14)

The six-body Tavi / Cassi & Issac / Varg / Vesper / Ryth proxy completed four Corners/Interlock matches on both sides against each of the starter and G2. It went 2/4 against each. Against G2 it won Corners B and Interlock A, while G2 won Corners A and Interlock B. The proxy had zero crashes but recorded 19–26 deaths per match. Its high gold totals support the gold-passive mechanism, but do not establish better gem throughput or a stronger overall bot. Keep it as a mixed-strength matchup proxy.

The Vesper-for-Ren draft ablation completed four additional Corners/Interlock matches against G2 on both sides. It went 1/4 and recorded 3,264 submitted gems and 62 deaths versus G2's 3,684 and 54. Vesper won Corners A, but the draft swap did not generalize; reject it as the universal roster. This further shows that an economic mechanism or larger gold number cannot substitute for secured-gem and survival results.

## Assumptions under review

- **Still supported:** permanent tribute, not damage or carried gems, determines the main scoring race; capturing camp rewards and keeping the carrier alive are central.
- **Supported against starter only:** G2's compact camp / capture / bank loop and current draft outperform the prior recovery on the recorded suite.
- **Contradicted for this heuristic:** proximity to a teammate is not enough to reassign camps. Soft exclusion caused a major local regression.
- **Unsupported:** G2 is strong against competitive economic farmers; its metrics against the starter cannot answer that.
- **Unknown:** whether Interlock losses come mainly from objective routing, champion survival, altar interaction, composition, or a combination. End-of-match statistics show the deficit, not the first causal event. Replay-level action diagnosis is still needed.
- **Unknown:** actual per-turn fuel margin. Zero faults at 2,500,000 fuel is only an execution check, not a measured peak-use margin.

## Alternative strategies

| Strategy | Potential benefit | Main weakness / counter | Cost | Next evidence |
|---|---|---|---|---|
| Parallel economic farming with Cassi & Issac | An extra body from one draft choice can clear/capture separate areas and expand map coverage; Vesper can add gold income | Linked deaths can erase two bags; more units may split capture rewards or arrive underpowered | Low-medium: roster-only proxy first, then assignment work if it wins | Side-balanced matches on Interlock, Corners and an open map; track secured gems, deaths and time to 1,000 |
| Stronger single-team combat escort / defensive scorer | Can protect valuable carriers, interrupt enemy captures and reduce PvP losses | Sacrifices one high-throughput farmer; Marcella's stun immunity does not stop locks or lethal focus | Medium: composition and threat-aware routing | Compare G2 against a carrier hunter and parallel farmer; inspect replay turn order around deaths and tributes |
| Route economics and delayed banking | Combine nearby captures to save altar travel and tribute actions | Larger exposed bags can be stolen; enemy locks and capture timing can negate the gain | Medium-high: estimate travel, capture, channel and visible threat costs | Matched banking ablation across both sides and multiple maps; compare gems lost per death and secured gems/100 rounds |

## Recommended direction

Keep G2 unchanged as champion. Abandon proximity-only deconfliction. First build an explicitly labeled parallel-farming economic proxy based on a six-body Tavi / Cassi & Issac / Varg roster, with Vesper as the next economic choice. This tests whether body count and independent economic roles can outpace the current five-body G2 team without introducing a new coordination policy. Use it as a benchmark only after its own performance is demonstrated.

Retain the six-body proxy and Vesper roster as counter-archetypes, not replacements. The next isolated candidate tests Varg's Monster Strength emblem: the rules say five shards give the same shard stats plus 10% camp damage, while Power takes six shards for its extra stat shard and no passive. This is tightly coupled to Varg's grouped camp role and has a direct throughput mechanism. Begin with Corners and Interlock on both sides, then use an open map as a held-out contrast if the focused screen is favorable. Keep the starter matrix as a regression suite, not the primary competitive target.

## Next development programme

1. Preserve G2 and its build; preserve the rejected E01 source/results.
2. Build the parallel-farming proxy in `bots/opponents/` and establish that it is actually stronger than the starter before treating it as a difficult benchmark.
3. Compare proxy vs G2 on both sides and prioritize Interlock/Corners plus one open map.
4. Use replay or structured event evidence to locate the earliest scoring divergence and inspect lethal losses.
5. Add fuel instrumentation only if the runner exposes it; otherwise report the actual limitation rather than an inferred margin.
6. Retry read-only public competitor research when the pages are accessible; no ranked testing or official submission.
