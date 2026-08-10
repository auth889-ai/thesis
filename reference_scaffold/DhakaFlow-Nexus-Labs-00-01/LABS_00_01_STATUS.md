# Labs 00–01 Build Status

## What has been validated in this ZIP

- Project architecture validation: PASS.
- Python syntax/compile checks for Lab 00 and Lab 01 source: PASS.
- Lightweight unit/static tests: **9 passed**.
- Both Colab notebooks parse as valid nbformat v4 notebooks.
- Storage/secrets policy is encoded in `.gitignore`, `.env.example`, and lab runbooks.

## Lab 00 — must still be executed in Colab

The package does not include the multi-GB UTD19 measurement file. Put the official release in Google Drive and run `Lab00_UTD19_Full_Colab.ipynb`.

Required execution gates:
1. real schema audit;
2. full-release city audit;
3. explicit inspection of `error` semantics;
4. deterministic smoke subset;
5. selected full-city reconstruction;
6. full-release raw out-of-core aggregation;
7. paper-faithful regional reconstruction only where exact regional membership/length metadata are verified;
8. report every deviation from the 2019 historical calibration.

An exact reproduction claim is forbidden until the 107 regional-network definitions and method-specific calibration inputs are verified sufficiently.

## Lab 01 — must still be executed in Colab

SUMO is not installed in the artifact-build container, so the actual simulator was not run here. Run `Lab01_SUMO_Foundation_Colab.ipynb` in Colab.

Required execution gates:
1. install and record SUMO version;
2. `netconvert` validation of deterministic unit scenario;
3. run Fixed-Time, queue-actuated, Max-Pressure under identical deterministic demand;
4. collect tripinfo/summary metrics;
5. clone official `DLR-TS/sumo-scenarios` and record commit SHA;
6. run Bologna/Acosta unmodified first;
7. keep any compatibility wrapper outside upstream files;
8. preserve real-world scenario results separately from the unit-validation results.

## Important scope rule
Lab 00 establishes traffic-science ground truth. Lab 01 establishes simulation/control mechanics. Do not merge them into a false "UTD19 SUMO reproduction": the Loder UTD19 paper is not a SUMO-control experiment.
