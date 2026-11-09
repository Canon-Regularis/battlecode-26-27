# Movement-only neighborhood evidence

This fitting-only comparison tests a specific consequence of the reviewed V37
audit. Nearby terrain exists in the candidate grid, but the current pointwise
readout cannot use other cells to change supported-pair odds at fixed endpoint
features/context. That restriction is not proof of the cause of movement errors.
V6 already tested map CNNs and failed targeting guards; this study instead freezes
the entire reviewed R00 pass-eight backbone and corrects movement tile logits.

Both arms add the same 5,697 trainable parameters to the fixed 139,292-parameter
base. They receive the same 20 candidate features and 128-dimensional context.
N01 adds actual 3x3 in-map/blocked-in-map terrain from the existing grid. N00
repeats the destination's own terrain at each available patch slot. Both retain
identical crop-availability masks; padding is unavailable, not a world boundary.
The final residual readout starts at zero, so initial predictions match R00.

The residual enters movement tile logits before the original restricted/full
support mixture. Raw special logits, other-family formulas, action probabilities
and the backbone remain unchanged. Joint-MAP complete commands can still change
when movement competes with another family, so complete targeting and movement
false-positive guards remain necessary despite freezing nonmovement formulas.

Use every V36 fitting window, not the audit's error cohort: 34,720 rows, 1,085
windows, 40 groups. Both arms use residual seed 27, eight passes, 277,760 row
presentations and 272 optimizer calls, with identical permutations, denominators
and checkpoint opportunities. Full-command NLL is divided by actual batch rows
(1,024 or 928); only residual parameters train. Memory reset/detach8 and ordinary
gradient accumulation remain. AdamW uses lr0.0003, decay0.01 and global clip5.
Only final pass eight is a result; the paired cap is two hours, including final
comparisons and hashing, with no repeats, restarts or extensions.

All V36 behavioral allocation conditions must pass versus both N00 and the frozen
R00 base. These require complete-change gain5pp, movement gain1pp, continuation
loss at most0.5pp, change-coordinate NLL reduction0.15 and within-alternative
reduction0.05, lower balanced joint NLL, full NLL increase at most0.005,
complete-command loss at most0.2pp, macro F1 loss at most0.01, attack/cast
conditional and complete accuracy loss at most2pp, movement false-positive
increase at most0.2pp, and favorable change-accuracy/NLL signs after deleting each
group. Absent targeting categories cannot pass. No favorable checkpoint or
reference switching is allowed.

This is warm, fitting-only residual learning, not fresh full-policy training.
Passing only allocates a separately reviewed transfer experiment. Original
strong-reference, category-90%, reliability, three-seed and data limitations
remain. No strategic, playing-strength, generalization or promotion claim follows.
Sol xhigh reviews code before fitting; negative training results go to Astra high.
Each arm requires its actual preceding review to be bound separately.
