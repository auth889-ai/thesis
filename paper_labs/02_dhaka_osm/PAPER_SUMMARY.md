# PAPER_SUMMARY — Lab 02 references

Lab 02 is a data/tooling lab (no single reproduced paper). Its scientific
grounding:

1. **Alvarez Lopez et al. (2018), "Microscopic Traffic Simulation using SUMO",
   IEEE ITSC.** DOI 10.1109/ITSC.2018.8569938 — the canonical SUMO reference:
   scenario = network + infrastructure + demand; recommends repeated stochastic
   runs; describes OSM import workflow. (Same core reference as Lab 01.)
2. **Official SUMO documentation** (v1.27.1): OSM import
   (`docs/Networks/Import/OpenStreetMap.html`), netconvert options, sumolib,
   randomTrips/duarouter — PUBLISHED tooling semantics used throughout
   METHOD_SPEC.
3. **OpenStreetMap** data model + Overpass API (official OSM ecosystem docs);
   data © OpenStreetMap contributors, ODbL 1.0.

Classification: **Original DhakaFlow module (Category C)** built exclusively on
official upstream tooling; no third-party paper implementation is claimed.

Relevance to DhakaFlow Nexus: this lab produces the geographic substrate every
later lab stands on — the calibrated digital twin (Labs 4+), signal control and
routing experiments all inherit this network and its documented import
decisions.
