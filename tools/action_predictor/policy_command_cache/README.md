# Complete-family forecast interface

This preparation exposes each family's existing conditional MAP command and joint mode probability before any recorded answer is read. It introduces no learned parameters, strategy rules, candidate generators or replacement decoder. `family_forecast` accepts only the existing frozen policy step, personal geometry/rules, and the predicted priority mode and its conditional probability.

The need comes from the retained L02 archive schema: `coordinate` stores the recorded-family conditional diagnostic, while `proposed_coordinate` stores only the selected command. Those fields cannot provide the correct arguments for arbitrary newly predicted families. Any later action-selection intervention must obtain every-family forecasts from causal inputs; it must not route through the current recorded family.

The implementation uses the original GoalPolicy mixture and parameter scorer, preserving family and coordinate tie order and keeping attempted blocked commands separate from successful movement. Shop remains an observed marginalized bucket with unavailable purchase arguments. Entity coordinates retain the original identity ambiguity. No observation, candidate-legality or full numerical-certification claim is added.

Two independent no-update tests enumerate the mixture's command probabilities in NumPy, check every family rather than only the selected family, reject a supplied recorded-action argument, and check tie behavior. Run `python -m unittest tools.action_predictor.policy_command_cache.test_forecast -v`. They passed before committing this preparation. These are interface tests, not measured Fish imitation results or a training experiment.

An actual full-row cache producer, replay-context parity assessment and any learning protocol are not completed here. No additional fit is allocated by this interface. RC01 continues under its separate frozen V24 protocol; current inputs, predictors, checkpoints and evaluation remain unchanged. Both reserved partitions stay sealed, and no bot or runtime integration is performed.
