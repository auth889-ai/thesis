# PAPER_SUMMARY — Lab 01

Written after reading the archived full PDFs (not abstracts). Section numbers
refer to the actual papers in `paper/`.

---

## 1. PRIMARY PAPER — Alvarez Lopez et al. (2018), "Microscopic Traffic Simulation using SUMO"

IEEE ITSC 2018, pp. 2575–2582 · DOI `10.1109/ITSC.2018.8569938` ·
`paper/AlvarezLopez2018_SUMO_ITSC.pdf` (8 pp).

### What the paper is

Not an algorithm paper — it is the **reference publication of the SUMO
simulator**: an overview of the tool's workflow, models and validation
practice. This is precisely why it is Lab 01's primary paper: our lab is
`FOUNDATION_VALIDATION`, i.e. proving we can *correctly operate the tool* that
every later DhakaFlow controller will be trained in.

### Content that directly governs our implementation

**§I Introduction — simulation granularity.** Four classes are distinguished:
macroscopic (aggregate density), **microscopic (each vehicle and its dynamics
modelled individually)**, mesoscopic, submicroscopic (in-vehicle functions).
The paper focuses on microscopic simulation because it is "more precise
especially when emissions or individual routes should be simulated". DhakaFlow
needs per-vehicle behaviour (heterogeneous Dhaka fleet, per-lane queues), so
microscopic is the correct tier — Lab 01 adopts it deliberately, not by default.

**§II Workflow — what a scenario is.** Three elements are required: *network
data*, *additional traffic infrastructure (e.g. traffic lights)*, and *traffic
demand*. Critically for our experimental design, the paper states: **"Since
traffic simulation models are typically used for stochastic behavior, it makes
sense to simulate such a scenario a number of times and draw statistical
conclusions."** → this is the published justification for Lab 01's **5-seed
matrix** rather than single runs. The paper also lists the output families we
consume: vehicle trajectories, detector data, aggregated edge/lane data,
**trip-aggregated data (our `tripinfo`)**, **traffic-light switching protocols**,
whole-simulation aggregates, emissions.

**§III Bologna example.** The "Real-World Bologna" scenario is introduced as the
paper's running example: inner-city Bologna between *Andrea Costa* and *Pasubio*,
including the football stadium and the hospital; publicly available so
researchers "start with their research without the need to setup a complex
scenario first". Traffic-light **positions came from municipal telemetry files
and the signal time plans were included**; demand derives from **induction-loop
counts of 11 & 13 November 2008**, measured every 5 minutes, Savitzky–Golay
smoothed, condensed into a **typical 08:00–09:00 rush hour**. Vehicle types with
distinct emission classes (HBEFA / PHEM) are modelled, plus public transport,
bus stops and special lanes. → this is why Lab 01 uses Acosta as the *official
real-world execution check*.

**§IV Network setup.** SUMO networks = **nodes + unidirectional edges**; each
edge has geometry as line segments and one or more parallel lanes; attributes
(width, speed limit, access permissions) are constant along a lane, so a real
street becomes a *sequence* of edges whenever an attribute changes. Networks
carry "detailed information regarding possible movements at intersections and
corresponding right of way rules". **NETCONVERT** imports OSM/OpenDRIVE/
Shapefile/MATSim/Vissim and performs "heuristic refinement of missing network
data … synthesizing traffic light plans, right-of-way rules and intersection
geometries for OSM networks". → exactly the machinery Lab 01 uses to build its
deterministic unit intersection (and Lab 02 will use for Dhaka).

**§V Demand.** Demand may be individual trips, flows or routes; assignment via
**DUAROUTER / MAROUTER / Oneshot** (User Equilibrium, Stochastic UE, or fastest
route at departure time). `randomTrips.py` is described as "the simplest way to
generate trips as synthetic demand for a given network", with the warning that
in a not-fully-connected network "no routes between certain sources and
destinations can be found. Such trips will be discarded during simulation." →
our Lab 01 demand generator instead emits **seeded Poisson arrivals on explicit
routes**, which removes that failure mode for the unit scenario; the paper's
warning is the reason Lab 02 must census unroutable trips.

**§VII Validation — the honesty standard we adopt.** "There is no one-stop-shop
… permanent vigilance and scrutiny is needed." Calibration = adapting SUMO
parameters; validation = comparing output to real data; RMSE is recommended over
more complex measures. Published magnitudes: typical microscopic validation
errors **10–20 %** for gap prediction; for networks, a typical criterion is that
**more than 85 % of simulated counts deviate less than 15 % from measured
counts**. Fig. 3 shows the canonical simulated-vs-measured scatter (perfect
agreement = the diagonal). The authors "strongly advise against" by-hand
calibration because it is irreproducible, recommending numerical optimisation.
→ Lab 13 (Dhaka digital-twin calibration) inherits these exact criteria and the
scatter-plot form; Lab 01 records that no calibration claim is made here.

