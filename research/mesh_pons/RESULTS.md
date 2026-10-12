# Mesh prototype: PONS on Dhaka SUMO movement — SIMULATED results

**Every number on this page is SIMULATED.** Nothing here is a measurement of Dhaka. The demand is
synthetic and uncalibrated, the radio is an ideal disc, and only 17 vehicles take part (see
Scope). The app reads these files through `core/networking/mesh/results.py` (Offline alerts page and Lab → Evidence; 2026-10-06).

## Scope and provenance

| item | value |
|---|---|
| city / dataset | Dhaka, frozen SUMO network `data/cities/dhaka_r1/dhaka_r1.net.xml.gz` (OpenStreetMap -> netconvert, uncompressed sha256 `06194df039740fa2ceb0bcb2c438444efd755f26e0f863327f0e1d6524775dcb` per `config/cities/dhaka.yaml`); read only, never changed |
| demand | SYNTHETIC, UNCALIBRATED: SUMO `randomTrips.py`, seed 11, one departure every 2.0 s, 1800 s, the `sumo.build` values of the city config, same options as `core/simulation/twin/scenario_builder.py`; routes sha256 `838f509a7db07c47fc42ed52581e320950ed8ce538d2ac207e01cef5d38294e1` |
| SUMO | Eclipse SUMO sumo 1.27.1, default passenger-car model, seed 11 |
| movement window | SUMO seconds 900-1200 (300 steps), fixed before any result was seen; exported with SUMO's `traceExporter.py --ns2mobility-output`; ns2 trace sha256 `2ca59a89fc09483c1448e37990134bedbdfa10113fe677e2bc2bdcd62c4dab6b` |
| vehicles | 277 vehicles appear in the window; **17 are present at every step and only those are simulated** (why: below) |
| simulator | PONS `pons-dtn` 0.2.1 from PyPI (identical to git tag 0.2.1 = `2fd70381b1b02e3e2227b5e596dc7fd92f458893`), MIT licence; run on Python 3.11 |
| radio | one interface per vehicle, `range = 10 m`, ideal disc, no loss model beyond PONS's own. Source of the value: The ONE simulator, default_settings.txt, lines 19-23: "# \"Bluetooth\" interface for all nodes ... btInterface.transmitRange = 10" (range in meters). https://github.com/akeranen/the-one/blob/43eaab1e0592af2526d124ee9ba9590eeadcd49a/default_settings.txt ; simulator described in Keranen, Ott, Karkkainen, "The ONE Simulator for DTN Protocol Evaluation", SIMUTools 2009. |
| messages | PONS's own generator: one message per 1 s, random source and destination among the simulated vehicles, 100 bytes, TTL 300 s; so 300 messages per run |
| routers | PONS defaults: `EpidemicRouter()`, `SprayAndWaitRouter()` (7 copies, non-binary), `PRoPHETRouter()` (`PRoPHETConfig()` defaults); scan interval 2 s, unlimited buffer |
| seeds | [1, 2, 3, 4, 5] per router = 15 runs. The seed changes which vehicles send to which and when; **the movement trace is the same in every run**, so the spread is over message draws, not over traffic |
| evidence | `evidence/runs/<router>_seed<k>.json` (PONS statistics verbatim) + `.log`, `evidence/movement.json`, `evidence/SHA256SUMS` |

## Results (SIMULATED), mean ± sample standard deviation over 5 seeds

