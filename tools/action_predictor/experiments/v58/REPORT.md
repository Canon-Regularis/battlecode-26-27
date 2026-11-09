# V58: signed previous-command history

Movement reaches **309/513 (60.23%)**, compared with V57's 298/513 (58.09%). The new correction rescues 21 errors and introduces 10. Movement NLL improves from 1.3246 to **1.2924**. The 80% target remains unmet: it needs 411 correct moves, **102 more** than this checkpoint.

The no-fit audit examined only the 32 fitting games. Repeating the last executed move alone did not improve the V57 fitting score, but it rescued 905 errors while introducing 911. Previous-turn net direction rescued 777 and introduced 671. These counts motivated a context-dependent correction; they are fitting diagnostics, not achieved evaluation scores or an oracle ceiling.

Historical move vectors come from the original hash-bound actor index, strictly from the completed previous own turn. Every current query identity/round and chronological boundary is checked. Historical move counts and unsigned net displacement reproduce the existing descriptor exactly. The initial window query receives no earlier-window history. No current command is used as an input. This adds signed information previously omitted from an already-required command history, not hidden Fish goals.

Eight candidate features encode cosine alignment and exact sign match with the latest executed move and previous-turn net movement, with age and path straightness modifiers. Coefficients depend on V55's frozen recurrent state and soft code. V57 and its parents remain frozen. Two zero-initialized corrections were compared in four fitting-game folds, with the same original held windows and epoch-zero eligibility.

Selection chose the **1,048-parameter head with a 16-unit hidden layer at epoch eight**: 1,213/1,997 fitting-validation moves versus 1,156/1,997 for V57. Full fitting completed **208 updates / 98,544 movement presentations**, reaching 7,926/12,318 in-sample moves (64.34%). Only the selected setting was evaluated on the unchanged 513 research evaluation moves.

Code and goal predictions remain exactly unchanged: 573/699 inferred codes, 51/98 endpoints within two tiles and 15/98 exact. The result is improved conditional movement prediction, not a demonstrated strategic or playing-strength gain.

Verification reproduced the prior-command features and existing history descriptors, all five cached banks, all 40 validation measurements, selection, schedules, denominators and finite optimizer states. All 3,644 original fitting/evaluation forecasts reproduce exactly; 32 streaming turns match. Tests cover signed direction, net movement, age, missing-history rejection, causal prefixes, initial parity and gradients. No subagents were used.

The opt-in `CommandMovementPredictor` uses `.cambc/action-predictor/v58/selected.pt` plus bound V57/V55 parents. Its `predict` method additionally requires `previous_moves` after the first query: the list of executed `(dx, dy)` moves in the **completed previous own turn**, including moves whose PRE frame was unavailable. An empty list means that turn had no moves; missing history raises an error. The first query and actor/32-turn resets clear this history. State must remain separate per actor, and callers must reset it at genuine gaps. Supplying predicted commands instead changes the evaluated teacher-forced setting.

Original checkpoints and the playing bot remain untouched. Repeated evaluation exposure, inherited fitting-fold exposure, observed past commands, conditional movement, sparse goals and unnamed inferred codes remain material limits. Category/full-command quality, calibration, multiple seeds and autonomous performance are not established.
