"""LIFE OS core contracts (Phase 0): the entities every later phase reads and writes. Pydantic for the shapes,
SQLAlchemy + Alembic for the authoritative store, FastAPI for the routes. Derived state (plans, risks, repairs) is
rebuildable from these tables; nothing derived is authoritative."""
