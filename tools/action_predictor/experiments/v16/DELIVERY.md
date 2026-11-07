# Learned Fish policy: execution-oriented direction

The user requested a bot that learns strategic choices and execution from Fish
sequences. Next-command scores remain a comparison, not the final deliverable.
No hand-designed farming, banking, combat or pathfinding policy is substituted.

Implemented in learned_policy/: a goal-conditioned full command policy, learned
latent goal proposal and retention, persistent world-goal hypotheses/belief/age,
causal actor state and an SDK4 command dispatcher. Types and spatial execution
heads train; warm M01 and reusable P05 are learned components, not manual rules.
Current/earlier personal observation inputs, all cached visible champ/camp tokens
and all public altar/spawn coordinates are supplied, with explicit gap/memory
availability. Goal positions are learned from achieved future states, not named
Fish intent. The forecast horizon controls labels only, never a switch deadline.

All433071TRAIN and14439DEV rows are assembled in actual actor/event order,
including true intervening own-root counts and action-count summaries. Last16
actual observations/actions remain bounded detailed history; older history is
compressed/partly unavailable. Recurrent objective state carries forward across
sequence chunks; no sampled turns are treated as adjacent. Future achieved
positions enter losses/postprediction evaluation only. At inference, choose from
past state, execute the command, then filter using the ACTUAL own action/outcome.
A failed/rejected proposal is not assimilated as a demonstration.

The two-fit pilot is frozen: L00reset-goal control and L01persistent-goal policy,
same150599parameters/inputs/loss/budget. Full original DEV commandNLL checkpoint
rule retained; goal-forecast auxiliary is not a checkpoint-selection criterion.
Ten contracts and real-input preflight passed; no learning quality is inferred
from tests. Fresh requested Solxhigh review after each fit remains mandatory.

Shipping stages, still required:
1. Train/evaluate the two policies and audit causal rawPRE actor parity,
   sequence likelihood, goal conditioning/persistence and all-category regressions.
2. Export the trained actor to a native/no-Torch runtime with numerical parity;
   create an isolated bot entry and liveSDK4 personal-observation bridge. Reuse
   SDK legality/command ABI, not the existing bot's hand-designed strategic loop.
3. Resolve learned purchase arguments, ambiguous entity/ground target kinds,
   draft decisions and historical2/3-to-current4 semantics. The dispatcher refuses
   unsupported arguments rather than fabricating Fish purchases or targets.
4. Closed-loop behavior requires a separately authorized evaluation phase.
   Replay accuracy/goal forecasts do not establish autonomous playing strength.

The host Actor.act path already connects prediction to SDK calls and then commits
actual results, but the native/live bridge and complete command coverage are not
finished. This is therefore NOT presented as the eventual shipped bot. No model
is promoted or deployed. Existing bot files/predictors/checkpoints are preserved.
Both75-game reserved partitions remain sealed; no matches/proposed-action
simulations/downloads. PR11 stays DRAFT/open/unmerged, no auto-merge or queue.
