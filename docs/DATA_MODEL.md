# Data model (Phase 0, relational)

Authoritative store: `results/live/lifeos.sqlite` now, PostgreSQL by URL later, migrated by Alembic (`backend/alembic`).
One column per field; children in their own tables; foreign keys enforced (SQLite `foreign_keys=on`, cascades declared).
The only JSON columns are `actions.arguments`, `actions.result` and `events.payload`, which are free-form by nature: every
tool has its own arguments and every event kind its own facts. PostgreSQL stores them as `jsonb`.

```mermaid
erDiagram
    persons ||--o{ places : "has"
    persons ||--o| places : "home_place_id"
    persons ||--o{ commitments : "owns"
    persons ||--o{ constraints : "owns"
    persons ||--o{ travel_edges : "owns"
    persons ||--o{ outcomes : "owns"
    persons ||--o{ actions : "owns"
    persons ||--o{ events : "concerns"
    places ||--o{ commitments : "place_id"
    places ||--o{ travel_edges : "origin_place_id"
    places ||--o{ travel_edges : "destination_place_id"
    commitments ||--o{ commitment_requirements : "needs"
    commitments ||--o{ commitment_dependencies : "depends_on"
    commitments ||--o{ outcomes : "measured by"
    constraints ||--o{ constraint_params : "key, value"
    constraints ||--o{ constraint_targets : "applies to"

    persons { string id PK; string name; string timezone; string city; string home_place_id FK; float on_time_target; float calibration_factor; int max_walk_min; bool wheelchair; bool avoid_stairs; bool elevator_required; datetime created_at; datetime updated_at }
    places { string id PK; string person_id FK; string name; float lat; float lng; string kind }
    commitments { string id PK; string person_id FK; string title; string type; string place_id FK; datetime start; datetime deadline; int duration_min; string priority; string flexibility; datetime window_start; datetime window_end; string source; datetime created_at; datetime updated_at }
    commitment_requirements { string commitment_id PK_FK; int position PK; string item }
    commitment_dependencies { string commitment_id PK_FK; string depends_on_id PK_FK }
    constraints { string id PK; string person_id FK; string kind; string severity; string source; datetime created_at }
    constraint_params { string constraint_id PK_FK; string key PK; string value }
    constraint_targets { string constraint_id PK_FK; string target_id PK }
    travel_edges { string id PK; string person_id FK; string origin_place_id FK; string destination_place_id FK; string mode; datetime depart; int duration_s; int distance_m; int p10_s; int p50_s; int p90_s; string uncertainty_method; float cost; bool accessible; string provider; string model; string freshness; datetime generated_at }
    outcomes { string id PK; string person_id FK; string commitment_id FK; datetime planned_departure; datetime actual_departure; datetime predicted_arrival; datetime actual_arrival; bool on_time; int forecast_error_s; datetime recorded_at }
    actions { string id PK; string person_id FK; string tool; string risk; string decision; string approved_by; datetime executed_at; string goal_id; json arguments; json result }
    events { string id PK; string person_id FK; string kind; datetime occurred_at; string source; json payload }
```

## Rules the schema enforces

- A commitment, constraint, edge, outcome, action or event cannot exist without its person (foreign key; inserting one for an unknown person fails).
- Deleting a commitment deletes its requirements, dependencies and outcomes; deleting a person deletes everything of theirs.
- Every timestamp is stored in UTC and read back timezone-aware on every database (`UTC` type decorator).
- Indexes on the columns the day and the monitor query: `commitments.deadline`, `commitments.type`, `commitments.priority`, `travel_edges.depart`, `travel_edges.mode`, `travel_edges.freshness`, `events.kind`, `events.occurred_at`, `actions.tool`, `actions.decision`, `actions.goal_id`.
- Places are shared: a person's home, a commitment's location and an edge's origin are rows in `places`, so the same place has one id.

## What the contracts add on top

`backend/app/lifeos/entities.py` validates what a schema cannot express: a fixed commitment needs a start, a deadline cannot precede its start, a movable commitment needs a window, no self-dependency, p10 ≤ p50 ≤ p90, an unknown mode or priority is refused.