| router | delivery ratio (SIMULATED) | delay of delivered messages, s (SIMULATED) | copies: relayed transfers per created message (SIMULATED) | PONS overhead ratio (SIMULATED) |
|---|---|---|---|---|
| Epidemic | 0.028 ± 0.009 (min 0.013, max 0.033, n=5) | 65.2 ± 21.4 (min 33.7, max 91.0, n=5) | 0.62 ± 0.09 (min 0.55, max 0.77, n=5) | 23.8 ± 10.5 (min 16.0, max 40.5, n=5) |
| Spray and Wait (7 copies, non-binary) | 0.027 ± 0.014 (min 0.010, max 0.043, n=5) | 60.0 ± 20.7 (min 34.6, max 85.4, n=5) | 0.44 ± 0.04 (min 0.40, max 0.49, n=5) | 19.8 ± 12.1 (min 8.7, max 39.3, n=5) |
| PRoPHET (PONS defaults) | 0.029 ± 0.013 (min 0.010, max 0.047, n=5) | 77.6 ± 22.1 (min 40.6, max 93.5, n=5) | 0.03 ± 0.01 (min 0.01, max 0.05, n=5) | 0.0 ± 0.0 (min 0.0, max 0.0, n=5) |

Definitions, all taken verbatim from PONS's `routing_stats`: delivery ratio = `delivery_prob` =
delivered / created; delay = `latency_avg`, the mean of (delivery time - creation time) over
delivered messages only, so seeds without deliveries carry no delay; copies = `relayed` / `created`,
where `relayed` counts every successful message transfer between two vehicles (including the final
hop); overhead ratio = PONS's (`relayed` - `delivered`) / `delivered`.

### Per seed (SIMULATED)

| router | seed | created | delivered | delivery ratio | delay s | relayed | relayed/created | started | dups | hops avg |
|---|---|---|---|---|---|---|---|---|---|---|
| Epidemic | 1 | 300 | 4 | 0.013 | 60.8 | 166 | 0.55 | 177 | 48 | 1.00 |
| Epidemic | 2 | 300 | 10 | 0.033 | 91.0 | 170 | 0.57 | 182 | 47 | 1.20 |
| Epidemic | 3 | 300 | 8 | 0.027 | 33.7 | 230 | 0.77 | 237 | 74 | 1.00 |
| Epidemic | 4 | 300 | 10 | 0.033 | 63.1 | 180 | 0.60 | 192 | 42 | 1.00 |
| Epidemic | 5 | 300 | 10 | 0.033 | 77.4 | 188 | 0.63 | 201 | 57 | 1.00 |
| Spray and Wait (7 copies, non-binary) | 1 | 300 | 3 | 0.010 | 43.7 | 121 | 0.40 | 133 | 0 | 1.00 |
| Spray and Wait (7 copies, non-binary) | 2 | 300 | 13 | 0.043 | 72.0 | 126 | 0.42 | 138 | 3 | 1.15 |
| Spray and Wait (7 copies, non-binary) | 3 | 300 | 7 | 0.023 | 34.6 | 147 | 0.49 | 153 | 0 | 1.00 |
| Spray and Wait (7 copies, non-binary) | 4 | 300 | 6 | 0.020 | 85.4 | 126 | 0.42 | 137 | 0 | 1.00 |
| Spray and Wait (7 copies, non-binary) | 5 | 300 | 12 | 0.040 | 64.3 | 141 | 0.47 | 153 | 1 | 1.00 |
| PRoPHET (PONS defaults) | 1 | 300 | 3 | 0.010 | 90.7 | 3 | 0.01 | 3 | 0 | 1.00 |
| PRoPHET (PONS defaults) | 2 | 300 | 14 | 0.047 | 89.4 | 14 | 0.05 | 15 | 0 | 1.00 |
| PRoPHET (PONS defaults) | 3 | 300 | 7 | 0.023 | 40.6 | 7 | 0.02 | 10 | 0 | 1.00 |
| PRoPHET (PONS defaults) | 4 | 300 | 10 | 0.033 | 73.9 | 10 | 0.03 | 11 | 0 | 1.00 |
| PRoPHET (PONS defaults) | 5 | 300 | 9 | 0.030 | 93.5 | 9 | 0.03 | 9 | 0 | 1.00 |

### Reading these numbers

- With 17 vehicles spread over a 5.8 x 5.5 km network and a 10 m radio, contacts are rare; most
  messages never meet their destination within the 300 s TTL. Delivery ratios of a few percent are
  the consequence of this setup, not a property of Dhaka traffic.
