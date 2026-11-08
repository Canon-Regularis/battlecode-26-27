# ED00: family beliefs differ from complete-command decisions

This frozen-checkpoint attribution reconstructs L02 and U01's marginal action-family probabilities from the shared forward-causal upstream cache. It changes no weights, latent filtering, decoder or complete command. TRAIN uses the saved augmented-cadence filter; natural membership is reported separately, not called natural cadence. No new replay queries or optimization run.

On 576 original DEV priority rows:

| Diagnostic | L02 | U01 |
| --- | ---: | ---: |
| Marginal-family argmax is priority | 335 | 317 |
| Existing complete-command MAP chooses priority | 184 | 164 |
| Marginal priority, MAP another family | 152 | 154 |
| MAP priority, marginal another family | 1 | 1 |
| Conditional integer mode matches recording | 109 | 109 |
| Correct integer plus marginal priority | 65 | 66 |
| Correct complete priority command | 50 | 45 |
| Correct integer and marginal priority, but MAP another family | 15 | 21 |

This is not a surviving objective/decoder mismatch. A family with uncertain conditional arguments can have high marginal action probability while none of its individual commands wins joint MAP. The calculation follows the same normalized model used in training. The diagnostic marginal argmax is not selected as a replacement decoder, and no new complete-policy score is claimed.

Most priority failures cannot be repaired by merely switching to marginal-family selection: **467/576** already have a wrong conditional integer mode. Of the 109 correct integer modes, L02 loses 44 before even reaching marginal priority argmax, and a further 15 through complete-command competition. U01's corresponding losses are 43 and 21. These partitions describe frozen outputs; they do not identify whether missing inputs, training, representation or intrinsic uncertainty causes those distributions.

The generic historical action vector stores past action type and geometry but omits its exact priority argument. The newer GoalPolicy does not directly receive the recovered 39-field priority block, as previously disclosed in V16's input-omissions addendum. The older V8 C01/C02 classifier-input study was prepared but never fitted. This remains an untested information contrast, not a newly established explanation of these errors.

The output archive retains every original row and all fifteen family probabilities before comparison assertions. Reconstructed recorded-family NLL agrees with the saved primary archives within the registered tolerance. Existing numerical qualifications, reused-DEV exposure, incomplete shop arguments, sparse categories, identity and legality/calibration limitations remain. This is a cached-input attribution rather than a new raw-PRE serving audit.

Source was committed at `a403293` before execution. `ED00-plan.json` and `ED00.json` bind the inputs and output matrices. Reproduce only into absent destinations: `python -m tools.action_predictor.order_information.decoder_attribution`. This later diagnostic is outside the O01 review's stated coverage.
