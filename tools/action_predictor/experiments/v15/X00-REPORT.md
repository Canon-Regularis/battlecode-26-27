# X00: matched learned mixture of movement specialists

X00 is a negative result. It obtains1276/2362complete DEV moves versus G001318
and S001283. Blocked attempts are3/110 versus8 and2. It loses47commands overall
against G00 and6against S00. No promotion, repeats or robustness claim.

It uses the same causal inputs, normalized291-outcome support, naturalTRAIN rows,
loss, optimizer and selection rule as S00, with two latent heads and a soft gate.
No intent labels or direction partitions. The heads receive32hidden units each
versus64in S00; shared encoder/attention and+4.11%totalparameters make this a
matched mixture package, not a pure head-count-only or equal-compute intervention.

| DEV metric | G00 | S00 | X00 |
| --- | ---: | ---: | ---: |
| Complete all /14439 | 11510 | 11469 | 11463 |
| Conditional move /2362 | 1434 | 1384 | 1383 |
| Complete move /2362 | 1318 | 1283 | 1276 |
| Conditional continuation /1198 | 1120 | 1131 | 1141 |
| Complete continuation /1198 | 1053 | 1061 | 1067 |
| Conditional change /1158 | 311 | 250 | 237 |
| Complete change /1158 | 263 | 219 | 205 |
| Conditional blocked /110 | 24 | 9 | 6 |
| Complete blocked /110 | 8 | 2 | 3 |
| Observed joint NLL | .726556 | .735961 | .736393 |

X00 changes74G00errors to correct commands and introduces121errors. Movement is
74rescues/116regressions; blocked0rescues/5regressions. Against S00 it rescues70
and regresses76. Paired whole-group X00-G00 overallstrict interval is[-.422,-.229]
percentage points, movementjoint[-2.416,-1.164], and NLL[+.007699,+.011793]. Against
S00 overallstrict[-.168,+.081]pp and NLL[-.001858,+.002733] include zero. These are
selected-checkpoint, five-reused-group intervals, not untouched/three-seed evidence.
All other category commands, conditional parameters, types, confusion and losses
are exactly preserved; macroF1 stays.63239354. No targeting regression is introduced,
but original category/macro/movement/NLL success requirements remain unmet.

The weakness is already on natural TRAIN: change5206/22279 versus G006616 and
S005247. Continuation25005/25918 versus24345 and24905. Overall conditional move
30262/48286 versus31025 and30209; complete27633 versus28318 and27532. Augmented
TRAIN is also fully reported separately, never substituted for natural sampling.
Frozen encoder saw augmented TRAIN; neither TRAIN cohort is fresh held-out data.

## What the two heads actually learned

These are output relationships, not Fish intent labels. On DEV continuations,
head 0's top destination matches 1198/1198; head 1 matches 404. On changes, head 0
matches 140/1158 and head 1 matches 401. Their modes differ on1711/2362moves, so the mixture
has not collapsed to identical outputs.

At least one head mode matches1676/2362move destinations, versus the actual
mixture1383. It misses294correct head-mode opportunities and rescues1destination
outside either mode. For changes the union is473/1158 versus mixture237:
237available-mode misses and1outside-mode rescue. On natural TRAIN changes,
union9426/22279 versus actual5206, with4261misses and41outside-mode rescues.
Weak use of available alternatives is therefore present on TRAIN too.

With genuine predicted types, the DEV head-mode union would contain1532complete
moves, while X00gets1276:256correctlytyped available-mode misses. On changes,
union417versus205 leaves212such misses. These oracle counts are NOT learned
accuracy or an architecture ceiling. A mixture's MAP can lie outside both head
modes; arbitrary pointwise gate choice is unavailable at inference. No oracle
routing, pseudo-intent training, threshold tuning or checkpoint reselection occurs.
The current data establish a selection/combination problem, not its definitive
cause. Optimization, compressed switching evidence and missing persistent goals
remain hypotheses. Context-dependent probabilities are marginalized correctly;
this is not A00's opaque-fallback decision mismatch.

All2362DEVmove destinations remain inside the declared historical success-mask
support. Fixed types separately impose2127/2362joint move and40/110blocked
ceilings. X00move errors are235wrongtypes and851wrongdestinationsaftercorrecttype;
blocked70wrongtypes and37wrongdestinations. Current head-mode misses must not be
confused with absent coordinate vocabulary or proven insufficient observations.

## Reproduction and numerical qualification

Selected round9/15,1773selected/2955completedupdates,60278parameters. All checkpoints
and outputs retained. Actual stop/selection differ from S00 by the same rule;
row/update ALLOWANCE and parameters are comparable, actual compute is not equal.
Mixed fit interval582.386seconds versus S00506.083 includes optimization, per-round
DEV inference/saves and finalTRAIN/DEVinference/reporting. Wholecommand593.396
alsoincludes hashing/loading/normalization; no replay extraction occurred.

Original rawPRE check stopped in game24 because one blocked conditional branch
at DEV13393 differed by2.288818e-5 in log probability, exceeding frozen2e-5. Its
actual forecast was end. No command mismatch occurred. The original failure is
preserved in X00-roundtrip-preflight.json; no tolerance or model was changed.

roundtrip_diagnostic rechecked179cases/25games/bothengines: all 179 sampled action types and 74 changed-family
commands (52 move,22 blocked) match, raw nonneural inputs/entities/grid/masks exact, frozen128context
maxdifference4.768e-6within its existing1e-5tolerance. Replaying the new head with
identical RAWcontext gives bit-identical probabilities. This attributes the small
cached/raw difference to frozenencoder batch rounding; max probability-mass
difference5.364e-7. It DOES NOT convert the original test into a pass, establish
all-row raw parity or certify production numerical robustness. Nonmovement
required arguments reuse prior unchanged G00 serving evidence; the new sampler
checks their action choices, not every unchanged argument independently. Actual inference
costs include PREfeatures,G00/P05 and both newfamily calls, exclude initialization/
historyreplay, and come from a separate diagnostic run; no speed advantage claim.

Use the corrected recipe in X00-evidence-inventory.json. The older generic
X00-completion.json lists the original roundtrip command, which fails its original
tolerance; the diagnostic command and failure receipt supersede that recipe only.
Original seven protocol-bound sources remain unchanged. Per-category observed
loss and six original V7diagnostic hashes are in X00-loss-supplement.json. Shop
argument likelihood remains absent and all43shops strict failures. Sparsecategories
and ambiguous entityIDs uncertified. Full legality unassessed; success-mask
rejections and blocked-attempt rejections separated in the fit report.

The two-fit movement protocol is now trained, pending fresh independent review
and DRAFTPRhandoff. Ward research remains user-discontinued at3/4fits; T01 unrun.
Both75+75reserved partitions sealed. No matches, hypotheticalaction simulations,
replaydownloads, playingbotchanges or deployment.
