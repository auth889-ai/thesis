# Verified Resource Manifest

Verified on 2026-08-10. Re-verify before execution if upstream changes materially.

## SUMO general reference
- Title: **Microscopic Traffic Simulation using SUMO**
- Authors: Pablo Alvarez Lopez et al.
- Venue/year: IEEE ITSC 2018
- DOI: `10.1109/ITSC.2018.8569938`
- Official DLR landing page: https://elib.dlr.de/127994/
- Official DLR public PDF: https://elib.dlr.de/127994/1/08569938.pdf
- Strategy: `CORE_REFERENCE`

## Official SUMO source
- Repository: https://github.com/eclipse-sumo/sumo
- Verified owner/project: Eclipse SUMO
- Pinned SHA at handoff creation: `bc5912c007652a5e7b7af95320265a8ff8591b38`
- Strategy: `OFFICIAL_UPSTREAM`

## Official SUMO docs
- General: https://sumo.dlr.de/docs/
- SUMO executable: https://sumo.dlr.de/docs/sumo.html
- Traffic lights: https://sumo.dlr.de/docs/Simulation/Traffic_Lights.html
- TraCI: https://sumo.dlr.de/docs/TraCI/index.html
- Python TraCI: https://sumo.dlr.de/docs/TraCI/Interfacing_TraCI_from_Python.html
- TraCI traffic-light tutorial: https://sumo.dlr.de/docs/Tutorials/TraCI4Traffic_Lights.html

## Bologna real-world scenario
- Paper: **Traffic Simulation for All: A Real World Traffic Scenario from the City of Bologna**
- Authors: Laura Bieker, Daniel Krajzewicz, Antonio Pio Morra, Carlo Michelacci, Fabio Cartolano
- DLR record: https://elib.dlr.de/89354/
- DOI: `10.1007/978-3-319-15024-6_4`
- Official SUMO scenario catalog: https://sumo.dlr.de/docs/Data/Scenarios.html
- Official repository: https://github.com/DLR-TS/sumo-scenarios
- Pinned SHA at handoff creation: `00f6eb479a9dc0fbaeb731495c11d48d7a9661d3`
- Scenario path: `bologna/acosta/run.sumocfg`
- Strategy: `OFFICIAL_SCENARIO_UNMODIFIED_FIRST`

## Max-Pressure foundation
- Paper: **Max pressure control of a network of signalized intersections**
- Author: Pravin Varaiya
- Journal/year: Transportation Research Part C, 2013
- DOI: `10.1016/j.trc.2013.08.014`
- Strategy: `CONCEPTUAL_REFERENCE`; Lab 01 tests the core movement-pressure idea only.

## Copyright / packaging note
This handoff intentionally does **not** redistribute full papers or vendor repositories. It records official URLs and clone/fetch scripts. Claude should use the verified sources directly and preserve their licenses/provenance.


## Colab runtime lock (2026-08-10 verification)

- Official SUMO download documentation lists **SUMO 1.27.1** as the latest release (release date 2026-06-25).
- The official documentation supports installing the complete applications through `pip install eclipse-sumo`; this package includes compiled SUMO binaries.
- Lab 01 therefore pins `eclipse-sumo==1.27.1` for Colab execution.
- Official source tag used for matching source inspection: `v1_27_1`.
- The official Bologna/Acosta scenario remains pinned to the commit in `UPSTREAM_LOCK.json`.
