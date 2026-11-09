# V46: directly train the existing code-prediction weights

The user requested continuing weight edits until inferred-code accuracy reaches 85%. V46 preserves the existing 45,762-parameter `SegmentPolicy`, input schema, eight output codes and causal prediction interface. It trains only the existing context projection, GRU and code readout: eight tensors totaling 20,680 parameters. The map encoder and movement/goal heads remain frozen.

Initialization is the preserved V44 combined checkpoint. Full-map features are cached only for the 256 fitting windows; their code logits reproduce the original forward path exactly. Four deterministic whole-game folds within the 32 fitting groups compare learning rates 0.0003 and 0.001 for 96 epochs, measuring every four epochs. The objective is unweighted code cross entropy on observed queries, with whole-window recurrence, batch size 16 windows, AdamW decay 0.01 and clipping at 5. No labels or metadata are added to prediction inputs.

The selected configuration is learning rate 0.0003, epoch 96: **2,363/2,945 pooled validation queries correct, 80.24%**. Higher-rate later checkpoints overfit. Repeating the selected configuration from the same initialization on all fitting groups yields **2,515/2,945, 85.40% fitting accuracy**. That fitting score is not attainment of the evaluation target.

The original map encoder and segmentation discovery were already exposed to all fitting groups, including fold validation groups. These folds evaluate the additional weight updates conditional on that earlier work. They are not fresh end-to-end holdouts. No outer evaluation occurs in this stage. V47 and V48 test further weight changes before a single final external evaluation.

There are eight fold runs of 1,152 updates and one full fitting run of 1,536 updates. All initialization, schedules, denominator counts, gradient norms, optimizer states, checkpoint forecasts and selection are checked by the final [V48 verification](../v48/verification.json). The final selected checkpoint and outcome are described in the [V48 report](../v48/REPORT.md).