**§IX-C Sublane model — the single most Dhaka-relevant sentence in the paper.**
By default SUMO drives each vehicle in the lane centre and overtaking requires a
separate lane; where that is insufficient, **"the Sublane Model within SUMO may
be used to model heterogeneous traffic and reduced lane discipline"**, with
configurable lateral resolution, vehicle widths, lateral dynamics and virtual
lane formation. → this is the officially supported mechanism for Bangladeshi
mixed traffic (rickshaw/CNG/bus/motorcycle sharing a lane) and is recorded here
as the intended tool for Lab 13's heterogeneous vTypes. **Not enabled in Lab 01**
(the unit scenario is deliberately plain), but pinned as a decision for later.

**§IX-A/B Numerical integration & action points.** Default Euler update vs the
ballistic scheme (since SUMO 0.28); default reaction time = simulation step
length Δt, decoupled via action points since 0.32. → justifies our explicit
`--step-length 1` and treating the step length as a scientific parameter.

**§X Simulator coupling — TraCI.** "This interface is given in SUMO via TraCI
(Traffic Control Interface) … The user can write a program (e.g. using Python)
or use a software to retrieve data, start, stop or modify the simulation via a
socket connection." → the published basis of our entire control loop
(`src/dhakaflow_lab01/runner.py`).

### Why this paper matters to DhakaFlow

It legitimises the whole simulation tier of the thesis: the tool is peer-
reviewed, open (EPL-2.0), actively maintained, supports the intermodal and
heterogeneous features Dhaka needs, and — via TraCI — is externally
controllable, which is the precondition for every RL/MARL controller in Labs
15–20.

---

## 2. REAL-WORLD SCENARIO PAPER — Bieker et al. (2014/15), "Traffic simulation for all: a real world traffic scenario from the city of Bologna"

SUMO 2014 (Lecture Notes in Mobility, Springer 2015) · DOI
`10.1007/978-3-319-15024-6_4` · `paper/Bieker2014_Bologna_SUMO2014.pdf` (8 pp).

### Provenance of the scenario we executed

- Built inside the EC-funded **iTETRIS** project (2008–2011); the **municipality
  of Bologna was a project partner** and supplied the data.
- Source data arrived as **VISSIM (PTV) input files** for the areas around
  *Andrea Costa* and *Pasubio*, each covering the **08:00–09:00 peak hour**,
  plus traffic-light positions, signal plans and inductive-loop positions/measures.
- **Three scenarios** result: **Acosta** (football-stadium area — the one we run),
  **Pasubio** (hospital area + routes to the stadium), and **joined**.
- **Traffic lights**: telemetry in `dwg` format + signal time plans in Excel;
  the sheets contain "variable phases" used by the city's **UTOPIA** adaptive
  system.
- **Demand/validation data**: **636 detection sites**; days 11–13 Nov 2008
  (Tue–Thu, chosen because Mon/Fri have atypical shapes); aggregated to 30-min
  and 5-min intervals; ~90 sites per day reported errors coded `-1`. Because
  they are **single induction loops there is no speed information and no vehicle
  class distinction**.
- **Conversion honesty**: VISSIM is not graph-based (roads + connections, not
  nodes + edges), which "makes import of VISSIM networks very complicated and
  the results must often be edited by hand"; networks had to be translated
  English→German first; lane *numbers* were correct but **connections between
  lanes over intersections required manual correction**, validated against aerial
  imagery.
- **Validation method**: simulated vs measured flows per detector; "the optimal
  results would be a bisectrix"; the authors note a **warm-up** is required —
  "normally, double of the maximum travel time through the network".

### Documented limitations (quoted faithfully — these bound our claims)

- Demand covers **only one hour**; with warm-up and cool-down "there is only
  approximately 30 minutes of simulation which can be used".
- The networks are **small**, so route choice is very limited: **"rerouting
  algorithms should better not be simulated"** with these scenarios.
- **Multi-lane roundabouts produce unrealistic traffic jams**.
- **Pedestrians are not included**.

→ Consequently Lab 01 uses Acosta strictly as an **official real-world
execution check** (does our pinned SUMO run a real municipal scenario
unmodified, start to finish, with the upstream tree untouched?) and **not** as a
control benchmark or a routing testbed. Lab 14 will build the serious control
benchmark elsewhere.

---

## 3. THEORY REFERENCE — Varaiya (2013), "Max pressure control of a network of signalized intersections"

Transportation Research Part C 36, 177–195 · DOI `10.1016/j.trc.2013.08.014`.

Provides the max-pressure concept our third controller borrows: at each
decision, serve the phase maximising the pressure of its movements, where
pressure ≍ upstream queue minus downstream queue; the paper's central claim is a
**network-level stability guarantee** (max-pressure stabilises the network
whenever any control can), proved for a network of intersections with known
turning ratios.

**Explicit scope statement:** Lab 01 implements a **single-intersection
movement-pressure controller** — `BASELINE_IMPLEMENTATION`, *not* a reproduction
of Varaiya's network-scale results. We do not claim the stability property, we
do not implement the network formulation, and we do not report Varaiya's
metrics. The dedicated classical-control lab performs that benchmark.
