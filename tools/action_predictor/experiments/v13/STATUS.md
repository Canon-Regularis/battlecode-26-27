# V13 continuation checkpoint

The user's current request is to align likelihood and decoding, then test better
goal information and persistent memory. Do not replace it with a new architecture
search or promote an aggregate-only gain.

Completed before any fit:

- Shared `command_mixture.FallbackDistribution`, observed-command `log_mass` and
  MAP `decode`; duplicate point explanations marginalized consistently.
- Exact finite-distribution tests and all-DEV U00 winner-probability identity
  (maximum log error 6.7e-16, zero available-command ordering violations).
- No-refit D01: 12,044 strict DEV successes, 0.6130 macro F1. Against A00: 549
  rescues, 127 regressions, net422; paired accuracy interval +2.606 to +3.238pp.
  Likelihood is unchanged apart from 1e-6 numerical precision. Not promoted.
- Q-only and fixed0.9/0.1 mixture controls frozen. DEV both get11,953 strict
  commands, with different command sets/type metrics. Full-TRAIN controls run
  separately before the first fit.
- All433,071 TRAIN rows/470eligiblegames and original14,439DEV rows/25games have
  repaired57 proposals, current-goal and causal-memory features. DEV proposal
  array is byte-identical to C03. Raw PRE serving reproduces347 cases exactly
  for features/descriptors/commands/modes, both historical engines.
- FullTRAIN candidate-grid features equal the immutable rich NPZ at emitted
  coordinates. Shared-Q target NLL differs from frozen G00 by at most1.6e-6.
- Reachable oracle union: DEV13,371/14,439; naturalTRAIN270,063/288,801.
  These are support ceilings, not achieved learned accuracy.
- TRAIN memory traverses8,022,592 earlier actual own roots. Personal PREs are
  available for1,899,147; other PREs stay explicitly unavailable. Goal identity
  evidence is updated only after its actual earlier action, at its historical
  PRE positions. No current answer, future, smoothing or sampled-turn stitching.

`protocol-r3.json` is the current frozen fit protocol. R3 adds consumer input
binding to r2; architecture, three arms and experimental rules are unchanged.
R1 failed before any fit because v7 target shards lack grid. All old protocols,
failed-preparation evidence and exact old source hashes are retained in `frozen`.
Source checkpoint commit: `3ed6215` (local; prior pushed PR head39dd724).

Next execution, without asking the user again:

1. Finish full-TRAIN Q00/U00 controls if their session is running; do not restart
   or overwrite completed control files.
2. Run `python -m tools.action_predictor.consistent_study B00` exactly once.
   Its verified input receipt is already available. Max35 rounds, improvement
   .0001, patience6 on every originalDEV row. Retain every round.
3. Complete B00 analysis, selection opportunity accounting, probability-contract
   audit and raw-PRE parity. Then launch a FRESH requested GPT6.1Sol xhigh review
   with the exact user sentence:
   “Read my thread and find all the errors my model has now made and how we could improve all of it substantially”
   Give full thread/code/results/previous objections. Follow async next/end-turn
   instructions; no B01 fit before this review. Do not reuse an old reviewer.
4. After addressing review, run B01 (current goals) once, fresh review; then B02
   (current goals+forward goal memory) once, fresh review. No extra pilot or repeat
   seed allocation from a weak/negative result. Controls share architecture,
   support, loss, decoder, data, seed, row order and regularization; zero feature
   blocks isolate added information.
5. Report paired B01-B00 and B02-B01/B00 comparisons, natural TRAIN/DEV, category
   and movement-continuation/change results and opportunity capture. Keep data
   sufficiency and Fish internal-goal claims unresolved unless evidence supports.
6. Update only DRAFT PR11, never merge/ready/automerge/deploy. Link immediately
   after pushing. Preserve unrelated benchmarks/frequency preparation/untracked
   R00 evidence. Both reserved partitions remain sealed; no matches/simulations,
   downloads, bot changes or repeated unchanged495-game audit.

Use `.venv-action-predictor/Scripts/python.exe` from repository root. Further
commands: `consistent_analysis B00`, `consistent_selection B00`,
`mixture_contract_audit B00`, `consistent_roundtrip B00` (likewise other arms).
Every shop remains strict/unassessed; sparse altar/teleport/submit uncertified.
No observed loss includes unavailable shop arguments. Model-level support still
misses1,068DEV commands and cannot meet every-category targets by selection alone.