- PONS's PRoPHET (default `PRoPHETConfig`) forwards to a peer only if that peer's delivery
  predictability for the destination exceeds the sender's own. In this sparse window it never did:
  `relayed` equals `delivered` in every seed, i.e. all PRoPHET deliveries are direct source-to-
  destination contacts, and PRoPHET's delivery ratio is then the direct-contact rate.
- Spray and Wait (7 copies) and Epidemic reach the same destinations through more transfers;
  Epidemic spends the most copies.

### Why only 17 of 277 vehicles

PONS's ns2 model (`pons.Ns2Movement`) parks a node at its first position before its first entry
and at its last position after its last entry. A vehicle that departs or arrives inside the window
would therefore sit as a stationary relay that does not exist in the SUMO run. Keeping only vehicles
present at every step of the window avoids that artefact at the cost of a small, long-trip-biased
sample. A follow-up that models vehicles entering and leaving (PONS has no node on/off switch in
its ns2 path) is noted in README.md; it is not done here.

### Our adapter code, and why (please read)

1. **ns2 -> PONS movement adapter is our code** (`scripts/03_run_pons.py`, `read_ns2`). PONS's own
   ns2 reader, `pons.Ns2Movement.from_file`, divides by the `setdest` speed and a stopped vehicle has
   speed 0, so it raises `ZeroDivisionError` on this trace (`evidence/ns2_reader_failure.log`).
   The adapter reads the same ns2 file written by SUMO's traceExporter and turns each
   `$ns_ at t "$node_(i) setdest x y v"` line into PONS's native move tuple `(t, i, x, y, 0)`,
   which is what PONS's own movement manager consumes. No position or time is changed, and PONS
   itself is not modified.
2. **Message generator with `metadata={}`, for Spray and Wait only.** PONS 0.2.1's
   `SprayAndWaitRouter.add` writes `msg.metadata["copies"]`, but PONS's own message generator
   creates messages with `metadata=None`, so Spray and Wait crashes on its first message
   (`evidence/spray_and_wait_failure.log`; the code is the same at master `90a6a35`). Our
   `generator_with_metadata` repeats PONS's generator statements and random draws for our fixed
   settings and adds `metadata={}`. Check: Epidemic and PRoPHET were each run twice per seed, with
   PONS's generator and with ours; all 10 pairs gave identical statistics
   (`evidence/generator_equivalence.json`, identical = True).
3. **Upstream examples ran on Python 3.11.** Run unchanged on Python 3.13 they crash
   (`random.randint` with a float `max_pause`, `evidence/upstream_sim_python313_failure.log`), so the
   venv uses Python 3.11.

## Upstream examples, unchanged (step 2 of the task)

PONS publishes no reference numbers for its examples, so there is nothing to compare against; the
outputs below are ours, saved for the record (`evidence/upstream_sim.log`, `evidence/upstream_ext_ns2.log`).

`sim.py` (README example: 10 random-waypoint nodes, Epidemic, 24 h, seed 42) — SIMULATED:
```json
{
    "created": 2880,
    "delivered": 2561,
    "dropped": 0,
    "started": 81718,
    "relayed": 81264,
    "removed": 22055,
    "aborted": 364,
    "dups": 58933,
    "latency_avg": 873.8002361692731,
    "delivery_prob": 0.8892361111111111,
    "hops_avg": 2.1144084342053886,
    "overhead_ratio": 30.731354939476766
}
```

`examples/ext_ns2.py` (PONS's own ns2 test trace, Epidemic) — SIMULATED:
```json
{
    "created": 110,
    "delivered": 50,
    "dropped": 0,
    "started": 1296,
    "relayed": 1296,
    "removed": 50,
    "aborted": 0,
    "dups": 1020,
    "latency_avg": 22.330001851851893,
    "delivery_prob": 0.45454545454545453,
    "hops_avg": 1.0,
    "overhead_ratio": 24.92
}
```

Environment: `evidence/pip_freeze.txt`. All evidence hashes: `evidence/SHA256SUMS`.
