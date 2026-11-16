from .common import router as common_router
from .location import router as location_router
from .events import router as events_router
from .services import router as services_router
from .reminders import router as reminders_router
from .news import router as news_router
from .admin import router as admin_router

__all__ = [
    "common_router",
    "location_router",
    "events_router",
    "services_router",
    "reminders_router",
    "news_router",
    "admin_router",
]
