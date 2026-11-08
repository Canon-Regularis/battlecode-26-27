# Learned sequential Fish policy

This namespace implements a learned goal-conditioned command policy and a
stateful execution core. It replaces no existing predictor or playing bot.
The executing sandbox bot is the eventual deliverable; cached next-command
evaluation alone does not complete that deliverable.

`model.py` learns four latent goal hypotheses, their current proposal, retention
and goal-conditioned execution from recorded actor trajectories. Future achieved
positions supervise a goal forecast. They are neither verified Fish intentions
nor inference inputs. Command types and all spatial heads train; the existing P05
integer distribution is reused independently. There are no manually ranked
farming, banking, attack or retreat objectives, route choices or switch deadlines.

All original TRAIN/DEV rows remain. Sequence gaps carry real root/round counts,
past action-count summaries and explicit missing history. Detailed history keeps
the existing bounded action/observation windows. The recurrent state therefore
does not claim lossless memory or supervision at every unobserved action.

L00 resets goal state at each selected decision; L01 carries the learned forward
state. They share inputs, weights/parameterization, initialization seed, loss and
fit budget. This contrast tests this particular memory mechanism. It does not
identify Fish's internal strategy. Training uses earlier actual demonstrations;
the executing actor updates from its own actual command and returned outcome.

The likelihood and decoder use the same normalized latent mixture. Execution
marginalizes goals and ranks complete modeled commands, including individual
priority values. It never compares a point command with an opaque fallback
weight. Shops remain an observed type bucket with unavailable purchase arguments;
every original shop remains a strict failure. Entity coordinates retain the
original identity ambiguity.

From the repository root, using the pinned interpreter:

```powershell
.venv-action-predictor/Scripts/python.exe -m tools.action_predictor.learned_policy.fit L00
.venv-action-predictor/Scripts/python.exe -m tools.action_predictor.learned_policy.analysis L00
.venv-action-predictor/Scripts/python.exe -m tools.action_predictor.learned_policy.export L00
.venv-action-predictor/Scripts/python.exe -m tools.action_predictor.learned_policy.portable_roundtrip L00
.venv-action-predictor/Scripts/python.exe -m tools.action_predictor.learned_policy.actor_roundtrip L00
.venv-action-predictor/Scripts/python.exe -m tools.action_predictor.learned_policy.completion L00
```

Fit commands refuse existing attempt directories. Reuse saved checkpoints for
inference; do not retrain to reproduce a report. L01 requires its own invocation
after the fresh requested post-L00 review. No extra seeds are allocated.
See `experiments/v16/policy-design.json`, `STATUS.md` and `DELIVERY.md`.

`actor.py` and `portable_actor.py` expose decide/execute/commit. A proposed move
that returns blocked is assimilated as a blocked attempt. A rejected command
does not become a demonstration. State is bound to one actor/game; identifiers
are metadata, never neural features. The dispatcher uses SDK calls and rejects
unavailable purchases and unresolved target identities, without a hand-designed
strategy fallback. SDK call-recording tests do not run a game.

`personal_inputs.py` reconstructs causal inputs from personal snapshots and
completed own actions. `input_roundtrip.py` checks this new boundary against
existing caches using already-recorded PREs. `portable.py` and
`portable_priority.py` independently implement the trained core and retained P05
using NumPy. The full Torch adapter is still used to construct/verify host inputs.
NumPy availability in the game's WASI sandbox is not assumed. Native build,
live SDK4 personal snapshot encoding, draft decisions, unavailable purchase
arguments and ambiguous target kinds remain shipping work. Historical engine2/3
evidence does not establish current SDK4 behavioral equivalence.

No matches, proposed-action game simulations, replay downloads, playing-bot
changes or deployment are authorized here. Both reserved75-game partitions stay
sealed. PR11 remains DRAFT, open and unmerged; no auto-merge or merge queue.
