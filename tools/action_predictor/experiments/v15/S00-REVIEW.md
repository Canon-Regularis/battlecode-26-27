# Fresh independent S00 post-fit review

GPT-6.1 Sol xhigh task0ca4a334-85d3-4856-91f4-8b68d29a1c8a reviewed
86a298dcf5ec5b912d491e98fc26dbbe2dff2330. Full review preserved in parent.
Verdict valid negative: all saved outputs, selection and causal inference valid;
no promotion or repeat seeds. Review approves no future X00 result.

Demonstrated weakness is destination prediction despite available support,
already visible on TRAIN, not a DEV-only failure. DEV move failures235wrongtypes
and844wrongdestinationsaftercorrecttype; blocked70wrongtypes/38wrongdestinations.
Fixed type ceilings2127/2362 and40/110 remain separate. Causes such as capacity,
optimization, compression, missing history or hidden intent remain unresolved.

Two small findings: add complete per-category NLL; bind six diagnostic arrays
(direction, availability, obstacle across TRAIN/DEV). Reviewer checked all six
against originalV7receipt: exactmatches. S00-loss-supplement.json addresses both
without changing receipts, inference or fitting.

Independent reproduction: every433071TRAIN/14439DEV output/gate;62bindings;
natural normalization/counts; round14/20 and2758/3940updates; independent probability
NLLwithin1.4e-6; pairedintervals;28additionalrawPREcasesbothengines. Nonmovement
predictions/lossesexact; successmaskreject0,blockedrejectionsseparate. No edits,
fits, simulations, extraction, sealeddata or PRactions.
