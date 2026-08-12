# PAPER_SUMMARY — Understanding traffic capacity of urban networks

**Paper:** Loder, A., Ambühl, L., Menendez, M., Axhausen, K. W. (2019).
*Understanding traffic capacity of urban networks.* Scientific Reports 9, 16283.
DOI: [10.1038/s41598-019-51539-5](https://www.nature.com/articles/s41598-019-51539-5)

**Local paper artifacts:**
- `paper/loder2019_fulltext.xml` — full text (JATS XML, Europe PMC, PMC6841661)
- `paper/loder2019_fulltext_extracted.md` — readable extraction incl. Methods
- Publisher PDF: Nature's server blocked non-browser downloads from this machine; the Colab notebook downloads it into Drive. The full text above is complete and is the primary artifact.

**Lab classification:** *Independent paper-faithful reconstruction; this is not the authors' official analysis code.* The `ambuehll/UTD19` GitHub repository (cloned to `upstream/author_vignette/`) contains **only a README** pointing to the dataset — it is a dataset vignette, not the paper's analysis code.

---

## Part 1 — The ideas in simple language

### The problem the paper solves

Everyone knows one road can get congested. But a **whole city network** also has a
"breaking point": as more and more cars enter the network, at first more trips get
completed per hour — until a critical number of vehicles is reached. Beyond that
point, adding cars makes the *whole network* produce **less** travel (gridlock
dynamics). Before this paper, nobody had measured, across many cities, **where**
that breaking point lies and **what determines it**. The paper answers: the
breaking point is predictable — road and bus network topology explain ~90% of its
variation across 107 urban networks in 41 cities (Abstract; Introduction ¶1–3).

### The chain of concepts (learn these in order)

1. **Flow (q)** — how many vehicles pass a point per unit time (vehicles/hour).
   A loop detector under the asphalt counts them (Methods, "Initial dataset").

2. **Occupancy (o)** — the fraction of time the detector has a vehicle on top of
   it (0–1, dimensionless). It is what a loop detector can actually measure
   instead of density.

3. **Density (k)** — how many vehicles occupy a kilometer of road at one instant
   (vehicles/km). Occupancy is a *proxy* for density: the more time the detector
   is covered, the more crowded the road. Converting o → k needs vehicle+detector
   length, which UTD19 mostly lacks — that is why the paper needs a speed
   calibration step (Methods, "MFD estimation and calibration").

4. **Accumulation (n)** — density scaled up to the whole network: the number of
   vehicles simultaneously inside the network (vehicles), often normalized per
   km² for cross-city comparison (Introduction ¶4).

5. **Production (P)** — the network's "output": total vehicle-kilometers traveled
   per hour (vehicle-km/h, normalized per km²). High production = the network is
   moving many vehicles over distance.

6. **MFD (Macroscopic Fundamental Diagram)** — the curve P(n): plot accumulation
   on the x-axis, production on the y-axis. Empirically it is a smooth, reproducible,
   ∩-shaped curve (Introduction ¶4; Fig. 1d,e).

7. **Free-flow state** — left of the peak (n < n*): adding vehicles adds production.

8. **Critical point (n\*, P\*)** — the peak. **P\*** is the network's traffic
   capacity; **n\*** is the critical accumulation; **v\* = P\*/n\*** is the
   critical speed at which congestion begins (Introduction ¶1, ¶4).

9. **Congested state** — right of the peak (n > n*): adding vehicles *destroys*
   production. This is the scientific definition of network congestion used here.

### Why network congestion ≠ one-road congestion

A single road has its own flow-density curve (link fundamental diagram, standardized
in the Highway Capacity Manual — Introduction ¶2). But a network adds interactions a
single road cannot show: queue **spillback** across intersections, rerouting, signal
interactions, buses blocking cars. Individual detectors look chaotic (Fig. 1b,c), yet
*averaging over all detectors in a coherent region* produces a smooth curve (Fig. 1d,e).
The network behaves like a single "traffic reservoir" with its own capacity — an
emergent property that does not exist at the link level. Also counter-intuitive
(Results ¶1): drivers may experience *low speeds* in a network that is macroscopically
still uncongested — critical speed averaged 18.8 km/h across networks (Fig. 2b).

### What the paper found

- Mean critical point over 107 networks: **P̄\* = 12,236 ± 5,513 vehicle-km h⁻¹ km⁻²**,
  **n̄\* = 653 ± 308 vehicles km⁻²** (Results ¶1). P\* vs n\* correlate with R² ≈ 0.91.
- Four topology variables explain ~90% of critical-point variation (Table 1):
  road density R (+, sublinear), betweenness centrality b_c (−), intersection
  spacing × density R×I (−), bus production density B (− on capacity).
- **Sublinear scaling**: elasticity of n\* with respect to R ≈ 0.84 (95% CI
  [0.727, 0.950]) — doubling road supply less-than-doubles the critical
  accumulation: *decreasing marginal returns of building roads* (Table 1, bottom).

### Why this matters for DhakaFlow Nexus later

- **Signal control (future RL labs) — bounded claim:** the paper states that, to
  maximise *travel production*, an ideal control would act near n ≈ n\*
  (Introduction ¶4). That is the paper's statement about one macroscopic
  quantity in its study networks; it is **not** DhakaFlow's control objective.
  In this project the critical point is used as a traffic-science diagnostic, a
  congestion/capacity reference, and an *optional* state feature, reward-shaping
  term or risk/constraint signal whose value must be demonstrated by ablation.
  Later controllers (Labs 14–21) optimise travel time, waiting, queue, pressure,
  spillback, throughput, downstream capacity, person-delay, pedestrian delay,
  emergency delay, forecast risk and safety — Forecast-Aware MAPPO is never
  required to simply hold n ≈ n\*. Critical values are also network-specific:
  the torino estimate below must never be transferred into Dhaka control or
  calibration.
- **Routing:** congested-branch behavior explains why routing more vehicles into
  a saturated region reduces total throughput.
- **Dhaka:** bus production density B reducing capacity is directly relevant to a
  bus-heavy, paratransit-heavy city. The MFD gives a way to measure Dhaka's
  network capacity from detector-like measurements (later: from video-derived counts).

---

## Part 2 — The mathematics, mapped to the paper

| Quantity | Definition | Units | Where in paper |
|---|---|---|---|
| q_i(t) | flow at detector i, interval t (300 s typical) | veh/h | Methods "Initial dataset" |
| o_i(t) | occupancy at detector i | – (fraction) | Methods "Initial dataset" |
| Average network flow q̄(t) | mean over detectors of q_i(t) ("loops method") | veh/h per lane | Methods "MFD estimation", refs 12, 37 |
| Average network occupancy ō(t) | mean over detectors of o_i(t) | – | same |
| Production P | q̄ scaled by network lane length L, per area A | veh-km h⁻¹ km⁻² | Methods "MFD estimation" ¶3; Introduction ¶4 |
| Accumulation n | density scaled by L, per area A | veh km⁻² | same |
| Speed v | v = P/n (fundamental traffic equation) | km/h | Introduction ¶4 |
| Critical point (n\*, P\*) | argmax / max of fitted P(n) | as above | Methods "Critical point estimation" |
| Critical speed v\* | P\*/n\* | km/h | Introduction ¶4 |

**Fundamental relation** (link level, used implicitly): q = k·v — flow = density × speed.
At detector level the paper uses q/o as a speed proxy (Methods "MFD estimation" ¶2).

**Estimation chain** (Methods, three numbered steps in Introduction ¶6):

1. **Regional networks** defined heuristically (<10 km², roughly homogeneous);
   partitioning algorithms (refs 13, 16) could not be applied due to sparse
   detector coverage.
2. **MFD estimation** by the loops method (ref 12) + re-sampling (ref 17):
   300 random draws of 80% of detectors; each draw gives a (mean occupancy, mean
   flow) cloud; the union of draws maps the *boundary of feasible traffic states*
   independent of demand fluctuations.
3. **Critical point**: extract upper bound = 95th–97.5th percentile of flow in
   density bins (quantile-regression approach, ref 43), then fit the smooth MFD
   functional form of ref 18 by nonlinear least squares; the critical point is
   the fitted maximum — "borrowing information from all observations" rather than
   trusting the single highest point.

**Observation weights** (Methods "Calculation of observation weights"), used later
in the regression:

    w_i = log(N) / (P*_95 − P*_5) · exp( −(s_high − s_low)/s_mean )

More observed intervals N ⇒ more weight; wider production spread at n\* ⇒ less
weight; more dispersed speed-calibration scalars ⇒ less weight.

**Critical-point regression** (Table 1): two-stage least squares; n\* is endogenous
to P\*, instrumented by R, b_c, R×I; B enters the capacity equation. This regression
needs OSM topology variables and is **out of scope for the Lab 00 smoke test** —
our target is the estimation chain up to per-network critical points.

### Equation-to-code map (planned)

| Paper element | Lab 00 implementation |
|---|---|
| Loops method aggregation (ref 12) | notebook Step 7 + `src/mfd.py` (future) |
| Re-sampling 300×80% (ref 17) | PAPER_FAITHFUL_MFD stage (not in smoke test) |
| Upper-bound percentile extraction | PAPER_FAITHFUL_MFD stage |
| Functional-form fit (ref 18) + max | PAPER_FAITHFUL_MFD stage |
| Raw scatter of mean flow vs mean occupancy | notebook `RAW_SANITY_MFD` (explicitly NOT the paper's MFD) |
| Google API speed calibration | **UNREPRODUCIBLE_FROM_AVAILABLE_HISTORICAL_INPUTS** — see ASSUMPTIONS.md |
