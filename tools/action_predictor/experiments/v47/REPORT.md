# V47: test updating the existing map encoder

V46 remains below the requested 85% on fitting-game validation. V47 tests whether updating the existing map/entity encoder as well as context, GRU and code weights improves that result. Architecture, labels, inputs and output decoding remain unchanged. The movement/goal heads are frozen and the objective is code cross entropy only.

Each of the four folds starts from its corresponding selected V46 checkpoint with a fresh optimizer. Training runs for 16 epochs, measuring every two epochs, with learning rate 0.0003, batch size eight whole windows, decay 0.01 and clipping at 5. The loss denominator is the actual number of observed queries across the accumulated batch. Epoch zero is an eligible control so an unhelpful encoder update can be rejected.

**Epoch zero wins** with the same 2,363/2,945 correct validation predictions as V46. None of the encoder-update durations improves pooled validation accuracy. Four fold runs complete 384 optimizer updates each. The selected full-data transfer uses zero further updates and preserves V46's weights exactly.

Its accumulated NLL differs from V46 by about 6.6e-9 because the scoring batches differ. This numerical tie-break leads the final selector to name `encoder` epoch zero; direct tensor comparison proves that the final weights are exactly V46's full-fit weights. No encoder benefit follows.

No outer evaluation is performed here. V48 selects across all three stages before evaluating one final checkpoint. See the [final report](../v48/REPORT.md) and [verification](../v48/verification.json). Earlier fitting-group exposure and inferred-label limitations remain.
