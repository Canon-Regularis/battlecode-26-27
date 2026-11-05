# Accounting and channel-guard trial

C++ clone of `leader_party_tuned`, frozen as `c02_record_guard`. Experimental; the original champion is retained.

Enabled changes: guarded recall/tribute starts and life/channel/score-aware bank-completion bookkeeping. Original dispatch, combat, draft, Subhan planning, native navigation and tuned constants remain preserved. No leader/follower/rally/inspection strategy is enabled.

Training:653-307,36-28 directly against champion. Reserved validation:749-391,37-39 directly. Full 86-map/15-opponent matrix:1,718-862,90-82 directly; common opponents 1,628/2,408 versus champion 1,635/2,408. Zero normal-fuel VM faults; matched logged errors 81 versus 273. Lower errors did not establish a winning improvement.

See the [final report](../../docs/strategy/leader_party/feature_experiment_results.md) and [frozen artifact receipt](../../docs/strategy/leader_party/evaluation/2026-11-04/features/c02_record_guard-artifact.json).

WASM SHA-256: `605207958ed3f3dc778f03b0b122dfa9c7469f09e19dd7b48c979a47532e73d7`.

Build: `.venv/Scripts/cambc.exe build lp_feature_c02_record_guard --release` from the repository root. Strength results use the frozen `.cambc/features/c02_record_guard.zip`; do not silently replace that archive with a new build.
