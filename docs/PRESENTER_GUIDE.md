# PRESENTER'S GUIDE — say it in your own voice

Short spoken sentences. Practice each block aloud until you can say it without
reading. Numbers in **bold** are yours — you generated them.

---

## The one-breath summary (memorize first)

> "My system watches real traffic video, understands the current traffic,
> predicts congestion 15 minutes before it happens, finds better routes and
> signal timings, tests every decision inside a digital twin of real Dhaka
> roads, and proves — with statistics — that total delay goes down."

## Block 1 — Seeing (perception)

> "Standard AI doesn't know what a rickshaw or a CNG is. So I fine-tuned a
> CVPR-2024 detector, RT-DETR, on 9,058 real Bangladeshi images. It now
> detects CNG at **96% accuracy** and rickshaw at **90%** — better overall
> than the best model published with that dataset (**0.711 vs 0.643 mAP**)."

If asked *how*: "Transfer learning — the model already saw 2 million images;
my data taught it the Bangladeshi vehicles."

## Block 2 — Understanding (traffic state)

> "Every camera is pinned to its road segment on a real map of 6,527 Dhaka
> road segments. From tracked vehicles I compute count, speed and
> stopped-fraction, and each segment gets a state: free, slowing, congested.
> On a real rush-hour video, 10 of 11 windows were flagged congested; on a
> quiet road it correctly did nothing — that's how you know it's not scripted."

## Block 3 — Predicting (forecasting)

> "Graph WaveNet — an IJCAI paper's official code — learns how congestion
> flows through connected roads. It predicts each segment's speed 15 minutes
> ahead with **0.44 m/s error, three times better** than just assuming
> traffic stays the same. Prediction matters because a signal change needs
> minutes to help — you must act before the jam, not after."

## Block 4 — Best route (and WHY total traffic falls)

> "Dijkstra's algorithm runs over PREDICTED travel times — the route that's
> best when you arrive, not when you leave. And here is the key idea: we
> cannot rescue cars already stuck in a jam. We stop the jam being FED —
> upstream cars divert one junction early, the queue stops growing at the
> back and drains from the front. Selfish routing piles everyone onto one
> road; system routing spreads them. In the twin, that alone cut mean delay
> **19.5 percent, p equals ten to the minus five, ten seeds**."

## Block 5 — Signals

> "The tested classical pressure baseline made my network **13 percent worse**
> than fixed timing — consistent with uncoordinated per-junction switching
> hurting at network scale (mechanism to be verified). That's why I
> trained a coordinated multi-agent controller, official MAPPO, with my
> forecast as an input. At its first checkpoint it recovers most of that degradation — within 1–2
> percent of tuned fixed timing, 11 percent better than the tested pressure
> baseline, though not yet beating fixed-time — and I
> report it honestly at-checkpoint, because honest numbers are the method."

## Block 6 — The twin is the proof

> "You cannot replay the same morning twice in a real city. The SUMO twin
> runs the same 3,000 trips, same random seed, twice — only the policy
> differs. So the difference is CAUSED by the policy. That's the only
> scientifically valid before/after, and it's how every claim here is proven."

## Block 7 — Honesty (your strongest card)

> "Every simulated number is labelled simulated — the code refuses to let a
> simulation-only result claim reality. I also measured where my system
> fails: on American cameras my Dhaka detector hallucinates CNGs — 40 phantom
> CNGs in 60 frames. I show my failure modes myself, because that is what
> real engineering looks like."

## The demo script (live, ~3 minutes)

1. "Give me any traffic video." → run
   `python scripts/case_report.py --source <their file>`
2. While it runs: say Block 1 + 2.
3. Report opens → walk the steps: verdict → map with two routes → seconds
   saved → twin video → the 19.5% statistic.
4. If congested: "the system chose to act." If free: "and it correctly does
   nothing — this is a system, not a script."

## If something breaks on stage

- Stream dead → use the saved rush clip: "live feeds die; that's why
  engineers keep a recorded fallback — here is the same pipeline on
  yesterday's rush hour."
- Say calmly: "the pipeline is deterministic; let me rerun" — never apologize
  twice.

## Three sentences to end on

> "Every algorithm is a top-venue paper's official code, pinned by commit.
> Every number regenerates from one command. And the parts that are still
> training are reported exactly as far as they got — because a system you can
> trust matters more than a number that looks pretty."
