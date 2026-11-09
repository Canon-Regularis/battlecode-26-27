# Matched recurrent access and gradient horizon

This V33 research study follows Astra's recommendation to test longer genuine
history before adding strategic objectives. V32 restored and reviewed 97,152
eligible cached rows across 60 groups. Its normalizer uses fitting groups only.

The same fresh direct policy runs in three configurations: A resets extra
recurrent memory every eight roots; B carries memory but detaches gradients every
eight; C carries memory and detaches every 32. All reset at actual missing-root
gaps and actor starts. All retain the same explicit 16-command/observation inputs,
so A is not history-free. Every command is scored before its actual occurrence is
assimilated. Metadata and direction labels are excluded from prediction inputs.

All variants use identical initial tensors, actor permutations, examples, losses,
32-node optimizer windows, denominator, update cadence and 12 checkpoint
opportunities. There are no pretrained components. Primary tuning selection
balances change and continuation joint NLL; secondary selection uses aggregate
modeled-command NLL. Both policies are reported. Assessment is loaded only after
selection is saved. Missing shop arguments are excluded from likelihood and every
shop remains a strict complete-command failure.

`protocol.py` freezes committed source bytes and every used input, and requires
an actual bound independent review before fitting. A/B/C execute separately;
each subsequent arm requires fresh reviews of all preceding results. No repeated
fits, extra seeds, runtime changes, matches or reserved-game access are automatic.

Assessment includes joint/conditional command accuracy, every action family,
movement strata, false positives, macro-F1, paired group intervals and genuine
16/32-root windows. The original 14,439-row DEV and G00/L02/JP02 are retained as
secondary regression checks. Their different training exposure prevents a causal
comparison with the fresh model. Research exposure and availability enrichment
remain limitations. A positive offline result would establish predictive memory
benefit within this configuration, not recovered intent or playing strength.

Run tests with `.venv-action-predictor/Scripts/python.exe -m unittest
tools.action_predictor.history_horizon.test_contract -v`. After committing and
freezing, obtain prefit review before invoking `history_horizon.fit A`.
