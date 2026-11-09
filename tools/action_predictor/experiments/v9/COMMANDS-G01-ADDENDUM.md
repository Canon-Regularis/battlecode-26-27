# G01 and cost-correction executed commands

Repository-root commands with the pinned .venv-action-predictor/Scripts/python.exe interpreter:

```powershell
python -m tools.action_predictor.movement_study G01
python -m tools.action_predictor.movement_analysis G01
python -m tools.action_predictor.movement_roundtrip G01
python -m tools.action_predictor.movement_loss_diagnostics G01
python -m tools.action_predictor.movement_pair_analysis
python -m tools.action_predictor.movement_serving_actual P05
python -m tools.action_predictor.movement_serving_actual G00
python -m tools.action_predictor.movement_serving_actual G01
python -m tools.action_predictor.movement_loss_diagnostics G00
```

The python abbreviation above denotes the exact pinned interpreter; local commands.jsonl retains executable argv and original redirected transcripts are preserved. All cost timing occurred after training and earlier diagnostics completed. Old reduced-kernel receipts remain preserved. No further fit occurred during decomposition/timing/analysis.
