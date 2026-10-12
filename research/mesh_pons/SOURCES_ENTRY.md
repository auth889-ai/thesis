# Entry for third_party/SOURCES.md (prepared here because this session may write only under research/mesh_pons/)

## PONS — Python Opportunistic Network Simulator
- Repo: https://github.com/gh0st42/PONS
- Commit used: `2fd70381b1b02e3e2227b5e596dc7fd92f458893` (git tag `0.2.1`, 2025-07-10). The PyPI
  package `pons-dtn==0.2.1` was diffed against this tag's `pons/` directory: identical. Master at
  the time of use was `90a6a3558a6107f68b5ee3245e37f2ef9206fda8` (23 commits ahead; not used).
- Licence: MIT (LICENSE file, "Copyright (c) 2024 Lars Baumgärtner"; PyPI classifier
  "License :: OSI Approved :: MIT License").
- Paper title and venue: not stated in the repository README or pyproject at tag 0.2.1; none claimed.
- Files used, unchanged: the installed package `pons` (routing: `EpidemicRouter`,
  `SprayAndWaitRouter`, `PRoPHETRouter`; `NetSim`, `NetworkSettings`, `generate_nodes`,
  `message_event_generator`, `Message`); the shipped examples `sim.py` and `examples/ext_ns2.py`
  run as-is from a clone at the tag (`research/mesh_pons/upstream/PONS`, not committed).
- Files changed: none. Our own code around it (`research/mesh_pons/scripts/03_run_pons.py`):
  (1) `read_ns2`, an ns2-line to PONS-move-tuple translation, because `pons.Ns2Movement`
  divides by zero on stopped vehicles; (2) `generator_with_metadata`, PONS's message-generator
  statements plus `metadata={}`, because `SprayAndWaitRouter` needs a dict that PONS's generator
  does not supply. Both documented in `research/mesh_pons/RESULTS.md`.
- Known upstream issues met (not reported upstream yet): `random.randint` with a float in
  `generate_randomwaypoint_movement` (fails on Python >= 3.12); the two items above.

## The ONE simulator default settings (used only as the cited source of the 10 m Bluetooth range)
- Repo: https://github.com/akeranen/the-one, file `default_settings.txt` at commit
  `43eaab1e0592af2526d124ee9ba9590eeadcd49a`, lines 19-23:
  `# "Bluetooth" interface for all nodes` ... `btInterface.transmitRange = 10` (metres).
- Paper: A. Keränen, J. Ott, T. Kärkkäinen, "The ONE Simulator for DTN Protocol Evaluation",
  SIMUTools 2009.
- Licence: GitHub reports no SPDX identifier (NOASSERTION). No code copied; one configuration
  value quoted as a citation only.
