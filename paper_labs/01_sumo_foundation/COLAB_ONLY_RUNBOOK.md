# Colab-only execution runbook

## Policy

All SUMO installation and real simulation execution for Lab 01 happen in Google Colab. The Mac is not a SUMO execution environment for this lab.

## Pinned runtime

- SUMO release: `1.27.1`
- Python distribution: official `eclipse-sumo==1.27.1` wheel/package
- Official source tag for inspection: `v1_27_1`
- Official Bologna scenario repository: `DLR-TS/sumo-scenarios`, pinned by `resources/UPSTREAM_LOCK.json`

The SUMO download documentation states that the `eclipse-sumo` Python package contains the compiled SUMO applications/binaries and provides an easy virtual-environment installation path. We use that route in Colab to avoid system-level installation on the Mac and to pin the simulator release.

## Colab runtime layout

```text
/content/
├── DhakaFlow-Nexus/                 # cloned/available thesis code
├── dhakaflow_upstreams/             # temporary official source/scenario checkouts
└── drive/MyDrive/
    └── DhakaFlow-Nexus-Data/
        └── Lab01_SUMO/              # persistent heavy/full outputs
```

## Notebook order

1. Mount Google Drive.
2. Point `LAB_ROOT` to the merged active Lab 01 folder in the Colab checkout.
3. Run `scripts/install_colab.sh`.
4. Configure `SUMO_HOME`, `PATH`, and Python tools using `dhakaflow_lab01.colab_env.configure_sumo_env()`.
5. Verify `sumo`, `netconvert`, `traci`, and `sumolib`.
6. Run tests.
7. Build the unit network.
8. Run the smoke controller matrix.
9. Run the full multi-seed matrix.
10. Fetch pinned official upstream resources.
11. Run Bologna/Acosta unmodified first.
12. Audit outputs; copy only lightweight evidence back to Git.

## Persistence

Colab runtimes are temporary. Persist:
- full experiment result directories;
- logs required to reconstruct failures;
- final manifests;
- any expensive-to-regenerate simulation dumps that are actually needed.

Do not persist redundant caches or duplicate upstream repositories in Drive. They can be fetched again from pinned refs.

## Recovery

Every experiment output directory must contain enough metadata to identify:
- SUMO version;
- scenario/upstream ref;
- controller;
- seed;
- config;
- exit status.

If a Colab runtime disconnects, remount Drive, reinstall the pinned runtime, restore the code checkout, and rerun only missing experiments. Do not overwrite verified result folders silently.
