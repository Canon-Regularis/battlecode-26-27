# P01 / Experiment A: richer causal ward placement

The richer-input placement expert improves conditional placement fitting, but
adds no net complete DEV commands with the unchanged G00 action choices.
This is a bounded partial result, not a promoted predictor or robust benefit.

| Exact ward placements | G00 | P00 simpler expert | P01 richer expert |
| --- | ---: | ---: | ---: |
| Augmented TRAIN /10842 | 2274 | 2247 | 2990 |
| Natural TRAIN /2192 | 449 | 445 | 591 |
| DEV /112 | 24 | 25 | 29 |

P01 versus G00 rescues10 and regresses5 conditional DEV placements. On the35
correctly typed ward rows, it rescues1 and regresses1; on the77 wrong-type rows,
it rescues9 and regresses4. Thus the net placement gain occurs where the action
selector does not choose ward. Conditional accuracy is a diagnostic using the
recorded ward family, never an oracle route in complete forecasts.

The paired whole-group conditional difference interval versus G00 is
[-5.49,+13.41] percentage points, and versus P00 [-1.83,+10.08]. Neither establishes
an accuracy benefit. DEV group supports and correct placements (G00 -> P01) are:
15 (6->6),32 (3->9),13 (6->4),34 (6->6),18 (3->4). Five repeatedly reused groups
and one seed do not establish robustness or policy-version effects.

Primary A keeps action choices exactly fixed: ward TP35/112, FP282, recall->ward257,
correctly typed parameter7/35, joint7/112, joint FP310. Overall11510/14439 (79.7147%)
and macro F1 .63239354 are unchanged. All nonward conditional predictions remain
unchanged, including attack943/985, cast0 193/213, cast1 146/243, move1434/2362.
Observed joint NLL is .72515091 versus G00 .72655565 and P00 .72618306. Conditional
ward NLL is2.514727 versus G00 2.695832. P01-P00 joint-NLL difference has a paired
interval [-.001652,-.000263], conditional on the selected checkpoints/reused DEV.

Secondary, separately predeclared joint MAP obtains11954 complete commands versus
control11953 and P00 11956; it gets1/112 complete wards. Its results cannot replace
the primary fixed-action experiment retrospectively. Shop probabilities concern
the observed representation;43 original purchase arguments remain strict failures.

The same21882-parameter architecture, sampling, optimizer, loss, masking and
checkpoint rule as P00 were retained. Only the predeclared richer input blocks
were enabled. P01 selected round20/26 (1700 selected/2210 completed updates).
The measured10.762-second interval starts after data loading/normalization and
includes optimization, per-round DEV inference, saving, final inference/evaluation;
it is neither pure optimization nor total preparation time. All rounds retained.
The selected model's TRAIN-only context-shuffle check gives2675 placements versus
2990 unshuffled; this measures reliance, not sufficiency of observations.

Raw personal-PRE serving matches both decoded command streams in413 cases across
all25 DEV games and both engines. Non-neural inputs/tiles/masks match exactly;
frozen neural context discrepancy max5.722e-6 and command log-probability max4.523e-6
are within the existing tolerance. Existing ward-state extraction was reused.
No matches, proposed actions, new downloads or reserved payloads were used.

Reproduction commands, dependencies, checkpoints, predictions and reporting hashes
are in P01-completion-v2-A.json. A-reporting-addendum.json supplies direct P01-P00
comparisons, all-family/typed parameter metrics, augmented/natural TRAIN and DEV
contexts with support/group concentration. Original benchmark targets are unmet;
no promotion or repeat seeds. T00/T01 remain unrun pending a fresh requested review.
