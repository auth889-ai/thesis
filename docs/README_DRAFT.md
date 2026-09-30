# LIFE OS — Make my day actually work

> **Evidence-gated planning for real-life commitments.**
>
> **The model proposes; deterministic tools decide what is true; an independent checker signs every plan; the person decides when it may act.**
>
> Tell LIFE OS what your day holds. It compiles your commitments, builds your Life Twin, checks whether the day can physically work, repairs it when it cannot, asks before anything consequential, watches for change, and records what actually happened.
>
> `UNDERSTAND → MODEL → PREDICT → PROVE FEASIBILITY → PLAN → ACT → MONITOR → REPAIR → VERIFY → LEARN`

[badges: CI · licence · tests · benchmark verdicts · eval checks — each linking to the artifact that proves it]

## See it work

One run on Eva's day, graded by code on N machine-checked criteria (numbers filled in from `evals/results/` after the run, never typed):

| | |
|---|---|
| The day | university 09:00, mother's hospital appointment 13:00, interview 16:00, assignment 18:00, a CV to print |
| Verdict | NO — the print shop closes at 15:00 and the only slot collides with the hospital (the hospital leg that looked tight fits) |
| Repair | study block moved, CV printed at 12:10, hospital leg by rail, departure 15:05 |
| Verification | independent checker: N/N constraints, certificate signed |
| The receipt | [`examples/eva_day/repaired_day.ics`](examples/eva_day/) — import it into any calendar |

## Why trust it

| Failure mode | Structural defence | Proof |
|---|---|---|
| The model invents a travel time | edges exist only with a provider and a freshness | contract + tests |
| It declares a healthy day broken | healthy-day control: no hypothesis confirmed, nothing moved | eval |
| A repair fixes one thing and breaks another | the independent checker re-derives the whole day | `bad_repair_rejected` eval |
| Stale data treated as live | freshness on every evidence item; stale → RISKY | eval |
| It acts without permission | exact-action approval, standing rules, hash-chained audit | tests |

## Quickstart · Judge check · What is real vs synthetic · Limitations · Architecture · Research · Licence

(Each section in the shape of the two reference READMEs; filled only with measured facts.)
