# SYSTEM DESIGN (corrected, literature-aligned) — v2, 29 Aug 2026

The audit-corrected architecture, mapped to current digital-twin literature.
This is THE design; every gate below names its implementation file and status.

## The causal spine (what makes it a system, not artifacts)

```
REAL / RECORDED VIDEO  (examiner-supplied or registered R1 camera)
   ↓  RT-DETR (Dhaka fine-tune) + tracking          [research/perception/*]
TRAFFIC STATE per approach: queue, speed, stopped, arrival/discharge
   ↓  registered camera → road-graph edge/lanes     [scripts/case_report.py]
SUMO DIGITAL TWIN on the frozen real network        [scripts/same_state_counterfactual.py]
   ↓  forecast 5/15/30 min (GWNet, official harness)[research/forecasting/*]
SAVE EXACT STATE t0  (traci.simulation.saveState)
   ├── branch A: NO ACTION            → +10 min
   └── branch B: CONTROL (signals + capacity-gated bounded rerouting) → +10 min
MEASURED DIFFERENCE (queue / stopped / arrivals / delay)  ← the proof
```

This matches the field's direction: SUMO motorway twins driven by continuous
real data streams (IEEE ITSC line of work), the 2025 SUMO-conference
digital-twin-aided municipal control study (video → per-vehicle timing →
repeated SUMO testing of control), and 2025-26 closed-loop twin platforms
synchronizing live state into SUMO via TraCI.

## Design rules learned by experiment (each has an artifact)

1. **Same-state causality** — branches share a byte-identical t0 via
   saveState/loadState; differences are caused, not correlated.
2. **Never just move the jam** — rerouting is capacity-gated: if alternative
   lanes are loaded (>0.35 halting/lane), hold traffic instead of diverting
   (aggressive variant measured: network −13% worse).
3. **Know when NOT to act** — intervention requires target queue ≥ 20 at t0
   (acting on a barely-queued junction measured worse, seed 13).
4. **Trapped vehicles are never teleported** — control affects discharge and
   the approaching population only.
5. **Forecast quality gates prevention** — persistence-triggered prevention
   nets ~0%; the graph model (3× better MAE) is the active ingredient.
6. **Local greed harms networks** — the tested pressure baseline and
   aggressive discharge both degrade network metrics → coordination (MAPPO
   track) is the research frontier, evaluated at-checkpoint honestly.

## Gate status

| Gate | Status |
|---|---|
| REAL_STATE (detector, tracker, state, registered cameras, honest LOCATION_REQUIRED) | v1 ✅ (metric speed + stationary-queue absolute evidence: v2 listed) |
| TWIN_SYNC (video selects site/trigger; demand fair-fixed) | v1 ✅ (trajectory-level reconstruction: declared future gate) |
| SAME_STATE_COUNTERFACTUAL (saveState, branches, 3 seeds) | ✅ |
| DYNAMIC_ROUTING (measured travel times, bounded, capacity-gated) | ✅ |
| SIGNAL_CONTROL (fixed/pressure baselines + MAPPO at-checkpoint, paired seeds) | ✅ at-checkpoint |
| FORECAST_IN_LOOP (GWNet z-scored; history preload before FA re-run) | preload fix pending — FA arms relabeled until then |
| Four-pane report on the counterfactual | in progress |

## Known limitations (declared)

Trajectory-level twin calibration from video (2026 direction) is future work;
calibration scale 0.584 not yet consumed by the control scenario (wording
adjusted until wired); FA arms trained pre-preload are MAPPO-variants, not
forecast-aware claims.
