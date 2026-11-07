The first structured-target experiment was aborted before test evaluation.
The initial extractor incorrectly required every ability event's `from` field
to match the actor position. Training-only inspection showed that this field
is unset `(0,0)` for several ability designs, despite a valid recorded `to`.
This excluded all cast-slot-zero labels and some slot-one labels.

The stateless action MLP and GRU-coordinate validation fits completed; their
reports are retained. The stateless target fit was interrupted. None of the
structured models in this attempt is a candidate for inference.
No target test performance was inspected or used. The corrected extraction
and full predefined comparison are in `../v3`, with identical group splits.
The shared payload audit, split lock and baseline metrics are retained once in
`../v3`; their hashes match this attempt's original locks.
