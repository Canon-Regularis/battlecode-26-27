# E36 — Jungle emblem for Cassi & Issac

Based on E05A. Only `buy_shard` changes: Cassi and Issac buy Strength Jungle shards until they complete one Jungle Strength emblem (five shards), then resume the existing Power Strength shard. Both builds give Strength; the Jungle emblem adds 30% less camp damage. The hypothesis is that this small purchase rule cuts linked-pair deaths to camps without adding tactical decision logic.

Full matrix: nine maps, both sides, against G2, the carrier-hunter proxy, altar denial, and starter-python (72 matches total) at `--fuel 100000` (2,500,000 Python fuel). All matches reported zero faults. Results are summarized in `bots/larpbot/COMPETITIVE_BENCHMARKS.md`; raw JSON is in `results/`, and replays are in `replays/E36_pair_jungle_emblem/`.

Decision: retain as an unpromoted pressure specialist. It improved the hunter and altar-denial suites but lost score and wins against G2 and starter-python. G2 remains canonical. These fixed map/side runs are not independent randomized trials; the runner exposes no seed option.
