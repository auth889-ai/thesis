# Graveyard — what was tried and dropped, with the number that killed it

The habit from Pixy: a project that records its failures is easier to trust. One line per entry; the commit where it died.

| Date | Tried | Killed by | Replaced with |
|---|---|---|---|
| 2026-09-30 | spaCy DATE/TIME entities as the time phrase in the compiler | missed "10 Oct" next to "9 am" and labelled ISO times as numbers; `when` accuracy 0.838 on the evaluation set | our own day and clock patterns in front of dateparser; `when` 1.000 (`d442d398`) |
| 2026-09-30 | dateparser for the whole phrase | returns None for a bare clock time ("6 PM", "18:00") with a timezone-aware base | our clock parser; dateparser only for explicit dates |
| 2026-09-30 | dateparser Bangla for numerals | "আগামীকাল সকাল ৯টা" → None | the model path handles Bangla; recorded as a limitation of the rules path |
| 2026-09-30 | entities stored as JSON documents beside a few query columns | could not filter on requirements or dependencies without reading rows; not defensible as a database | thirteen relational tables with foreign keys (`be0b04c7`) |
| 2026-09-29 | the day monitor's 5-minute change threshold | a departure flipped earlier and later between two routes on successive checks: 44 notifications in a morning | hysteresis planned in the event-driven monitor (P17); logged as debt |
| 2026-09-29 | "at X in Y" place detection with a capitalised-word regex only | a saved place typed in lower case ("at ucla") was missed | fuzzy match of the "at" phrase against saved places, case-folded |
| 2026-09-29 | a lease that expires by clock only | a goal stranded up to 120 s after a `kill -9` because the dead worker's lease looked alive | a dead-process check on the same host plus a reaper every 30 s (`669b90a7`) |

### Time-MoE (ICLR 2025) zero-shot under Protocol B — blocked, 2026-10-03

`Maple728/TimeMoE-50M` loads through `transformers` with `trust_remote_code`, but its remote generation code targets
an older `transformers`: `generate` fails on `DynamicCache.seen_tokens`; with `use_cache=False` it fails on
`_extract_past_from_model_output`, and the released weights are bfloat16 against float32 inputs. Re-implementing its
decoding loop would mean writing model code, which the policy forbids. Left out of the table rather than run through a
local rewrite; the row returns when the upstream code is updated or a pinned older environment is justified.

### Moirai 2 (uni2ts 2.0.0) zero-shot under Protocol B — blocked, 2026-10-03

`uni2ts` pins `numpy~=1.26`, `scipy~=1.11`, `gluonts~=0.14`, `torch<2.5`; this workspace runs numpy 2.x and torch
2.13 for Chronos-2, TimesFM 2.5 and the BasicTS checkpoints, and numpy 1.26 has no wheel for this Python. Running Moirai
would need a second, older environment on the GPU machine; the row is deferred to the AWS job (where an isolated
environment is cheap) rather than forced onto the laptop.
