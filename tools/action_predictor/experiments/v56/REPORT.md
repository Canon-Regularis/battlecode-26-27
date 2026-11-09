# V56: full-map weight update did not beat its warm start

The fitting-game selector retained **epoch zero**, so the delivered checkpoint exactly retains V55: **229/513 evaluation moves (44.64%)**, movement NLL 1.5211 and 573/699 inferred codes. This experiment adds no performance gain. The 80% target remains unmet.

Both candidate epochs updated 46,821 existing parameters: map encoder, context projection, recurrent memory, movement readout and geometry correction. Code readout/embedding and goal readout weights stayed frozen. Each fold started from its matching V54 weights plus V55 bias. The objective was movement cross entropy plus code KL with coefficient 1, using eight-window accumulation and the original 32-turn histories. This also changes batching relative to V54, so it does not isolate map weights as the cause of its result.

Across the four fitting folds, warm-start movement correctness was 938/1,997. Epoch one scored 897; epoch two scored 906. The frozen selector therefore chose the original weights. No evaluation outcome selected this checkpoint, and full refit correctly performed zero updates. All fitted candidates and traces remain archived.

Parent verification reproduced all twelve validation measurements, initialization, schedules, denominators, optimizer states, frozen tensors and 32 raw-map teacher probes. All 3,644 original-query forecasts reproduce exactly, and 32 streaming turns match. Focused full-map gradient and accumulation tests pass. No subagents or delegated reviews were used.

This negative result applies to the specified two-epoch configuration and budget. It establishes neither a capacity ceiling nor that more training would help. The earlier preexposure, inherited fold exposure, observed histories, inferred-code, sparse-goal and conditional-movement limitations remain. Original checkpoints and the playing bot are unchanged.
