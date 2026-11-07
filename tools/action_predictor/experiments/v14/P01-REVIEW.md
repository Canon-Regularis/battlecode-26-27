# Fresh independent P01 post-fit review

Reviewed HEAD87a490241b4245d0ffdfe2a0a2ba645b98ae568b, GPT-6.1 Sol xhigh,
task7007997f-ffb1-41cb-8656-71a7a7030a9a. Full review is preserved in parent thread.

Verdict: saved P01 predictions, likelihoods, normalization and round20/26 selection
valid. Better TRAIN fitting, no net complete-command DEV benefit. No promotion or
repeat seeds. No current-answer inference input or opaque fallback veto found.

Findings: (1) B/C fixed placement ceilings24/112 and29/112; (2) priorward32-root
history positive support246augTRAIN,61naturalTRAIN,zeroDEV limits attribution;
(3) undefined context F1 should be null, not zero; (4) completion inventory should
include diagnosis commands and comparator archive hashes. P01-review-response.json
and completion_v3 address these additively. Old receipts remain unchanged.

Independent checks reproduced every P01 output, both decoder archives, TRAIN
normalization, selection/update/parameter counts, full291-bucket conditional
probabilities to9e-16, paired intervals and bound hashes; extraction reused.
No fits, edits, simulations, sealed access or PR actions by reviewer. No future
fit result approved.
