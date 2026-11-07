# E01 executed-command addendum

COMMANDS.md is the immutable E00-era snapshot; its "no E01 fit" statement applied only then. The following commands subsequently ran from the repository root with the same .venv-action-predictor interpreter:

```powershell
.venv-action-predictor/Scripts/python.exe -m tools.action_predictor.entity_experiment E01
.venv-action-predictor/Scripts/python.exe -m tools.action_predictor.entity_analysis E01
.venv-action-predictor/Scripts/python.exe -m tools.action_predictor.entity_pair_analysis
# First diagnostic version is preserved; subsequent V2 corrects only parameter accounting.
.venv-action-predictor/Scripts/python.exe -m tools.action_predictor.entity_pair_analysis
.venv-action-predictor/Scripts/python.exe -m tools.action_predictor.entity_roundtrip E01
.venv-action-predictor/Scripts/python.exe -m tools.action_predictor.entity_attention_checks
.venv-action-predictor/Scripts/python.exe -m tools.action_predictor.entity_serving_benchmark P05
.venv-action-predictor/Scripts/python.exe -m tools.action_predictor.entity_serving_benchmark E00
.venv-action-predictor/Scripts/python.exe -m tools.action_predictor.entity_serving_benchmark E01
```

Exact argv remain in local v9/commands.jsonl; original redirected transcripts are preserved in completion bindings. E01 used the identical fitting source as E00. No games, deployment, new downloads or reserved-content reads occurred.
