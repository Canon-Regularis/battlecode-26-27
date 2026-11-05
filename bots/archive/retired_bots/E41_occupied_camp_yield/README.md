# E41 — yield occupied camp groups (unpromoted altar specialist)

E41 starts from G2 and adds one conditional to empty-handed farm goal selection: skip a camp group while a visible ally occupies one of its spawn tiles. If that leaves no available targets, it immediately falls back to G2's complete goal set. Banking, combat, draft and navigation are unchanged.

Built successfully and run at `--fuel 100000` (2,500,000 Python fuel). The 42-match pilot covered four maps, both sides, against G2, E05A, the carrier hunter and altar denial; then the altar-denial suite was extended to all nine maps and both sides. All matches had zero bot faults. The statistics export does not report fuel consumption.

| Opponent | Matches | Wins | E41 submitted | Opponent submitted | Net secured gems | E41 deaths |
|---|---:|---:|---:|---:|---:|---:|
| G2 | 8 | 2 | 6,956 | 8,076 | -1,120 | 113 |
| E05A | 8 | 4 | 7,030 | 7,096 | -66 | 105 |
| Carrier hunter | 8 | 1 | 5,918 | 8,088 | -2,170 | 122 |
| Altar denial | 18 | 9 | 12,974 | 12,557 | +417 | 262 |
| **Total** | **42** | **16** | **32,878** | **35,817** | **-2,939** | **602** |

On the same nine maps and sides against altar denial, G2 scored 7/18 and 11,843 - 13,471 = -1,628. E41 gained two wins, submitted 1,131 more gems, denied 914 more, and improved net differential by 2,045; it also had 72 more deaths. Keep E41 as an unpromoted altar-denial specialist, not a universal bot. Its hunter result is a clear regression. Do not replace G2.

Raw statistics remain under `results/`, with local replays under `replays/E41_occupied_camp_yield/`.
