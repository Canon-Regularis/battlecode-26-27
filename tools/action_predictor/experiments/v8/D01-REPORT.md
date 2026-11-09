# D01: TRAIN event and channel semantics

This is a read-only diagnostic, not a model improvement. It preserves all433,071 training rows/470games/94groups; no development behavior or reserved contents were inspected. Original prediction studies remain unchanged.

## Recorded roots and terminal reasons

| Engine | End roots | Cancel roots | Priority roots | End reason0 | Rollovers | Bot errors |
|---|---:|---:|---:|---:|---:|---:|
| 2.0.0 | 1242156 | 815295 | 158389 | 1242156 | 0 | 0 |
| 3.0.0 | 1038743 | 685436 | 127678 | 1038743 | 0 | 0 |

Reason0 is named **Yielded** by the hash-pinned decoder. The frozen reader calls completed turns `explicit_end`; this historical name is not proof of explicit bot API-call origin. Yielding on a normal return and explicit calling cannot be distinguished from reason0 alone. No frozen strings, labels or completeness filters were changed.

## Personally observed target PRE channels

| Recorded target | Channel0 | Channel1 | Channel2 | Channel3 | Channel4 | Unavailable |
|---|---:|---:|---:|---:|---:|---:|
| end | 14570 | 86179 | 8814 | 0 | 670 | 0 |
| cancel | 0 | 73075 | 33 | 0 | 0 | 0 |
| priority | 13179 | 576 | 1017 | 0 | 44 | 0 |
| recall | 79748 | 0 | 0 | 0 | 0 | 0 |
| ward | 10842 | 0 | 0 | 0 | 0 | 0 |

Channels are observed PRE scalars with availability checked; this table describes recorded behavior, not allowable-action rules or intent. Previous-action counts use the full own index, exact actor/event order and true turn identity; sampled turns are never joined as adjacent frames.

## Eight recorded PRE/POST probes

| Engine | Root kind | PRE→event | PRE channel→POST | PRE priority→scheduled POST | Header phase after |
|---|---:|---|---|---|---:|
| v2_0_0 | 16 | 183:8→184:0 | 1→0 | -3→-3 | 10 |
| v2_0_0 | 11 | 185:0→186:0 | 0→1 | -3→-3 | 10 |
| v2_0_0 | 8 | 186:0→187:0 | 1→1 | -3→-3 | 13 |
| v2_0_0 | 9 | 1957:0→1958:0 | 0→0 | 503→-497 | 10 |
| v3_0_0 | 9 | 32:0→33:0 | 0→0 | 0→-4 | 10 |
| v3_0_0 | 8 | 33:0→34:0 | 0→0 | 0→-4 | 13 |
| v3_0_0 | 11 | 367:0→368:0 | 0→1 | -4→-4 | 10 |
| v3_0_0 | 16 | 547:8→548:0 | 1→0 | -3→-3 | 10 |

Each engine uses the first retained TRAIN target of end/priority/recall/cancel in its first TRAIN game, selected by recorded category, never prediction correctness. Probes restore MAIN and advance recorded events only. Up to24 following headers are diagnostic evidence, not predictor inputs. No action, branch, match or bot is executed.

## Implications for the next experiment

Keep end/cancel/priority as their original recorded categories. Do not use target header phase, kind, end reason, POST channel or a future event to construct inputs. Do not force end after priority, cancel for every channel, or a type from current/scheduled equality. Any observed PRE cue requires a separate soft-input comparison with the same target rows and frozen parameter paths. Current channel identity is already encoded in M01; a new experiment must not claim it was entirely absent.

Root/effect counts, actual next-root classes after priority, PRE priority relations, engine-specific examples, all input hashes and missing-value counts are in the JSON reports. The static wrapper shows a visualiser compound endTurn(priority) method, but this does not prove how historical Fish bots called the engine. All caller-origin ambiguity remains explicit.

No prediction result changes. P05 retains109exact/71joint priorities, fails its125exact continuation gate and triggers no repeats. The original90%joint-per-category/three-seed goal, original macro-F1/movement/loss/targeting guards, all43 unassessed shops and both75-game sealed partitions remain unchanged. Fresh Solxhigh review is required before the next model implementation.
