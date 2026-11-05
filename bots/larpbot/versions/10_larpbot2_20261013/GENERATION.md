# G2 — LARPBOT2

Validated 2026-10-13 and preserved before E01 experiments.

- Draft priority: Tavi, Varg, Ren, Ryth, Vendetta, then remaining picks.
- Gameplay: starter-derived camp clearing/capture/banking with immediate positive-bag banking and lethal-only carrier attack priority.
- Recorded suite: 16/18 against `starter-python` on nine maps and both sides; zero reported faults.
- Source identity: copied from canonical `bots/larpbot/src` immediately after its successful build. The full benchmark summary is included in `RAPID_UPGRADE_RESULTS.md`.
- Known weaknesses: Interlock A and Monolith A losses. Local matches completed at the 2,500,000-per-turn budget with zero reported faults; exact peak fuel use and unused margin were not recorded.

Use the root `cambc.toml` and SDK when rebuilding; this archive is intentionally source-only and contains no recursive version archives or replay bundles.
