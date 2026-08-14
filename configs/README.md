# Configuration hierarchy

One directory per subsystem. **No important hyperparameter may live only as an
unexplained hard-coded constant** — if a number changes a result, it lives here
with a comment saying where it came from.

Every value carries a provenance tag in its comment:
`OFFICIAL` (from the upstream repo's own config), `MEASURED` (from our audit of
real data), `ASSUMED` (our choice, must be justified or ablated).

Each subsystem provides `smoke.yaml` (tiny, runs on a laptop) and the real
config. Smoke configs exist so a pipeline breakage is found in seconds, not
after an hour of GPU time.
