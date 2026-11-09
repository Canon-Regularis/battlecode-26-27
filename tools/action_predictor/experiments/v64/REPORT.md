# V64 - map and trajectory weight adaptation

The full-map update failed its fitting-game comparison. Selection retained epoch zero, preserving **310/513 (60.43%) combined movement** and **318/513 (61.99%) direct movement** on the unchanged research evaluation. The requested 80% requires **411 correct moves**: the combined planner remains 101 short. No model was promoted, and no strategy or playing-strength gain is established.

This changes existing weights rather than adding a network. Starting from each corresponding selected V59 checkpoint, it trains 48,097 map, context, GRU, base-movement, geometry, observed-heading and prior-command parameters. Code readout, code embeddings, legacy goal weights and V62 objective-head weights stay frozen. Unlike the earlier V56 map experiment, this starts after signed trajectory features and their V59 adaptation. Candidate construction, support, routing, goal retention and all inputs are unchanged.

All 1,607 expanded fitting windows are retained. Each of four fitting-game folds trains the other 24 games for two passes and validates the original 64 windows in its held eight games. Batches accumulate eight complete windows with common actual movement/observation denominators. Loss is supported movement cross-entropy plus KL to the matching selected V59 code teacher. Selection maximizes combined planner correctness, subject to code protection, nonnegative replay utility and at least 10% goal activity. Evaluation answers never select weights.

| Epoch | Combined moves | Direct moves | Direct NLL | Correct inferred codes | Goal activity | Utility sum |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 0 | 1124/1997 | 1237/1997 | 1.163820 | 2416/2945 | 595/2941 | 42.3333 |
| 1 | 1109/1997 | 1222/1997 | 1.181377 | 2420/2945 | 651/2941 | 44.3333 |
| 2 | 1085/1997 | 1206/1997 | 1.174520 | 2426/2945 | 677/2941 | 46.5833 |

The second epoch loses 39 combined moves and 31 direct moves despite slightly improving inferred-code accuracy and the goal-progress proxy. This is evidence against this update configuration, not proof that map information is sufficient or that all map learning fails. Training changes all 22,528 map parameters in every fold; protected head tensors remain exact. Gradient clipping and tensor deltas are recorded in `weight-inspection.json`.

Parent verification reproduced all 12 fold measurements, original fold predictions, schedules, denominators, 1208 optimizer-update records, finite optimizer states, frozen tensors, selection, both complete assessment forecast sets and 64 streaming turns. The tuning run took 997.88 seconds inside its frozen 3,600-second cap. Twelve focused tests passed, including exact synthetic full-batch versus accumulated AdamW parity and causal-prefix checks. No subagents or delegated reviews were used.

## Combined outcome of this continuation

Three further weight interventions were completed: [V63 movement-supervised readout](../v63/REPORT.md), this full-map adaptation, and [V65 hard-choice margin readout](../v65/REPORT.md). All selected their starting checkpoint. V63 increased goal activity while hurting movement. V65 almost disabled planning and failed its activity guard. This run also hurt movement. Original and rejected checkpoints remain separate; the playing bot is unchanged.

The fitting-only output audit found the correct move among the fixed direct/candidate-route choices on only 1,598/1,997 movement rows (80.02%). A perfect hindsight selector would therefore barely reach the target on those rows; a learned selector would have to make almost no mistakes on the covered rows. This is only a bound for that fixed choice set, not an accuracy ceiling for a redesigned movement model. It does not prove that more training, different features or different supervision would work.

The 80% objective remains **unachieved**. These are conditional replay movement predictions with observed past commands, inferred behavior/goal labels, inherited fitting-fold exposure and repeatedly exposed research evaluation games. Goal activity and a replay-progress proxy do not demonstrate autonomous strategy. Historical full-command/category, reliability and multi-seed requirements remain open. No evaluation-dependent tuning, denominator changes or planner-disabling shortcut was accepted.
