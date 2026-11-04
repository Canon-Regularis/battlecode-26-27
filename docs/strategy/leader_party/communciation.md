# Experimental shared-memory protocol

Release coordination is **disabled** by `Config::coordination`. Autonomous scoring and direct visible protection remain active. The implementation and native tests retain this protocol for later controlled experiments. The pre-implementation layout is retired.

One little-endian 64-bit word:

| Bits | Meaning |
| --- | --- |
| 0-5 | Leader guidance chunk; 63 absent |
| 6-8 | Leader slot; 7 absent |
| 9-11 | Activity message |
| 12-17 | Rally chunk; 63 absent |
| 18-19 | NONE/BANK/ATTACK; 3 invalid |
| 20-22 | Creator slot |
| 23-33 | Full creation round |
| 34-45 | Six two-bit safety summaries |
| 46-56 | Full leader heartbeat round |
| 57 | Initialized marker |
| 58-60 | Version 1 |
| 61-63 | Reserved zero |

Stable roster slots are sorted engine champion IDs. Slot zero initializes once. Unknown versions, future timestamps and out-of-range rounds disable interpretation. Full timestamps cover the normal 2,000-round game without wrapping. Native tests cover late timestamps, ABA replacement, expiry and leader leases.

Immutable attempt identity is creator plus full creation round. Age 12 expires it. No creator may reuse an identity in the same round. A matching owner can cancel; expiry or confirmed creator death can clear it. The implemented publisher creates BANK requests with a 15-round retry spacing; ATTACK creation and BANK-over-ATTACK replacement are not enabled. Remote chunk inspection/responders are not implemented. Local bank protection only uses current personal vision.

Experimental election uses Heart, Ren, Marcella, then starting HP and stable slot preference. A candidate claims its modulo-roster window if alive, >50% HP and outside recovery/escape. Heartbeats expire after three rounds. A returning candidate cannot preempt a live leader. Leadership identity survives ordinary activity changes. A free follower can join a uniquely resolved nearby visible leader camp; otherwise it plans locally immediately.

Shared writes recheck round and fuel immediately before writing. No hidden ally Health or remote enemy reports are used. The experimental path has not been proven against every forced-suspension interleaving and is disabled in the release.
