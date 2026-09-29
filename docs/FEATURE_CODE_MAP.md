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

Authoritative state: the seven tables in `results/live/lifeos.sqlite` (Alembic head). Derived state (plans, risks, repairs) is
rebuildable from them and is never the source of truth.

## Map

| Feature | Code | Tests | Phase | Limitations |
|---|---|---|---|---|
| The seven contracts | `backend/app/lifeos/entities.py` | `test_lifeos_core.py` | P0 | `Person` overlaps the earlier `app/profile` store; the profile becomes a view of `Person` in P2 |
| Authoritative store and migrations | `backend/app/lifeos/db.py`, `backend/alembic/` | `test_lifeos_core.py` | P0 | SQLite; PostgreSQL by URL, untested until P17 |
| Reads and writes | `backend/app/lifeos/repo.py` | `test_lifeos_core.py` | P0 | no pagination beyond a limit |
| Routes and schema | `backend/app/lifeos/router.py` (`/api/lifeos/*`) | `test_lifeos_core.py` | P0 | no authentication until accounts (block D/F) |
| Person profile (zone, city, home, target) | `backend/app/profile/` | `test_profile.py` | pre-plan | to be folded into `Person` |
| Feasibility grades and conflicts | `backend/app/plan/{feasibility,conflicts}.py` | `test_feasibility.py`, `test_conflicts.py` | pre-plan | reads the commute planner, not `TravelEdge`; replaced by P3 |
| Departure probability | `backend/app/commute/service.py` | `test_commute*.py` | pre-plan | real only where recorded Dhaka corridor bands exist; replaced by P9–P10 |
| Agent, approvals, audit, worker | `backend/app/agent/` | `test_agent.py`, `test_approvals.py`, `test_worker.py` | pre-plan (P13–P14 pattern already in) | tools will be re-pointed at `lifeos` |
| Consumer pages | `frontend/src/features/*` | Vitest | pre-plan (P28) | read older functions; re-pointed page by page from P3 |
