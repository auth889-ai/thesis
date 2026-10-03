# Feature → code map

The structure the EchoNotes reference kept: a pipeline you can read top to bottom, a map from every feature to the code
that implements it, tests beside each, and limitations stated. Updated at the end of every phase.

## Pipeline

```
text / calendar / email ──(P1 compiler)──▶ Commitment ──(P2 Life Twin)──▶ day graph ──(P3 OR-Tools)──▶ feasible plan
                                                                 ▲                                          │
                       TravelEdge ◀──(P4 routing, P9 uncertainty, P10 AccessTwin)                          ▼
                                                                                          Event ──(P16 repair)──▶ updated plan
                                                                                          Outcome ──(P11 personal ML)──▶ calibration
```

Authoritative state: the thirteen relational tables in `results/live/lifeos.sqlite` (Alembic head; see `DATA_MODEL.md`). Derived state
(plans, risks, repairs) is rebuildable from them and is never the source of truth.

## Map

| Feature | Code | Tests | Phase | Limitations |
|---|---|---|---|---|
| The seven contracts | `backend/app/lifeos/entities.py` | `test_lifeos_core.py` | P0 | `Person` overlaps the earlier `app/profile` store; the profile becomes a view of `Person` in P2 |
| Authoritative store and migrations | `backend/app/lifeos/db.py` (13 relational tables, foreign keys, UTC timestamps), `backend/alembic/` | `test_lifeos_core.py` | P0 | SQLite; PostgreSQL by URL, untested until P17; tool arguments and event payloads are JSON columns by nature |
| Reads and writes | `backend/app/lifeos/repo.py` | `test_lifeos_core.py` | P0 | no pagination beyond a limit |
| Routes and schema | `backend/app/lifeos/router.py` (`/api/lifeos/*`) | `test_lifeos_core.py` | P0 | no authentication until accounts (block D/F) |
| Commitment compiler: text → Commitment (rules path: spaCy, dateparser, rapidfuzz; model path: Bedrock validated by the contract) | `backend/app/lifeos/compiler/{rules,model,service,router}.py`, `POST /api/lifeos/compile` | `test_compiler.py`; `evaluate.py` → `results/lifeos/compiler.json` | P1 | English rules only; Bangla and free prose need the model; "next Friday" follows the next-week convention |
| Person profile (zone, city, home, target) | `backend/app/profile/` | `test_profile.py` | pre-plan | to be folded into `Person` |
| Feasibility grades and conflicts | `backend/app/plan/{feasibility,conflicts}.py` | `test_feasibility.py`, `test_conflicts.py` | pre-plan | reads the commute planner, not `TravelEdge`; replaced by P3 |
| Departure probability | `backend/app/commute/service.py` | `test_commute*.py` | pre-plan | real only where recorded Dhaka corridor bands exist; replaced by P9–P10 |
| Agent, approvals, audit, worker | `backend/app/agent/` | `test_agent.py`, `test_approvals.py`, `test_worker.py` | pre-plan (P13–P14 pattern already in) | tools will be re-pointed at `lifeos` |
| Consumer pages | `frontend/src/features/*` | Vitest | pre-plan (P28) | read older functions; re-pointed page by page from P3 |

## Map, road-traffic thesis (added 2026-10-03)

| Feature | Code | Tests | Phase | Limitations |
|---|---|---|---|---|
| Protocol A reproduction of the official models on AWS (DCRNN, GWNet, STID, STAEformer, MegaCRN) | `backend/app/forecasting/training/aws/{cli,benchmark,scripts,report}.py`, `--finish` | `test_canonical_prediction.py` (job-script fixes, finish sequence) | P1, P4 | one GPU slot per 4 vCPU of quota; spot reclaims a long run |
| Protocol B: regime-stratified scoring of every model on the same windows | `backend/app/forecasting/evaluation/{evaluate_models,checkpoint_stage,foundation_stage}.py`; persisted blocks `results/forecasting/protocol_b/*.npz`; `--merge` | `test_canonical_prediction.py` (checkpoint stage, merge guard, future-speed guard) | P2, P9a | one 80-road block and one seed on METR-LA; PEMS-BAY has only GWNet and STID so far |
| Conformal intervals per regime (global, observed-regime, predicted-regime) with stored half-widths | `backend/app/forecasting/evaluation/conformal.py` (MAPIE) | `test_canonical_prediction.py` (synthetic regimes) | P8a | calibrated on one validation block |
| Onset and intervals served and shown | `backend/app/forecasting/routers/onset.py`, `frontend/src/features/forecast/{OnsetTab,IntervalsTable}.tsx` | `test_alerts.py`, API tests | P2, P8a | read from committed run files, never recomputed on request |
| Served checkpoints: any trained model on the forecast map | `backend/app/forecasting/operations/{served_checkpoints,scientific_prediction}.py` | `test_canonical_prediction.py` | P12a | METR-LA scope only |
| Roads about to tip, watches, alerts with hysteresis | `backend/app/forecasting/operations/onset_now.py`, `backend/app/alerts/{db,service,router}.py`, migration `0003_road_watches`, `frontend/src/features/forecast/OnsetNow.tsx` | `test_alerts.py` | P10 | alerts evaluate at a dataset moment; a live-city tick is the recorder's job |
| Departure advice on a sensor corridor with a 90 % worst case | `backend/app/forecasting/operations/departure.py`, `frontend/src/features/forecast/LeaveWhen.tsx` | `test_alerts.py` | P8b | corridors on the DCRNN sensor graph; no turn-by-turn routing |
| The phone as the sensor (probes → cells) | `backend/app/probes/{db,snap,service,router}.py`, migration `0002_probes`, `frontend/src/features/mobility/{probe,useProbe,ProbePanel}.ts(x)` | `test_probes.py`, `probe.test.ts` | S1 | cells are H3 × heading, not named ways; snapping needs Amazon Location |
| Sparse sensing: imputation under the paper's protocol | `backend/app/forecasting/evaluation/imputation.py` (PyPOTS ImputeFormer), `frontend/src/features/forecast/SparseTab.tsx` | `test_alerts.py` | Q1 | laptop budget, not the paper's 300 × 300 batches |
| Live-sampling liveness in health and the shell chip | `backend/app/data/live_providers/observatory.py` (`liveness`), `backend/app/platform/router.py`, `frontend/src/app/AppShell.tsx` | `test_api.py` | fix 2 | the recorder is opt-in (`TRAFFICTWIN_RECORDER=1`) |
