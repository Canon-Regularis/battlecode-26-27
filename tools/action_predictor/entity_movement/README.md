# Destination-conditioned entity execution

E00/E01 test whether relating each possible movement destination to current
personally known entities improves execution. The matched control attends to
entities once per state; the treatment attends separately for each destination.
Both use the same inputs, parameter shapes, initialization, trainable hierarchy
and execution, sequence traversal, loss and checkpoint rule. A zero-initialized
movement residual preserves the baseline initial distribution. The residual
enters before the existing restricted/full-support mixture.

This addresses H01's execution-distribution limitation. It does not attach
persistent identities to objectives, label a state as a strategy, or establish
that observation information is sufficient. Missing-root resets and eight-node
gradient detachment retain their temporal limitations.

Run tests with the pinned interpreter from the repository root:

```text
.venv-action-predictor/Scripts/python.exe -m unittest tools.action_predictor.entity_movement.test_model -v
```

Commit the source closure and freeze the protocol before optimization with
`python -m tools.action_predictor.entity_movement.protocol`. Run only one arm
per invocation: `python -m tools.action_predictor.entity_movement.fit E00`.
E01 requires a fresh independent review bound to the completed E00 result and
checkpoint. Every fit attempt is preserved. The predeclared treatment comparison
requires movement and direction-change gains, lower joint NLL, continuation and
the original targeting/category guards; the stronger retained predictors remain
comparators. No results or strategy improvement are claimed before evaluation.

Both reserved partitions stay sealed. No playing-bot changes or deployment.
