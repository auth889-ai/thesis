"""One router for the whole API: every route module registers here, grouped by domain."""
from fastapi import APIRouter

from app.api.routes.evidence import experiments, live_reference, panels, references, research, stress
from app.api.routes.forecasting import model_prototypes, predictions, training
from app.api.routes.platform import cities, system
from app.api.routes.routing import trips
from app.api.routes.twin import simulation, v2x

api_router = APIRouter()
for module in (system, cities, predictions, training, model_prototypes, trips, simulation, v2x, experiments, stress, research, panels, live_reference, references):
    api_router.include_router(module.router)
