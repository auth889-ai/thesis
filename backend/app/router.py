"""The API: every domain registers its router here."""
from fastapi import APIRouter

from app.agent import router as agent_router
from app.calendar import router as calendar_router
from app.plan import router as plan_router
from app.commute import router as commute_router
from app.data import router as data_router
from app.forecasting.routers import model_prototypes, predictions, training
from app.networking import router as networking_router
from app.platform import router as platform_router
from app.profile import router as profile_router
from app.protocols.routers import experiments, live_reference, panels, references, research, stress
from app.routing import router as routing_router
from app.transit import router as transit_router
from app.twin import router as twin_router

api_router = APIRouter()
for module in (platform_router, profile_router, data_router, commute_router, transit_router, agent_router, calendar_router, plan_router, predictions, training, model_prototypes, routing_router, twin_router, networking_router,
               experiments, stress, research, panels, live_reference, references):
    api_router.include_router(module.router)
