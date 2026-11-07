# Fresh X00 post-fit and completed-study review

GPT-6.1 Sol xhigh task4dde9213-bbbf-459b-9f16-d0eb9ebe7acb reviewed
48b016677dc0b18bb08406440f7283a1a2be9e67 and full parent history.
Verdict: valid negative; no defects invalidating saved outputs, likelihoods,
normalization or checkpoint selection. No promotion or additional fits.
Full review text remains in the parent thread.

High finding: weak destination learning already on TRAIN. DEV movement errors
235wrongtypes and851wrongdestinationsaftercorrecttype; of latter256havecorrect
current headmode,595neitherheadmodecorrect. Coordinate support is complete.

Medium clarification:184of256available-mode misses put correctmode in lowerweight
head;72give it largerweight but mixturestillwrong. Alltruefamily movement counts
211/83 (total294);naturalTRAINchanges1537of4261misses favorcorrectmode head.
Weighted probability shapes, not just gateweight, determine MAP. No fallbackveto
bug. Exact scalar-gate MAP reachability remains a proposed no-fit diagnostic.

Low wording correction:77DEV/2712augTRAIN recorded-nonmovement rows change an
alreadywrongmove/blocked destination. Preserve types/nonmovement conditional
paths/commands with PREDICTED nonmovement families/categoryscores/losses, not
every wrongforecast on a true-nonmovement row. Additive correction follows.

Independent all433071TRAIN/14439DEV outputs/gates/contextmetrics/uncertainty and
normalizers/counts reproduced. All50192TRAIN/2472DEV component records checked;
independentNLLwithin1.14e-6 andnoMAPmismatch.82inventorybindings matched.
Numericalcontrol at13393 confirms encoder batch256 reproducescache andbatch1
rawcontext; original2e-5test remains failed. Scope/bytes/secrets/whitespace for
155-filelocaldiff pass. Suitable DRAFTnegative-result update after corrections.
No edits/fits/optimizerprobes/simulations/downloads/sealedaccess/PRactions/delegates.
WardT01absent;3/4protocol discontinued andT00findings honestly unresolved.
