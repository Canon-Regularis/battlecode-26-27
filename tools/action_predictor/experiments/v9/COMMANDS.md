# V9 executed commands

Commands ran from `F:/Code/battlecode-26-27` using `.venv-action-predictor/Scripts/python.exe` (Python/Torch versions remain bound by existing runtime receipts).

```powershell
.venv-action-predictor/Scripts/python.exe -m tools.action_predictor.fundamental_audit
.venv-action-predictor/Scripts/python.exe -m tools.action_predictor.entity_cache *> .cambc/entity-cache.txt
.venv-action-predictor/Scripts/python.exe -m unittest tools.action_predictor.test_entity_set -v
.venv-action-predictor/Scripts/python.exe -m tools.action_predictor.entity_experiment E00 *> .cambc/E00-run.txt
# The preceding invocation failed before optimization; its original sources/log are preserved.
.venv-action-predictor/Scripts/python.exe -m tools.action_predictor.entity_experiment E00 *> .cambc/E00-run-v2.txt
.venv-action-predictor/Scripts/python.exe -m tools.action_predictor.entity_analysis E00 *> .cambc/E00-analysis-output.txt
.venv-action-predictor/Scripts/python.exe -m tools.action_predictor.entity_roundtrip E00 *> .cambc/E00-full-roundtrip.txt
```

The V9 local commands.jsonl retains executable argv. D02 completion and D03 arithmetic/context report scripts are preserved verbatim beside their input/output bindings. The first D02 completion wrapper lacked the repository import path and made no outputs; it was executed successfully through `python -c "import runpy; runpy.run_path('.cambc/complete_D02.py',run_name='__main__')"`. No model fitting occurred in these reporting scripts. E00's first pre-fit failure is separate from its only completed training experiment. No E01 or other V9 fit has run yet.
